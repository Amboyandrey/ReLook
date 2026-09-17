"""Turns a file on disk into Messages API content blocks.

PDFs (including scanned/image-only ones) are sent inline as base64 `document`
blocks -- Claude reads them natively, page images and all, so no local OCR
step is needed for phase 1. DOCX and plain text files have no native
`document` block type, so their text is extracted locally and sent as a
`text` block instead.
"""

from __future__ import annotations

import base64
from pathlib import Path

import docx
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class UnsupportedDocumentError(ValueError):
    pass


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def load_content_blocks(path: Path) -> list[dict]:
    """Return the list of Messages API content blocks for this file."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return [_pdf_block(path)]
    if suffix == ".docx":
        return [_text_block(_extract_docx_text(path), path)]
    if suffix in (".txt", ".md"):
        return [_text_block(path.read_text(encoding="utf-8", errors="replace"), path)]

    raise UnsupportedDocumentError(
        f"{path.name}: unsupported file type {suffix!r} "
        f"(supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))})"
    )


def page_count(path: Path) -> int | None:
    """Best-effort page count, used only for logging -- not sent to the API."""
    if path.suffix.lower() == ".pdf":
        try:
            return len(PdfReader(str(path)).pages)
        except Exception:
            return None
    return None


def _pdf_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": data,
        },
        "title": path.name,
    }


def _text_block(text: str, path: Path) -> dict:
    return {
        "type": "text",
        "text": f"--- Document: {path.name} ---\n\n{text}",
    }


def _extract_docx_text(path: Path) -> str:
    document = docx.Document(str(path))
    parts: list[str] = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    return "\n".join(parts)
