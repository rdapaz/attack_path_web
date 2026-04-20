"""Mermaid diagram generator — ported from gui/views/viewer.py."""

from __future__ import annotations

import re
from collections import defaultdict


def _mermaid_id(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _app_label(application, service):
    app = (application or "").strip()
    svc = (service or "").strip()
    if app and app != "any" and app != "application-default":
        return app
    if svc and svc != "any" and svc != "application-default":
        return svc
    if app == "any" or svc == "any":
        return "any"
    return app or svc or "any"


def generate_mermaid(
    rows: list[dict],
    target: str,
    target_is_zone: bool,
    view_by_zones: bool,
) -> str:
    """Generate a Mermaid flowchart LR diagram from the current result rows."""
    lines: list[str] = ["flowchart LR", ""]

    if view_by_zones:
        edges: dict[tuple, set] = defaultdict(set)
        policy_counts: dict[tuple, set] = defaultdict(set)

        for r in rows:
            sz = r.get("source_zone") or "unknown"
            dz = r.get("destn_zone") or target
            key = (sz, dz)
            edges[key].add(_app_label(r.get("application"), r.get("service")))
            policy_counts[key].add(r.get("policy_name", ""))

        src_zones = sorted({k[0] for k in edges})
        dst_zones = sorted({k[1] for k in edges})

        for z in src_zones:
            lines.append(f'    {_mermaid_id(z)}["{z}"]')
        lines.append("")
        for z in dst_zones:
            lines.append(f'    {_mermaid_id(z)}(("{z}"))')
        lines.append("")

        for (sz, dz), apps in sorted(edges.items()):
            n_pol = len(policy_counts[(sz, dz)])
            label = ",<br/>".join(sorted(apps))
            if n_pol > 1:
                label += f"<br/>({n_pol} policies)"
            lines.append(
                f'    {_mermaid_id(sz)} -->|"{label}"| {_mermaid_id(dz)}')

    else:
        zone_sources: dict[str, list[str]] = defaultdict(list)
        seen_src: set[str] = set()
        for r in rows:
            src = r["source"]
            sz = r.get("source_zone") or "unknown"
            if src not in seen_src:
                seen_src.add(src)
                zone_sources[sz].append(src)

        dst_nodes: set[str] = set()
        for r in rows:
            dst_nodes.add(r["destination"])

        for zone, sources in sorted(zone_sources.items()):
            lines.append(f'    subgraph "{zone}"')
            for src in sources:
                lines.append(f'        {_mermaid_id(src)}["{src}"]')
            lines.append("    end")
        lines.append("")

        for dst in sorted(dst_nodes):
            lines.append(f'    {_mermaid_id(dst)}(["{dst}"])')
        lines.append("")

        edge_map: dict[tuple, set] = defaultdict(set)
        for r in rows:
            edge_map[(r["source"], r["destination"])].add(
                _app_label(r.get("application"), r.get("service")))

        for (src, dst), apps in sorted(edge_map.items()):
            label = ",<br/>".join(sorted(apps))
            lines.append(
                f'    {_mermaid_id(src)} -->|"{label}"| {_mermaid_id(dst)}')

    lines.append("")
    lines.append(f'%% Target: {target}')
    return "\n".join(lines)
