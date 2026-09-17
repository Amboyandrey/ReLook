# ReLook

AI document triage with a human in the loop. Drop a PDF or DOCX in, and
Claude classifies it, summarizes it, and pulls out what needs to be done —
with a confidence score and a flag for when a person should look before
anything gets acted on.

This is **phase 1**: a CLI pipeline. No database, no review UI yet — the
goal is to validate classification/extraction quality on real documents
before building anything around it. See [Roadmap](#roadmap).

## How it works

```
PDF/DOCX in  ──►  Claude (structured output)  ──►  JSON out
                   category, confidence,
                   summary, requests[],
                   needs_human flag
```

- **PDFs** (including scanned/image-only ones) are sent to Claude inline —
  it reads pages natively, so no local OCR step is needed.
- **DOCX/TXT/MD** files have their text extracted locally and sent as plain
  text.
- The category list, descriptions, and default routing owners live in
  [`config/taxonomy.yaml`](config/taxonomy.yaml) — edit it to relabel or add
  categories without touching code.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # then add your ANTHROPIC_API_KEY
```

If you've already run `ant auth login`, you can skip `.env` entirely — the
SDK picks up the stored login automatically.

## Usage

```bash
# Process every supported file in a folder
relook samples/

# Process a single file
relook samples/leave-request.pdf

# Keep watching a folder and process new files as they arrive
relook samples/ --watch
```

Each run writes one JSON file per document to `output/`, e.g.:

```json
{
  "category": "leave_request",
  "confidence": 0.93,
  "summary": "Employee requests three weeks of unpaid leave starting Nov 4...",
  "requests": [
    {"text": "Approve leave from Nov 4-25", "deadline": "2026-10-20", "owner": "HR manager", "page": 1}
  ],
  "entities": {"person": "Jordan Diaz", "department": "Engineering", "dates": ["2026-11-04", "2026-11-25"]},
  "needs_human": true,
  "reason_for_review": "Leave window overlaps a blackout period mentioned on page 2",
  "source_file": "samples/leave-request.pdf",
  "auto_approve_eligible": false
}
```

## Known limitation (by design, for now)

Page numbers on extracted requests are self-reported by the model, not
generated from the Messages API's citations feature — citations can't be
combined with structured outputs (`output_config.format`) in one request.
Good enough to point a reviewer at roughly the right page today; wiring in
real citations (a second, citations-only pass) is a natural phase-2 upgrade
once there's a review UI to click through to a highlighted page.

## Roadmap

1. ✅ CLI pipeline (this phase)
2. Review queue: FastAPI + Postgres + a React screen showing the document
   next to the AI's output, with approve/edit/reject actions
3. Routing & actions: notifications, filing, task creation from `requests[]`
4. Learning loop: store human corrections, build an eval set, use accuracy
   data to safely raise the auto-approve confidence threshold
