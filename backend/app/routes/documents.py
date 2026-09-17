"""Document upload, listing, detail, file serving, and review actions."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from relook.parsing import UnsupportedDocumentError

from .. import pipeline, routing, storage
from ..db import get_db
from ..models import Document, ReviewEvent
from ..schemas import DocumentDetail, DocumentSummary, ReviewSubmission, TaxonomyOut, TaxonomyCategory

router = APIRouter()


@router.get("/taxonomy", response_model=TaxonomyOut)
def get_taxonomy() -> TaxonomyOut:
    taxonomy = pipeline.get_taxonomy()
    return TaxonomyOut(
        categories=[
            TaxonomyCategory(name=c.name, description=c.description, default_owner=c.default_owner)
            for c in taxonomy.categories
        ],
        auto_approve_threshold=taxonomy.auto_approve_threshold,
    )


@router.post("/documents", response_model=DocumentDetail)
def upload_document(file: UploadFile, db: Session = Depends(get_db)) -> Document:
    stored_path, content_type = storage.save_upload(file)

    try:
        record = pipeline.analyze(stored_path)
    except UnsupportedDocumentError as e:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=502, detail=f"Analysis failed: {e}") from e

    ai_snapshot = {
        "category": record["category"],
        "confidence": record["confidence"],
        "summary": record["summary"],
        "requests": record["requests"],
        "entities": record["entities"],
        "needs_human": record["needs_human"],
        "reason_for_review": record["reason_for_review"],
    }

    document = Document(
        filename=file.filename or stored_path.name,
        stored_path=str(stored_path),
        content_type=content_type,
        preview_text=record["preview_text"],
        status="pending",
        category=record["category"],
        confidence=record["confidence"],
        summary=record["summary"],
        requests=record["requests"],
        entities=record["entities"],
        needs_human=record["needs_human"],
        reason_for_review=record["reason_for_review"],
        auto_approve_eligible=record["auto_approve_eligible"],
        original_ai_result=ai_snapshot,
    )
    db.add(document)
    db.flush()

    db.add(
        ReviewEvent(
            document_id=document.id,
            action="analyzed",
            ai_snapshot=ai_snapshot,
            human_snapshot=None,
            reviewer="system",
        )
    )
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(
    status: Optional[str] = None,
    needs_human: Optional[bool] = None,
    db: Session = Depends(get_db),
) -> list[Document]:
    query = select(Document).order_by(Document.uploaded_at.desc())
    if status is not None:
        query = query.where(Document.status == status)
    if needs_human is not None:
        query = query.where(Document.needs_human == needs_human)
    return list(db.scalars(query))


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(document_id: int, db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/documents/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)) -> FileResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(document.stored_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Original file is no longer on disk")

    return FileResponse(path, media_type=document.content_type, filename=document.filename)


@router.post("/documents/{document_id}/review", response_model=DocumentDetail)
def review_document(document_id: int, submission: ReviewSubmission, db: Session = Depends(get_db)) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != "pending":
        raise HTTPException(status_code=409, detail=f"Document is already {document.status}")

    now = datetime.datetime.now(datetime.timezone.utc)
    human_snapshot = None

    if submission.action == "approve":
        if submission.category is not None:
            document.category = submission.category
        if submission.summary is not None:
            document.summary = submission.summary
        if submission.requests is not None:
            document.requests = [r.model_dump() for r in submission.requests]
        if submission.entities is not None:
            document.entities = submission.entities.model_dump()
        if submission.needs_human is not None:
            document.needs_human = submission.needs_human
        if submission.reason_for_review is not None:
            document.reason_for_review = submission.reason_for_review

        document.status = "approved"
        human_snapshot = {
            "category": document.category,
            "confidence": document.confidence,
            "summary": document.summary,
            "requests": document.requests,
            "entities": document.entities,
            "needs_human": document.needs_human,
            "reason_for_review": document.reason_for_review,
        }
        action = "edited" if human_snapshot != document.original_ai_result else "approved"
    else:
        document.status = "rejected"
        action = "rejected"

    document.reviewed_by = submission.reviewer
    document.reviewed_at = now
    document.review_notes = submission.notes

    db.add(
        ReviewEvent(
            document_id=document.id,
            action=action,
            ai_snapshot=document.original_ai_result,
            human_snapshot=human_snapshot,
            reviewer=submission.reviewer,
            notes=submission.notes,
        )
    )

    if document.status == "approved":
        # File the original, create tasks from requests[], notify owners.
        # Runs in the same transaction as the review event above -- if this
        # raises, the whole review (including the approval itself) rolls
        # back rather than leaving a half-routed document.
        routing.route_approved_document(db, document)

    db.commit()
    db.refresh(document)
    return document
