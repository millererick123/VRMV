import json
import os
from datetime import datetime, timezone

LOG_FILE = os.path.join(os.path.dirname(__file__), "change_log.json")


def _load():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(entries):
    with open(LOG_FILE, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def record(operation: str, resource_type: str, resource_id, summary: str,
           before: dict = None, after: dict = None):
    entries = _load()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "operation": operation.upper(),
        "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id is not None else None,
        "summary": summary,
        "before": before or {},
        "after": after or {},
    }
    entries.append(entry)
    _save(entries)
    return entry


def load_all():
    return _load()


def format_entry(entry: dict) -> str:
    lines = [
        f"  [{entry['operation']}] {entry['resource_type']} id={entry['resource_id']}",
        f"  Time    : {entry['timestamp']}",
        f"  Summary : {entry['summary']}",
    ]
    if entry.get("before"):
        lines.append(f"  Before  : {json.dumps(entry['before'], default=str)}")
    if entry.get("after"):
        lines.append(f"  After   : {json.dumps(entry['after'], default=str)}")
    return "\n".join(lines)
