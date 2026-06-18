"""
Phase 1 — Audit engine.
Checks property-level configurations against the gap checklist.
Trigger/template checks are flagged as manual review — OwnerRez API v2
does not expose triggers or message templates.
"""

from datetime import datetime
from ownerrez_client import OwnerRezClient
from config import (
    GAP_CHECKLIST,
    SECURITY_DEPOSIT_EXEMPT,
)

MANUAL_REVIEW_NOTE = (
    "OwnerRez API v2 does not expose triggers or templates. "
    "Verify this manually in the OwnerRez dashboard under Messaging > Triggers."
)


def build_property_map(properties):
    by_id = {}
    by_name = {}
    for p in properties:
        pid = str(p.get("id", ""))
        name = (p.get("name") or p.get("short_name") or "").upper()
        by_id[pid] = p
        if name:
            by_name[name] = pid
    return by_id, by_name


def resolve_property_ids(rule_properties, by_id, by_name):
    if rule_properties == "all":
        return set(by_id.keys())
    if rule_properties == "non_exempt":
        exempt_ids = set()
        for name in SECURITY_DEPOSIT_EXEMPT:
            pid = by_name.get(name.upper())
            if pid:
                exempt_ids.add(pid)
        return set(by_id.keys()) - exempt_ids
    ids = set()
    for name in rule_properties:
        pid = by_name.get(name.upper())
        if pid:
            ids.add(pid)
        else:
            for pname, ppid in by_name.items():
                if name.upper() in pname:
                    ids.add(ppid)
    return ids


def audit(client: OwnerRezClient) -> dict:
    print("Fetching data from OwnerRez API...")
    properties = client.get_properties()
    print(f"  Found {len(properties)} properties")

    by_id, by_name = build_property_map(properties)

    findings = []
    summary = {"pass": 0, "fail": 0, "manual": 0}

    for rule in GAP_CHECKLIST:
        rule_id = rule["id"]
        desc = rule["description"]

        if rule["type"] == "trigger":
            finding = {
                "status": "manual",
                "issues": [MANUAL_REVIEW_NOTE],
                "dashboard_url": "https://app.ownerrez.com/messaging/triggers",
            }
        elif rule["type"] == "property_config":
            finding = _audit_property_config(rule, properties, by_id, by_name)
        else:
            finding = {"status": "manual", "issues": [MANUAL_REVIEW_NOTE]}

        finding["rule_id"] = rule_id
        finding["description"] = desc
        findings.append(finding)
        summary[finding["status"]] += 1

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "properties_count": len(properties),
        "summary": summary,
        "findings": findings,
        "raw": {"properties": properties},
    }


def _audit_property_config(rule, properties, by_id, by_name) -> dict:
    required_prop_ids = resolve_property_ids(rule["properties"], by_id, by_name)
    check = rule["check"]
    issues = []

    for pid in required_prop_ids:
        prop = by_id.get(pid, {})
        name = prop.get("name", pid)

        if check == "door_lock":
            if not _has_door_lock(prop):
                issues.append(f"Property '{name}' has no door lock integration configured")

        elif check == "security_deposit":
            deposit = (
                prop.get("security_deposit")
                or prop.get("security_deposit_amount")
                or prop.get("damage_deposit")
            )
            if not deposit or float(str(deposit).replace(",", "") or 0) <= 0:
                issues.append(f"Property '{name}' has no security deposit configured")

    if issues:
        return {"status": "fail", "issues": issues}
    if not required_prop_ids:
        return {"status": "manual", "issues": ["No matching properties found — check property names in config.py"]}
    return {"status": "pass", "issues": []}


def _has_door_lock(prop: dict) -> bool:
    lock_fields = (
        "door_lock", "lock_integration", "smartlock", "smart_lock",
        "lock_provider", "keyless_entry", "door_lock_provider",
    )
    for f in lock_fields:
        val = prop.get(f)
        if val and str(val).lower() not in ("none", "false", "0", ""):
            return True
    integrations = prop.get("integrations") or prop.get("connected_devices") or []
    if isinstance(integrations, list) and integrations:
        return True
    return False


def format_report(result: dict) -> str:
    lines = []
    s = result["summary"]

    lines.append("=" * 70)
    lines.append("  VRMV OwnerRez Audit Report")
    lines.append(f"  Generated: {result['timestamp']}")
    lines.append("=" * 70)
    lines.append(f"\n  Properties: {result['properties_count']}")
    lines.append(
        f"\n  Summary — PASS: {s['pass']}  FAIL: {s['fail']}  MANUAL REVIEW: {s['manual']}\n"
    )
    lines.append("-" * 70)

    for f in result["findings"]:
        icon = {"pass": "✓", "fail": "✗", "manual": "⚑"}.get(f["status"], "?")
        lines.append(f"\n[{icon}] {f['description']}")
        lines.append(f"    Rule    : {f['rule_id']}")
        lines.append(f"    Status  : {f['status'].upper()}")
        if f.get("dashboard_url"):
            lines.append(f"    Check at: {f['dashboard_url']}")
        for issue in f.get("issues", []):
            lines.append(f"    NOTE    : {issue}")

    lines.append("\n" + "=" * 70)
    fail_ids = [f["rule_id"] for f in result["findings"] if f["status"] == "fail"]
    manual_ids = [f["rule_id"] for f in result["findings"] if f["status"] == "manual"]
    if fail_ids:
        lines.append(f"  GAPS TO FIX ({len(fail_ids)}): {', '.join(fail_ids)}")
    if manual_ids:
        lines.append(f"  MANUAL REVIEW ({len(manual_ids)}): verify these in the OwnerRez dashboard")
        lines.append(f"  Dashboard: https://app.ownerrez.com/messaging/triggers")
    if not fail_ids and not manual_ids:
        lines.append("  All checks passed.")
    lines.append("=" * 70)

    return "\n".join(lines)
