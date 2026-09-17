"""Wraps the relook library so the API and the phase-1 CLI share one engine.

The taxonomy and Anthropic client are loaded once per process rather than
per-request.
"""

from __future__ import annotations

from pathlib import Path

import anthropic
from relook.classify import analyze_document, result_to_record
from relook.parsing import extract_preview_text, load_content_blocks
from relook.taxonomy import Taxonomy, load_taxonomy

_client: anthropic.Anthropic | None = None
_taxonomy: Taxonomy | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def get_taxonomy() -> Taxonomy:
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = load_taxonomy()
    return _taxonomy


def analyze(path: Path) -> dict:
    """Runs the full pipeline on a stored file and returns a record ready to
    populate a Document row (see relook.classify.result_to_record)."""
    taxonomy = get_taxonomy()
    blocks = load_content_blocks(path)
    result = analyze_document(get_client(), blocks, taxonomy)
    record = result_to_record(result, taxonomy, path)
    record["preview_text"] = extract_preview_text(path)
    return record
