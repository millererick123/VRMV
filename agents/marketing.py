"""
Marketing sub-agent.

Generates draft Instagram/Facebook captions based on real property data
pulled from OwnerRez (availability, bed/bath count, location). It does
NOT post anything — there's no Meta API connection wired up yet. Every
draft is written to drafts/marketing/ as a text file for human review,
and surfaced to the orchestrator as a Suggestion whose "approval" just
means "save this draft to disk" (not "post it live").

When Meta Graph API credentials exist (see README — Phase 2), the
action_fn here can be swapped to actually call the posting endpoint.
That should be a deliberate, separate decision — not bundled into this
file silently.
"""

import os
from datetime import date
from approvals import Suggestion

DRAFTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "drafts", "marketing")

CHANNELS = {
    "instagram": {"headline_limit": 50, "caption_limit": 2200},
    "facebook": {"headline_limit": 80, "caption_limit": 5000},
}


def _ensure_drafts_dir():
    os.makedirs(DRAFTS_DIR, exist_ok=True)


def _draft_caption(prop):
    name = prop.get("name") or prop.get("short_name") or "this property"
    city = prop.get("city") or (prop.get("address") or {}).get("city") or "Martha's Vineyard"
    beds = prop.get("bedrooms") or prop.get("bedroom_count") or "?"
    baths = prop.get("bathrooms") or prop.get("bathroom_count") or "?"

    caption = (
        f"Open dates at {name} in {city} — {beds} bed / {baths} bath, "
        f"steps from everything Martha's Vineyard does best this summer. "
        f"Link in bio to check availability.\n\n"
        f"#MarthaVineyard #VineyardRental #MVsummer"
    )
    return caption


def _make_save_draft_action(prop, caption, channel):
    def action():
        _ensure_drafts_dir()
        name = (prop.get("name") or prop.get("short_name") or "property").replace(" ", "_")
        ts = date.today().isoformat()
        fname = f"{ts}_{channel}_{name}.txt"
        path = os.path.join(DRAFTS_DIR, fname)
        with open(path, "w") as f:
            f.write(caption)
        return {"file": path, "channel": channel, "property": prop.get("name")}
    return action


def generate_suggestions(client, properties=None, channel="instagram", limit=5):
    """
    Build draft post suggestions for up to `limit` active properties.
    Pass in `properties` if you already fetched them (e.g. from an audit
    run) to avoid hitting the API twice.
    """
    if properties is None:
        properties = client.get_properties()

    active = [p for p in properties if p.get("active")]
    suggestions = []

    for prop in active[:limit]:
        caption = _draft_caption(prop)
        limits = CHANNELS.get(channel, CHANNELS["instagram"])
        name = prop.get("name") or prop.get("short_name") or "Property"

        suggestions.append(
            Suggestion(
                agent="marketing",
                title=f"Draft {channel} post for '{name}'",
                detail=(
                    f"Proposed caption ({len(caption)} chars, limit {limits['caption_limit']}):\n\n"
                    f"{caption}\n\n"
                    f"This will save the draft to drafts/marketing/ for your review. "
                    f"It does NOT post live — there's no Meta API connection configured yet. "
                    f"Pull the actual current availability dates before this goes out for real."
                ),
                action_fn=_make_save_draft_action(prop, caption, channel),
                risk="low",
            )
        )

    return suggestions


def log_result(suggestion, result):
    """No change_log entry needed for local draft files — they're not live changes.
    Kept as a no-op hook so the orchestrator's logging interface stays uniform."""
    pass
