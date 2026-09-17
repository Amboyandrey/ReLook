"""Saves uploaded files to disk and resolves them back for the API."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import UploadFile

from .db import DATA_DIR

UPLOAD_DIR = DATA_DIR / "uploads"


def save_upload(file: UploadFile) -> tuple[Path, str]:
    """Writes the upload to disk under a UUID-prefixed name and returns
    (stored_path, content_type)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename or "upload").suffix
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name

    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    with open(stored_path, "wb") as out:
        out.write(file.file.read())

    return stored_path, content_type
