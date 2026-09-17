#!/usr/bin/env python3
"""Prints the phase-4 accuracy report and exports the corrections dataset,
without needing the API server running.

    python scripts/build_eval_set.py

Writes data/eval/corrections.jsonl (one reviewed document per line, pairing
the AI's original output with the human's final decision) and prints the
accuracy report -- category agreement rate, confidence-bucket breakdown,
needs_human effectiveness, and a recommended auto-approve threshold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import eval as eval_module  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        report = eval_module.compute_accuracy_report(db)
        path, count = eval_module.export_corrections_jsonl(db)
    finally:
        db.close()

    print(json.dumps(report, indent=2))
    print(f"\nWrote {count} rows to {path}")


if __name__ == "__main__":
    main()
