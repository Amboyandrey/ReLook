"""What happens when a document is approved: file it, create tasks from its
requests[], and notify the owners.

Called once, synchronously, from the review endpoint right after a document
is approved. Kept synchronous and best-effort on purpose for phase 3 -- if
any step needs to become a background job (e.g. a slow external notifier)
that's a natural follow-up once there's real traffic to justify it.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from . import notifications
from .db import DATA_DIR
from .models import Document, Task

FILED_DIR = DATA_DIR / "filed"


def _safe_slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "file"


def file_document(document: Document) -> None:
    """Moves the original from the flat uploads/ dir into
    filed/<category>/<year>/<month>/<id>_<filename>, and updates
    document.stored_path to match. No-op if the source file is already
    gone (e.g. filed twice, or manually cleaned up)."""
    source = Path(document.stored_path)
    if not source.exists():
        return

    uploaded_at = document.uploaded_at
    dest_dir = FILED_DIR / _safe_slug(document.category) / f"{uploaded_at:%Y}" / f"{uploaded_at:%m}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_path = dest_dir / f"{document.id}_{_safe_slug(document.filename)}"
    shutil.move(str(source), str(dest_path))
    document.stored_path = str(dest_path)


def create_tasks_from_requests(db: Session, document: Document) -> list[Task]:
    """One Task per entry in document.requests. Safe to call more than once
    per document in principle, but the review endpoint only calls it once,
    on the transition into "approved"."""
    tasks = []
    for req in document.requests:
        task = Task(
            document_id=document.id,
            text=req.get("text", ""),
            deadline=req.get("deadline"),
            owner=req.get("owner"),
            status="open",
        )
        db.add(task)
        tasks.append(task)
    db.flush()  # populate task.id for the notifications below
    return tasks


def notify_owners(db: Session, document: Document, tasks: list[Task]) -> None:
    if not tasks:
        notifications.notify(
            db,
            document_id=document.id,
            recipient=document.reviewed_by or "unassigned",
            message=f"'{document.filename}' was approved ({document.category}) with no action items.",
        )
        return

    for task in tasks:
        recipient = task.owner or "unassigned"
        deadline_note = f" (due {task.deadline})" if task.deadline else ""
        notifications.notify(
            db,
            document_id=document.id,
            task_id=task.id,
            recipient=recipient,
            subject=f"New task from {document.filename}",
            message=f"{task.text}{deadline_note} -- from '{document.filename}' ({document.category})",
        )


def route_approved_document(db: Session, document: Document) -> list[Task]:
    """Runs the full post-approval pipeline: file the original, create
    tasks from requests[], notify their owners. Returns the created tasks."""
    file_document(document)
    tasks = create_tasks_from_requests(db, document)
    notify_owners(db, document, tasks)
    return tasks
