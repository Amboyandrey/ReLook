"""Task and notification listing -- the human side of phase 3's routing:
tasks created from an approved document's requests[], and the notification
trail sent about them."""

from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notification, Task
from ..schemas import NotificationOut, TaskOut

router = APIRouter()


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    status: Optional[str] = None,
    owner: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    query = select(Task).order_by(Task.created_at.desc())
    if status is not None:
        query = query.where(Task.status == status)
    if owner is not None:
        query = query.where(Task.owner == owner)

    tasks = db.scalars(query).all()
    return [
        TaskOut.model_validate(t, from_attributes=True).model_copy(
            update={"document_filename": t.document.filename}
        )
        for t in tasks
    ]


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: int, db: Session = Depends(get_db)) -> TaskOut:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "done":
        raise HTTPException(status_code=409, detail="Task is already done")

    task.status = "done"
    task.completed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(task)
    return TaskOut.model_validate(task, from_attributes=True).model_copy(
        update={"document_filename": task.document.filename}
    )


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    recipient: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[Notification]:
    query = select(Notification).order_by(Notification.created_at.desc()).limit(200)
    if recipient is not None:
        query = query.where(Notification.recipient == recipient)
    return list(db.scalars(query))
