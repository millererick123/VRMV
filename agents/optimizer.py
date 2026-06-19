"""
Optimizer sub-agent.

Wraps the existing audit.py logic and turns each "fail" finding into a
Suggestion the orchestrator can present for approval. If approved, it
performs the actual OwnerRez write via the client and logs it.

This agent NEVER writes to OwnerRez on its own — it only proposes.
The orchestrator (via approvals.review_loop) is what triggers execution,
and only after a human says yes.
"""

from approvals import Suggestion
import change_log


def _make_security_deposit_action(client, property_id, property_name, amount):
    def action():
        before = client.get_property(property_id)
        result = client.update_property(property_id, {"security_deposit_amount": amount})
        return {
            "property_id": property_id,
            "property_name": property_name,
            "before": {"security_deposit": before.get("security_deposit_amount")
                       or before.get("security_deposit")},
            "after": {"security_deposit_amount": amount},
        }
    return action


def generate_suggestions(client, audit_result, default_deposit_amount=500):
    """
    Look at audit findings with status == 'fail' and turn the ones we know
    how to fix automatically into Suggestion objects. Findings we can't
    safely auto-fix (e.g. door lock integration — that's a physical/account
    setup, not a field we can PATCH) are reported as informational only.
    """
    suggestions = []

    for finding in audit_result["findings"]:
        if finding["status"] != "fail":
            continue

        rule_id = finding["rule_id"]

        if rule_id == "security_deposit":
            for issue in finding["issues"]:
                # issue text looks like: "Property 'X' has no security deposit configured"
                prop_name = issue.split("'")[1] if "'" in issue else "unknown"
                prop = _find_property_by_name(audit_result["raw"]["properties"], prop_name)
                if not prop:
                    continue
                pid = prop.get("id")
                suggestions.append(
                    Suggestion(
                        agent="optimizer",
                        title=f"Set security deposit for '{prop_name}' to ${default_deposit_amount}",
                        detail=(
                            f"OwnerRez shows no security deposit configured for '{prop_name}'. "
                            f"VRMV policy requires a deposit on all non-CMH properties. "
                            f"This will set it to ${default_deposit_amount} via the OwnerRez API. "
                            f"Confirm this is the right amount for this property before approving — "
                            f"some properties may warrant a higher deposit."
                        ),
                        action_fn=_make_security_deposit_action(
                            client, pid, prop_name, default_deposit_amount
                        ),
                        risk="medium",
                    )
                )

        elif rule_id == "door_lock_integration":
            for issue in finding["issues"]:
                prop_name = issue.split("'")[1] if "'" in issue else "unknown"
                suggestions.append(
                    Suggestion(
                        agent="optimizer",
                        title=f"Manual setup needed: door lock for '{prop_name}'",
                        detail=(
                            f"'{prop_name}' has no door lock integration in OwnerRez. "
                            f"This isn't something the API can configure — it requires physically "
                            f"pairing a smart lock (e.g. Schlage) and connecting it in the OwnerRez "
                            f"dashboard under Property > Devices. Flagging for your manual action."
                        ),
                        action_fn=lambda: {"note": "manual action — no API call made"},
                        risk="low",
                    )
                )

        else:
            # Generic fallback: surface it, but mark as informational-only
            for issue in finding["issues"]:
                suggestions.append(
                    Suggestion(
                        agent="optimizer",
                        title=f"Review needed: {finding['description']}",
                        detail=issue,
                        action_fn=lambda: {"note": "informational — no automated fix available"},
                        risk="low",
                    )
                )

    return suggestions


def _find_property_by_name(properties, name):
    name_lower = name.strip().lower()
    for p in properties:
        pname = (p.get("name") or p.get("short_name") or "").lower()
        if pname == name_lower:
            return p
    return None


def log_result(suggestion, result):
    """Hook passed to approvals.review_loop — writes executed actions to change_log.py."""
    if "property_id" in result:
        change_log.record(
            operation="update",
            resource_type="property",
            resource_id=result["property_id"],
            summary=suggestion.title,
            before=result.get("before"),
            after=result.get("after"),
        )
