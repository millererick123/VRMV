import sys
import json
import textwrap

import change_log
from ownerrez_client import OwnerRezClient
from audit import audit, format_report

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          VRMV OwnerRez Interactive Agent                     ║
║  Type 'help' for available commands. 'exit' to quit.         ║
╚══════════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
Available commands:
  properties          List all properties
  triggers            List all triggers
  templates           List all message templates
  bookings            Show recent bookings
  show trigger <id>   Show full detail of a trigger
  show template <id>  Show full detail of a template (including body)
  show property <id>  Show full detail of a property
  audit               Run Phase 1 audit and show report
  log                 Show the change log
  help                Show this help menu
  exit / quit         Exit the agent
"""


def _col(value, width):
    s = str(value) if value is not None else ""
    if len(s) > width:
        s = s[: width - 1] + "…"
    return s.ljust(width)


def _hr(char="-", width=78):
    return char * width


def _table(rows, headers, widths):
    sep = _hr()
    header_row = "  ".join(_col(h, widths[i]) for i, h in enumerate(headers))
    lines = [sep, header_row, _hr("=", 78)]
    for row in rows:
        lines.append("  ".join(_col(row[i] if i < len(row) else "", widths[i]) for i in range(len(headers))))
    lines.append(sep)
    return "\n".join(lines)


def _safe_get(d, *keys, default=""):
    for k in keys:
        if d is None:
            return default
        d = d.get(k)
    return d if d is not None else default


def cmd_properties(client):
    try:
        props = client.get_properties()
    except Exception as e:
        print(f"  Error fetching properties: {e}")
        return
    if not props:
        print("  No properties found.")
        return
    rows = []
    for p in props:
        rows.append([
            _safe_get(p, "id"),
            _safe_get(p, "name") or _safe_get(p, "short_name"),
            _safe_get(p, "city") or _safe_get(p, "address", "city"),
            _safe_get(p, "bedrooms") or _safe_get(p, "bedroom_count"),
            _safe_get(p, "bathrooms") or _safe_get(p, "bathroom_count"),
            _safe_get(p, "active") if "active" in p else "",
        ])
    print(f"\n  {len(props)} properties\n")
    print(_table(rows, ["ID", "Name", "City", "Beds", "Baths", "Active"], [8, 28, 18, 6, 7, 8]))


def cmd_triggers(client):
    try:
        triggers = client.get_triggers()
    except Exception as e:
        print(f"  Error fetching triggers: {e}")
        return
    if not triggers:
        print("  No triggers found.")
        return
    rows = []
    for t in triggers:
        event = _safe_get(t, "event") or _safe_get(t, "trigger_type") or _safe_get(t, "type")
        medium = _safe_get(t, "medium") or _safe_get(t, "channel") or _safe_get(t, "delivery_method")
        timing = ""
        for f in ("offset_days", "days_offset", "offset_hours", "hours_offset"):
            v = t.get(f)
            if v is not None:
                unit = "d" if "day" in f else "h"
                timing = f"{v}{unit}"
                break
        rows.append([
            _safe_get(t, "id"),
            _safe_get(t, "name"),
            event,
            medium,
            timing,
        ])
    print(f"\n  {len(triggers)} triggers\n")
    print(_table(rows, ["ID", "Name", "Event", "Medium", "Timing"], [8, 32, 22, 10, 8]))


def cmd_templates(client):
    try:
        templates = client.get_templates()
    except Exception as e:
        print(f"  Error fetching templates: {e}")
        return
    if not templates:
        print("  No templates found.")
        return
    rows = []
    for t in templates:
        rows.append([
            _safe_get(t, "id"),
            _safe_get(t, "name"),
            _safe_get(t, "subject"),
        ])
    print(f"\n  {len(templates)} templates\n")
    print(_table(rows, ["ID", "Name", "Subject"], [8, 30, 38]))


def cmd_bookings(client):
    try:
        bookings = client.get_bookings(params={"limit": 25})
    except Exception as e:
        print(f"  Error fetching bookings: {e}")
        return
    if not bookings:
        print("  No bookings found.")
        return
    rows = []
    for b in bookings:
        rows.append([
            _safe_get(b, "id"),
            _safe_get(b, "property_name") or _safe_get(b, "property_id"),
            _safe_get(b, "guest_name") or _safe_get(b, "first_name"),
            _safe_get(b, "arrival") or _safe_get(b, "check_in"),
            _safe_get(b, "departure") or _safe_get(b, "check_out"),
            _safe_get(b, "status"),
        ])
    count = len(bookings)
    print(f"\n  {count} recent bookings (showing up to 25)\n")
    print(_table(rows, ["ID", "Property", "Guest", "Arrival", "Departure", "Status"],
                 [10, 18, 20, 12, 12, 10]))


def _print_detail(label, data):
    print(f"\n  {_hr()}")
    print(f"  {label}")
    print(f"  {_hr()}")
    if not data:
        print("  (empty)")
        return
    for k, v in data.items():
        if isinstance(v, str) and len(v) > 120:
            print(f"  {k}:")
            for line in textwrap.wrap(v, width=74):
                print(f"    {line}")
        elif isinstance(v, (dict, list)):
            print(f"  {k}: {json.dumps(v, default=str)}")
        else:
            print(f"  {k}: {v}")
    print(f"  {_hr()}")


def cmd_show_trigger(client, trigger_id):
    try:
        t = client.get_trigger(trigger_id)
    except Exception as e:
        print(f"  Error fetching trigger {trigger_id}: {e}")
        return
    _print_detail(f"Trigger {trigger_id}", t)


def cmd_show_template(client, template_id):
    try:
        t = client.get_template(template_id)
    except Exception as e:
        print(f"  Error fetching template {template_id}: {e}")
        return
    body = t.pop("body", t.pop("content", None))
    _print_detail(f"Template {template_id}", t)
    if body:
        print(f"\n  --- Body ---")
        for line in (body or "").splitlines():
            print(f"  {line}")
        print(f"  {_hr()}")


def cmd_show_property(client, prop_ref):
    try:
        props = client.get_properties()
    except Exception as e:
        print(f"  Error fetching properties: {e}")
        return

    target = None
    ref_lower = prop_ref.strip().lower()
    for p in props:
        if str(p.get("id")) == ref_lower:
            target = p
            break
        name = (p.get("name") or p.get("short_name") or "").lower()
        if ref_lower in name or name.startswith(ref_lower):
            target = p
            break

    if not target:
        print(f"  No property found matching '{prop_ref}'.")
        return

    prop_id = target.get("id")
    try:
        detail = client.get_property(prop_id)
    except Exception:
        detail = target

    _print_detail(f"Property {prop_ref}", detail)


def cmd_audit(client):
    print("\n  Running Phase 1 audit...")
    try:
        result = audit(client)
    except Exception as e:
        print(f"  Audit error: {e}")
        return
    print()
    print(format_report(result))


def cmd_log():
    entries = change_log.load_all()
    if not entries:
        print("\n  Change log is empty.")
        return
    print(f"\n  {len(entries)} change log entries\n")
    print(_hr())
    for entry in entries:
        print(change_log.format_entry(entry))
        print(_hr())


def run_agent(client):
    print(BANNER)
    print(HELP_TEXT)

    while True:
        try:
            raw = input("ownerrez> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            break

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("exit", "quit"):
            print("  Goodbye.")
            break

        elif cmd == "help":
            print(HELP_TEXT)

        elif cmd in ("properties", "list properties"):
            cmd_properties(client)

        elif cmd == "triggers":
            cmd_triggers(client)

        elif cmd == "templates":
            cmd_templates(client)

        elif cmd == "bookings":
            cmd_bookings(client)

        elif cmd.startswith("show trigger "):
            trigger_id = raw[len("show trigger "):].strip()
            if trigger_id:
                cmd_show_trigger(client, trigger_id)
            else:
                print("  Usage: show trigger <id>")

        elif cmd.startswith("show template "):
            template_id = raw[len("show template "):].strip()
            if template_id:
                cmd_show_template(client, template_id)
            else:
                print("  Usage: show template <id>")

        elif cmd.startswith("show property "):
            prop_ref = raw[len("show property "):].strip()
            if prop_ref:
                cmd_show_property(client, prop_ref)
            else:
                print("  Usage: show property <id or name>")

        elif cmd == "audit":
            cmd_audit(client)

        elif cmd == "log":
            cmd_log()

        else:
            print("  Command not recognized. Type 'help' for available commands.")
