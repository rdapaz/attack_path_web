"""CRUD for policy annotations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import DB_PATH
from ..db import connect, ensure_annotations_table

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


class AnnotationIn(BaseModel):
    classification: str | None = None
    notes: str | None = None


def _require_db() -> None:
    if not DB_PATH.exists():
        raise HTTPException(404, "No database — upload a firewall.txt first")
    ensure_annotations_table(DB_PATH)


@router.get("/{policy_name}")
def get_annotation(policy_name: str) -> dict:
    _require_db()
    conn = connect()
    row = conn.execute(
        "SELECT classification, notes, updated_at FROM t_annotations"
        " WHERE policy_name = ?",
        (policy_name,),
    ).fetchone()
    conn.close()
    if not row:
        return {
            "policy_name": policy_name,
            "classification": None,
            "notes": None,
            "updated_at": None,
        }
    return {
        "policy_name": policy_name,
        "classification": row["classification"],
        "notes": row["notes"],
        "updated_at": row["updated_at"],
    }


@router.put("/{policy_name}")
def put_annotation(policy_name: str, payload: AnnotationIn) -> dict:
    _require_db()
    conn = connect()
    conn.execute(
        "INSERT OR REPLACE INTO t_annotations"
        " (policy_name, classification, notes, updated_at)"
        " VALUES (?, ?, ?, datetime('now'))",
        (policy_name, payload.classification, payload.notes),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/{policy_name}")
def delete_annotation(policy_name: str) -> dict:
    _require_db()
    conn = connect()
    conn.execute("DELETE FROM t_annotations WHERE policy_name = ?", (policy_name,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("")
def list_annotations() -> dict:
    _require_db()
    conn = connect()
    rows = conn.execute(
        "SELECT policy_name, classification, notes, updated_at"
        " FROM t_annotations ORDER BY policy_name"
    ).fetchall()
    conn.close()
    return {"annotations": [dict(r) for r in rows]}
