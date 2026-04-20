"""SQLite connection helper + schema bootstrap for annotations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_annotations_table(db_path: Path | None = None) -> None:
    """The pipeline never touches this table, so it survives rebuilds."""
    path = db_path or DB_PATH
    if not path.exists():
        return
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS t_annotations (
            policy_name    TEXT PRIMARY KEY,
            classification TEXT,
            notes          TEXT,
            updated_at     TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def table_exists(name: str, db_path: Path | None = None) -> bool:
    path = db_path or DB_PATH
    if not path.exists():
        return False
    conn = sqlite3.connect(path)
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    conn.close()
    return row is not None
