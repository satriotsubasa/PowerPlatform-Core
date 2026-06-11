#!/usr/bin/env python3
"""Run a read-only Dataverse SDK WhoAmI smoke test."""

from __future__ import annotations

import argparse
import json

from powerplatform_common import resolve_live_connection, run_dataverse_tool


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a read-only Dataverse SDK WhoAmI smoke test through the shared helper.",
    )
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication. Defaults from active PAC auth profile.")
    parser.add_argument("--tenant-id", help="Tenant ID for MSAL authentication. Defaults from active PAC auth profile when available.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before the smoke test.")
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

    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )
    auth_payload = connection["auth_payload"]
    if auth_payload and auth_payload.get("whoAmI"):
        print(json.dumps(auth_payload["whoAmI"], indent=2))
        return 0

    command = [
        "whoami",
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
    if args.force_prompt:
        command.append("--force-prompt")
    if args.verbose:
        command.append("--verbose")

    completed = run_dataverse_tool(command)
    print(completed.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
