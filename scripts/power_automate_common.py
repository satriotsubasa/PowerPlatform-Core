#!/usr/bin/env python3
"""Shared helpers for solution-aware Power Automate flow scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
ENVIRONMENT_URL_RE = re.compile(r"https://[A-Za-z0-9.-]+(?:\.crm\d*\.dynamics\.com|\.crm\.dynamics\.com)\S*")
IGNORED_GUID_PATH_PARTS = {
    "operationMetadataId",
    "connectionReferences",
    "apiId",
    "connectionName",
    "workflowid",
    "x-ms-workflow-name",
}
RETRY_RECOMMENDED_ACTION_TYPES = {"openapiconnection", "http", "httpwebhook", "apiconnection"}
LIST_OPERATION_PATTERNS = ("list", "getitems", "listrows", "listrecords", "query")
SIDE_EFFECT_OPERATION_PATTERNS = ("create", "add", "update", "upsert", "delete", "send", "post")


def prepare_flow_spec(spec: dict[str, Any], repo: Path) -> dict[str, Any]:
    final = json.loads(json.dumps(spec))

    if "clientDataPath" in final:
        final["clientData"] = load_json_path(final.pop("clientDataPath"), repo)

    if "definitionPath" in final:
        final["definition"] = load_json_path(final.pop("definitionPath"), repo)

    if "connectionReferencesPath" in final:
        final["connectionReferences"] = load_json_path(final.pop("connectionReferencesPath"), repo)

    if "clientData" not in final and any(key in final for key in ("definition", "connectionReferences", "schemaVersion")):
        definition = final.pop("definition", None)
        if definition is None:
            raise RuntimeError("Flow specs that use definition or connectionReferences must provide a definition.")
        connection_references = final.pop("connectionReferences", {}) or {}
        schema_version = final.pop("schemaVersion", "1.0.0.0")
        final["clientData"] = {
            "properties": {
                "connectionReferences": connection_references,
                "definition": definition,
            },
            "schemaVersion": schema_version,
        }

    return final


def compare_flow_semantics(
    baseline_client_data: dict[str, Any] | None,
    proposed_client_data: dict[str, Any],
    *,
    flow_guard: dict[str, Any] | None,
    comparison_label: str,
) -> list[dict[str, Any]]:
    proposed_summary = summarize_flow_structure(proposed_client_data)
    findings: list[dict[str, Any]] = []

    if baseline_client_data is not None:
        baseline_summary = summarize_flow_structure(baseline_client_data)
        missing_triggers = sorted(set(baseline_summary["triggerNames"]) - set(proposed_summary["triggerNames"]))
        if missing_triggers:
            findings.append(
                {
                    "severity": "high",
                    "code": "trigger-missing",
                    "message": f"The updated flow would remove triggers: {', '.join(missing_triggers)}.",
                    "missingTriggerNames": missing_triggers,
                    "comparisonLabel": comparison_label,
                }
            )

        missing_top_level_actions = sorted(set(baseline_summary["actionNames"]) - set(proposed_summary["actionNames"]))
        if missing_top_level_actions:
            findings.append(
                {
                    "severity": "medium",
                    "code": "top-level-actions-missing",
                    "message": f"The updated flow would remove top-level actions: {', '.join(missing_top_level_actions)}.",
                    "missingActionNames": missing_top_level_actions,
                    "comparisonLabel": comparison_label,
                }
            )

        for case_key, baseline_case in baseline_summary["switchCases"].items():
            proposed_case = proposed_summary["switchCases"].get(case_key)
            if not proposed_case:
                findings.append(
                    {
                        "severity": "high",
                        "code": "switch-case-missing",
                        "message": (
                            f"Switch '{baseline_case['switchName']}' case '{baseline_case['caseName']}' is missing "
                            "from the updated flow."
                        ),
                        "switchName": baseline_case["switchName"],
                        "caseName": baseline_case["caseName"],
                        "comparisonLabel": comparison_label,
                    }
                )
                continue

            if baseline_case["actionCount"] > 0 and proposed_case["actionCount"] == 0:
                findings.append(
                    {
                        "severity": "high",
                        "code": "switch-case-became-empty",
                        "message": (
                            f"Switch '{baseline_case['switchName']}' case '{baseline_case['caseName']}' would become empty."
                        ),
                        "switchName": baseline_case["switchName"],
                        "caseName": baseline_case["caseName"],
                        "comparisonLabel": comparison_label,
                    }
                )

            missing_case_actions = sorted(set(baseline_case["actionNames"]) - set(proposed_case["actionNames"]))
            if missing_case_actions:
                findings.append(
                    {
                        "severity": "medium",
                        "code": "switch-case-actions-missing",
                        "message": (
                            f"Switch '{baseline_case['switchName']}' case '{baseline_case['caseName']}' would lose "
                            f"actions: {', '.join(missing_case_actions)}."
                        ),
                        "switchName": baseline_case["switchName"],
                        "caseName": baseline_case["caseName"],
                        "missingActionNames": missing_case_actions,
                        "comparisonLabel": comparison_label,
                    }
                )

    findings.extend(validate_flow_guard_requirements(proposed_summary, flow_guard, comparison_label=comparison_label))
    return deduplicate_findings(findings)


def summarize_flow_structure(client_data: dict[str, Any]) -> dict[str, Any]:
    properties = client_data.get("properties")
    definition = properties.get("definition") if isinstance(properties, dict) else None
    triggers = definition.get("triggers") if isinstance(definition, dict) else {}
    actions = definition.get("actions") if isinstance(definition, dict) else {}

    switch_cases: dict[str, dict[str, Any]] = {}
    if isinstance(actions, dict):
        collect_switch_case_summaries(actions, switch_cases)

    return {
        "triggerNames": sorted(triggers.keys()) if isinstance(triggers, dict) else [],
        "actionNames": sorted(actions.keys()) if isinstance(actions, dict) else [],
        "switchCases": switch_cases,
    }


def collect_switch_case_summaries(actions: dict[str, Any], switch_cases: dict[str, dict[str, Any]]) -> None:
    for action_name, node in actions.items():
        if not isinstance(node, dict):
            continue

        action_type = str(node.get("type") or "").strip().lower()
        if action_type == "switch":
            cases = node.get("cases")
            if isinstance(cases, dict):
                for case_name, case_node in cases.items():
                    if not isinstance(case_node, dict):
                        continue
                    case_actions = case_node.get("actions")
                    summarized = summarize_branch_actions(case_actions if isinstance(case_actions, dict) else {})
                    switch_cases[switch_case_key(action_name, case_name)] = {
                        "switchName": action_name,
                        "caseName": str(case_name),
                        "actionCount": len(summarized),
                        "actionNames": summarized,
                    }
                    if isinstance(case_actions, dict):
                        collect_switch_case_summaries(case_actions, switch_cases)

            default_branch = node.get("default")
            if isinstance(default_branch, dict):
                default_actions = default_branch.get("actions")
                if isinstance(default_actions, dict):
                    collect_switch_case_summaries(default_actions, switch_cases)

        nested_actions = node.get("actions")
        if isinstance(nested_actions, dict):
            collect_switch_case_summaries(nested_actions, switch_cases)

        for branch_key in ("else",):
            nested_branch = node.get(branch_key)
            if isinstance(nested_branch, dict):
                nested_branch_actions = nested_branch.get("actions")
                if isinstance(nested_branch_actions, dict):
                    collect_switch_case_summaries(nested_branch_actions, switch_cases)


def summarize_branch_actions(actions: dict[str, Any]) -> list[str]:
    collected: set[str] = set()
    collect_action_names(actions, collected)
    return sorted(collected)


def collect_action_names(actions: dict[str, Any], collected: set[str]) -> None:
    for action_name, node in actions.items():
        collected.add(str(action_name))
        if not isinstance(node, dict):
            continue

        nested_actions = node.get("actions")
        if isinstance(nested_actions, dict):
            collect_action_names(nested_actions, collected)

        if str(node.get("type") or "").strip().lower() == "switch":
            cases = node.get("cases")
            if isinstance(cases, dict):
                for case_node in cases.values():
                    if isinstance(case_node, dict) and isinstance(case_node.get("actions"), dict):
                        collect_action_names(case_node["actions"], collected)
            default_branch = node.get("default")
            if isinstance(default_branch, dict) and isinstance(default_branch.get("actions"), dict):
                collect_action_names(default_branch["actions"], collected)

        for branch_key in ("else",):
            nested_branch = node.get(branch_key)
            if isinstance(nested_branch, dict) and isinstance(nested_branch.get("actions"), dict):
                collect_action_names(nested_branch["actions"], collected)


def select_flow_guard(raw_contract: dict[str, Any] | None, flow_identity: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw_contract, dict):
        return None

    flows = raw_contract.get("flows")
    if not isinstance(flows, list):
        return None

    for entry in flows:
        if not isinstance(entry, dict):
            continue
        if flow_guard_matches(entry.get("match"), flow_identity):
            return entry
    return None


def flow_guard_matches(match: Any, flow_identity: dict[str, Any]) -> bool:
    if not isinstance(match, dict):
        return False

    for key in (
        "workflowId",
        "workflowUniqueId",
        "uniqueName",
        "name",
        "displayName",
        "solutionUniqueName",
        "definitionPath",
    ):
        expected = normalize_guard_value(match.get(key))
        if expected is None:
            continue
        actual = normalize_guard_value(flow_identity.get(key))
        if actual != expected:
            return False
    return True


def validate_flow_guard_requirements(
    flow_summary: dict[str, Any],
    flow_guard: dict[str, Any] | None,
    *,
    comparison_label: str,
) -> list[dict[str, Any]]:
    if not isinstance(flow_guard, dict):
        return []

    findings: list[dict[str, Any]] = []
    required_switch_cases = flow_guard.get("requiredSwitchCases")
    if isinstance(required_switch_cases, list):
        for item in required_switch_cases:
            if not isinstance(item, dict):
                continue
            switch_name = str(item.get("switchName") or "").strip()
            case_name = str(item.get("caseName") or "").strip()
            if not switch_name or not case_name:
                continue
            case_summary = flow_summary["switchCases"].get(switch_case_key(switch_name, case_name))
            if case_summary is None:
                findings.append(
                    {
                        "severity": "high",
                        "code": "required-switch-case-missing",
                        "message": f"Required switch case '{switch_name}' -> '{case_name}' is missing.",
                        "switchName": switch_name,
                        "caseName": case_name,
                        "comparisonLabel": comparison_label,
                    }
                )
                continue

            required_actions = sorted(
                {
                    str(action_name).strip()
                    for action_name in item.get("requiredActionNames", [])
                    if str(action_name).strip()
                }
            )
            missing_actions = sorted(set(required_actions) - set(case_summary["actionNames"]))
            if missing_actions:
                findings.append(
                    {
                        "severity": "high",
                        "code": "required-switch-case-actions-missing",
                        "message": (
                            f"Required actions are missing from switch '{switch_name}' case '{case_name}': "
                            f"{', '.join(missing_actions)}."
                        ),
                        "switchName": switch_name,
                        "caseName": case_name,
                        "missingActionNames": missing_actions,
                        "comparisonLabel": comparison_label,
                    }
                )

    return findings


def switch_case_key(switch_name: str, case_name: str) -> str:
    return f"{switch_name.casefold()}::{case_name.casefold()}"


def normalize_guard_value(value: Any) -> str | None:
    text = str(value or "").strip()
    return text.casefold() if text else None


def load_json_path(raw_path: Any, repo: Path) -> Any:
    path = Path(str(raw_path))
    if not path.is_absolute():
        path = (repo / path).resolve()
    return json.loads(path.read_text(encoding="utf-8"))


def parse_client_data(value: Any) -> tuple[dict[str, Any], str]:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise RuntimeError("Flow clientData is empty.")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError("Flow clientData must be a JSON object.")
        return parsed, raw

    if isinstance(value, dict):
        return value, json.dumps(value, indent=2)

    raise RuntimeError("Flow clientData must resolve to either a JSON object or a JSON string.")


def summarize_client_data(client_data: dict[str, Any]) -> dict[str, Any]:
    properties = client_data.get("properties")
    if not isinstance(properties, dict):
        return {
            "hasProperties": False,
            "connectionReferenceCount": 0,
            "triggerCount": 0,
            "actionCount": 0,
            "triggerNames": [],
            "actionNames": [],
            "parameterNames": [],
        }

    connection_references = properties.get("connectionReferences")
    definition = properties.get("definition")
    triggers = definition.get("triggers") if isinstance(definition, dict) else None
    actions = definition.get("actions") if isinstance(definition, dict) else None
    parameters = definition.get("parameters") if isinstance(definition, dict) else None

    return {
        "hasProperties": True,
        "connectionReferenceCount": len(connection_references) if isinstance(connection_references, dict) else 0,
        "triggerCount": len(triggers) if isinstance(triggers, dict) else 0,
        "actionCount": len(actions) if isinstance(actions, dict) else 0,
        "triggerNames": sorted(triggers.keys()) if isinstance(triggers, dict) else [],
        "actionNames": sorted(actions.keys()) if isinstance(actions, dict) else [],
        "parameterNames": sorted(parameters.keys()) if isinstance(parameters, dict) else [],
    }


def lint_client_data(client_data: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    properties = client_data.get("properties")
    if not isinstance(properties, dict):
        findings.append(
            {
                "severity": "high",
                "code": "missing-properties",
                "message": "clientData does not contain the expected top-level properties object.",
            }
        )
        return findings

    definition = properties.get("definition")
    if not isinstance(definition, dict):
        findings.append(
            {
                "severity": "high",
                "code": "missing-definition",
                "message": "clientData.properties.definition is missing or not a JSON object.",
            }
        )
        return findings

    connection_references = properties.get("connectionReferences")
    if not isinstance(connection_references, dict) or not connection_references:
        findings.append(
            {
                "severity": "medium",
                "code": "missing-connection-references",
                "message": "The flow definition does not declare any connection references.",
            }
        )

    triggers = definition.get("triggers")
    if not isinstance(triggers, dict) or not triggers:
        findings.append(
            {
                "severity": "high",
                "code": "missing-triggers",
                "message": "The flow definition does not declare any triggers.",
            }
        )

    actions = definition.get("actions")
    if not isinstance(actions, dict) or not actions:
        findings.append(
            {
                "severity": "high",
                "code": "missing-actions",
                "message": "The flow definition does not declare any actions.",
            }
        )

    parameters = definition.get("parameters")
    if isinstance(parameters, dict):
        for required_parameter in ("$connections", "$authentication"):
            if required_parameter not in parameters:
                findings.append(
                    {
                        "severity": "low",
                        "code": "missing-parameter",
                        "message": f"The flow definition parameters do not declare {required_parameter}.",
                        "path": f"properties.definition.parameters.{required_parameter}",
                    }
                )

    declared_references = set(connection_references.keys()) if isinstance(connection_references, dict) else set()
    if isinstance(triggers, dict):
        findings.extend(find_missing_connection_reference_aliases(triggers, declared_references, "properties.definition.triggers"))
    if isinstance(actions, dict):
        findings.extend(find_missing_connection_reference_aliases(actions, declared_references, "properties.definition.actions"))
        findings.extend(find_invalid_run_after(actions))

    findings.extend(find_hardcoded_guid_literals(client_data))
    findings.extend(find_hardcoded_environment_urls(client_data))
    return findings


def review_flow_hardening(client_data: dict[str, Any]) -> dict[str, Any]:
    findings = lint_client_data(client_data)
    properties = client_data.get("properties")
    definition = properties.get("definition") if isinstance(properties, dict) else None
    triggers = definition.get("triggers") if isinstance(definition, dict) else {}
    actions = definition.get("actions") if isinstance(definition, dict) else {}

    checklist = {
        "retryPolicy": {"status": "not-applicable", "message": "No retry-eligible actions were detected."},
        "concurrency": {"status": "not-applicable", "message": "No trigger or loop concurrency controls were detected."},
        "pagination": {"status": "not-applicable", "message": "No list-style actions were detected."},
        "idempotency": {"status": "warning", "message": "Idempotency still needs human confirmation for side-effect actions."},
        "errorHandling": {"status": "warning", "message": "Error handling still needs human confirmation."},
        "maintainability": {"status": "passed", "message": "No obvious maintainability red flags were detected."},
    }

    if isinstance(triggers, dict):
        findings.extend(find_trigger_concurrency_findings(triggers))
        findings.extend(find_trigger_split_on_findings(triggers))
    if isinstance(actions, dict):
        findings.extend(find_retry_policy_findings(actions))
        findings.extend(find_pagination_findings(actions))
        findings.extend(find_foreach_concurrency_findings(actions))
        findings.extend(find_error_handling_findings(actions))
        findings.extend(find_idempotency_findings(actions))
        findings.extend(find_maintainability_findings(actions))

    findings = deduplicate_findings(findings)

    checklist["retryPolicy"] = summarize_checklist(
        findings,
        {"missing-retry-policy", "nonstandard-retry-policy"},
        "Retry policy checks passed for detected external or connector actions.",
    )
    checklist["concurrency"] = summarize_checklist(
        findings,
        {"missing-trigger-concurrency", "missing-foreach-concurrency"},
        "Concurrency controls are explicit where the helper can infer they matter.",
    )
    checklist["pagination"] = summarize_checklist(
        findings,
        {"missing-pagination"},
        "Pagination settings are explicit on detected list-style actions.",
    )
    checklist["idempotency"] = summarize_checklist(
        findings,
        {"possible-non-idempotent-side-effect"},
        "No obvious non-idempotent side-effect pattern was detected.",
    )
    checklist["errorHandling"] = summarize_checklist(
        findings,
        {"missing-error-handling"},
        "The flow exposes at least one explicit failure-handling path or scope pattern.",
    )
    checklist["maintainability"] = summarize_checklist(
        findings,
        {"large-action-set", "missing-scope-grouping"},
        "The flow shape stays within the current maintainability heuristics.",
    )

    return {
        "summary": summarize_client_data(client_data),
        "checklist": checklist,
        "findings": findings,
        "findingCount": len(findings),
        "riskLevel": compute_risk_level(findings),
    }


def find_missing_connection_reference_aliases(section: dict[str, Any], declared_aliases: set[str], base_path: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name, node in section.items():
        if not isinstance(node, dict):
            continue
        if str(node.get("type", "")).lower() != "openapiconnection":
            continue
        inputs = node.get("inputs")
        host = inputs.get("host") if isinstance(inputs, dict) else None
        connection_name = host.get("connectionName") if isinstance(host, dict) else None
        if isinstance(connection_name, str) and connection_name and connection_name not in declared_aliases:
            findings.append(
                {
                    "severity": "medium",
                    "code": "missing-connection-alias",
                    "message": f"{name} references connection alias '{connection_name}' that is not declared in connectionReferences.",
                    "path": f"{base_path}.{name}.inputs.host.connectionName",
                }
            )
    return findings


def find_invalid_run_after(actions: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    declared_actions = set(actions.keys())
    for action_name, node in actions.items():
        if not isinstance(node, dict):
            continue
        run_after = node.get("runAfter")
        if not isinstance(run_after, dict):
            continue
        for dependency in run_after.keys():
            if dependency not in declared_actions:
                findings.append(
                    {
                        "severity": "medium",
                        "code": "missing-runafter-action",
                        "message": f"{action_name} depends on missing action '{dependency}' in runAfter.",
                        "path": f"properties.definition.actions.{action_name}.runAfter.{dependency}",
                    }
                )
    return findings


def find_retry_policy_findings(actions: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for action_name, node in actions.items():
        if not isinstance(node, dict):
            continue
        action_type = str(node.get("type", "")).lower()
        if action_type not in RETRY_RECOMMENDED_ACTION_TYPES:
            continue
        inputs = node.get("inputs")
        retry_policy = inputs.get("retryPolicy") if isinstance(inputs, dict) else None
        path = f"properties.definition.actions.{action_name}.inputs.retryPolicy"
        if not isinstance(retry_policy, dict):
            findings.append(
                {
                    "severity": "medium",
                    "code": "missing-retry-policy",
                    "message": f"{action_name} does not declare an explicit retryPolicy.",
                    "path": path,
                }
            )
            continue
        retry_type = str(retry_policy.get("type", "")).lower()
        if retry_type and retry_type not in {"fixed", "exponential"}:
            findings.append(
                {
                    "severity": "low",
                    "code": "nonstandard-retry-policy",
                    "message": f"{action_name} uses retryPolicy type '{retry_type}', which should be reviewed explicitly.",
                    "path": path,
                }
            )
    return findings


def find_pagination_findings(actions: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for action_name, node in actions.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        host = inputs.get("host") if isinstance(inputs, dict) else None
        operation_id = str(host.get("operationId", "")).lower() if isinstance(host, dict) else ""
        if not any(pattern in operation_id for pattern in LIST_OPERATION_PATTERNS):
            continue
        pagination = node.get("paginationPolicy")
        if not isinstance(pagination, dict):
            findings.append(
                {
                    "severity": "medium",
                    "code": "missing-pagination",
                    "message": f"{action_name} looks like a list-style operation but does not declare paginationPolicy.",
                    "path": f"properties.definition.actions.{action_name}.paginationPolicy",
                }
            )
    return findings


def find_trigger_concurrency_findings(triggers: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for trigger_name, node in triggers.items():
        if not isinstance(node, dict):
            continue
        trigger_type = str(node.get("type", "")).lower()
        if trigger_type not in {"request", "recurrence", "openapiconnection", "openapiconnectionwebhook"}:
            continue
        runtime = node.get("runtimeConfiguration")
        concurrency = runtime.get("concurrency") if isinstance(runtime, dict) else None
        if trigger_type != "request" and not isinstance(concurrency, dict):
            findings.append(
                {
                    "severity": "low",
                    "code": "missing-trigger-concurrency",
                    "message": f"{trigger_name} does not declare runtimeConfiguration.concurrency explicitly.",
                    "path": f"properties.definition.triggers.{trigger_name}.runtimeConfiguration.concurrency",
                }
            )
    return findings


def find_trigger_split_on_findings(triggers: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for trigger_name, node in triggers.items():
        if not isinstance(node, dict):
            continue
        split_on = node.get("splitOn")
        if split_on is not None and not isinstance(split_on, str):
            findings.append(
                {
                    "severity": "low",
                    "code": "invalid-spliton",
                    "message": f"{trigger_name} declares splitOn but not as a string expression.",
                    "path": f"properties.definition.triggers.{trigger_name}.splitOn",
                }
            )
    return findings


def find_foreach_concurrency_findings(actions: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for action_name, node in actions.items():
        if not isinstance(node, dict):
            continue
        if str(node.get("type", "")).lower() != "foreach":
            continue
        runtime = node.get("runtimeConfiguration")
        concurrency = runtime.get("concurrency") if isinstance(runtime, dict) else None
        if not isinstance(concurrency, dict):
            findings.append(
                {
                    "severity": "low",
                    "code": "missing-foreach-concurrency",
                    "message": f"{action_name} is a foreach action without explicit runtime concurrency settings.",
                    "path": f"properties.definition.actions.{action_name}.runtimeConfiguration.concurrency",
                }
            )
    return findings


def find_error_handling_findings(actions: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    has_scope = any(isinstance(node, dict) and str(node.get("type", "")).lower() == "scope" for node in actions.values())
    has_failure_path = False
    for node in actions.values():
        if not isinstance(node, dict):
            continue
        run_after = node.get("runAfter")
        if not isinstance(run_after, dict):
            continue
        for statuses in run_after.values():
            if isinstance(statuses, list) and any(str(status).lower() in {"failed", "timedout", "skipped"} for status in statuses):
                has_failure_path = True
                break
        if has_failure_path:
            break

    if not has_scope and not has_failure_path and len(actions) > 1:
        findings.append(
            {
                "severity": "medium",
                "code": "missing-error-handling",
                "message": "The flow does not show an explicit scope-based or runAfter-based error-handling path.",
                "path": "properties.definition.actions",
            }
        )
    return findings


def find_idempotency_findings(actions: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for action_name, node in actions.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        host = inputs.get("host") if isinstance(inputs, dict) else None
        operation_id = str(host.get("operationId", "")).lower() if isinstance(host, dict) else ""
        if not any(pattern in operation_id for pattern in SIDE_EFFECT_OPERATION_PATTERNS):
            continue
        if "upsert" in operation_id:
            continue
        parameters = inputs.get("parameters") if isinstance(inputs, dict) else None
        flattened = json.dumps(parameters, sort_keys=True).lower() if parameters is not None else ""
        if any(keyword in flattened for keyword in ("alternatekey", "if-match", "if-none-match", "rowid", "key")):
            continue
        findings.append(
            {
                "severity": "low",
                "code": "possible-non-idempotent-side-effect",
                "message": f"{action_name} looks like a side-effect action without an obvious idempotency or alternate-key pattern.",
                "path": f"properties.definition.actions.{action_name}.inputs",
            }
        )
    return findings


def find_maintainability_findings(actions: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if len(actions) > 20:
        findings.append(
            {
                "severity": "low",
                "code": "large-action-set",
                "message": f"The flow currently contains {len(actions)} actions, which may be hard to maintain without stronger grouping.",
                "path": "properties.definition.actions",
            }
        )
    if len(actions) > 8:
        has_scope = any(isinstance(node, dict) and str(node.get("type", "")).lower() == "scope" for node in actions.values())
        if not has_scope:
            findings.append(
                {
                    "severity": "low",
                    "code": "missing-scope-grouping",
                    "message": "The flow has many actions but no Scope grouping blocks, which may make maintenance harder.",
                    "path": "properties.definition.actions",
                }
            )
    return findings


def find_hardcoded_guid_literals(payload: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, value in iter_string_values(payload):
        matches = GUID_RE.findall(value)
        if not matches:
            continue
        if any(part in path for part in IGNORED_GUID_PATH_PARTS):
            continue
        findings.append(
            {
                "severity": "medium",
                "code": "hardcoded-guid",
                "message": f"Possible hardcoded GUID literal found at {path}.",
                "path": path,
                "samples": sorted(set(matches))[:5],
            }
        )
    return findings


def find_hardcoded_environment_urls(payload: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, value in iter_string_values(payload):
        matches = ENVIRONMENT_URL_RE.findall(value)
        if not matches:
            continue
        findings.append(
            {
                "severity": "medium",
                "code": "hardcoded-environment-url",
                "message": f"Possible environment-specific Dataverse URL found at {path}.",
                "path": path,
                "samples": sorted(set(matches))[:5],
            }
        )
    return findings


def iter_string_values(payload: Any, path: str = "$"):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield from iter_string_values(value, f"{path}.{key}")
        return
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            yield from iter_string_values(value, f"{path}[{index}]")
        return
    if isinstance(payload, str):
        yield path, payload


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        code = str(finding.get("code") or "")
        path = str(finding.get("path") or "")
        key = (code, path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def summarize_checklist(findings: list[dict[str, Any]], codes: set[str], passed_message: str) -> dict[str, Any]:
    matching = [finding for finding in findings if finding.get("code") in codes]
    if not matching:
        return {"status": "passed", "message": passed_message}

    severities = {finding.get("severity") for finding in matching}
    if "high" in severities:
        status = "failed"
    else:
        status = "warning"
    return {
        "status": status,
        "message": "; ".join(str(finding.get("message")) for finding in matching[:3]),
        "findingCount": len(matching),
    }


def compute_risk_level(findings: list[dict[str, Any]]) -> str:
    severities = {str(finding.get("severity")) for finding in findings}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if findings:
        return "low"
    return "minimal"
