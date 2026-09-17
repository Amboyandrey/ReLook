"""Database engine and session management.

Defaults to a local SQLite file so the review queue runs with zero extra
setup. Point DATABASE_URL at a Postgres instance for anything beyond local
dev -- SQLAlchemy's ORM layer doesn't change, only the connection string
(install the "postgres" extra for the driver: `pip install -e ".[postgres]"`).
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DATABASE_URL = f"sqlite:///{DATA_DIR / 'relook.db'}"

DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
    # Import models so their tables are registered on Base before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
