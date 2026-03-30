#!/usr/bin/env python3
"""Resolve a signed callback URL for an HTTP-trigger Power Automate flow."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from power_automate_common import parse_client_data
from powerplatform_common import (
    apply_selected_solution_to_spec,
    read_json_argument,
    repo_root,
    resolve_live_connection,
    run_command,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve a signed callback URL for an HTTP-trigger Power Automate flow.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the flow selector.")
    parser.add_argument("--repo-root", default=".", help="Repository root used as the working directory.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before resolving the trigger URL.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool when the auth dialog is not used.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print auth diagnostics to stderr.")
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

    flow_spec = apply_selected_solution_to_spec(dict(spec), connection)
    flow_payload = inspect_flow(flow_spec, repo=repo, connection=connection, auth_flow=args.auth_flow, force_prompt=args.force_prompt, verbose=args.verbose)
    organization_id = resolve_organization_id(connection, repo=repo, auth_flow=args.auth_flow, force_prompt=args.force_prompt, verbose=args.verbose)
    trigger_request = build_trigger_request(flow_payload, flow_spec, environment_url=connection["environment_url"], organization_id=organization_id)

    script_path = Path(__file__).resolve().with_name("get_flow_trigger_url.ps1")
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as handle:
        handle.write(json.dumps(trigger_request, indent=2))
        request_path = Path(handle.name)

    try:
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-SpecFile",
            str(request_path),
        ]
        if connection.get("username"):
            command.extend(["-Username", str(connection["username"])])
        if connection.get("tenant_id"):
            command.extend(["-TenantId", str(connection["tenant_id"])])

        completed = run_command(command, cwd=repo)
        print(completed.stdout.strip())
        return 0
    finally:
        request_path.unlink(missing_ok=True)


def inspect_flow(
    spec: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any],
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> dict[str, Any]:
    inspect_spec = {
        key: value
        for key, value in spec.items()
        if key
        in {
            "workflowId",
            "workflowUniqueId",
            "uniqueName",
            "name",
            "solutionUniqueName",
        }
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
            auth_flow,
        ]
        if connection.get("tenant_id"):
            command.extend(["--tenant-id", str(connection["tenant_id"])])
        if force_prompt:
            command.append("--force-prompt")
        if verbose:
            command.append("--verbose")

        completed = run_dataverse_tool(command, cwd=repo)
        payload = json.loads(completed.stdout)
        return payload["flow"]
    finally:
        spec_path.unlink(missing_ok=True)


def resolve_organization_id(
    connection: dict[str, Any],
    *,
    repo: Path,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> str:
    auth_payload = connection.get("auth_payload")
    if isinstance(auth_payload, dict):
        whoami = auth_payload.get("whoAmI") or auth_payload.get("WhoAmI")
        if isinstance(whoami, dict):
            organization_id = whoami.get("organizationId") or whoami.get("OrganizationId")
            if organization_id:
                return str(organization_id)

    command = [
        "whoami",
        "--environment-url",
        connection["environment_url"],
        "--username",
        connection["username"],
        "--auth-flow",
        auth_flow,
    ]
    if connection.get("tenant_id"):
        command.extend(["--tenant-id", str(connection["tenant_id"])])
    if force_prompt:
        command.append("--force-prompt")
    if verbose:
        command.append("--verbose")

    completed = run_dataverse_tool(command, cwd=repo)
    payload = json.loads(completed.stdout)
    organization_id = payload.get("organizationId")
    if not organization_id:
        raise RuntimeError("Could not resolve the Dataverse organization ID needed for Power Automate environment mapping.")
    return str(organization_id)


def build_trigger_request(
    flow_payload: dict[str, Any],
    spec: dict[str, Any],
    *,
    environment_url: str,
    organization_id: str,
) -> dict[str, Any]:
    workflow_id = str(flow_payload.get("workflowId") or "").strip()
    if not workflow_id:
        raise RuntimeError("Flow inspection did not return a workflowId.")

    explicit_trigger_name = str(spec.get("triggerName") or "").strip()
    trigger_name = explicit_trigger_name or infer_trigger_name(flow_payload)

    return {
        "environmentUrl": environment_url,
        "organizationId": organization_id,
        "workflowId": workflow_id,
        "workflowName": flow_payload.get("name"),
        "triggerName": trigger_name,
    }


def infer_trigger_name(flow_payload: dict[str, Any]) -> str:
    client_data_text = flow_payload.get("clientData")
    if not client_data_text:
        raise RuntimeError("Flow inspection did not return clientData, so triggerName could not be inferred.")

    client_data, _ = parse_client_data(client_data_text)
    triggers = client_data.get("properties", {}).get("definition", {}).get("triggers")
    if not isinstance(triggers, dict) or not triggers:
        raise RuntimeError("Flow clientData does not contain any triggers.")

    if len(triggers) == 1:
        return next(iter(triggers))

    http_like = [
        name
        for name, details in triggers.items()
        if isinstance(details, dict)
        and (
            str(details.get("type") or "").strip().lower() == "request"
            or str(details.get("kind") or "").strip().lower() == "http"
        )
    ]
    if len(http_like) == 1:
        return http_like[0]

    trigger_names = ", ".join(sorted(triggers.keys()))
    raise RuntimeError(
        "The flow exposes more than one trigger, so triggerName must be supplied explicitly. "
        f"Detected triggers: {trigger_names}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
