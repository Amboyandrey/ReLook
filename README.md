# ReLook

AI document triage with a human in the loop. Drop a PDF or DOCX in, and
Claude classifies it, summarizes it, and pulls out what needs to be done —
with a confidence score and a flag for when a person should look before
anything gets acted on.

**Phase 1** is a CLI pipeline (still here, still works). **Phase 2** adds a
review queue: a FastAPI backend that stores every document and its AI
analysis, and a React screen where a human sees the document next to the
AI's output and approves, edits, or rejects it before anything downstream
acts on it. **Phase 3** makes approval actually do something: the original
gets filed, every extracted request becomes a trackable task, and task
owners get notified. See [Roadmap](#roadmap).

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

## Usage: CLI (phase 1)

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

## Usage: Review queue (phase 2)

The review queue reuses the same `relook` engine as the CLI (`src/relook/`)
behind a FastAPI backend, with a React frontend for the human review step.

```bash
# Backend (from the repo root, same venv as above)
pip install -e ".[api]"
uvicorn backend.app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env   # only needed if the backend isn't on localhost:8000
npm run dev
```

Open the frontend's printed URL (default `http://localhost:5173`). Upload a
PDF/DOCX/TXT/MD file, and it's classified immediately and dropped into the
**Pending** queue. Click a document to see it next to the AI's category,
summary, and extracted requests — edit any field, then **Approve** or
**Reject**. Approved/rejected documents move to their own tabs and become
read-only.

Storage defaults to a local SQLite file at `data/relook.db` (created
automatically) with uploaded originals in `data/uploads/` — nothing to set
up for local dev. Point `DATABASE_URL` at a Postgres instance for anything
beyond that (install the `postgres` extra for the driver:
`pip install -e ".[postgres]"`).

Every review action is logged to an append-only `review_events` table
pairing the AI's original (frozen) output with what the human decided —
this is the dataset the phase-4 learning loop will train on.

## Usage: Routing & actions (phase 3)

Approving a document (in the review queue's UI, or via `POST
/documents/{id}/review`) now triggers three things automatically, in the
same request:

1. **Filing** — the original file moves from the flat `data/uploads/` drop
   folder into `data/filed/<category>/<year>/<month>/`.
2. **Task creation** — every entry in the document's `requests[]` becomes a
   row in a `tasks` table (text, owner, deadline, status). View and
   complete them from the **Tasks** tab in the frontend, or via `GET
   /tasks` / `POST /tasks/{id}/complete`.
3. **Notification** — each task's owner is notified. This always writes an
   in-app record (visible in the Tasks tab's notification feed and via `GET
   /notifications`) with no setup required. Two optional external channels
   activate automatically when configured via environment variables:

   ```bash
   # Email (optional)
   SMTP_HOST=smtp.example.com
   SMTP_PORT=587                # default 587
   SMTP_USER=...                # optional
   SMTP_PASSWORD=...            # optional
   SMTP_FROM=relook@example.com # default relook@localhost
   SMTP_USE_TLS=true            # default true

   # Slack (optional)
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
   ```

   A failed external delivery (bad webhook, SMTP auth failure, ...) is
   recorded on the notification row rather than blocking the approval —
   check `GET /notifications` for `delivered: false` entries.

A document with no extracted requests still gets a single notification
confirming it was filed, sent to whoever approved it.

## Known limitation (by design, for now)

Page numbers on extracted requests are self-reported by the model, not
generated from the Messages API's citations feature — citations can't be
combined with structured outputs (`output_config.format`) in one request.
Good enough to point a reviewer at roughly the right page today; wiring in
real citations (a second, citations-only pass) is a natural phase-2 upgrade
once there's a review UI to click through to a highlighted page.

## Roadmap

1. ✅ CLI pipeline
2. ✅ Review queue: FastAPI + SQLite/Postgres + a React screen showing the
   document next to the AI's output, with approve/edit/reject actions
3. ✅ Routing & actions: filing, task creation from `requests[]`, and
   notifications (in-app always; email/Slack optional) on approval
4. Learning loop: use the `review_events` audit log as a correction
   dataset, build an eval set, use accuracy data to safely raise the
   auto-approve confidence threshold
