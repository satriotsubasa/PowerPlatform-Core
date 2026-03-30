#!/usr/bin/env python3
"""Review connector-specific patterns inside a solution-aware cloud flow."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from power_automate_common import parse_client_data, prepare_flow_spec
from powerplatform_common import apply_selected_solution_to_spec, read_json_argument, repo_root, resolve_live_connection, run_dataverse_tool, write_json_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review connector-specific patterns inside a solution-aware cloud flow.",
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
            print("ERROR: Could not retrieve live flow payload for connector review.", file=sys.stderr)
            return 1
        client_data_value = flow_payload.get("clientData")
        source = "live"

    client_data, raw_client_data = parse_client_data(client_data_value)
    review = review_connectors(client_data)
    payload = {
        "success": True,
        "mode": "review-flow-connectors",
        "source": source,
        "clientDataBytes": len(raw_client_data.encode("utf-8")),
        **review,
    }
    if inspect_payload:
        payload["flow"] = inspect_payload.get("flow")
    write_json_output(payload, args.output)
    return 0


def review_connectors(client_data: dict[str, Any]) -> dict[str, Any]:
    definition = ((client_data.get("properties") or {}).get("definition") or {})
    actions = definition.get("actions") if isinstance(definition, dict) else {}
    if not isinstance(actions, dict):
        actions = {}

    connectors: dict[str, list[dict[str, Any]]] = {}
    findings: list[dict[str, Any]] = []

    for action_name, node in actions.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        host = inputs.get("host") if isinstance(inputs, dict) else None
        api_id = str(host.get("apiId") or "").lower() if isinstance(host, dict) else ""
        operation_id = str(host.get("operationId") or "").lower() if isinstance(host, dict) else ""
        parameters = inputs.get("parameters") if isinstance(inputs, dict) and isinstance(inputs.get("parameters"), dict) else {}
        connector_name = classify_connector(api_id)
        if connector_name == "other":
            continue
        connectors.setdefault(connector_name, []).append(
            {
                "actionName": action_name,
                "operationId": operation_id,
                "apiId": api_id,
            }
        )
        if connector_name == "dataverse":
            findings.extend(review_dataverse_action(action_name, operation_id, parameters))
        elif connector_name == "sharepoint":
            findings.extend(review_sharepoint_action(action_name, operation_id, parameters))
        elif connector_name == "outlook":
            findings.extend(review_outlook_action(action_name, operation_id, parameters))

    return {
        "connectors": connectors,
        "findingCount": len(findings),
        "riskLevel": compute_risk_level(findings),
        "findings": findings,
        "recommendations": build_recommendations(findings),
    }


def classify_connector(api_id: str) -> str:
    if "commondataserviceforapps" in api_id or "shared_dataverse" in api_id:
        return "dataverse"
    if "sharepointonline" in api_id:
        return "sharepoint"
    if "office365" in api_id or "outlook" in api_id:
        return "outlook"
    return "other"


def review_dataverse_action(action_name: str, operation_id: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    if any(token in operation_id for token in ("listrows", "listrecords")):
        if not any(key in parameters for key in ("$select", "selectColumns", "fetchXml")):
            findings.append(make_finding("medium", "dataverse-list-no-select", f"{action_name} lists Dataverse rows without explicit column selection."))
        if not any(key in parameters for key in ("$filter", "filterRows", "fetchXml")):
            findings.append(make_finding("medium", "dataverse-list-no-filter", f"{action_name} lists Dataverse rows without an explicit filter or FetchXML query."))
        if not any(key in parameters for key in ("$top", "topCount", "fetchXml")):
            findings.append(make_finding("low", "dataverse-list-no-top", f"{action_name} lists Dataverse rows without an explicit row limit."))
    if any(token in operation_id for token in ("createrecord", "updaterow", "updaterecord")):
        if not parameters:
            findings.append(make_finding("low", "dataverse-write-no-parameters", f"{action_name} is a Dataverse write action with no obvious parameters payload."))
    return findings


def review_sharepoint_action(action_name: str, operation_id: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    if any(token in operation_id for token in ("getitems", "getfiles", "listfolder")):
        if "filterQuery" not in parameters and "$filter" not in parameters:
            findings.append(make_finding("medium", "sharepoint-list-no-filter", f"{action_name} reads SharePoint items without an explicit filter query."))
        if "topCount" not in parameters and "$top" not in parameters:
            findings.append(make_finding("low", "sharepoint-list-no-top", f"{action_name} reads SharePoint items without an explicit row limit."))
    return findings


def review_outlook_action(action_name: str, operation_id: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    if "send" in operation_id and "mail" in operation_id:
        if not any(key in parameters for key in ("to", "To")):
            findings.append(make_finding("medium", "outlook-send-no-recipient", f"{action_name} looks like an Outlook send action without a clear recipient parameter."))
        if not any(key in parameters for key in ("subject", "Subject")):
            findings.append(make_finding("low", "outlook-send-no-subject", f"{action_name} looks like an Outlook send action without an explicit subject."))
    return findings


def make_finding(severity: str, code: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "code": code, "message": message}


def build_recommendations(findings: list[dict[str, Any]]) -> list[str]:
    recommendations = []
    codes = {finding["code"] for finding in findings}
    if any(code.startswith("dataverse-list-") for code in codes):
        recommendations.append("For Dataverse list actions, prefer explicit select columns, filters, and row limits.")
    if any(code.startswith("sharepoint-list-") for code in codes):
        recommendations.append("For SharePoint list actions, prefer explicit filters and top limits to avoid broad reads.")
    if any(code.startswith("outlook-send-") for code in codes):
        recommendations.append("For Outlook send actions, keep recipients and subjects explicit and review environment-specific recipients.")
    return recommendations


def compute_risk_level(findings: list[dict[str, Any]]) -> str:
    severities = {str(finding.get("severity")) for finding in findings}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if "low" in severities:
        return "low"
    return "minimal"


if __name__ == "__main__":
    raise SystemExit(main())
