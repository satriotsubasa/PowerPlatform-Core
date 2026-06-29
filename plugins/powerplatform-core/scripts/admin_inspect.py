#!/usr/bin/env python3
"""Read-only Power Platform administration inspection via the pac admin CLI.

Lists environments, tenant settings, DLP policies, and environment groups headlessly using
the active `pac auth` profile. These operations are READ-ONLY: they make no changes and need
no admin preflight. They DO require the active pac profile to hold the Power Platform
Administrator (or Global Administrator) role - distinct from the maker/developer Dataverse
auth used elsewhere in this plugin. Writes/deletes are intentionally not exposed here; perform
them via the specific pac admin command only after the admin preflight and explicit approval.
"""

from __future__ import annotations

import argparse
import json

from powerplatform_common import run_command

ADMIN_COMMANDS = {
    "environments": ["admin", "list"],
    "tenant-settings": ["admin", "list-tenant-settings"],
    "dlp-policies": ["admin", "dlp-policy", "list"],
    "groups": ["admin", "list-groups"],
}

AUTH_HINT = (
    "Read-only admin commands use the active pac auth profile, which must hold the Power "
    "Platform Administrator (or Global Administrator) role. Check it with `pac auth who` / "
    "`pac auth list`, or create an admin profile with `pac auth create` using an admin account."
)


def build_admin_command(mode: str) -> list[str]:
    if mode not in ADMIN_COMMANDS:
        raise SystemExit(f"ERROR: unknown mode '{mode}'. Use one of: {', '.join(sorted(ADMIN_COMMANDS))}.")
    return ["pac", *ADMIN_COMMANDS[mode]]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Power Platform admin inspection (environments, tenant settings, DLP policies, environment groups) via pac admin.",
    )
    parser.add_argument("--mode", required=True, choices=sorted(ADMIN_COMMANDS), help="What to inspect.")
    parser.add_argument("--timeout-seconds", type=float, default=120.0, help="Timeout for the pac admin command.")
    args = parser.parse_args()

    command = build_admin_command(args.mode)
    completed = run_command(command, check=False, timeout_seconds=args.timeout_seconds)

    payload = {
        "success": completed.returncode == 0,
        "mode": args.mode,
        "command": " ".join(command),
        "output": (completed.stdout or "").strip(),
    }
    if completed.returncode != 0:
        payload["error"] = (completed.stderr or completed.stdout or "").strip()
        payload["hint"] = AUTH_HINT

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
