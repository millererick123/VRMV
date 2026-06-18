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
  properties            List all properties
  bookings              Show recent bookings (last 30 days)
  guests                List guests
  fees                  List fees
  reviews               List reviews
  inquiries             List recent inquiries
  show property <id>    Full detail of a property (ID or name)
  show booking <id>     Full detail of a booking
  show guest <id>       Full detail of a guest
  audit                 Run property config audit
  log                   Show the change log
  help                  Show this help menu
  exit / quit           Exit

Note: Triggers and templates must be managed directly in the OwnerRez
      dashboard — https://app.ownerrez.com/messaging/triggers
"""


def _col(value, width):
    s = str(value) if value is not None else ""
    if len(s) > width:
        s = s[: width - 1] + "…"
    return s.ljust(width)


def _hr(char="-", width=78):
    return char * width


def _table(rows, headers, widths):
    header_row = "  ".join(_col(h, widths[i]) for i, h in enumerate(headers))
    lines = [_hr(), header_row, _hr("=", 78)]
    for row in rows:
        lines.append("  ".join(_col(row[i] if i < len(row) else "", widths[i]) for i in range(len(headers))))
    lines.append(_hr())
    return "\n".join(lines)


def _safe(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return ""
        d = d.get(k)
    return str(d) if d is not None else ""


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
            for line in textwrap.wrap(v, width=72):
                print(f"    {line}")
        elif isinstance(v, (dict, list)):
            print(f"  {k}: {json.dumps(v, default=str)}")
        else:
            print(f"  {k}: {v}")
    print(f"  {_hr()}")


def cmd_properties(client):
    try:
        props = client.get_properties()
    except Exception as e:
        print(f"  Error: {e}")
        return
    if not props:
        print("  No properties found.")
        return
    rows = [
        [
            _safe(p, "id"),
            _safe(p, "name") or _safe(p, "short_name"),
            _safe(p, "city") or _safe(p, "address", "city"),
            _safe(p, "bedrooms") or _safe(p, "bedroom_count"),
            _safe(p, "bathrooms") or _safe(p, "bathroom_count"),
            _safe(p, "active"),
        ]
        for p in props
    ]
    print(f"\n  {len(props)} properties\n")
    print(_table(rows, ["ID", "Name", "City", "Beds", "Baths", "Active"], [8, 28, 18, 6, 7, 8]))


def cmd_bookings(client):
    from datetime import date, timedelta
    today = date.today().isoformat()
    ago = (date.today() - timedelta(days=30)).isoformat()
    try:
        bookings = client.get_bookings(params={"since": ago, "until": today, "limit": 50})
    except Exception:
        try:
            bookings = client.get_bookings(params={"limit": 25})
        except Exception as e:
            print(f"  Error: {e}")
            return
    if not bookings:
        print("  No bookings found.")
        return
    rows = [
        [
            _safe(b, "id"),
            _safe(b, "property_name") or _safe(b, "property_id"),
            _safe(b, "guest_name") or _safe(b, "first_name"),
            _safe(b, "arrival") or _safe(b, "check_in"),
            _safe(b, "departure") or _safe(b, "check_out"),
            _safe(b, "status"),
            _safe(b, "total_amount") or _safe(b, "amount"),
        ]
        for b in bookings
    ]
    print(f"\n  {len(bookings)} bookings\n")
    print(_table(rows, ["ID", "Property", "Guest", "Arrival", "Departure", "Status", "Total"],
                 [10, 16, 18, 12, 12, 10, 10]))


def cmd_guests(client):
    try:
        guests = client.get_guests(params={"limit": 50})
    except Exception as e:
        print(f"  Error: {e}")
        return
    if not guests:
        print("  No guests found.")
        return
    rows = [
        [
            _safe(g, "id"),
            f"{_safe(g, 'first_name')} {_safe(g, 'last_name')}".strip() or _safe(g, "name"),
            _safe(g, "email"),
            _safe(g, "phone"),
        ]
        for g in guests
    ]
    print(f"\n  {len(guests)} guests\n")
    print(_table(rows, ["ID", "Name", "Email", "Phone"], [10, 24, 28, 16]))


def cmd_fees(client):
    try:
        fees = client.get_fees()
    except Exception as e:
        print(f"  Error: {e}")
        return
    if not fees:
        print("  No fees found.")
        return
    rows = [
        [
            _safe(f, "id"),
            _safe(f, "name"),
            _safe(f, "type") or _safe(f, "fee_type"),
            _safe(f, "amount") or _safe(f, "value"),
            _safe(f, "active"),
        ]
        for f in fees
    ]
    print(f"\n  {len(fees)} fees\n")
    print(_table(rows, ["ID", "Name", "Type", "Amount", "Active"], [8, 28, 18, 12, 8]))


def cmd_reviews(client):
    try:
        reviews = client.get_reviews(params={"limit": 25})
    except Exception as e:
        print(f"  Error: {e}")
        return
    if not reviews:
        print("  No reviews found.")
        return
    rows = [
        [
            _safe(r, "id"),
            _safe(r, "property_name") or _safe(r, "property_id"),
            _safe(r, "guest_name"),
            _safe(r, "rating"),
            (_safe(r, "created_at") or _safe(r, "date") or "")[:10],
        ]
        for r in reviews
    ]
    print(f"\n  {len(reviews)} reviews\n")
    print(_table(rows, ["ID", "Property", "Guest", "Rating", "Date"], [10, 24, 22, 8, 12]))


def cmd_inquiries(client):
    try:
        inquiries = client.get_inquiries(params={"limit": 25})
    except Exception as e:
        print(f"  Error: {e}")
        return
    if not inquiries:
        print("  No inquiries found.")
        return
    rows = [
        [
            _safe(i, "id"),
            _safe(i, "property_name") or _safe(i, "property_id"),
            _safe(i, "guest_name") or _safe(i, "name"),
            _safe(i, "arrival") or _safe(i, "check_in"),
            _safe(i, "departure") or _safe(i, "check_out"),
            _safe(i, "status"),
        ]
        for i in inquiries
    ]
    print(f"\n  {len(inquiries)} inquiries\n")
    print(_table(rows, ["ID", "Property", "Guest", "Arrival", "Departure", "Status"],
                 [10, 20, 20, 12, 12, 10]))


def cmd_show_property(client, prop_ref):
    try:
        props = client.get_properties()
    except Exception as e:
        print(f"  Error: {e}")
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
    try:
        detail = client.get_property(target["id"])
    except Exception:
        detail = target
    _print_detail(f"Property — {target.get('name', prop_ref)}", detail)


def cmd_show_booking(client, booking_id):
    try:
        b = client.get_booking(booking_id)
    except Exception as e:
        print(f"  Error: {e}")
        return
    _print_detail(f"Booking {booking_id}", b)


def cmd_show_guest(client, guest_id):
    try:
        g = client.get_guest(guest_id)
    except Exception as e:
        print(f"  Error: {e}")
        return
    _print_detail(f"Guest {guest_id}", g)


def cmd_audit(client):
    print("\n  Running audit...")
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
        print("\n  Change log is empty — no changes made yet.")
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
        elif cmd == "properties":
            cmd_properties(client)
        elif cmd == "bookings":
            cmd_bookings(client)
        elif cmd == "guests":
            cmd_guests(client)
        elif cmd == "fees":
            cmd_fees(client)
        elif cmd == "reviews":
            cmd_reviews(client)
        elif cmd == "inquiries":
            cmd_inquiries(client)
        elif cmd.startswith("show property "):
            cmd_show_property(client, raw[14:].strip())
        elif cmd.startswith("show booking "):
            cmd_show_booking(client, raw[13:].strip())
        elif cmd.startswith("show guest "):
            cmd_show_guest(client, raw[11:].strip())
        elif cmd == "audit":
            cmd_audit(client)
        elif cmd == "log":
            cmd_log()
        else:
            print("  Command not recognized. Type 'help' for available commands.")
