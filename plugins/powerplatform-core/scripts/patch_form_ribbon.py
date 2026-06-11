#!/usr/bin/env python3
"""Patch RibbonDiffXml for a targeted Dataverse form through the shared SDK helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from powerplatform_common import read_json_argument, repo_root, resolve_live_connection, run_dataverse_tool


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch Dataverse form RibbonDiffXml through the shared SDK metadata helper.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the form ribbon patch.")
    parser.add_argument("--repo-root", default=".", help="Repository root used for relative path resolution when needed.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before the ribbon patch.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool when the auth dialog is not used.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )
    command = [
        "metadata",
        "patch-form-ribbon",
        "--spec",
        json.dumps(spec),
        "--environment-url",
        connection["environment_url"],
        "--username",
        connection["username"],
        "--auth-flow",
        args.auth_flow,
    ]
    if connection["tenant_id"]:
        command.extend(["--tenant-id", connection["tenant_id"]])
    if args.force_prompt:
        command.append("--force-prompt")
    if args.verbose:
        command.append("--verbose")

    completed = run_dataverse_tool(command, cwd=repo)
    print(completed.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
