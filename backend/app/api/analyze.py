"""POST /api/analyze — query rows for a target and compute view/row highlights."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import DB_PATH
from ..db import connect, ensure_annotations_table, table_exists
from ..services.rowcolor import host_row_tag, zone_row_tag

router = APIRouter(prefix="/api", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    target: str
    target_is_zone: bool = False
    view_by_zones: bool = False
    data_source: str = Field("exploded", pattern="^(exploded|grouped)$")


HOST_COLS = [
    "source_zone", "source", "destn_zone", "destination",
    "application", "service", "action", "policy_name", "classification",
]
ZONE_COLS = [
    "source_zone", "destn_zone", "n_sources", "applications",
    "services", "action", "n_policies",
]


@router.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    if not DB_PATH.exists():
        raise HTTPException(404, "No database — upload a firewall.txt first")

    tbl = "t_attack_paths" if req.data_source == "exploded" else "t_attack_paths_raw"
    if not table_exists(tbl):
        raise HTTPException(404, f"Table {tbl} not found")

    ensure_annotations_table(DB_PATH)
    conn = connect()
    field = "destn_zone" if req.target_is_zone else "destination"
    raw_rows = conn.execute(
        f"SELECT policy_name, source_zone, destn_zone, source,"
        f"       destination, application, service, action"
        f" FROM  {tbl}"
        f" WHERE {field} = ?"
        f" ORDER BY source_zone, source",
        (req.target,),
    ).fetchall()

    pol_names: set[str] = set()
    for r in raw_rows:
        for p in (r["policy_name"] or "").split("|"):
            p = p.strip()
            if p:
                pol_names.add(p)

    annotations: dict[str, str] = {}
    if pol_names:
        placeholders = ",".join("?" * len(pol_names))
        for ar in conn.execute(
            f"SELECT policy_name, classification FROM t_annotations"
            f" WHERE policy_name IN ({placeholders})",
            tuple(pol_names),
        ).fetchall():
            if ar["classification"]:
                annotations[ar["policy_name"]] = ar["classification"]
    conn.close()

    # Drop self-paths except the wildcard any == any.
    rows = [
        dict(r) for r in raw_rows
        if r["source"] != r["destination"] or r["source"] == "any"
    ]

    if req.view_by_zones:
        return _render_zone_view(rows)
    return _render_host_view(rows, annotations)


def _render_host_view(rows: list[dict], annotations: dict[str, str]) -> dict:
    out_rows: list[dict] = []
    for r in rows:
        classifications = []
        for pol in (r.get("policy_name") or "").split("|"):
            c = annotations.get(pol.strip(), "")
            if c:
                classifications.append(c)
        row_cls = classifications[0] if classifications else ""
        out_rows.append({
            "source_zone": r.get("source_zone") or "",
            "source": r.get("source") or "",
            "destn_zone": r.get("destn_zone") or "",
            "destination": r.get("destination") or "",
            "application": r.get("application") or "",
            "service": r.get("service") or "",
            "action": r.get("action") or "",
            "policy_name": r.get("policy_name") or "",
            "classification": row_cls,
            "row_tag": host_row_tag(r),
        })
    return {"mode": "host", "columns": HOST_COLS, "rows": out_rows}


def _render_zone_view(rows: list[dict]) -> dict:
    agg: dict[tuple, dict] = {}
    for r in rows:
        key = (r.get("source_zone") or "unknown",
               r.get("destn_zone") or "unknown")
        if key not in agg:
            agg[key] = {
                "sources": set(), "apps": set(),
                "svcs": set(), "actions": set(), "policies": set(),
            }
        agg[key]["sources"].add(r.get("source") or "")
        agg[key]["apps"].add(r.get("application") or "")
        agg[key]["svcs"].add(r.get("service") or "")
        agg[key]["actions"].add(r.get("action") or "")
        agg[key]["policies"].add(r.get("policy_name") or "")

    out_rows: list[dict] = []
    for (sz, dz), d in sorted(agg.items()):
        out_rows.append({
            "source_zone": sz,
            "destn_zone": dz,
            "n_sources": len(d["sources"]),
            "applications": ", ".join(sorted(d["apps"] - {"", None})),
            "services": ", ".join(sorted(d["svcs"] - {"", None})),
            "action": ", ".join(sorted(d["actions"])),
            "n_policies": len(d["policies"]),
            "row_tag": zone_row_tag(sz, dz, d),
        })
    return {"mode": "zone", "columns": ZONE_COLS, "rows": out_rows}
