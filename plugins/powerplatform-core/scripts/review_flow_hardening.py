#!/usr/bin/env python3
"""Review a solution-aware cloud flow for reliability and hardening gaps."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from power_automate_common import parse_client_data, prepare_flow_spec, review_flow_hardening
from powerplatform_common import apply_selected_solution_to_spec, read_json_argument, repo_root, resolve_live_connection, run_dataverse_tool, write_json_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review a solution-aware cloud flow for retry, concurrency, pagination, idempotency, and error-handling gaps.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the flow or clientData source.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve relative flow definition paths.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL when reviewing a live flow.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before reviewing a live flow.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool when the auth dialog is not used.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    prepared = prepare_flow_spec(spec, repo)
    source = "spec"
    inspect_payload: dict[str, Any] | None = None
    client_data_value = prepared.get("clientData")

    if client_data_value is None:
        connection = resolve_live_connection(
            environment_url=args.environment_url,
            username=args.username,
            tenant_id=args.tenant_id,
            auth_dialog=args.auth_dialog,
            target_url=args.target_url,
            auto_validate=args.auto_validate,
        )
        prepared = apply_selected_solution_to_spec(prepared, connection)
        inspect_spec = {
            key: prepared[key]
            for key in ("workflowId", "workflowUniqueId", "uniqueName", "name", "solutionUniqueName")
            if prepared.get(key)
        }
        inspect_spec["includeClientData"] = True

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as handle:
            handle.write(json.dumps(inspect_spec, indent=2))
            spec_path = Path(handle.name)

        try:
            command = [
                "flow",
                "--mode",
                "inspect",
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
            inspect_payload = json.loads(completed.stdout)
        finally:
            spec_path.unlink(missing_ok=True)

        flow_payload = inspect_payload.get("flow") if isinstance(inspect_payload, dict) else None
        if not isinstance(flow_payload, dict):
            print("ERROR: Could not retrieve live flow payload for review.", file=sys.stderr)
            return 1
        client_data_value = flow_payload.get("clientData")
        source = "live"

    client_data, raw_client_data = parse_client_data(client_data_value)
    review = review_flow_hardening(client_data)
    payload = {
        "success": True,
        "mode": "review-flow-hardening",
        "source": source,
        "clientDataBytes": len(raw_client_data.encode("utf-8")),
        **review,
    }
    if inspect_payload:
        payload["flow"] = inspect_payload.get("flow")
    write_json_output(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
