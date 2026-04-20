"""Row-highlight classifier — ported from gui/views/viewer.py.

Returns a symbolic tag; the frontend maps the tag to a concrete color.
Tags: "deny" | "any" | "app_any" | "svc_any" | None.
"""

from __future__ import annotations


def host_row_tag(r: dict) -> str | None:
    if (r.get("action") or "").lower() == "deny":
        return "deny"

    def _norm(f: str) -> str:
        return (r.get(f) or "").strip().lower()

    app_any = _norm("application") == "any"
    svc = _norm("service")
    svc_open = svc in ("any", "application-default")
    zone_host_any = any(
        _norm(f) == "any"
        for f in ("source_zone", "source", "destn_zone", "destination")
    )

    if zone_host_any or (app_any and svc_open):
        return "any"
    if app_any:
        return "app_any"
    if svc == "any":
        return "svc_any"
    return None


def zone_row_tag(sz: str, dz: str, d: dict) -> str | None:
    """d contains sets: sources, apps, svcs, actions."""
    if "deny" in d["actions"]:
        return "deny"

    _any = {"any"}
    _open = {"any", "application-default"}
    app_any = bool(_any & d["apps"])
    svc_open = bool(_open & d["svcs"])
    svc_any = bool(_any & d["svcs"])
    zone_src_any = sz in _any or dz in _any or bool(_any & d["sources"])

    if zone_src_any or (app_any and svc_open):
        return "any"
    if app_any:
        return "app_any"
    if svc_any:
        return "svc_any"
    return None
