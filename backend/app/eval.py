"""Turns the review_events audit trail into a correction dataset and an
accuracy report, and uses that report to recommend an auto-approve
confidence threshold.

Nothing here calls the Anthropic API. Every `ReviewEvent` already stores
both the AI's frozen original output (`ai_snapshot`) and what the human
decided (`human_snapshot`, null for rejections) -- this module only reads
and aggregates data that's already in the database.

Vocabulary used throughout:

- A "miss" is a reviewed document whose action was `edited` or `rejected`
  -- the AI's original output wasn't good enough to leave untouched.
- A "risky miss" is a miss where the AI had also set `needs_human=False`
  -- i.e. the AI was confident enough to wave it through, but a human
  still had to fix or reject it. These are the cases that matter for
  tuning the auto-approve threshold: raising the threshold trades away
  auto-approve coverage to drive the risky-miss rate toward zero.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import pipeline
from .db import DATA_DIR
from .models import ReviewEvent

MIN_SAMPLES_FOR_RECOMMENDATION = 10
CONFIDENCE_BUCKET_EDGES = [1.01, 0.95, 0.90, 0.85, 0.80, 0.70, 0.0]
EVAL_EXPORT_PATH = DATA_DIR / "eval" / "corrections.jsonl"

REVIEWED_ACTIONS = ("approved", "edited", "rejected")
MISS_ACTIONS = ("edited", "rejected")


def _reviewed_events(db: Session) -> list[ReviewEvent]:
    query = select(ReviewEvent).where(ReviewEvent.action.in_(REVIEWED_ACTIONS))
    return list(db.scalars(query))


def _bucket_label(confidence: float) -> str:
    for i in range(len(CONFIDENCE_BUCKET_EDGES) - 1):
        hi, lo = CONFIDENCE_BUCKET_EDGES[i], CONFIDENCE_BUCKET_EDGES[i + 1]
        if lo <= confidence < hi:
            return "< 0.70" if lo == 0.0 else f"{lo:.2f}–{min(hi, 1.0):.2f}"
    return "< 0.70"


def _category_agrees(event: ReviewEvent) -> bool | None:
    """True/False if comparable (approved/edited, so human_snapshot exists),
    None for rejections where there's no finalized category to compare."""
    if event.human_snapshot is None:
        return None
    return event.human_snapshot.get("category") == event.ai_snapshot.get("category")


def recommend_threshold(events: list[ReviewEvent]) -> tuple[float | None, str]:
    """Finds the lowest confidence threshold tau such that every reviewed
    needs_human=False event with confidence >= tau was a clean approval
    (zero edits/rejections at or above tau). Returns (None, reason) when
    there isn't enough data, or when no threshold achieves zero misses."""
    candidates = [e for e in events if e.ai_snapshot.get("needs_human") is False]

    if len(candidates) < MIN_SAMPLES_FOR_RECOMMENDATION:
        return None, (
            f"insufficient data: {len(candidates)} reviewed needs_human=False "
            f"documents, need at least {MIN_SAMPLES_FOR_RECOMMENDATION}"
        )

    sorted_asc = sorted(candidates, key=lambda e: e.ai_snapshot["confidence"])
    for i, event in enumerate(sorted_asc):
        threshold = event.ai_snapshot["confidence"]
        subset = sorted_asc[i:]  # every candidate with confidence >= threshold
        misses = sum(1 for e in subset if e.action in MISS_ACTIONS)
        if misses == 0:
            return round(threshold, 4), (
                f"{len(subset)} reviewed documents at or above this confidence, "
                f"0 required edits or rejections"
            )

    return None, (
        "no confidence level had zero risky misses in the reviewed history -- "
        "keep every document in human review until more data is collected"
    )


def compute_accuracy_report(db: Session) -> dict:
    events = _reviewed_events(db)

    by_action = {"approved": 0, "edited": 0, "rejected": 0}
    for e in events:
        by_action[e.action] += 1

    comparable = [e for e in events if e.human_snapshot is not None]
    category_matches = sum(1 for e in comparable if _category_agrees(e))
    category_agreement_rate = (category_matches / len(comparable)) if comparable else None

    buckets: dict[str, dict] = {}
    for e in events:
        confidence = e.ai_snapshot.get("confidence")
        if confidence is None:
            continue
        label = _bucket_label(confidence)
        b = buckets.setdefault(
            label, {"range": label, "count": 0, "category_matches": 0, "category_comparable": 0,
                    "needs_human_false_count": 0, "risky_misses": 0}
        )
        b["count"] += 1
        agrees = _category_agrees(e)
        if agrees is not None:
            b["category_comparable"] += 1
            b["category_matches"] += int(agrees)
        if e.ai_snapshot.get("needs_human") is False:
            b["needs_human_false_count"] += 1
            if e.action in MISS_ACTIONS:
                b["risky_misses"] += 1

    bucket_report = []
    for label in [_bucket_label(edge) for edge in CONFIDENCE_BUCKET_EDGES[1:]]:
        if label not in buckets:
            continue
        b = buckets[label]
        bucket_report.append(
            {
                "range": b["range"],
                "count": b["count"],
                "category_agreement_rate": (
                    b["category_matches"] / b["category_comparable"] if b["category_comparable"] else None
                ),
                "risky_miss_rate": (
                    b["risky_misses"] / b["needs_human_false_count"] if b["needs_human_false_count"] else None
                ),
            }
        )
    # Dedup while preserving the fixed high-to-low bucket order.
    seen = set()
    ordered_bucket_report = []
    for b in bucket_report:
        if b["range"] not in seen:
            seen.add(b["range"])
            ordered_bucket_report.append(b)

    flagged_true = [e for e in events if e.ai_snapshot.get("needs_human") is True]
    flagged_false = [e for e in events if e.ai_snapshot.get("needs_human") is False]
    risky_misses = [e for e in flagged_false if e.action in MISS_ACTIONS]

    recommended_threshold, recommendation_basis = recommend_threshold(events)

    return {
        "total_reviewed": len(events),
        "by_action": by_action,
        "category_agreement_rate": category_agreement_rate,
        "confidence_buckets": ordered_bucket_report,
        "needs_human_effectiveness": {
            "flagged_true_count": len(flagged_true),
            "flagged_false_count": len(flagged_false),
            "risky_misses": len(risky_misses),
            "risky_miss_rate": (len(risky_misses) / len(flagged_false)) if flagged_false else None,
        },
        "current_auto_approve_threshold": pipeline.get_taxonomy().auto_approve_threshold,
        "recommended_auto_approve_threshold": recommended_threshold,
        "recommendation_basis": recommendation_basis,
    }


def build_corrections_dataset(db: Session) -> list[dict]:
    """One row per reviewed document, pairing the AI's original output with
    the human's final decision -- the dataset for prompt/few-shot tuning
    and for the accuracy report above."""
    rows = []
    for e in _reviewed_events(db):
        rows.append(
            {
                "document_id": e.document_id,
                "action": e.action,
                "reviewer": e.reviewer,
                "reviewed_at": e.created_at.isoformat(),
                "notes": e.notes,
                "ai_category": e.ai_snapshot.get("category"),
                "ai_confidence": e.ai_snapshot.get("confidence"),
                "ai_needs_human": e.ai_snapshot.get("needs_human"),
                "ai_summary": e.ai_snapshot.get("summary"),
                "human_category": (e.human_snapshot or {}).get("category"),
                "human_summary": (e.human_snapshot or {}).get("summary"),
                "human_needs_human": (e.human_snapshot or {}).get("needs_human"),
                "category_agreed": _category_agrees(e),
            }
        )
    return rows


def export_corrections_jsonl(db: Session, path: Path | None = None) -> tuple[Path, int]:
    path = path or EVAL_EXPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = build_corrections_dataset(db)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    return path, len(rows)
