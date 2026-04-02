#!/usr/bin/env python3
"""Create, update, or upsert Dataverse rows with the shared SDK tool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from powerplatform_common import (
    coerce_dataverse_row_data,
    load_deployment_defaults,
    read_json_argument,
    repo_root,
    resolve_live_connection,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create, update, or upsert Dataverse business data through the shared Dataverse SDK helper.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve project-profile deployment defaults.")
    parser.add_argument("--mode", choices=["create", "update", "upsert"], default="upsert")
    parser.add_argument("--table", required=True, help="Dataverse table logical name.")
    parser.add_argument("--data", required=True, help="JSON object or path to a JSON file with the columns to write.")
    parser.add_argument("--id", help="Primary key GUID for update or upsert.")
    parser.add_argument("--key", help="JSON object or path to a JSON file with alternate key values.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for interactive OAuth connection. Defaults from active PAC auth profile.")
    parser.add_argument("--tenant-id", help="Tenant ID for MSAL authentication. Defaults from active PAC auth profile when available.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before the write.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool. 'auto' tries silent first, then device code.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    parser.add_argument("--verify", action="store_true", help="Retrieve the changed columns after the write.")
    args = parser.parse_args()

    data = read_json_argument(args.data)
    if not isinstance(data, dict):
        print("ERROR: --data must resolve to a JSON object.", file=sys.stderr)
        return 2
    repo = repo_root(Path(args.repo_root))
    deployment_defaults = load_deployment_defaults(repo)
    data = coerce_dataverse_row_data(args.table, data, deployment_defaults)

    key_text = None
    if args.key:
        key = read_json_argument(args.key)
        if not isinstance(key, dict):
            print("ERROR: --key must resolve to a JSON object.", file=sys.stderr)
            return 2
        key_text = json.dumps(key)

    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )

    command = [
        "row",
        "--mode",
        args.mode,
        "--table",
        args.table,
        "--data",
        json.dumps(data),
        "--environment-url",
        connection["environment_url"],
        "--username",
        connection["username"],
        "--auth-flow",
        args.auth_flow,
    ]
    tenant_id = connection["tenant_id"]
    if tenant_id:
        command.extend(["--tenant-id", tenant_id])
    if args.id:
        command.extend(["--id", args.id])
    if key_text:
        command.extend(["--key", key_text])
    if args.verify:
        command.append("--verify")
    if args.force_prompt:
        command.append("--force-prompt")
    if args.verbose:
        command.append("--verbose")

    completed = run_dataverse_tool(command)
    print(completed.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
