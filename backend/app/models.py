"""SQLAlchemy ORM models for the review queue.

Two tables:

- `Document` holds the current state of each document -- the mutable fields
  a reviewer can edit (category, summary, requests, ...) plus an immutable
  `original_ai_result` snapshot of exactly what the AI produced on first
  analysis. Keeping the original frozen means edits never erase the
  AI's original answer.
- `ReviewEvent` is an append-only audit log: one row per human action
  (approve/edit/reject), each pairing the frozen AI snapshot with what the
  human decided. This is the dataset the phase-4 learning loop will train
  on and the eval set will be built from.
"""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)

    # File metadata
    filename: Mapped[str] = mapped_column(String)
    stored_path: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    preview_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Review state
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | approved | rejected
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Current (possibly human-edited) analysis fields
    category: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    requests: Mapped[list] = mapped_column(JSON, default=list)
    entities: Mapped[dict] = mapped_column(JSON, default=dict)
    needs_human: Mapped[bool] = mapped_column(default=True)
    reason_for_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_approve_eligible: Mapped[bool] = mapped_column(default=False)

    # Frozen at ingest time -- never mutated by a review action.
    original_ai_result: Mapped[dict] = mapped_column(JSON)

    events: Mapped[list["ReviewEvent"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="ReviewEvent.created_at"
    )


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    action: Mapped[str] = mapped_column(String)  # analyzed | approved | edited | rejected
    ai_snapshot: Mapped[dict] = mapped_column(JSON)
    human_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewer: Mapped[str] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    document: Mapped[Document] = relationship(back_populates="events")
