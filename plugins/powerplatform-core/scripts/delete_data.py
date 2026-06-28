#!/usr/bin/env python3
"""Delete a Dataverse business row by primary key or alternate key.

This is a LIVE, irreversible mutation. The caller must run the orchestrator
live-mutation preflight and obtain explicit user approval before invoking it, the same
as any other write. Prefer the auth dialog (`--auth-dialog`) so the target environment
is confirmed before the delete executes.
"""

from __future__ import annotations

import argparse
import json

from powerplatform_common import (
    read_json_argument,
    resolve_live_connection,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete a single Dataverse row by primary key or alternate key (live mutation).",
    )
    parser.add_argument("--table", required=True, help="Dataverse table logical name.")
    parser.add_argument("--id", help="Primary-key GUID of the row to delete.")
    parser.add_argument("--key", help="JSON object or path with alternate-key values identifying the row to delete.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org/environment URL for the auth dialog.")
    parser.add_argument("--username", help="Username for interactive OAuth connection. Defaults from active PAC auth profile.")
    parser.add_argument("--tenant-id", help="Tenant ID for MSAL authentication. Defaults from active PAC auth profile when available.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before the delete (recommended).")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool. 'auto' tries silent first, then device code.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    args = parser.parse_args()

    if not args.id and not args.key:
        raise SystemExit("ERROR: delete requires --id or --key.")

    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )

    command = build_delete_command(args, connection)
    completed = run_dataverse_tool(command)
    print(completed.stdout.strip())
    return 0


def build_delete_command(args: argparse.Namespace, connection: dict) -> list[str]:
    if not args.id and not args.key:
        raise SystemExit("ERROR: delete requires --id or --key.")

    command = ["row", "--mode", "delete", "--table", args.table]
    if args.id:
        command.extend(["--id", args.id])
    if args.key:
        key = read_json_argument(args.key)
        if not isinstance(key, dict):
            raise SystemExit("ERROR: --key must resolve to a JSON object.")
        command.extend(["--key", json.dumps(key)])
    command.extend(
        [
            "--environment-url",
            connection["environment_url"],
            "--username",
            connection["username"],
            "--auth-flow",
            args.auth_flow,
        ]
    )
    tenant_id = connection["tenant_id"]
    if tenant_id:
        command.extend(["--tenant-id", tenant_id])
    if args.force_prompt:
        command.append("--force-prompt")
    if args.verbose:
        command.append("--verbose")
    return command


if __name__ == "__main__":
    raise SystemExit(main())
