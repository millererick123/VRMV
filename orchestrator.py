#!/usr/bin/env python3
"""
VRMV Orchestrator — "Platt"

The main operator agent. Talks to the human (Erick), decides which
sub-agent to consult, collects their suggestions, and runs everything
through the same approval gate before anything actually changes.

Usage:
  python orchestrator.py                 — interactive menu
  python orchestrator.py --optimize       — run OwnerRez optimizer only
  python orchestrator.py --marketing      — run marketing draft generator only
  python orchestrator.py --all            — run both, one after another

Nothing here executes a write without an explicit y/n from the human.
See approvals.py for the gate all sub-agents share.
"""

import sys

from ownerrez_client import OwnerRezClient
from audit import audit, format_report
from approvals import review_loop, summarize
from agents import optimizer, marketing


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║                  VRMV Orchestrator — Platt                   ║
║   Main operator agent for OwnerRez optimization + marketing  ║
╚══════════════════════════════════════════════════════════════╝
"""

MENU = """
What should I look at?
  1) Audit OwnerRez and suggest optimizations
  2) Draft marketing posts for active properties
  3) Do both
  4) Show recent audit report only (no suggestions, no changes)
  q) Quit
"""


def connect():
    try:
        client = OwnerRezClient()
    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Create a .env file based on .env.example and add your credentials.")
        sys.exit(1)

    print("\nConnecting to OwnerRez...")
    try:
        client.test_connection()
        print("  Connected.")
    except Exception as e:
        print(f"  Connection FAILED: {e}")
        sys.exit(1)

    return client


def run_optimizer(client, audit_result=None):
    print("\n" + "=" * 70)
    print("  OwnerRez Optimizer")
    print("=" * 70)

    if audit_result is None:
        print("\nRunning audit...")
        audit_result = audit(client)

    print()
    print(format_report(audit_result))

    suggestions = optimizer.generate_suggestions(client, audit_result)

    if not suggestions:
        print("\n  No fixable gaps found — OwnerRez config looks clean.")
        return audit_result, []

    print(f"\n  The optimizer found {len(suggestions)} item(s) to review.")
    reviewed = review_loop(suggestions, auto_log_fn=optimizer.log_result)
    summarize(reviewed)
    return audit_result, reviewed


def run_marketing(client, properties=None, channel="instagram"):
    print("\n" + "=" * 70)
    print("  Marketing Agent")
    print("=" * 70)

    suggestions = marketing.generate_suggestions(client, properties=properties, channel=channel)

    if not suggestions:
        print("\n  No active properties found to draft content for.")
        return []

    print(f"\n  Drafted {len(suggestions)} post(s) for review.")
    reviewed = review_loop(suggestions, auto_log_fn=marketing.log_result)
    summarize(reviewed)
    return reviewed


def interactive(client):
    print(BANNER)
    last_audit = None

    while True:
        print(MENU)
        choice = input("Choice: ").strip().lower()

        if choice in ("q", "quit", "exit"):
            print("Goodbye.")
            break
        elif choice == "1":
            last_audit, _ = run_optimizer(client, audit_result=last_audit)
        elif choice == "2":
            props = last_audit["raw"]["properties"] if last_audit else None
            run_marketing(client, properties=props)
        elif choice == "3":
            last_audit, _ = run_optimizer(client, audit_result=last_audit)
            run_marketing(client, properties=last_audit["raw"]["properties"])
        elif choice == "4":
            last_audit = audit(client)
            print()
            print(format_report(last_audit))
        else:
            print("  Not a valid choice — pick from the menu.")


def main():
    args = set(sys.argv[1:])
    client = connect()

    if "--optimize" in args:
        run_optimizer(client)
    elif "--marketing" in args:
        run_marketing(client)
    elif "--all" in args:
        audit_result, _ = run_optimizer(client)
        run_marketing(client, properties=audit_result["raw"]["properties"])
    else:
        interactive(client)


if __name__ == "__main__":
    main()
