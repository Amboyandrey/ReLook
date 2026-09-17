"""Accuracy reporting and correction-dataset export (phase 4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import eval as eval_module
from ..db import get_db

router = APIRouter()


@router.get("/eval/report")
def get_accuracy_report(db: Session = Depends(get_db)) -> dict:
    return eval_module.compute_accuracy_report(db)


@router.post("/eval/export")
def export_corrections(db: Session = Depends(get_db)) -> dict:
    path, count = eval_module.export_corrections_jsonl(db)
    return {"path": str(path), "count": count}
