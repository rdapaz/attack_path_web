"""POST /api/pipeline/build — accept a firewall.txt upload and rebuild the DB."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config import DB_PATH, MAX_UPLOAD_MB, UPLOAD_DIR, ensure_dirs
from ..db import ensure_annotations_table
from ..services.pipeline import run_pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/build")
async def build(file: UploadFile = File(...)) -> dict:
    ensure_dirs()

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(413, f"Upload too large ({size_mb:.1f} MB > {MAX_UPLOAD_MB} MB)")

    upload_name = f"{uuid.uuid4().hex}.txt"
    upload_path = UPLOAD_DIR / upload_name
    upload_path.write_bytes(contents)

    try:
        result = run_pipeline(upload_path, DB_PATH, log=lambda m: None)
    except Exception as exc:
        raise HTTPException(500, f"Pipeline failed: {exc}") from exc

    ensure_annotations_table(DB_PATH)

    return {
        "ok": True,
        "original_filename": file.filename,
        "stored_as": upload_name,
        "size_bytes": len(contents),
        "counts": result["counts"],
        "logs": result["logs"],
    }


@router.get("/status")
def status() -> dict:
    return {
        "db_exists": DB_PATH.exists(),
        "db_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
    }
