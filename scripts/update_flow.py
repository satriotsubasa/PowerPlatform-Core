#!/usr/bin/env python3
"""Update a solution-aware cloud flow through the shared Dataverse SDK helper."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from typing import Any
from pathlib import Path

from power_automate_common import compare_flow_semantics, parse_client_data, prepare_flow_spec, select_flow_guard
from powerplatform_common import (
    apply_selected_solution_to_spec,
    load_flow_guard_contract,
    read_json_argument,
    repo_root,
    resolve_live_connection,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update a solution-aware cloud flow through the shared Dataverse SDK helper.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the flow update.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve relative flow definition paths.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before updating the flow.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool when the auth dialog is not used.",
    )
    parser.add_argument(
        "--allow-semantic-drift",
        action="store_true",
        help="Allow semantic flow drift such as emptied switch cases or removed branch actions after showing the findings.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    spec = prepare_flow_spec(spec, repo)
    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )
    spec = apply_selected_solution_to_spec(spec, connection)
    flow_identity = build_flow_identity(spec, None)
    proposed_client_data = spec.get("clientData")
    semantic_guard = None
    baseline_client_data = None
    if isinstance(proposed_client_data, dict):
        live_flow = inspect_live_flow(spec, connection=connection, auth_flow=args.auth_flow, force_prompt=args.force_prompt, verbose=args.verbose, cwd=repo)
        flow_identity = build_flow_identity(spec, live_flow)
        live_client_data_value = live_flow.get("clientData")
        if live_client_data_value is None:
            raise RuntimeError("The inspected live flow did not return clientData, so semantic verification could not run.")
        baseline_client_data, _ = parse_client_data(live_client_data_value)
        semantic_guard = select_flow_guard(load_flow_guard_contract(repo).get("raw"), flow_identity)
        findings = compare_flow_semantics(
            baseline_client_data,
            proposed_client_data,
            flow_guard=semantic_guard,
            comparison_label="source-preflight",
        )
        if findings and not args.allow_semantic_drift:
            raise RuntimeError(build_semantic_guard_error(findings))

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as handle:
        handle.write(json.dumps(spec, indent=2))
        spec_path = Path(handle.name)

    try:
        command = [
            "flow",
            "--mode",
            "update",
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
        if isinstance(proposed_client_data, dict):
            post_deploy_flow = inspect_live_flow(
                spec,
                connection=connection,
                auth_flow=args.auth_flow,
                force_prompt=args.force_prompt,
                verbose=args.verbose,
                cwd=repo,
            )
            post_client_data_value = post_deploy_flow.get("clientData")
            if post_client_data_value is None:
                raise RuntimeError("The updated live flow did not return clientData, so post-deploy semantic verification could not run.")
            post_client_data, _ = parse_client_data(post_client_data_value)
            post_findings = compare_flow_semantics(
                proposed_client_data,
                post_client_data,
                flow_guard=semantic_guard,
                comparison_label="post-deploy",
            )
            if post_findings:
                raise RuntimeError(build_semantic_guard_error(post_findings))
        print(completed.stdout.strip())
        return 0
    finally:
        spec_path.unlink(missing_ok=True)


def inspect_live_flow(
    spec: dict[str, Any],
    *,
    connection: dict[str, Any],
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
    cwd: Path,
) -> dict[str, Any]:
    inspect_spec = {
        key: spec[key]
        for key in ("workflowId", "workflowUniqueId", "uniqueName", "name", "solutionUniqueName")
        if spec.get(key)
    }
    if not inspect_spec:
        raise RuntimeError(
            "Flow semantic verification requires an identifying value such as workflowId, uniqueName, or name in the update spec."
        )
    inspect_spec["includeClientData"] = True

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as handle:
        handle.write(json.dumps(inspect_spec, indent=2))
        inspect_spec_path = Path(handle.name)

    try:
        command = [
            "flow",
            "--mode",
            "inspect",
            "--spec-file",
            str(inspect_spec_path),
            "--environment-url",
            connection["environment_url"],
            "--username",
            connection["username"],
            "--auth-flow",
            auth_flow,
        ]
        if connection["tenant_id"]:
            command.extend(["--tenant-id", connection["tenant_id"]])
        if force_prompt:
            command.append("--force-prompt")
        if verbose:
            command.append("--verbose")
        completed = run_dataverse_tool(command, cwd=cwd)
    finally:
        inspect_spec_path.unlink(missing_ok=True)

    payload = json.loads(completed.stdout)
    flow_payload = payload.get("flow") if isinstance(payload, dict) else None
    if not isinstance(flow_payload, dict):
        raise RuntimeError("Flow inspect did not return a usable flow payload for semantic verification.")
    return flow_payload


def build_flow_identity(spec: dict[str, Any], live_flow: dict[str, Any] | None) -> dict[str, Any]:
    identity: dict[str, Any] = {}
    for key in ("workflowId", "workflowUniqueId", "uniqueName", "name", "solutionUniqueName", "definitionPath"):
        if spec.get(key):
            identity[key] = spec[key]

    if isinstance(live_flow, dict):
        for source_key, target_key in (
            ("workflowId", "workflowId"),
            ("workflowUniqueId", "workflowUniqueId"),
            ("uniqueName", "uniqueName"),
            ("name", "name"),
            ("displayName", "displayName"),
        ):
            if live_flow.get(source_key):
                identity[target_key] = live_flow[source_key]
    return identity


def build_semantic_guard_error(findings: list[dict[str, Any]]) -> str:
    ordered = sorted(
        findings,
        key=lambda item: (
            severity_rank(str(item.get("severity") or "")),
            str(item.get("code") or ""),
            str(item.get("message") or ""),
        ),
    )
    lines = [
        "Flow semantic verification blocked the update:"
    ]
    for finding in ordered:
        label = str(finding.get("comparisonLabel") or "semantic-check")
        lines.append(f"- [{label}] {finding.get('message')}")
    lines.append("Pass --allow-semantic-drift only if this branch or action loss is intentional.")
    return "\n".join(lines)


def severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity.lower(), 3)


if __name__ == "__main__":
    raise SystemExit(main())
