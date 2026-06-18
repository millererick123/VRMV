#!/usr/bin/env python3
"""
VRMV OwnerRez Automation Agent
Usage:
  python main.py                — run Phase 1 audit and print report
  python main.py --interactive  — launch the interactive agent
  python main.py --json         — save audit results to audit_report_<timestamp>.json
  python main.py --test         — test API connectivity, then exit
"""

import sys
import json
from datetime import datetime

from ownerrez_client import OwnerRezClient
from audit import audit, format_report


def main():
    args = set(sys.argv[1:])
    save_json = "--json" in args
    test_only = "--test" in args
    interactive = "--interactive" in args

    print("\nVRMV OwnerRez Automation Agent")
    print("=" * 40)

    try:
        client = OwnerRezClient()
    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Create a .env file based on .env.example and add your credentials.")
        sys.exit(1)

    print("\nTesting API connection...")
    try:
        data = client.test_connection()
        count = (
            data.get("total_count", data.get("total", "?"))
            if isinstance(data, dict)
            else len(data) if isinstance(data, list)
            else "?"
        )
        print(f"  Connected successfully. ({count} properties visible)")
    except Exception as e:
        print(f"  Connection FAILED: {e}")
        sys.exit(1)

    if test_only:
        print("\nConnection test passed. Exiting (--test mode).")
        return

    if interactive:
        from agent import run_agent
        run_agent(client)
        return

    print("\nRunning Phase 1 audit...")
    try:
        result = audit(client)
    except Exception as e:
        print(f"\nAudit failed: {e}")
        raise

    print()
    print(format_report(result))

    if save_json:
        output = {k: v for k, v in result.items() if k != "raw"}
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = f"audit_report_{ts}.json"
        with open(fname, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\nFull results saved to {fname}")

    fail_count = result["summary"]["fail"]
    if fail_count:
        print(f"\nPhase 2 (auto-fix) is not yet active. Run with --fix to apply corrections.")
    else:
        print("\nNo gaps found — nothing to fix.")


if __name__ == "__main__":
    main()
