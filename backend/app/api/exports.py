"""Export endpoints: Mermaid / CSV / YAML / Excel."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..config import DB_PATH, SETTINGS_PATH
from ..services.exports import (
    fetch_full_policies_with_annotations,
    make_csv,
    make_excel,
    make_yaml,
)
from ..services.mermaid import generate_mermaid

router = APIRouter(prefix="/api/export", tags=["export"])


def _load_categories() -> list[dict]:
    if not SETTINGS_PATH.exists():
        return []
    try:
        data = json.loads(SETTINGS_PATH.read_text())
        return data.get("categories", [])
    except Exception:
        return []


def _safe_name(target: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", target or "export")


class TableExportRequest(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    target: str = ""
    view_by_zones: bool = False


class MermaidRequest(BaseModel):
    rows: list[dict]
    target: str
    target_is_zone: bool = False
    view_by_zones: bool = False
    fenced: bool = False


class ExcelRequest(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    target: str = ""
    view_by_zones: bool = False
    full_policies: bool = Field(False, description="Export t_policies + annotations, ignoring headers/rows")


@router.post("/mermaid")
def export_mermaid(req: MermaidRequest) -> Response:
    chart = generate_mermaid(req.rows, req.target, req.target_is_zone, req.view_by_zones)
    body = chart
    if req.fenced:
        body = f"# Attack Paths -> {req.target}\n\n```mermaid\n{chart}\n```\n"
    filename = f"attack_path_{_safe_name(req.target)}.md"
    return Response(
        content=body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/csv")
def export_csv(req: TableExportRequest) -> Response:
    body = make_csv(req.headers, req.rows)
    view = "zones" if req.view_by_zones else "hosts"
    filename = f"attack_path_{_safe_name(req.target)}_{view}.csv"
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/yaml")
def export_yaml(req: TableExportRequest) -> Response:
    body = make_yaml(req.headers, req.rows)
    view = "zones" if req.view_by_zones else "hosts"
    filename = f"attack_path_{_safe_name(req.target)}_{view}.yaml"
    return Response(
        content=body,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/excel")
def export_excel(req: ExcelRequest) -> Response:
    categories = _load_categories()
    if req.full_policies:
        if not DB_PATH.exists():
            raise HTTPException(404, "No database — build the pipeline first")
        headers, rows = fetch_full_policies_with_annotations(DB_PATH)
        body = make_excel(headers, rows, categories, sheet_title="Policies")
        filename = "attack_path_full_policies.xlsx"
    else:
        body = make_excel(req.headers, req.rows, categories, sheet_title="Attack Paths")
        view = "zones" if req.view_by_zones else "hosts"
        filename = f"attack_path_{_safe_name(req.target)}_{view}.xlsx"

    return Response(
        content=body,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
