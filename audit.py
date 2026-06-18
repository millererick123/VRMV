"""
Phase 1 — Audit engine.
Pulls live data from OwnerRez and compares against the gap checklist in config.py.
"""

import json
import re
from datetime import datetime
from ownerrez_client import OwnerRezClient
from config import (
    GAP_CHECKLIST,
    DOOR_CODE_PROPERTIES,
    SECURITY_DEPOSIT_EXEMPT,
    AIRBNB_CHANNELS,
)

# OwnerRez trigger event/type field names vary by API version.
# These mappings normalize the raw API values to our checklist vocabulary.
EVENT_MAP = {
    # booking lifecycle
    "booking_created": ["bookingcreated", "booking_created", "created", "new_booking"],
    # arrival-relative
    "arrival_based": [
        "checkin", "check_in", "arrival", "beforearrival", "before_arrival",
        "afterarrival", "after_arrival", "arrivalday",
    ],
    # departure-relative
    "departure_based": [
        "checkout", "check_out", "departure", "afterdeparture", "after_departure",
        "departureday", "beforedeparture",
    ],
}


def normalize_event(raw: str) -> str:
    raw_lower = raw.lower().replace(" ", "").replace("-", "").replace("_", "")
    for canonical, aliases in EVENT_MAP.items():
        for alias in aliases:
            if alias.replace("_", "") in raw_lower or raw_lower in alias.replace("_", ""):
                return canonical
    return raw_lower


def keywords_in_text(keywords: list, text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def get_trigger_offset_days(trigger: dict) -> float | None:
    """Extract day offset from trigger timing fields (varies by API shape)."""
    for field in ("offset_days", "days_offset", "days", "trigger_days", "timing_days"):
        val = trigger.get(field)
        if val is not None:
            return float(val)
    # Some APIs embed timing in a nested object
    timing = trigger.get("timing") or trigger.get("send_timing") or {}
    if isinstance(timing, dict):
        for field in ("days", "offset_days", "days_offset"):
            val = timing.get(field)
            if val is not None:
                return float(val)
    return None


def get_trigger_offset_hours(trigger: dict) -> float | None:
    for field in ("offset_hours", "hours_offset", "hours", "timing_hours"):
        val = trigger.get(field)
        if val is not None:
            return float(val)
    timing = trigger.get("timing") or trigger.get("send_timing") or {}
    if isinstance(timing, dict):
        for field in ("hours", "offset_hours"):
            val = timing.get(field)
            if val is not None:
                return float(val)
    return None


def get_trigger_medium(trigger: dict) -> str:
    for field in ("medium", "channel", "delivery_method", "type", "send_via"):
        val = trigger.get(field)
        if val:
            return str(val).lower()
    return "unknown"


def get_trigger_property_ids(trigger: dict) -> list:
    """Return list of property IDs the trigger applies to, or [] for all."""
    for field in ("property_ids", "properties", "property_id"):
        val = trigger.get(field)
        if val:
            if isinstance(val, list):
                return [str(v) for v in val]
            return [str(val)]
    return []  # empty means "all properties"


def get_trigger_channels(trigger: dict) -> list:
    for field in ("channel_ids", "channels", "booking_sources", "source_ids"):
        val = trigger.get(field)
        if val:
            if isinstance(val, list):
                return [str(v).lower() for v in val]
            return [str(val).lower()]
    return []  # empty means all channels


def get_trigger_template_body(trigger: dict, templates: list) -> str:
    template_id = trigger.get("template_id") or trigger.get("message_template_id")
    if not template_id:
        # inline body
        return trigger.get("body", trigger.get("message", trigger.get("content", "")))
    for t in templates:
        if str(t.get("id")) == str(template_id):
            return t.get("body", t.get("content", t.get("subject", ""))) or ""
    return ""


def build_property_map(properties: list) -> dict:
    """Return {prop_id: prop_dict} and also a {short_name: prop_id} map."""
    by_id = {}
    by_name = {}
    for p in properties:
        pid = str(p.get("id", ""))
        name = (p.get("name") or p.get("short_name") or "").upper()
        by_id[pid] = p
        if name:
            by_name[name] = pid
    return by_id, by_name


def resolve_property_ids(rule_properties, by_id: dict, by_name: dict) -> set:
    """
    Convert a rule's 'properties' value to a set of property IDs.
    rule_properties can be "all", "non_exempt", or a list of short names.
    """
    if rule_properties == "all":
        return set(by_id.keys())
    if rule_properties == "non_exempt":
        exempt_ids = set()
        for name in SECURITY_DEPOSIT_EXEMPT:
            pid = by_name.get(name.upper())
            if pid:
                exempt_ids.add(pid)
        return set(by_id.keys()) - exempt_ids
    # list of short names
    ids = set()
    for name in rule_properties:
        pid = by_name.get(name.upper())
        if pid:
            ids.add(pid)
        else:
            # fallback: find by partial name match
            for pname, ppid in by_name.items():
                if name.upper() in pname:
                    ids.add(ppid)
    return ids


def audit(client: OwnerRezClient) -> dict:
    print("Fetching data from OwnerRez API...")
    properties = client.get_properties()
    triggers = client.get_triggers()
    templates = client.get_templates()
    print(f"  Found {len(properties)} properties, {len(triggers)} triggers, {len(templates)} templates")

    by_id, by_name = build_property_map(properties)

    findings = []
    summary = {"pass": 0, "fail": 0, "warn": 0}

    for rule in GAP_CHECKLIST:
        rule_id = rule["id"]
        desc = rule["description"]

        if rule["type"] == "property_config":
            finding = _audit_property_config(rule, properties, by_id, by_name)
        else:
            finding = _audit_trigger_rule(rule, triggers, templates, properties, by_id, by_name)

        finding["rule_id"] = rule_id
        finding["description"] = desc
        findings.append(finding)
        summary[finding["status"]] += 1

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "properties_count": len(properties),
        "triggers_count": len(triggers),
        "templates_count": len(templates),
        "summary": summary,
        "findings": findings,
        "raw": {
            "properties": properties,
            "triggers": triggers,
            "templates": templates,
        },
    }


def _audit_trigger_rule(rule, triggers, templates, properties, by_id, by_name) -> dict:
    required_event = rule["event"]
    required_medium = rule["medium"]
    required_prop_ids = resolve_property_ids(rule["properties"], by_id, by_name)
    keywords = rule.get("keywords", [])
    timing_days = rule.get("timing_offset_days")
    timing_hours = rule.get("timing_offset_hours")

    matched_triggers = []
    issues = []

    for t in triggers:
        raw_event = t.get("event", t.get("trigger_type", t.get("type", "")))
        if not raw_event:
            continue
        if normalize_event(str(raw_event)) != required_event:
            continue

        # Medium check
        medium = get_trigger_medium(t)
        if required_medium not in medium and medium not in required_medium:
            continue

        # Timing check (lenient ±12h for hours, ±1 day for days)
        if timing_days is not None:
            offset = get_trigger_offset_days(t)
            if offset is not None and abs(offset - timing_days) > 1:
                continue
        if timing_hours is not None:
            offset_h = get_trigger_offset_hours(t)
            if offset_h is not None and abs(offset_h - timing_hours) > 12:
                continue

        matched_triggers.append(t)

    if not matched_triggers:
        return {
            "status": "fail",
            "issues": [f"No {required_medium} trigger found for event '{required_event}'"],
            "matched_triggers": [],
        }

    # For each matched trigger, check property and channel coverage
    covered_props = set()
    uncovered_props = set(required_prop_ids)

    for t in matched_triggers:
        trigger_props = get_trigger_property_ids(t)
        trigger_channels = get_trigger_channels(t)

        # Channel filter for door code rule
        if rule.get("channel") == "not_airbnb":
            # Trigger must explicitly exclude Airbnb channels
            # If no channel filter is set (all channels), it may also fire for Airbnb — flag it
            excludes_airbnb = _trigger_excludes_airbnb(t)
            if not excludes_airbnb:
                issues.append(
                    f"Trigger '{t.get('name', t.get('id', '?'))}' does not exclude Airbnb channels"
                )

        # Determine which required properties this trigger covers
        if not trigger_props:
            # applies to all properties
            covered_props.update(required_prop_ids)
        else:
            covered_props.update(p for p in trigger_props if p in required_prop_ids)

        # Keywords check
        if keywords:
            body = get_trigger_template_body(t, templates)
            if body and not keywords_in_text(keywords, body):
                issues.append(
                    f"Trigger '{t.get('name', t.get('id', '?'))}' template doesn't contain expected keywords: {keywords}"
                )

        # Payment status check
        if rule.get("ignore_payment_status"):
            payment_filter = t.get("require_payment") or t.get("payment_status") or t.get("payment_required")
            if payment_filter and str(payment_filter).lower() not in ("false", "0", "none", "any", "all"):
                issues.append(
                    f"Trigger '{t.get('name', t.get('id', '?'))}' is gated on payment status — should fire regardless"
                )

    uncovered_props = required_prop_ids - covered_props
    if uncovered_props:
        uncovered_names = [
            by_id.get(pid, {}).get("name", pid) for pid in uncovered_props
        ]
        issues.append(f"Not covered for properties: {', '.join(uncovered_names)}")

    if issues:
        return {"status": "fail", "issues": issues, "matched_triggers": [t.get("id") for t in matched_triggers]}

    return {"status": "pass", "issues": [], "matched_triggers": [t.get("id") for t in matched_triggers]}


def _trigger_excludes_airbnb(trigger: dict) -> bool:
    """
    Return True if the trigger is configured to exclude Airbnb channels.
    OwnerRez may use exclude lists, negative channel filters, or the trigger may only
    apply to specific non-Airbnb channels.
    """
    exclude_fields = ("exclude_channels", "excluded_channels", "excluded_sources")
    for f in exclude_fields:
        val = trigger.get(f)
        if val:
            vals = [str(v).lower() for v in (val if isinstance(val, list) else [val])]
            if any(ab in v for ab in AIRBNB_CHANNELS for v in vals):
                return True

    # If trigger applies only to specific channels and none are Airbnb, it implicitly excludes
    channels = get_trigger_channels(trigger)
    if channels and not any(ab in ch for ab in AIRBNB_CHANNELS for ch in channels):
        return True

    return False


def _audit_property_config(rule, properties, by_id, by_name) -> dict:
    required_prop_ids = resolve_property_ids(rule["properties"], by_id, by_name)
    check = rule["check"]
    issues = []

    for pid in required_prop_ids:
        prop = by_id.get(pid, {})
        name = prop.get("name", pid)

        if check == "door_lock":
            has_lock = _has_door_lock(prop)
            if not has_lock:
                issues.append(f"Property '{name}' has no door lock integration configured")

        elif check == "security_deposit":
            deposit = (
                prop.get("security_deposit")
                or prop.get("security_deposit_amount")
                or prop.get("damage_deposit")
            )
            if not deposit or float(deposit) <= 0:
                issues.append(f"Property '{name}' has no security deposit configured")

    if issues:
        return {"status": "fail", "issues": issues}
    if not required_prop_ids:
        return {"status": "warn", "issues": ["No matching properties found to check"]}
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
    # Check nested integrations list
    integrations = prop.get("integrations") or prop.get("connected_devices") or []
    if isinstance(integrations, list) and integrations:
        return True
    return False


def format_report(result: dict) -> str:
    lines = []
    ts = result["timestamp"]
    s = result["summary"]

    lines.append("=" * 70)
    lines.append("  VRMV OwnerRez Audit Report")
    lines.append(f"  Generated: {ts}")
    lines.append("=" * 70)
    lines.append(
        f"\n  Properties: {result['properties_count']}  |  "
        f"Triggers: {result['triggers_count']}  |  "
        f"Templates: {result['templates_count']}"
    )
    lines.append(
        f"\n  Summary — PASS: {s['pass']}  FAIL: {s['fail']}  WARN: {s['warn']}\n"
    )
    lines.append("-" * 70)

    for f in result["findings"]:
        status_icon = {"pass": "✓", "fail": "✗", "warn": "!"}.get(f["status"], "?")
        lines.append(f"\n[{status_icon}] {f['description']}")
        lines.append(f"    Rule ID : {f['rule_id']}")
        lines.append(f"    Status  : {f['status'].upper()}")
        if f.get("matched_triggers"):
            lines.append(f"    Matched : trigger IDs {f['matched_triggers']}")
        if f.get("issues"):
            for issue in f["issues"]:
                lines.append(f"    ISSUE   : {issue}")

    lines.append("\n" + "=" * 70)
    fail_ids = [f["rule_id"] for f in result["findings"] if f["status"] == "fail"]
    if fail_ids:
        lines.append(f"  GAPS TO FIX ({len(fail_ids)}): {', '.join(fail_ids)}")
    else:
        lines.append("  All checks passed — no gaps found.")
    lines.append("=" * 70)

    return "\n".join(lines)
