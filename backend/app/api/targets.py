"""GET /api/targets — list available destination targets (host or zone)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..config import DB_PATH
from ..db import connect, table_exists

router = APIRouter(prefix="/api", tags=["targets"])

ALLOWED_MODES = {"host", "zone"}
ALLOWED_SOURCES = {"exploded", "grouped"}


@router.get("/targets")
def targets(
    mode: str = Query("host", pattern="^(host|zone)$"),
    source: str = Query("exploded", pattern="^(exploded|grouped)$"),
) -> dict:
    if mode not in ALLOWED_MODES or source not in ALLOWED_SOURCES:
        raise HTTPException(400, "Invalid mode or source")
    if not DB_PATH.exists():
        raise HTTPException(404, "No database — upload a firewall.txt first")

    tbl = "t_attack_paths" if source == "exploded" else "t_attack_paths_raw"
    if not table_exists(tbl):
        raise HTTPException(404, f"Table {tbl} not found — rebuild pipeline")

    field = "destination" if mode == "host" else "destn_zone"
    conn = connect()
    if mode == "host":
        rows = conn.execute(
            f"SELECT DISTINCT {field} FROM {tbl}"
            f" WHERE {field} != 'any' ORDER BY {field}"
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT DISTINCT {field} FROM {tbl}"
            f" WHERE {field} IS NOT NULL ORDER BY {field}"
        ).fetchall()
    conn.close()

    return {
        "mode": mode,
        "source": source,
        "grouped_available": table_exists("t_attack_paths_raw"),
        "targets": [r[0] for r in rows],
    }
