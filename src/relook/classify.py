"""Calls Claude to classify, summarize, and extract requests from a document."""

from __future__ import annotations

import json
from pathlib import Path

import anthropic

from .schema import AnalysisResult, build_json_schema
from .taxonomy import Taxonomy

MODEL = "claude-opus-5"

SYSTEM_PROMPT_TEMPLATE = """\
You are the triage desk for an HR document intake system. For every document \
you are given, you classify it, summarize it, and pull out anything that \
needs to be acted on.

Categories (choose exactly one):
{taxonomy_block}

Guidelines:
- `confidence` reflects how sure you are about the category choice, not the \
quality of the document.
- `requests` should list every distinct ask or required action, each with \
its own deadline/owner/page when you can determine them. An informational \
document with nothing to act on should have an empty `requests` list.
- Set `needs_human` to true whenever the document is ambiguous, sensitive \
(e.g. a complaint, legal matter, or anything involving pay or termination), \
or your confidence is below 0.85. Otherwise set it to false.
- When `needs_human` is true, `reason_for_review` must briefly say why. \
Otherwise set it to null.
- Base every field only on what the document actually says -- do not invent \
names, dates, or amounts that aren't present.
"""


def analyze_document(
    client: anthropic.Anthropic,
    content_blocks: list[dict],
    taxonomy: Taxonomy,
) -> AnalysisResult:
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(taxonomy_block=taxonomy.as_prompt_block())

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={
            "effort": "medium",
            "format": build_json_schema(taxonomy.names),
        },
        messages=[
            {
                "role": "user",
                "content": [
                    *content_blocks,
                    {
                        "type": "text",
                        "text": "Analyze this document per your instructions.",
                    },
                ],
            }
        ],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(
            f"Claude declined to analyze this document "
            f"(category: {getattr(response.stop_details, 'category', None)})"
        )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise RuntimeError(f"No text content in response (stop_reason={response.stop_reason})")

    data = json.loads(text)
    return AnalysisResult.model_validate(data)


def result_to_record(result: AnalysisResult, taxonomy: Taxonomy, source_path: Path) -> dict:
    """Attach routing info (default owner) and source metadata for storage."""
    record = result.model_dump()
    record["source_file"] = str(source_path)
    record["auto_approve_eligible"] = (
        result.confidence >= taxonomy.auto_approve_threshold and not result.needs_human
    )
    for req in record["requests"]:
        if req["owner"] is None:
            req["owner"] = taxonomy.owner_for(result.category)
    return record
