"""Attack path pipeline — ported verbatim from the desktop app.

Parses a PAN-OS `set`-command firewall config into a SQLite database with four
tables: t_zonedata, t_addresses, t_policies, t_address_groups, and the two
derived attack-path tables (t_attack_paths exploded, t_attack_paths_raw grouped).
"""

from __future__ import annotations

import ipaddress
import re
import sqlite3
from pathlib import Path
from typing import Callable

LogFn = Callable[[str], None]

_RE_TOKEN = re.compile(r'"[^"]+"|\S+')


def _clean(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in {'"', "'"}:
        v = v[1:-1]
    return v


def _parse_net(value: str):
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None


def _best_zone(net, zone_records: list[dict]):
    matches = [
        r for r in zone_records
        if net.version == r["network"].version and net.subnet_of(r["network"])
    ]
    return max(matches, key=lambda r: r["network"].prefixlen) if matches else None


def step_objects(fw_path: Path, db_path: Path, log: LogFn = print) -> None:
    log("Step 1/4 — Parsing network objects and zones ...")
    data = fw_path.read_text(encoding="utf-8").splitlines()

    iface_ip_re = re.compile(
        r"^set network interface aggregate-ethernet ae2 layer3 units (ae2\.\d+) ip (.+)$"
    )
    zone_single_re = re.compile(r"^set zone (\S+) network layer3 (ae2\.\d+)$")
    zone_multi_re = re.compile(r"^set zone (\S+) network layer3 \[\s*(.*?)\s*\]$")

    interface_ips: dict[str, str] = {}
    interface_zones: dict[str, str] = {}

    for line in data:
        m = iface_ip_re.search(line)
        if m:
            interface_ips[m.group(1)] = m.group(2).strip()
        m = zone_single_re.search(line)
        if m:
            interface_zones[m.group(2)] = m.group(1)
            continue
        m = zone_multi_re.search(line)
        if m:
            for iface in m.group(2).split():
                interface_zones[iface] = m.group(1)

    zone_data: list[tuple] = []
    zone_records: list[dict] = []
    for ifce, ip in interface_ips.items():
        zone = interface_zones.get(ifce)
        if zone is None:
            continue
        vlan = ifce.split(".", 1)[1] if "." in ifce else None
        try:
            net = ipaddress.ip_interface(ip).network
        except ValueError:
            log(f"  ! Skipping invalid interface IP: {ifce} -> {ip}")
            continue
        zone_data.append((ifce, vlan, ip, zone))
        zone_records.append({
            "ifce": ifce, "vlan": vlan, "ip_address": ip,
            "zone": zone, "network": net,
        })

    addr_re = re.compile(r"^set address\s+(\S+)\s+(ip-netmask|description|tag)\s+(.+)$")
    addresses: dict[str, dict] = {}
    for line in data:
        m = addr_re.search(line)
        if m:
            name, ftype, val = m.group(1), m.group(2), _clean(m.group(3))
            addresses.setdefault(name, {"ip-netmask": None, "description": None, "tag": None})
            addresses[name][ftype] = val

    valid_rows, skipped, unmatched = [], [], []
    for name, rec in addresses.items():
        if rec["ip-netmask"] is None:
            skipped.append(name)
            continue
        net = _parse_net(rec["ip-netmask"])
        vlan = zone = None
        if net is None:
            unmatched.append(name)
        else:
            best = _best_zone(net, zone_records)
            if best:
                vlan, zone = best["vlan"], best["zone"]
            else:
                unmatched.append(name)
        valid_rows.append((name, rec["ip-netmask"], rec["description"],
                           rec["tag"], vlan, zone))

    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS t_zonedata")
    conn.execute("""
        CREATE TABLE t_zonedata (
            id         INTEGER PRIMARY KEY,
            ifce       TEXT NOT NULL,
            vlan       TEXT,
            ip_address TEXT NOT NULL,
            zone       TEXT NOT NULL
        )""")
    conn.executemany(
        "INSERT INTO t_zonedata (ifce,vlan,ip_address,zone) VALUES (?,?,?,?)",
        zone_data)

    conn.execute("DROP TABLE IF EXISTS t_addresses")
    conn.execute("""
        CREATE TABLE t_addresses (
            id          INTEGER PRIMARY KEY,
            inet_name   TEXT NOT NULL,
            ip_netmask  TEXT NOT NULL,
            description TEXT,
            tag         TEXT,
            vlan        TEXT,
            zone        TEXT
        )""")
    conn.executemany(
        "INSERT INTO t_addresses (inet_name,ip_netmask,description,tag,vlan,zone)"
        " VALUES (?,?,?,?,?,?)",
        valid_rows)
    conn.commit()
    conn.close()

    log(f"  [OK] {len(zone_data)} zone/interface records  ->  t_zonedata")
    log(f"  [OK] {len(valid_rows)} address objects         ->  t_addresses")
    if skipped:
        log(f"  [!]  {len(skipped)} address(es) skipped - no ip-netmask")
    if unmatched:
        log(f"  [!]  {len(unmatched)} address(es) without a matching VLAN/zone")


def step_policies(fw_path: Path, db_path: Path, log: LogFn = print) -> None:
    log("Step 2/4 — Parsing security policies ...")
    data = fw_path.read_text(encoding="utf-8").splitlines()

    rex_base = re.compile(r"set rulebase security rules .*")
    rex1 = re.compile(
        r'set rulebase security rules (?:\")?(.*)(?:\")? '
        r'(description|source|destination|source\-user|category|application'
        r'|service|hip\-profiles|tag|action|group\-tag) (.+)'
    )
    rex2 = re.compile(
        r'set rulebase security rules (?:\")?(.*)(?:\")? (to|from)(?!.*\")\s(?:\")?(.*)(?:\")?'
    )

    _fields = ["to", "from", "source", "destination", "source-user", "category",
               "application", "service", "hip-profiles", "tag", "action",
               "group-tag", "description"]
    policies: dict[str, dict] = {}

    for line in data:
        if not rex_base.search(line):
            continue
        m1 = rex1.search(line)
        m2 = rex2.search(line)
        if not (m1 or m2):
            continue
        mx = m1 if m1 else m2
        rulename, _type, val = mx.group(1), mx.group(2), mx.group(3)
        policies.setdefault(rulename, {f: None for f in _fields})
        policies[rulename][_type] = val

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS t_policies (
            id          INTEGER PRIMARY KEY,
            policyname  TEXT NOT NULL,
            destn_zone  TEXT, source_zone  TEXT,
            source      TEXT, destination  TEXT,
            source_user TEXT, category     TEXT,
            application TEXT, service      TEXT,
            hip_profiles TEXT, tag         TEXT,
            action      TEXT, group_tag    TEXT,
            description TEXT
        )""")
    conn.execute("DELETE FROM t_policies")
    conn.executemany(
        "INSERT INTO t_policies"
        " (policyname,destn_zone,source_zone,source,destination,source_user,"
        "  category,application,service,hip_profiles,tag,action,group_tag,description)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [[p, r["to"], r["from"], r["source"], r["destination"],
          r["source-user"], r["category"], r["application"], r["service"],
          r["hip-profiles"], r["tag"], r["action"], r["group-tag"], r["description"]]
         for p, r in policies.items()])
    conn.commit()
    conn.close()

    log(f"  [OK] {len(policies)} security policies  ->  t_policies")


def step_address_groups(fw_path: Path, db_path: Path, log: LogFn = print) -> None:
    log("Step 3/4 — Parsing address groups ...")

    RE_LINE = re.compile(r"^set address-group (\S+) (static|description|tag) (.+)")
    RE_BRACKETED = re.compile(r"^\[ (.+) \]$")

    groups: dict[str, dict] = {}
    for line in fw_path.read_text(encoding="utf-8").splitlines():
        m = RE_LINE.match(line)
        if not m:
            continue
        name, attr, rest = m.group(1), m.group(2), m.group(3).strip()
        groups.setdefault(name, {"members": [], "description": None, "tag": None})
        if attr == "static":
            mb = RE_BRACKETED.match(rest)
            raw = mb.group(1) if mb else rest
            groups[name]["members"] = [t.strip('"') for t in _RE_TOKEN.findall(raw)]
        elif attr == "description":
            groups[name]["description"] = rest.strip('"')
        elif attr == "tag":
            groups[name]["tag"] = rest.strip('"')

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS t_address_groups (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            members     TEXT,
            description TEXT,
            tag         TEXT
        )""")
    conn.execute("DELETE FROM t_address_groups")
    conn.executemany(
        "INSERT INTO t_address_groups (name,members,description,tag) VALUES (?,?,?,?)",
        [(n, " | ".join(g["members"]) if g["members"] else None,
          g["description"], g["tag"])
         for n, g in groups.items()])
    conn.commit()
    conn.close()

    log(f"  [OK] {len(groups)} address groups  ->  t_address_groups")


def _parse_field(value: str | None) -> list[str]:
    if not value or value.strip() == "any":
        return ["any"]
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1].strip()
    return [t.strip('"') for t in _RE_TOKEN.findall(v)]


def _parse_zone_field(value: str | None) -> list[str]:
    if not value or value.strip() == "any":
        return ["any"]
    v = value.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1].strip()
    tokens = [t.strip('"') for t in _RE_TOKEN.findall(v)]
    return tokens if tokens else ["any"]


def _expand_token(token: str, ag: dict[str, list[str]],
                  seen: frozenset | None = None) -> list[str]:
    if seen is None:
        seen = frozenset()
    if not token.startswith("AG-"):
        return [token]
    if token in seen or token not in ag:
        return [token]
    new_seen = seen | {token}
    leaves: list[str] = []
    for member in ag[token]:
        leaves.extend(_expand_token(member, ag, new_seen))
    return leaves


def _expand_field(tokens: list[str], ag: dict[str, list[str]]) -> list[str]:
    seen, out = set(), []
    for tok in tokens:
        for leaf in _expand_token(tok, ag):
            if leaf not in seen:
                seen.add(leaf)
                out.append(leaf)
    return out


def _token_type(t: str) -> str:
    if t == "any":                           return "any"
    if t.startswith("H-"):                   return "host"
    if t.startswith("AG-"):                  return "group(unexpanded)"
    if t.startswith("N-"):                   return "network"
    if t.startswith("OG-"):                  return "object-group"
    if re.match(r"^\d+\.\d+\.\d+\.\d+", t):  return "cidr"
    return "other"


def step_attack_paths(db_path: Path, log: LogFn = print) -> None:
    log("Step 4/4 — Building attack path matrix ...")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    ag: dict[str, list[str]] = {}
    for row in conn.execute("SELECT name, members FROM t_address_groups"):
        ag[row["name"]] = (
            [m.strip() for m in row["members"].split("|")]
            if row["members"] else []
        )

    addr_zone: dict[str, str] = {}
    for row in conn.execute(
            "SELECT inet_name, zone FROM t_addresses WHERE zone IS NOT NULL"):
        addr_zone[row["inet_name"]] = row["zone"]

    policies = conn.execute(
        "SELECT policyname, source_zone, destn_zone, source, destination,"
        "       application, service, action, tag, description"
        " FROM  t_policies"
    ).fetchall()

    PathKey = tuple
    dedup: dict[PathKey, set[str]] = {}
    dedup_raw: dict[PathKey, set[str]] = {}

    for pol in policies:
        srcs = _expand_field(_parse_field(pol["source"]), ag)
        dsts = _expand_field(_parse_field(pol["destination"]), ag)
        src_zones = _parse_zone_field(pol["source_zone"])
        dst_zones = _parse_zone_field(pol["destn_zone"])
        apps = _parse_field(pol["application"])
        svcs = _parse_field(pol["service"])
        action = pol["action"] or ""
        raw_app = pol["application"] or "any"
        raw_svc = pol["service"] or "any"

        for src in srcs:
            sz_list = [addr_zone[src]] if src in addr_zone else src_zones
            for dst in dsts:
                dz_list = [addr_zone[dst]] if dst in addr_zone else dst_zones
                src_t = _token_type(src)
                dst_t = _token_type(dst)
                for sz in sz_list:
                    for dz in dz_list:
                        raw_key = (sz, dz, src, dst, src_t, dst_t,
                                   raw_app, raw_svc, action)
                        dedup_raw.setdefault(raw_key, set()).add(pol["policyname"])
                        for app in apps:
                            for svc in svcs:
                                key = (sz, dz, src, dst, src_t, dst_t,
                                       app, svc, action)
                                dedup.setdefault(key, set()).add(pol["policyname"])

    def _build_rows(d: dict[PathKey, set[str]]) -> list[tuple]:
        return [
            (" | ".join(sorted(pols)), sz, dz, src, dst,
             src_t, dst_t, app, svc, action, None, None)
            for (sz, dz, src, dst, src_t, dst_t, app, svc, action), pols
            in d.items()
        ]

    rows_exploded = _build_rows(dedup)
    rows_grouped = _build_rows(dedup_raw)

    _SCHEMA = """(
            id           INTEGER PRIMARY KEY,
            policy_name  TEXT NOT NULL,
            source_zone  TEXT,
            destn_zone   TEXT,
            source       TEXT,
            destination  TEXT,
            source_type  TEXT,
            dest_type    TEXT,
            application  TEXT,
            service      TEXT,
            action       TEXT,
            tag          TEXT,
            description  TEXT
        )"""
    _INSERT = (
        "INSERT INTO {tbl}"
        " (policy_name,source_zone,destn_zone,source,destination,"
        "  source_type,dest_type,application,service,action,tag,description)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
    )

    conn.execute("DROP TABLE IF EXISTS t_attack_paths")
    conn.execute(f"CREATE TABLE t_attack_paths {_SCHEMA}")
    conn.executemany(_INSERT.format(tbl="t_attack_paths"), rows_exploded)

    conn.execute("DROP TABLE IF EXISTS t_attack_paths_raw")
    conn.execute(f"CREATE TABLE t_attack_paths_raw {_SCHEMA}")
    conn.executemany(_INSERT.format(tbl="t_attack_paths_raw"), rows_grouped)

    conn.commit()
    conn.close()

    log(f"  [OK] {len(rows_exploded):,} rows (app/svc exploded) ->  t_attack_paths")
    log(f"  [OK] {len(rows_grouped):,} rows (app/svc grouped)  ->  t_attack_paths_raw")


def run_pipeline(fw_path: Path, db_path: Path, log: LogFn = print) -> dict:
    """Run all four steps and return a summary dict the API can serialize."""
    logs: list[str] = []

    def tee(msg: str) -> None:
        logs.append(msg)
        log(msg)

    tee("=" * 56)
    tee(f"  Source   : {fw_path}")
    tee(f"  Database : {db_path}")
    tee("=" * 56)
    step_objects(fw_path, db_path, tee)
    tee("")
    step_policies(fw_path, db_path, tee)
    tee("")
    step_address_groups(fw_path, db_path, tee)
    tee("")
    step_attack_paths(db_path, tee)
    tee("")
    tee("=" * 56)
    tee("  Pipeline complete.")
    tee("=" * 56)

    conn = sqlite3.connect(db_path)
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("t_zonedata", "t_addresses", "t_policies",
                  "t_address_groups", "t_attack_paths", "t_attack_paths_raw")
    }
    conn.close()
    return {"logs": logs, "counts": counts}
