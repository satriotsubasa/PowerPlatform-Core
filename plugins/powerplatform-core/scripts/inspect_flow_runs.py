#!/usr/bin/env python3
"""List recent run history for a solution-aware cloud flow (read-only).

Reads the Dataverse `flowrun` table for the target flow through the shared SDK helper,
using the same token the tool already caches. Run history in Dataverse is conditional:
it only covers SOLUTION-AWARE flows, the capture feature must be enabled in the
environment (`Organization.FlowRunTimeToLiveInSeconds > 0`), it is retained for a limited
window (28 days by default), and it is a best-effort mirror - the Power Automate portal
remains the complete, transactional source. The tool reports whether capture looks
enabled so an empty list is not mistaken for "no runs".

Read-only: no live-mutation preflight required.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from powerplatform_common import repo_root, resolve_live_connection, run_dataverse_tool


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List recent run history (status/start/end/error) for a solution-aware cloud flow. Read-only.",
    )
    parser.add_argument("--workflow-id", help="Workflow GUID of the flow.")
    parser.add_argument("--workflow-unique-id", help="workflowidunique GUID of the flow.")
    parser.add_argument("--unique-name", help="Flow unique (schema) name.")
    parser.add_argument("--name", help="Flow display name.")
    parser.add_argument("--solution-unique-name", help="Restrict the flow lookup to a solution.")
    parser.add_argument("--max-runs", type=int, default=20, help="Maximum runs to return, most recent first (default 20, capped at 200).")
    parser.add_argument("--status", help="Filter to a single run status (e.g. Failed, Succeeded, Running, Cancelled).")
    parser.add_argument("--repo-root", default=".", help="Repository root used for relative path resolution.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org/environment URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication. Defaults from active PAC auth profile.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before reading (optional for reads).")
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

    if not (args.workflow_id or args.workflow_unique_id or args.unique_name or args.name):
        print("ERROR: identify the flow with --workflow-id, --workflow-unique-id, --unique-name, or --name.", file=sys.stderr)
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

    spec = build_runs_spec(args, connection)

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as handle:
        handle.write(json.dumps(spec, indent=2))
        spec_path = Path(handle.name)

    try:
        command = [
            "flow",
            "--mode",
            "runs",
            "--spec-file",
            str(spec_path),
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
    finally:
        spec_path.unlink(missing_ok=True)


def build_runs_spec(args: argparse.Namespace, connection: dict) -> dict:
    spec = {
        "workflowId": args.workflow_id,
        "workflowUniqueId": args.workflow_unique_id,
        "uniqueName": args.unique_name,
        "name": args.name,
        "solutionUniqueName": args.solution_unique_name or connection.get("solution_unique_name"),
        "maxRuns": args.max_runs,
        "status": args.status,
    }
    return {key: value for key, value in spec.items() if value is not None}


if __name__ == "__main__":
    raise SystemExit(main())
