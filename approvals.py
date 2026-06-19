"""
Shared approval gate.

Every sub-agent that wants to WRITE something (update OwnerRez, post to
social media, send a message) must go through here. Nothing executes
without an explicit 'y' from the human at the keyboard. This is the one
chokepoint — keep it boring and easy to audit.
"""

import textwrap


class Suggestion:
    """
    A single proposed action. Sub-agents produce a list of these.
    Nothing in here has happened yet — it's a plan, not an action.
    """

    def __init__(self, agent, title, detail, action_fn, risk="low"):
        self.agent = agent              # which sub-agent proposed this, e.g. "optimizer"
        self.title = title              # one-line summary
        self.detail = detail            # longer explanation, shown on request
        self.action_fn = action_fn      # callable, takes no args, performs the write, returns a result dict
        self.risk = risk                # "low" | "medium" | "high" — purely informational for the human
        self.status = "pending"         # pending | approved | rejected | executed | failed

    def __repr__(self):
        return f"<Suggestion [{self.agent}] {self.title} ({self.status})>"


def print_suggestions(suggestions):
    if not suggestions:
        print("\n  No suggestions right now — nothing to optimize.")
        return
    print(f"\n  {len(suggestions)} suggestion(s):\n")
    for i, s in enumerate(suggestions, 1):
        risk_tag = {"low": "LOW", "medium": "MED", "high": "HIGH"}.get(s.risk, "?")
        print(f"  [{i}] ({risk_tag} risk, {s.agent}) {s.title}")
    print()


def print_detail(s: Suggestion, index=None):
    label = f"[{index}] " if index is not None else ""
    print(f"\n  {'-' * 70}")
    print(f"  {label}{s.title}")
    print(f"  Source agent : {s.agent}")
    print(f"  Risk level   : {s.risk}")
    print(f"  {'-' * 70}")
    for line in textwrap.wrap(s.detail, width=68):
        print(f"  {line}")
    print(f"  {'-' * 70}")


def review_loop(suggestions, auto_log_fn=None):
    """
    Walks the human through each pending suggestion one at a time.
    auto_log_fn(suggestion, result) is called after every executed action,
    so the orchestrator can write to change_log.py.
    Returns the list of suggestions with updated .status.
    """
    if not suggestions:
        print("\n  Nothing to review.")
        return suggestions

    print_suggestions(suggestions)

    for i, s in enumerate(suggestions, 1):
        if s.status != "pending":
            continue
        print_detail(s, index=i)
        while True:
            choice = input(
                "  Approve this action? [y]es / [n]o / [s]kip-all-remaining / [d]etails again: "
            ).strip().lower()
            if choice in ("y", "yes"):
                try:
                    result = s.action_fn()
                    s.status = "executed"
                    print(f"  ✓ Done: {s.title}")
                    if auto_log_fn:
                        auto_log_fn(s, result)
                except Exception as e:
                    s.status = "failed"
                    print(f"  ✗ Failed: {e}")
                break
            elif choice in ("n", "no"):
                s.status = "rejected"
                print("  Skipped.")
                break
            elif choice in ("s", "skip"):
                print("  Skipping all remaining suggestions — nothing else will be changed.")
                return suggestions
            elif choice in ("d", "details"):
                print_detail(s, index=i)
                continue
            else:
                print("  Please answer y, n, s, or d.")

    return suggestions


def summarize(suggestions):
    counts = {}
    for s in suggestions:
        counts[s.status] = counts.get(s.status, 0) + 1
    parts = [f"{v} {k}" for k, v in counts.items()]
    print(f"\n  Summary: {', '.join(parts)}" if parts else "\n  Summary: nothing processed")
