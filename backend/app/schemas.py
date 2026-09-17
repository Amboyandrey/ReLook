"""Pydantic request/response models for the review queue API."""

from __future__ import annotations

import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RequestItem(BaseModel):
    text: str
    deadline: Optional[str] = None
    owner: Optional[str] = None
    page: Optional[int] = None


class Entities(BaseModel):
    person: Optional[str] = None
    department: Optional[str] = None
    dates: list[str] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    uploaded_at: datetime.datetime
    status: str
    category: str
    confidence: float
    needs_human: bool
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime.datetime] = None


class DocumentDetail(DocumentSummary):
    preview_text: Optional[str] = None
    summary: str
    requests: list[RequestItem]
    entities: Entities
    reason_for_review: Optional[str] = None
    auto_approve_eligible: bool
    review_notes: Optional[str] = None
    original_ai_result: dict


class ReviewSubmission(BaseModel):
    """What a reviewer submits for one document.

    `action=approve` accepts the AI's fields as-is (or as touched up by the
    reviewer -- the frontend always sends the current field values, whether
    or not they were edited). `action=reject` only requires `reviewer` and
    optional `notes`; the document is parked as rejected without changing
    its analysis fields.
    """

    action: Literal["approve", "reject"]
    reviewer: str
    notes: Optional[str] = None

    category: Optional[str] = None
    summary: Optional[str] = None
    requests: Optional[list[RequestItem]] = None
    entities: Optional[Entities] = None
    needs_human: Optional[bool] = None
    reason_for_review: Optional[str] = None


class TaxonomyCategory(BaseModel):
    name: str
    description: str
    default_owner: str


class TaxonomyOut(BaseModel):
    categories: list[TaxonomyCategory]
    auto_approve_threshold: float
