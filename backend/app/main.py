"""FastAPI app for the ReLook review queue.

Run with:  uvicorn backend.app.main:app --reload --port 8000
(from the repo root, with the relook package installed via `pip install -e .`)
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from .db import init_db  # noqa: E402
from .routes.documents import router as documents_router  # noqa: E402

app = FastAPI(title="ReLook Review Queue", version="0.1.0")

allowed_origins = os.environ.get("RELOOK_CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(documents_router)
