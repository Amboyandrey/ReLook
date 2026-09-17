"""The structured output contract for document analysis.

`AnalysisResult` is what every pipeline run produces. `build_json_schema`
renders the matching JSON Schema for `output_config.format`, so the API
response is guaranteed to validate against this model -- no free-text
parsing, no "the model forgot a field" failures.

Design note: this schema asks the model to self-report a page number per
extracted request rather than using the Messages API's citations feature,
because citations are incompatible with `output_config.format` in the same
request. Self-reported pages are good enough to jump a reviewer to roughly
the right page; wiring in real citations (via a second, citations-only call)
is a good phase-2 upgrade once the review UI exists to make use of them.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ExtractedRequest(BaseModel):
    text: str = Field(description="What is being asked for, in the document's own terms.")
    deadline: Optional[str] = Field(
        default=None, description="ISO date (YYYY-MM-DD) if a deadline is stated or implied, else null."
    )
    owner: Optional[str] = Field(
        default=None, description="Who should act on this (role or team), if determinable."
    )
    page: Optional[int] = Field(
        default=None, description="1-indexed page number this request appears on, if known."
    )


class Entities(BaseModel):
    person: Optional[str] = None
    department: Optional[str] = None
    dates: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    requests: list[ExtractedRequest] = Field(default_factory=list)
    entities: Entities
    needs_human: bool
    reason_for_review: Optional[str] = None


def build_json_schema(category_names: tuple[str, ...]) -> dict:
    """Render the JSON Schema for output_config.format, matching AnalysisResult."""
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": list(category_names),
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
                "summary": {
                    "type": "string",
                    "description": "2-4 sentence plain-language summary of the document.",
                },
                "requests": {
                    "type": "array",
                    "description": "Concrete asks or actions the document requires from someone.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "deadline": {"type": ["string", "null"]},
                            "owner": {"type": ["string", "null"]},
                            "page": {"type": ["integer", "null"]},
                        },
                        "required": ["text", "deadline", "owner", "page"],
                        "additionalProperties": False,
                    },
                },
                "entities": {
                    "type": "object",
                    "properties": {
                        "person": {"type": ["string", "null"]},
                        "department": {"type": ["string", "null"]},
                        "dates": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["person", "department", "dates"],
                    "additionalProperties": False,
                },
                "needs_human": {
                    "type": "boolean",
                    "description": "True if this document should always be reviewed by a person before acting on it.",
                },
                "reason_for_review": {
                    "type": ["string", "null"],
                    "description": "Why a human should double-check this, or null if there's no particular concern.",
                },
            },
            "required": [
                "category",
                "confidence",
                "summary",
                "requests",
                "entities",
                "needs_human",
                "reason_for_review",
            ],
            "additionalProperties": False,
        },
    }
