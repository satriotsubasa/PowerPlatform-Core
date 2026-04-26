#!/usr/bin/env python3
"""Orchestrate a Power Platform requirement spec across reusable helpers."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from powerplatform_common import (
    apply_selected_solution_to_spec,
    discover_repo_context,
    ensure_dataverse_solution_reference,
    has_local_solution_source_in_context,
    authoritative_unpacked_solutions,
    load_deployment_defaults,
    read_json_argument,
    repo_root,
    resolve_live_connection,
    run_command,
    write_json_output,
)

LOCAL_ONLY_STEP_TYPES = {
    "scaffold-pcf",
    "inspect-word-templates",
    "version-pcf-solution",
    "design-dataverse-schema",
    "design-dataverse-query",
    "review-solution-standards",
    "debug-power-fx",
    "design-custom-connector",
    "plan-document-generation",
    "plan-solution-patch-merge",
}

TARGETED_COMPONENT_STEP_TYPES = {
    "update-main-form",
    "patch-form-xml",
    "patch-form-ribbon",
    "update-form-events",
    "update-view",
    "set-table-icon",
    "sync-webresource",
    "sync-webresources-batch",
    "bind-pcf-control",
}

SOLUTION_INJECTED_STEP_TYPES = {
    "create-table",
    "create-field",
    "create-lookup",
    "create-flow",
    "update-flow",
    "get-flow-trigger-url",
    "set-table-icon",
    "sync-webresource",
    "create-custom-api",
    "create-security-role",
    "update-security-role",
    "add-solution-components",
    "register-plugin-assembly",
    "register-plugin-package",
    "inspect-plugin-steps",
    "ensure-plugin-step-state",
}

SPEC_PAYLOAD_STEP_TYPES = {
    "create-table",
    "create-field",
    "create-lookup",
    "inspect-flow",
    "lint-flow",
    "review-flow-hardening",
    "review-flow-connectors",
    "create-flow",
    "update-flow",
    "get-flow-trigger-url",
    "update-main-form",
    "patch-form-xml",
    "patch-form-ribbon",
    "update-form-events",
    "update-view",
    "bind-pcf-control",
    "set-table-icon",
    "sync-webresource",
    "create-custom-api",
    "inspect-environment-variable",
    "set-environment-variable-value",
    "inspect-security-role",
    "create-security-role",
    "update-security-role",
    "inspect-plugin-steps",
    "ensure-plugin-step-state",
    "add-solution-components",
    "design-dataverse-schema",
    "design-dataverse-query",
    "review-solution-standards",
    "debug-power-fx",
    "design-custom-connector",
    "plan-document-generation",
    "plan-solution-patch-merge",
}

STEP_DEPLOYMENT_METADATA = {
    "create-table": {"assetType": "metadata", "defaultPrimitive": "create-table", "targetedDeliverySupported": True},
    "create-field": {"assetType": "metadata", "defaultPrimitive": "create-field", "targetedDeliverySupported": True},
    "create-lookup": {"assetType": "metadata", "defaultPrimitive": "create-lookup", "targetedDeliverySupported": True},
    "inspect-flow": {"assetType": "flow", "defaultPrimitive": "inspect-flow", "targetedDeliverySupported": True},
    "lint-flow": {"assetType": "flow", "defaultPrimitive": "lint-flow", "targetedDeliverySupported": True},
    "review-flow-hardening": {"assetType": "flow", "defaultPrimitive": "review-flow-hardening", "targetedDeliverySupported": True},
    "review-flow-connectors": {"assetType": "flow", "defaultPrimitive": "review-flow-connectors", "targetedDeliverySupported": True},
    "create-flow": {"assetType": "flow", "defaultPrimitive": "create-flow", "targetedDeliverySupported": True},
    "update-flow": {"assetType": "flow", "defaultPrimitive": "update-flow", "targetedDeliverySupported": True},
    "get-flow-trigger-url": {"assetType": "flow", "defaultPrimitive": "get-flow-trigger-url", "targetedDeliverySupported": True},
    "update-main-form": {"assetType": "metadata", "defaultPrimitive": "update-main-form", "targetedDeliverySupported": True},
    "patch-form-xml": {"assetType": "metadata", "defaultPrimitive": "patch-form-xml", "targetedDeliverySupported": True},
    "patch-form-ribbon": {"assetType": "metadata", "defaultPrimitive": "patch-form-ribbon", "targetedDeliverySupported": True},
    "update-form-events": {"assetType": "metadata", "defaultPrimitive": "update-form-events", "targetedDeliverySupported": True},
    "bind-pcf-control": {"assetType": "metadata", "defaultPrimitive": "bind-pcf-control", "targetedDeliverySupported": True},
    "update-view": {"assetType": "metadata", "defaultPrimitive": "update-view", "targetedDeliverySupported": True},
    "set-table-icon": {"assetType": "metadata", "defaultPrimitive": "set-table-icon", "targetedDeliverySupported": True},
    "sync-webresource": {"assetType": "webresource", "defaultPrimitive": "sync-webresource", "targetedDeliverySupported": True},
    "sync-webresources-batch": {"assetType": "webresource", "defaultPrimitive": "sync-webresources-batch", "targetedDeliverySupported": True},
    "create-custom-api": {"assetType": "custom-api", "defaultPrimitive": "create-custom-api", "targetedDeliverySupported": True},
    "inspect-environment-variable": {"assetType": "environment-variable", "defaultPrimitive": "inspect-environment-variable", "targetedDeliverySupported": True},
    "set-environment-variable-value": {"assetType": "environment-variable", "defaultPrimitive": "set-environment-variable-value", "targetedDeliverySupported": True},
    "inspect-security-role": {"assetType": "security-role", "defaultPrimitive": "inspect-security-role", "targetedDeliverySupported": True},
    "create-security-role": {"assetType": "security-role", "defaultPrimitive": "create-security-role", "targetedDeliverySupported": True},
    "update-security-role": {"assetType": "security-role", "defaultPrimitive": "update-security-role", "targetedDeliverySupported": True},
    "register-plugin-assembly": {"assetType": "plugin", "defaultPrimitive": "register-plugin-assembly", "targetedDeliverySupported": True},
    "register-plugin-package": {"assetType": "plugin", "defaultPrimitive": "register-plugin-package", "targetedDeliverySupported": True},
    "inspect-plugin-steps": {"assetType": "plugin", "defaultPrimitive": "inspect-plugin-steps", "targetedDeliverySupported": True},
    "ensure-plugin-step-state": {"assetType": "plugin", "defaultPrimitive": "ensure-plugin-step-state", "targetedDeliverySupported": True},
    "push-plugin": {"assetType": "plugin", "defaultPrimitive": "push-plugin", "targetedDeliverySupported": True},
    "scaffold-pcf": {"assetType": "pcf", "defaultPrimitive": "scaffold-pcf", "targetedDeliverySupported": True},
    "version-pcf-solution": {"assetType": "pcf", "defaultPrimitive": "version-pcf-solution", "targetedDeliverySupported": True},
    "deploy-pcf": {"assetType": "pcf", "defaultPrimitive": "deploy-pcf", "targetedDeliverySupported": True},
    "add-solution-components": {"assetType": "metadata", "defaultPrimitive": "add-solution-components", "targetedDeliverySupported": True},
    "validate-delivery": {"assetType": "validation", "defaultPrimitive": "validate-delivery", "targetedDeliverySupported": True},
    "upsert-data": {"assetType": "data", "defaultPrimitive": "upsert-data", "targetedDeliverySupported": True},
    "inspect-word-templates": {"assetType": "document-template", "defaultPrimitive": "inspect-word-templates", "targetedDeliverySupported": False},
    "solution-version": {"assetType": "solution-version", "defaultPrimitive": "solution-version", "targetedDeliverySupported": False},
    "deploy-solution": {"assetType": "solution-import", "defaultPrimitive": "deploy-solution", "targetedDeliverySupported": False},
}

EXPLICIT_STEP_TYPE_ALIASES = {
    "table": "create-table",
    "create-table": "create-table",
    "field": "create-field",
    "create-field": "create-field",
    "lookup": "create-lookup",
    "create-lookup": "create-lookup",
    "flow-inspect": "inspect-flow",
    "inspect-flow": "inspect-flow",
    "flow-lint": "lint-flow",
    "lint-flow": "lint-flow",
    "flow-hardening-review": "review-flow-hardening",
    "review-flow-hardening": "review-flow-hardening",
    "flow-connector-review": "review-flow-connectors",
    "review-flow-connectors": "review-flow-connectors",
    "flow-create": "create-flow",
    "create-flow": "create-flow",
    "flow-update": "update-flow",
    "update-flow": "update-flow",
    "flow-trigger-url": "get-flow-trigger-url",
    "get-flow-trigger-url": "get-flow-trigger-url",
    "dataverse-schema-design": "design-dataverse-schema",
    "design-dataverse-schema": "design-dataverse-schema",
    "dataverse-query-design": "design-dataverse-query",
    "design-dataverse-query": "design-dataverse-query",
    "solution-standards-review": "review-solution-standards",
    "review-solution-standards": "review-solution-standards",
    "power-fx-debug": "debug-power-fx",
    "debug-power-fx": "debug-power-fx",
    "custom-connector-design": "design-custom-connector",
    "design-custom-connector": "design-custom-connector",
    "document-generation-plan": "plan-document-generation",
    "plan-document-generation": "plan-document-generation",
    "solution-patch-plan": "plan-solution-patch-merge",
    "patch-merge-plan": "plan-solution-patch-merge",
    "plan-solution-patch-merge": "plan-solution-patch-merge",
    "main-form": "update-main-form",
    "update-main-form": "update-main-form",
    "form-xml-patch": "patch-form-xml",
    "patch-form-xml": "patch-form-xml",
    "form-ribbon-patch": "patch-form-ribbon",
    "patch-form-ribbon": "patch-form-ribbon",
    "form-events": "update-form-events",
    "update-form-events": "update-form-events",
    "pcf-bind": "bind-pcf-control",
    "bind-pcf-control": "bind-pcf-control",
    "view": "update-view",
    "update-view": "update-view",
    "table-icon": "set-table-icon",
    "set-table-icon": "set-table-icon",
    "webresource": "sync-webresource",
    "sync-webresource": "sync-webresource",
    "webresource-batch": "sync-webresources-batch",
    "sync-webresources-batch": "sync-webresources-batch",
    "custom-api": "create-custom-api",
    "create-custom-api": "create-custom-api",
    "environment-variable-inspect": "inspect-environment-variable",
    "inspect-environment-variable": "inspect-environment-variable",
    "environment-variable-set-value": "set-environment-variable-value",
    "set-environment-variable-value": "set-environment-variable-value",
    "security-role-inspect": "inspect-security-role",
    "inspect-security-role": "inspect-security-role",
    "security-role-create": "create-security-role",
    "create-security-role": "create-security-role",
    "security-role-update": "update-security-role",
    "update-security-role": "update-security-role",
    "plugin-assembly": "register-plugin-assembly",
    "register-plugin-assembly": "register-plugin-assembly",
    "plugin-package": "register-plugin-package",
    "register-plugin-package": "register-plugin-package",
    "plugin-step-inspect": "inspect-plugin-steps",
    "inspect-plugin-steps": "inspect-plugin-steps",
    "plugin-step-state": "ensure-plugin-step-state",
    "ensure-plugin-step-state": "ensure-plugin-step-state",
    "push-plugin": "push-plugin",
    "pcf-scaffold": "scaffold-pcf",
    "scaffold-pcf": "scaffold-pcf",
    "pcf-version": "version-pcf-solution",
    "version-pcf-solution": "version-pcf-solution",
    "pcf-deploy": "deploy-pcf",
    "deploy-pcf": "deploy-pcf",
    "solution-components": "add-solution-components",
    "add-solution-components": "add-solution-components",
    "validate-delivery": "validate-delivery",
    "delivery-validation": "validate-delivery",
    "data": "upsert-data",
    "upsert-data": "upsert-data",
    "word-templates": "inspect-word-templates",
    "inspect-word-templates": "inspect-word-templates",
    "solution-version": "solution-version",
    "deploy-solution": "deploy-solution",
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute a Power Platform requirement spec across the reusable helper scripts.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the requirement.")
    parser.add_argument("--repo-root", default=".", help="Repository root used for discovery and relative paths.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL when bypassing the auth dialog.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Force the reusable auth dialog even when it would not be opened automatically.")
    parser.add_argument("--no-auth-dialog", action="store_true", help="Bypass the reusable auth dialog even for live steps.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument("--plan-only", action="store_true", help="Resolve context and output the execution plan without making changes.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue executing later steps after a failure.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Auth flow to pass to child Dataverse SDK helpers when the auth dialog is not used.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive prompt for child Dataverse SDK helpers.")
    parser.add_argument("--verbose", action="store_true", help="Print verbose diagnostics from child Dataverse SDK helpers.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    requirement = read_json_argument(args.spec)
    if not isinstance(requirement, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    discovery = discover_repo_context(repo)
    deployment_defaults = load_deployment_defaults(repo)
    steps = expand_requirement_spec(requirement)
    live_required = any(step_requires_live_connection(step) for step in steps)
    use_auth_dialog = determine_auth_dialog_usage(args, requirement, live_required)

    connection: dict[str, Any] | None = None
    dataverse_reference: dict[str, Any] | None = None
    if use_auth_dialog:
        connection = resolve_live_connection(
            environment_url=args.environment_url,
            username=args.username,
            tenant_id=args.tenant_id,
            auth_dialog=True,
            target_url=args.target_url,
            auto_validate=args.auto_validate,
        )
    elif live_required and not args.plan_only:
        connection = resolve_live_connection(
            environment_url=args.environment_url,
            username=args.username,
            tenant_id=args.tenant_id,
            auth_dialog=False,
        )

    if (
        connection
        and not args.plan_only
        and should_ensure_dataverse_reference(discovery, live_required, use_auth_dialog, connection)
    ):
        dataverse_reference = ensure_dataverse_solution_reference(
            repo,
            environment_url=connection["environment_url"],
            solution_unique_name=connection["solution_unique_name"],
        )
        if dataverse_reference.get("created"):
            discovery = discover_repo_context(repo)

    local_solution = resolve_local_solution_info(repo, discovery)
    preflight = build_preflight(
        repo=repo,
        requirement=requirement,
        discovery=discovery,
        steps=steps,
        live_required=live_required,
        use_auth_dialog=use_auth_dialog,
        connection=connection,
        local_solution=local_solution,
        dataverse_reference=dataverse_reference,
    )
    deployment_preflight = build_deployment_preflight(
        steps=steps,
        deployment_defaults=deployment_defaults,
    )

    results: list[dict[str, Any]] = []
    success = True
    failure_message: str | None = None

    if not args.plan_only:
        enforce_deployment_preflight(deployment_preflight)
        child_auth_flow = determine_child_auth_flow(args.auth_flow, use_auth_dialog)
        for index, step in enumerate(steps, start=1):
            try:
                result = execute_step(
                    step=step,
                    repo=repo,
                    connection=connection,
                    auth_flow=child_auth_flow,
                    force_prompt=args.force_prompt,
                    verbose=args.verbose,
                )
                results.append(
                    {
                        "index": index,
                        "name": step.get("name") or default_step_name(step, index),
                        "type": step["type"],
                        "success": True,
                        "result": result,
                    }
                )
            except Exception as exc:
                success = False
                failure_message = str(exc)
                results.append(
                    {
                        "index": index,
                        "name": step.get("name") or default_step_name(step, index),
                        "type": step["type"],
                        "success": False,
                        "error": str(exc),
                    }
                )
                if not args.continue_on_error:
                    break

    payload = {
        "success": success,
        "plan_only": args.plan_only,
        "repo_root": str(repo),
        "preflight": preflight,
        "deploymentPreflight": deployment_preflight,
        "steps": [summarize_step(step, index + 1) for index, step in enumerate(steps)],
        "results": results,
    }
    if failure_message:
        payload["error"] = failure_message

    write_json_output(payload, args.output)
    return 0 if success else 1


def determine_auth_dialog_usage(args: argparse.Namespace, requirement: dict[str, Any], live_required: bool) -> bool:
    if args.no_auth_dialog:
        return False
    if args.auth_dialog:
        return True

    preflight = requirement.get("preflight")
    if isinstance(preflight, dict) and preflight.get("useAuthDialog") is False:
        return False

    return live_required and not args.plan_only


def determine_child_auth_flow(configured_auth_flow: str, used_auth_dialog: bool) -> str:
    if configured_auth_flow == "auto" and used_auth_dialog:
        return "interactive"
    return configured_auth_flow


def build_preflight(
    *,
    repo: Path,
    requirement: dict[str, Any],
    discovery: dict[str, Any],
    steps: list[dict[str, Any]],
    live_required: bool,
    use_auth_dialog: bool,
    connection: dict[str, Any] | None,
    local_solution: dict[str, Any] | None,
    dataverse_reference: dict[str, Any] | None,
) -> dict[str, Any]:
    inferred = discovery.get("inferred", {})
    selected_solution = None
    if connection:
        selected_solution_candidate = {
            "solutionId": connection.get("solution_id"),
            "uniqueName": connection.get("solution_unique_name"),
            "friendlyName": connection.get("solution_friendly_name"),
            "version": connection.get("solution_version"),
            "isManaged": connection.get("solution_is_managed"),
            "isPatch": connection.get("solution_is_patch"),
            "parentUniqueName": connection.get("solution_parent_unique_name"),
        }
        if any(value is not None for value in selected_solution_candidate.values()):
            selected_solution = selected_solution_candidate

    warnings: list[str] = []
    if selected_solution and selected_solution.get("uniqueName") and local_solution and local_solution.get("uniqueName"):
        selected_name = selected_solution["uniqueName"]
        local_name = local_solution["uniqueName"]
        parent_name = selected_solution.get("parentUniqueName")
        if selected_name != local_name and parent_name != local_name:
            warnings.append(
                "The selected live solution does not match the local unpacked solution unique name. "
                f"Selected: {selected_name}. Local: {local_name}."
            )
        elif parent_name and parent_name == local_name:
            warnings.append(
                "The selected live solution is a patch whose parent matches the local unpacked solution. "
                f"Selected patch: {selected_name}. Local parent: {local_name}."
            )

    return {
        "description": requirement.get("description"),
        "live_required": live_required,
        "auth_dialog_used": use_auth_dialog,
        "planned_step_count": len(steps),
        "inferred_context": {
            "solution_unique_name": inferred.get("solution_unique_name"),
            "publisher_prefix": inferred.get("publisher_prefix"),
            "plugin_project": inferred.get("plugin_project"),
            "webresources_area": inferred.get("webresources_area"),
            "pcf_area": inferred.get("pcf_area"),
            "word_templates_area": inferred.get("word_templates_area"),
        },
        "selected_solution": selected_solution,
        "dataverse_reference": dataverse_reference,
        "environment_url": connection.get("environment_url") if connection else None,
        "local_solution": local_solution,
        "warnings": warnings,
    }


def resolve_local_solution_info(repo: Path, discovery: dict[str, Any]) -> dict[str, Any] | None:
    unpacked_solutions = authoritative_unpacked_solutions(discovery)
    if len(unpacked_solutions) != 1:
        return None

    relative_folder = unpacked_solutions[0].get("solution_folder_relative_path")
    if not relative_folder:
        return None

    solution_xml = repo / relative_folder / "Other" / "Solution.xml"
    if not solution_xml.exists():
        return None

    xml_root = ET.parse(solution_xml).getroot()
    unique_name = find_xml_text(xml_root, "UniqueName")
    version = find_xml_text(xml_root, "Version")
    friendly_name = find_xml_text(xml_root, "LocalizedName")

    return {
        "solutionXml": str(solution_xml),
        "uniqueName": unique_name,
        "friendlyName": friendly_name,
        "version": version,
    }


def should_ensure_dataverse_reference(
    discovery: dict[str, Any],
    live_required: bool,
    use_auth_dialog: bool,
    connection: dict[str, Any] | None,
) -> bool:
    if not live_required or not use_auth_dialog or not connection:
        return False
    if not connection.get("solution_unique_name") or not connection.get("environment_url"):
        return False
    return not has_local_solution_source_in_context(discovery)


def find_xml_text(root: ET.Element, local_name: str) -> str | None:
    for element in root.iter():
        if element.tag.split("}", 1)[-1] == local_name and element.text and element.text.strip():
            return element.text.strip()
    return None


def expand_requirement_spec(requirement: dict[str, Any]) -> list[dict[str, Any]]:
    explicit_steps = requirement.get("steps")
    if explicit_steps is not None:
        if not isinstance(explicit_steps, list):
            raise RuntimeError("'steps' must be a JSON array when present.")
        return [normalize_explicit_step(step, index + 1) for index, step in enumerate(explicit_steps)]

    steps: list[dict[str, Any]] = []

    versioning = requirement.get("versioning")
    when = "before-changes"
    if isinstance(versioning, dict):
        when = str(versioning.get("when", "before-changes")).strip().lower()
        if when in {"before", "before-change", "before-changes"}:
            steps.append({"type": "solution-version", "options": versioning, "name": "solution-version-before"})

    for key, step_type in [
        ("tables", "create-table"),
        ("fields", "create-field"),
        ("lookups", "create-lookup"),
        ("tableIcons", "set-table-icon"),
        ("webResources", "sync-webresource"),
        ("webResourceBatches", "sync-webresources-batch"),
        ("mainForms", "update-main-form"),
        ("formXmlPatches", "patch-form-xml"),
        ("formRibbonPatches", "patch-form-ribbon"),
        ("formEvents", "update-form-events"),
        ("views", "update-view"),
        ("customApis", "create-custom-api"),
        ("securityRoleInspections", "inspect-security-role"),
        ("securityRoleCreations", "create-security-role"),
        ("securityRoleUpdates", "update-security-role"),
        ("solutionComponents", "add-solution-components"),
        ("wordTemplateInspections", "inspect-word-templates"),
    ]:
        for index, item in enumerate(require_list(requirement, key), start=1):
            steps.append({"type": step_type, "spec": item, "name": f"{step_type}-{index}"})

    flows = requirement.get("flows")
    if isinstance(flows, dict):
        for index, item in enumerate(require_list(flows, "inspections"), start=1):
            steps.append({"type": "inspect-flow", "spec": item, "name": f"inspect-flow-{index}"})
        for index, item in enumerate(require_list(flows, "linters"), start=1):
            steps.append({"type": "lint-flow", "spec": item, "name": f"lint-flow-{index}"})
        for index, item in enumerate(require_list(flows, "hardeningReviews"), start=1):
            steps.append({"type": "review-flow-hardening", "spec": item, "name": f"review-flow-hardening-{index}"})
        for index, item in enumerate(require_list(flows, "connectorReviews"), start=1):
            steps.append({"type": "review-flow-connectors", "spec": item, "name": f"review-flow-connectors-{index}"})
        for index, item in enumerate(require_list(flows, "creations"), start=1):
            steps.append({"type": "create-flow", "spec": item, "name": f"create-flow-{index}"})
        for index, item in enumerate(require_list(flows, "updates"), start=1):
            steps.append({"type": "update-flow", "spec": item, "name": f"update-flow-{index}"})
        for index, item in enumerate(require_list(flows, "triggerUrls"), start=1):
            steps.append({"type": "get-flow-trigger-url", "spec": item, "name": f"get-flow-trigger-url-{index}"})

    environment_variables = requirement.get("environmentVariables")
    if isinstance(environment_variables, dict):
        for index, item in enumerate(require_list(environment_variables, "inspections"), start=1):
            steps.append({"type": "inspect-environment-variable", "spec": item, "name": f"inspect-environment-variable-{index}"})
        for index, item in enumerate(require_list(environment_variables, "valueSets"), start=1):
            steps.append({"type": "set-environment-variable-value", "spec": item, "name": f"set-environment-variable-value-{index}"})

    security_roles = requirement.get("securityRoles")
    if isinstance(security_roles, dict):
        for index, item in enumerate(require_list(security_roles, "inspections"), start=1):
            steps.append({"type": "inspect-security-role", "spec": item, "name": f"inspect-security-role-{index}"})
        for index, item in enumerate(require_list(security_roles, "creations"), start=1):
            steps.append({"type": "create-security-role", "spec": item, "name": f"create-security-role-{index}"})
        for index, item in enumerate(require_list(security_roles, "updates"), start=1):
            steps.append({"type": "update-security-role", "spec": item, "name": f"update-security-role-{index}"})

    for index, item in enumerate(require_list(requirement, "schemaDesigns"), start=1):
        steps.append({"type": "design-dataverse-schema", "spec": item, "name": f"design-dataverse-schema-{index}"})

    for index, item in enumerate(require_list(requirement, "queryDesigns"), start=1):
        steps.append({"type": "design-dataverse-query", "spec": item, "name": f"design-dataverse-query-{index}"})

    for index, item in enumerate(require_list(requirement, "standardsReviews"), start=1):
        steps.append({"type": "review-solution-standards", "spec": item, "name": f"review-solution-standards-{index}"})

    for index, item in enumerate(require_list(requirement, "powerFxDebugs"), start=1):
        steps.append({"type": "debug-power-fx", "spec": item, "name": f"debug-power-fx-{index}"})

    for index, item in enumerate(require_list(requirement, "customConnectorDesigns"), start=1):
        steps.append({"type": "design-custom-connector", "spec": item, "name": f"design-custom-connector-{index}"})

    for index, item in enumerate(require_list(requirement, "documentGenerationPlans"), start=1):
        steps.append({"type": "plan-document-generation", "spec": item, "name": f"plan-document-generation-{index}"})

    for index, item in enumerate(require_list(requirement, "solutionPatchPlans"), start=1):
        steps.append({"type": "plan-solution-patch-merge", "spec": item, "name": f"plan-solution-patch-merge-{index}"})

    plugins = requirement.get("plugins")
    if isinstance(plugins, dict):
        for index, item in enumerate(require_list(plugins, "assemblyRegistrations"), start=1):
            steps.append({"type": "register-plugin-assembly", "options": item, "name": f"register-plugin-assembly-{index}"})
        for index, item in enumerate(require_list(plugins, "packageRegistrations"), start=1):
            steps.append({"type": "register-plugin-package", "options": item, "name": f"register-plugin-package-{index}"})
        for index, item in enumerate(require_list(plugins, "stepInspections"), start=1):
            steps.append({"type": "inspect-plugin-steps", "spec": item, "name": f"inspect-plugin-steps-{index}"})
        for index, item in enumerate(require_list(plugins, "stepStateEnsures"), start=1):
            steps.append({"type": "ensure-plugin-step-state", "spec": item, "name": f"ensure-plugin-step-state-{index}"})
        for index, item in enumerate(require_list(plugins, "pushes"), start=1):
            steps.append({"type": "push-plugin", "options": item, "name": f"push-plugin-{index}"})

    pcf = requirement.get("pcf")
    if isinstance(pcf, dict):
        for index, item in enumerate(require_list(pcf, "scaffolds"), start=1):
            steps.append({"type": "scaffold-pcf", "options": item, "name": f"scaffold-pcf-{index}"})
        for index, item in enumerate(require_list(pcf, "versions"), start=1):
            steps.append({"type": "version-pcf-solution", "options": item, "name": f"version-pcf-solution-{index}"})
        for index, item in enumerate(require_list(pcf, "deployments"), start=1):
            steps.append({"type": "deploy-pcf", "options": item, "name": f"deploy-pcf-{index}"})
        for index, item in enumerate(require_list(pcf, "bindings"), start=1):
            steps.append({"type": "bind-pcf-control", "spec": item, "name": f"bind-pcf-control-{index}"})

    deployment = requirement.get("deployment")
    if isinstance(deployment, dict):
        deployment_options = deep_copy_json(deployment)
        if "changeScope" not in deployment_options and "change_scope" not in deployment_options:
            inferred_scope = infer_deployment_change_scope(steps)
            if inferred_scope:
                deployment_options["changeScope"] = inferred_scope
        steps.append({"type": "deploy-solution", "options": deployment_options, "name": "deploy-solution"})

    validation = requirement.get("validation")
    if isinstance(validation, dict):
        steps.append({"type": "validate-delivery", "options": validation, "name": "validate-delivery"})

    for index, item in enumerate(require_list(requirement, "data"), start=1):
        steps.append({"type": "upsert-data", "options": item, "name": f"upsert-data-{index}"})

    if isinstance(versioning, dict) and when in {"after", "after-change", "after-changes"}:
        steps.append({"type": "solution-version", "options": versioning, "name": "solution-version-after"})

    return steps


def normalize_explicit_step(step: Any, index: int) -> dict[str, Any]:
    if not isinstance(step, dict):
        raise RuntimeError(f"Step {index} must be a JSON object.")
    raw_type = step.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise RuntimeError(f"Step {index} must include a non-empty 'type'.")
    normalized_type = EXPLICIT_STEP_TYPE_ALIASES.get(raw_type.strip().lower())
    if not normalized_type:
        raise RuntimeError(f"Step {index} has an unsupported type: {raw_type}")

    normalized = dict(step)
    normalized["type"] = normalized_type
    if normalized_type in SPEC_PAYLOAD_STEP_TYPES:
        if "spec" not in normalized:
            normalized["spec"] = {
                key: value
                for key, value in normalized.items()
                if key not in {"type", "name"}
            }
    elif "options" not in normalized:
        normalized["options"] = {
            key: value
            for key, value in normalized.items()
            if key not in {"type", "name"}
        }
    return normalized


def require_list(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError(f"'{key}' must be a JSON array when present.")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Item {index} in '{key}' must be a JSON object.")
    return value  # type: ignore[return-value]


def infer_deployment_change_scope(steps: list[dict[str, Any]]) -> str | None:
    relevant_types = [
        str(step.get("type") or "").strip().lower()
        for step in steps
        if str(step.get("type") or "").strip().lower()
        not in {"deploy-solution", "validate-delivery", "solution-version"}
    ]
    if not relevant_types:
        return None
    if all(step_type in TARGETED_COMPONENT_STEP_TYPES for step_type in relevant_types):
        return "targeted-component"
    return None


def build_deployment_preflight(
    *,
    steps: list[dict[str, Any]],
    deployment_defaults: dict[str, Any],
) -> dict[str, Any]:
    preferred_paths = deployment_defaults.get("preferredDeploymentPaths", {})
    preferred_paths = preferred_paths if isinstance(preferred_paths, dict) else {}
    manual_only_surfaces = {
        str(item).strip().lower()
        for item in deployment_defaults.get("manualOnlySurfaces", [])
        if str(item).strip()
    }
    timeouts = deployment_defaults.get("timeouts", {})
    timeouts = timeouts if isinstance(timeouts, dict) else {}

    preflight_steps = [
        classify_deployment_step(
            step=step,
            preferred_paths=preferred_paths,
            manual_only_surfaces=manual_only_surfaces,
            timeouts=timeouts,
        )
        for step in steps
    ]
    blocked_steps = [item for item in preflight_steps if item["manualOnly"]]

    return {
        "blocked": bool(blocked_steps),
        "stepCount": len(preflight_steps),
        "blockedStepCount": len(blocked_steps),
        "steps": preflight_steps,
        "warnings": [item["fallbackMessage"] for item in blocked_steps],
    }


def classify_deployment_step(
    *,
    step: dict[str, Any],
    preferred_paths: dict[str, Any],
    manual_only_surfaces: set[str],
    timeouts: dict[str, Any],
) -> dict[str, Any]:
    step_type = str(step.get("type") or "").strip().lower()
    metadata = STEP_DEPLOYMENT_METADATA.get(
        step_type,
        {
            "assetType": "unknown",
            "defaultPrimitive": step_type or "unknown",
            "targetedDeliverySupported": False,
        },
    )
    asset_type = metadata["assetType"]
    preferred_primitive = preferred_paths.get(asset_type)
    chosen_primitive = str(preferred_primitive).strip() if isinstance(preferred_primitive, str) and preferred_primitive.strip() else metadata["defaultPrimitive"]
    timeout_budget_seconds = resolve_timeout_budget_seconds(asset_type, step, timeouts)
    manual_only = bool(
        {
            asset_type.lower(),
            step_type,
            chosen_primitive.lower(),
        }
        & manual_only_surfaces
    )
    targeted_delivery_supported = bool(metadata["targetedDeliverySupported"])
    fallback_message = build_deployment_fallback_message(
        step=step,
        asset_type=asset_type,
        chosen_primitive=chosen_primitive,
        manual_only=manual_only,
        targeted_delivery_supported=targeted_delivery_supported,
        timeout_budget_seconds=timeout_budget_seconds,
    )

    return {
        "name": step.get("name"),
        "type": step_type,
        "assetType": asset_type,
        "chosenPrimitive": chosen_primitive,
        "targetedDeliverySupported": targeted_delivery_supported,
        "manualOnly": manual_only,
        "highRisk": manual_only or step_type == "deploy-solution",
        "timeoutBudgetSeconds": timeout_budget_seconds,
        "durationClass": classify_duration(timeout_budget_seconds),
        "fallbackMessage": fallback_message,
    }


def resolve_timeout_budget_seconds(asset_type: str, step: dict[str, Any], timeouts: dict[str, Any]) -> int | None:
    option_values = step.get("options")
    if isinstance(option_values, dict):
        for key in ("maxRuntimeSeconds", "max_runtime_seconds"):
            value = option_values.get(key)
            if isinstance(value, int) and value > 0:
                return value

    timeout_key_by_asset_type = {
        "plugin": "pluginPushSeconds",
        "solution-import": "solutionImportSeconds",
    }
    timeout_key = timeout_key_by_asset_type.get(asset_type)
    if timeout_key is None:
        return None

    configured = timeouts.get(timeout_key)
    if isinstance(configured, int) and configured > 0:
        return configured

    if asset_type == "plugin":
        return 300
    if asset_type == "solution-import":
        return 900
    return None


def classify_duration(timeout_budget_seconds: int | None) -> str:
    if timeout_budget_seconds is None:
        return "unspecified"
    if timeout_budget_seconds <= 300:
        return "short"
    if timeout_budget_seconds <= 900:
        return "medium"
    return "long"


def build_deployment_fallback_message(
    *,
    step: dict[str, Any],
    asset_type: str,
    chosen_primitive: str,
    manual_only: bool,
    targeted_delivery_supported: bool,
    timeout_budget_seconds: int | None,
) -> str:
    step_type = str(step.get("type") or "").strip().lower()
    if manual_only:
        return (
            f"This {asset_type} surface is configured as manual-only. "
            f"Do not attempt headless deployment through {chosen_primitive}; switch to the maker or repo-approved manual path."
        )

    if step_type == "deploy-solution":
        options = step.get("options", {})
        change_scope = options.get("changeScope") if isinstance(options, dict) else None
        if not change_scope and isinstance(options, dict):
            change_scope = options.get("change_scope")
        if str(change_scope or "").strip().lower() in {"targeted-component", "solution-subset"}:
            return (
                "This deployment broadens a narrower reviewed change into a solution import. "
                "Stop and get explicit approval if the targeted helper path is insufficient."
            )

    if not targeted_delivery_supported:
        return (
            f"No targeted deployment primitive is defined for {asset_type}. "
            "Prefer a repo-owned deploy entry point or escalate early instead of improvising longer retries."
        )

    if timeout_budget_seconds is not None:
        return (
            f"If {chosen_primitive} is still blocked after {timeout_budget_seconds} second(s), "
            "stop and surface the blocker instead of continuing blind retries."
        )

    return (
        f"If {chosen_primitive} becomes blocked, stop quickly and surface the blocker and fallback path."
    )


def enforce_deployment_preflight(deployment_preflight: dict[str, Any]) -> None:
    blocked_steps = [
        item
        for item in deployment_preflight.get("steps", [])
        if isinstance(item, dict) and item.get("manualOnly")
    ]
    if not blocked_steps:
        return

    blocked_details = "; ".join(
        f"{item.get('name') or item.get('type')}: {item.get('fallbackMessage')}"
        for item in blocked_steps
    )
    raise RuntimeError(f"Deployment preflight blocked manual-only surfaces. {blocked_details}")


def step_requires_live_connection(step: dict[str, Any]) -> bool:
    if step["type"] in LOCAL_ONLY_STEP_TYPES:
        return False
    if step["type"] == "review-flow-connectors":
        spec = step.get("spec", {})
        if flow_spec_has_local_definition(spec):
            return False
        return True
    if step["type"] == "lint-flow":
        spec = step.get("spec", {})
        if flow_spec_has_local_definition(spec):
            return False
        return True
    if step["type"] == "review-flow-hardening":
        spec = step.get("spec", {})
        if flow_spec_has_local_definition(spec):
            return False
        return True
    if step["type"] == "validate-delivery":
        options = step.get("options", {})
        return bool(isinstance(options, dict) and options.get("livePreflight"))
    if step["type"] == "solution-version":
        options = step.get("options", {})
        return bool(isinstance(options, dict) and options.get("online"))
    if step["type"] == "deploy-solution":
        options = step.get("options", {})
        if not isinstance(options, dict):
            return True
        return not bool(options.get("skipImport"))
    return True


def summarize_step(step: dict[str, Any], index: int) -> dict[str, Any]:
    summary = {
        "index": index,
        "name": step.get("name") or default_step_name(step, index),
        "type": step["type"],
    }
    if "spec" in step and isinstance(step["spec"], dict):
        summary["keys"] = sorted(step["spec"].keys())
    elif "options" in step and isinstance(step["options"], dict):
        summary["keys"] = sorted(step["options"].keys())
    return summary


def default_step_name(step: dict[str, Any], index: int) -> str:
    return f"{step['type']}-{index}"


def flow_spec_has_local_definition(spec: Any) -> bool:
    return isinstance(spec, dict) and any(spec.get(key) for key in ("clientData", "clientDataPath", "definition", "definitionPath"))


def execute_step(
    *,
    step: dict[str, Any],
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    step_type = step["type"]

    if step_type == "create-table":
        return run_spec_helper("create_table.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "create-field":
        return run_spec_helper("create_field.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "create-lookup":
        return run_spec_helper("create_lookup.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "inspect-flow":
        return run_flow_inspection_helper(
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
        )
    if step_type == "lint-flow":
        return run_flow_lint_helper(
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
        )
    if step_type == "review-flow-hardening":
        return run_flow_hardening_helper(
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
        )
    if step_type == "review-flow-connectors":
        return run_flow_connector_review_helper(
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
        )
    if step_type == "create-flow":
        return run_spec_helper(
            "create_flow.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "update-flow":
        return run_spec_helper(
            "update_flow.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "get-flow-trigger-url":
        return run_spec_helper(
            "get_flow_trigger_url.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
            inject_selected_solution=False,
        )
    if step_type == "update-main-form":
        return run_spec_helper("update_main_form.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "patch-form-xml":
        return run_spec_helper(
            "patch_form_xml.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "patch-form-ribbon":
        return run_spec_helper(
            "patch_form_ribbon.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "update-form-events":
        return run_spec_helper("update_form_events.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "bind-pcf-control":
        return run_spec_helper(
            "bind_pcf_control.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "update-view":
        return run_spec_helper("update_view.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "set-table-icon":
        return run_spec_helper("set_table_icon.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "sync-webresource":
        return run_spec_helper(
            "sync_webresource.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "sync-webresources-batch":
        return run_spec_helper(
            "sync_webresources_batch.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "create-custom-api":
        return run_spec_helper("create_custom_api.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "inspect-environment-variable":
        return run_spec_helper(
            "inspect_environment_variable.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
            inject_selected_solution=False,
        )
    if step_type == "set-environment-variable-value":
        return run_spec_helper(
            "set_environment_variable_value.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
            inject_selected_solution=False,
        )
    if step_type == "inspect-security-role":
        return run_spec_helper(
            "inspect_security_role.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
            inject_selected_solution=False,
        )
    if step_type == "create-security-role":
        return run_spec_helper(
            "create_security_role.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "update-security-role":
        return run_spec_helper(
            "update_security_role.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "add-solution-components":
        return run_spec_helper("add_solution_components.py", step["spec"], repo=repo, connection=connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose)
    if step_type == "design-dataverse-schema":
        return run_local_spec_helper("design_dataverse_schema.py", step["spec"], repo=repo)
    if step_type == "design-dataverse-query":
        return run_local_spec_helper("design_dataverse_query.py", step["spec"], repo=repo)
    if step_type == "review-solution-standards":
        return run_local_repo_helper("review_solution_standards.py", step["spec"], repo=repo)
    if step_type == "debug-power-fx":
        return run_local_spec_helper("debug_power_fx.py", step["spec"], repo=repo)
    if step_type == "design-custom-connector":
        return run_local_spec_helper("design_custom_connector.py", step["spec"], repo=repo)
    if step_type == "plan-document-generation":
        return run_local_spec_helper("plan_document_generation.py", step["spec"], repo=repo)
    if step_type == "plan-solution-patch-merge":
        return run_local_spec_helper("plan_solution_patch_merge.py", step["spec"], repo=repo)
    if step_type == "inspect-word-templates":
        return run_inspect_word_templates_helper(step.get("spec", {}), repo=repo)
    if step_type == "register-plugin-assembly":
        return run_plugin_registration_helper(
            "register_plugin_headless.py",
            step.get("options", {}),
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            package_mode=False,
        )
    if step_type == "register-plugin-package":
        return run_plugin_registration_helper(
            "register_plugin_package_headless.py",
            step.get("options", {}),
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            package_mode=True,
        )
    if step_type == "inspect-plugin-steps":
        return run_spec_helper(
            "inspect_plugin_steps.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "ensure-plugin-step-state":
        return run_spec_helper(
            "ensure_plugin_step_state.py",
            step["spec"],
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
            extra_args=["--repo-root", str(repo)],
        )
    if step_type == "push-plugin":
        return run_push_plugin_helper(
            step.get("options", {}),
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
        )
    if step_type == "scaffold-pcf":
        return run_scaffold_pcf_helper(step.get("options", {}), repo=repo)
    if step_type == "version-pcf-solution":
        return run_version_pcf_solution_helper(step.get("options", {}), repo=repo)
    if step_type == "deploy-pcf":
        return run_deploy_pcf_helper(step.get("options", {}), repo=repo, connection=connection)
    if step_type == "upsert-data":
        return run_upsert_data_helper(
            step.get("options", {}),
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
        )
    if step_type == "solution-version":
        return run_solution_version_helper(step.get("options", {}), repo=repo, connection=connection)
    if step_type == "deploy-solution":
        return run_deploy_solution_helper(step.get("options", {}), repo=repo, connection=connection)
    if step_type == "validate-delivery":
        return run_validate_delivery_helper(
            step.get("options", {}),
            repo=repo,
            connection=connection,
            auth_flow=auth_flow,
            force_prompt=force_prompt,
            verbose=verbose,
        )

    raise RuntimeError(f"Unsupported step type: {step_type}")


def run_spec_helper(
    script_name: str,
    spec: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
    extra_args: list[str] | None = None,
    inject_selected_solution: bool = True,
) -> Any:
    if not isinstance(spec, dict):
        raise RuntimeError(f"{script_name} requires a JSON object 'spec'.")

    final_spec = deep_copy_json(spec)
    if inject_selected_solution and connection and script_name_to_step_type(script_name) in SOLUTION_INJECTED_STEP_TYPES:
        final_spec = apply_selected_solution_to_spec(final_spec, connection)

    with temporary_json_file(final_spec) as spec_path:
        command = [
            sys.executable,
            str(Path(__file__).resolve().parent / script_name),
            "--spec",
            str(spec_path),
        ]
        if extra_args:
            command.extend(extra_args)
        command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))
        completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_local_spec_helper(script_name: str, spec: dict[str, Any], *, repo: Path) -> Any:
    if not isinstance(spec, dict):
        raise RuntimeError(f"{script_name} requires a JSON object 'spec'.")

    with temporary_json_file(spec) as spec_path:
        command = [
            sys.executable,
            str(Path(__file__).resolve().parent / script_name),
            "--spec",
            str(spec_path),
            "--repo-root",
            str(repo),
        ]
        completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_local_repo_helper(script_name: str, options: dict[str, Any], *, repo: Path) -> Any:
    if options is not None and not isinstance(options, dict):
        raise RuntimeError(f"{script_name} options must be a JSON object when present.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / script_name),
        "--repo-root",
        str(repo),
    ]
    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_inspect_word_templates_helper(spec: dict[str, Any], *, repo: Path) -> Any:
    if not isinstance(spec, dict):
        raise RuntimeError("inspect-word-templates requires a JSON object spec.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "inspect_word_templates.py"),
        "--repo-root",
        str(repo),
    ]
    if value := spec.get("path"):
        command.extend(["--path", str(resolve_repo_path(repo, value))])
    if spec.get("recurse"):
        command.append("--recurse")
    if spec.get("summaryOnly"):
        command.append("--summary-only")

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_flow_inspection_helper(
    spec: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    return run_spec_helper(
        "inspect_flow.py",
        spec,
        repo=repo,
        connection=connection,
        auth_flow=auth_flow,
        force_prompt=force_prompt,
        verbose=verbose,
        extra_args=["--repo-root", str(repo)],
        inject_selected_solution=False,
    )


def run_flow_lint_helper(
    spec: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    if not isinstance(spec, dict):
        raise RuntimeError("lint-flow requires a JSON object 'spec'.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "lint_flow.py"),
        "--spec",
        json.dumps(spec),
        "--repo-root",
        str(repo),
    ]
    needs_live = not any(spec.get(key) for key in ("clientData", "clientDataPath", "definition", "definitionPath"))
    if needs_live:
        command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_flow_hardening_helper(
    spec: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    if not isinstance(spec, dict):
        raise RuntimeError("review-flow-hardening requires a JSON object 'spec'.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "review_flow_hardening.py"),
        "--spec",
        json.dumps(spec),
        "--repo-root",
        str(repo),
    ]
    needs_live = not any(spec.get(key) for key in ("clientData", "clientDataPath", "definition", "definitionPath"))
    if needs_live:
        command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_flow_connector_review_helper(
    spec: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    if not isinstance(spec, dict):
        raise RuntimeError("review-flow-connectors requires a JSON object 'spec'.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "review_flow_connectors.py"),
        "--spec",
        json.dumps(spec),
        "--repo-root",
        str(repo),
    ]
    if not flow_spec_has_local_definition(spec):
        command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_plugin_registration_helper(
    script_name: str,
    options: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
    package_mode: bool,
) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError(f"{script_name} options must be a JSON object.")
    spec = options.get("spec")
    if not isinstance(spec, dict):
        raise RuntimeError(f"{script_name} requires a nested 'spec' JSON object.")

    final_spec = deep_copy_json(spec)
    if connection:
        final_spec = apply_selected_solution_to_spec(final_spec, connection)

    with temporary_json_file(final_spec) as spec_path:
        command = [
            sys.executable,
            str(Path(__file__).resolve().parent / script_name),
            "--spec",
            str(spec_path),
            "--repo-root",
            str(repo),
        ]

        if value := options.get("project"):
            command.extend(["--project", str(resolve_repo_path(repo, value))])
        if package_mode:
            if value := options.get("packageFile"):
                command.extend(["--package-file", str(resolve_repo_path(repo, value))])
            if options.get("skipPack"):
                command.append("--skip-pack")
        else:
            if value := options.get("pluginFile"):
                command.extend(["--plugin-file", str(resolve_repo_path(repo, value))])
            if options.get("skipBuild"):
                command.append("--skip-build")
            if value := options.get("framework"):
                command.extend(["--framework", str(value)])

        if value := options.get("configuration"):
            command.extend(["--configuration", str(value)])

        command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))
        completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_push_plugin_helper(
    options: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("push-plugin options must be a JSON object.")
    plugin_id = options.get("pluginId")
    if not plugin_id:
        raise RuntimeError("push-plugin requires 'pluginId'.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "push_plugin.py"),
        "--repo-root",
        str(repo),
        "--plugin-id",
        str(plugin_id),
    ]
    if value := options.get("project"):
        command.extend(["--project", str(resolve_repo_path(repo, value))])
    if value := options.get("pluginFile"):
        command.extend(["--plugin-file", str(resolve_repo_path(repo, value))])
    if value := options.get("type"):
        command.extend(["--type", str(value)])
    if value := options.get("configuration"):
        command.extend(["--configuration", str(value)])
    if value := options.get("framework"):
        command.extend(["--framework", str(value)])
    if options.get("skipBuild"):
        command.append("--skip-build")
    if options.get("verifyStepState"):
        command.append("--verify-step-state")
    if options.get("skipStepStateVerification"):
        command.append("--skip-step-state-verification")
    if options.get("autoReconcileStepState"):
        command.append("--auto-reconcile-step-state")
    if options.get("skipStepStateReconcile"):
        command.append("--skip-step-state-reconcile")
    if value := options.get("stepStateSpec"):
        command.extend(["--step-state-spec", json.dumps(value) if isinstance(value, (dict, list)) else str(value)])
    if value := options.get("maxRuntimeSeconds") or options.get("max_runtime_seconds"):
        command.extend(["--max-runtime-seconds", str(value)])

    if connection:
        command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))
    elif value := options.get("environmentUrl"):
        command.extend(["--environment-url", str(value)])

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_scaffold_pcf_helper(options: dict[str, Any], *, repo: Path) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("scaffold-pcf options must be a JSON object.")
    namespace = options.get("namespace")
    name = options.get("name")
    if not namespace or not name:
        raise RuntimeError("scaffold-pcf requires 'namespace' and 'name'.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "scaffold_pcf_control.py"),
        "--repo-root",
        str(repo),
        "--namespace",
        str(namespace),
        "--name",
        str(name),
    ]
    if value := options.get("outputDir"):
        command.extend(["--output-dir", str(resolve_repo_path(repo, value))])
    if value := options.get("template"):
        command.extend(["--template", str(value)])
    if value := options.get("framework"):
        command.extend(["--framework", str(value)])
    if options.get("runNpmInstall"):
        command.append("--run-npm-install")

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_deploy_pcf_helper(options: dict[str, Any], *, repo: Path, connection: dict[str, Any] | None) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("deploy-pcf options must be a JSON object.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "deploy_pcf.py"),
        "--repo-root",
        str(repo),
    ]
    if value := options.get("project"):
        command.extend(["--project", str(resolve_repo_path(repo, value))])
    if value := options.get("mode"):
        command.extend(["--mode", str(value)])
    if value := options.get("configuration"):
        command.extend(["--configuration", str(value)])
    if value := options.get("artifactFile"):
        command.extend(["--artifact-file", str(resolve_repo_path(repo, value))])
    if value := options.get("publisherPrefix"):
        command.extend(["--publisher-prefix", str(value)])

    solution_name = options.get("solutionName")
    if not solution_name and connection:
        solution_name = connection.get("solution_unique_name")
    if solution_name:
        command.extend(["--solution-name", str(solution_name)])

    if value := options.get("environmentUrl"):
        command.extend(["--environment-url", str(value)])
    elif connection and connection.get("environment_url"):
        command.extend(["--environment-url", connection["environment_url"]])

    if options.get("skipInstall"):
        command.append("--skip-install")
    if options.get("skipBuild"):
        command.append("--skip-build")
    if options.get("skipSolutionBuild"):
        command.append("--skip-solution-build")
    if options.get("production"):
        command.append("--production")
    if options.get("incremental"):
        command.append("--incremental")
    if options.get("allowVersionMismatch"):
        command.append("--allow-version-mismatch")
    if options.get("runCheck"):
        command.append("--run-check")
    if value := options.get("checkerOutput"):
        command.extend(["--checker-output", str(resolve_repo_path(repo, value))])
    if options.get("skipImport"):
        command.append("--skip-import")
    if options.get("publishChanges"):
        command.append("--publish-changes")
    if options.get("activatePlugins"):
        command.append("--activate-plugins")
    if options.get("forceOverwrite"):
        command.append("--force-overwrite")
    if options.get("skipDependencyCheck"):
        command.append("--skip-dependency-check")
    if options.get("importAsHolding"):
        command.append("--import-as-holding")
    if options.get("stageAndUpgrade"):
        command.append("--stage-and-upgrade")
    if options.get("convertToManaged"):
        command.append("--convert-to-managed")
    if value := options.get("lockRetries"):
        command.extend(["--lock-retries", str(value)])
    if value := options.get("lockWaitSeconds"):
        command.extend(["--lock-wait-seconds", str(value)])
    if value := options.get("verbosity"):
        command.extend(["--verbosity", str(value)])

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_version_pcf_solution_helper(options: dict[str, Any], *, repo: Path) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("version-pcf-solution options must be a JSON object.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "version_pcf_solution.py"),
        "--repo-root",
        str(repo),
    ]
    if value := options.get("project"):
        command.extend(["--project", str(resolve_repo_path(repo, value))])
    if value := options.get("version"):
        command.extend(["--version", str(value)])
    if value := options.get("increment"):
        command.extend(["--increment", str(value)])
    if options.get("updateAllManifests"):
        command.append("--update-all-manifests")

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_upsert_data_helper(
    options: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("upsert-data options must be a JSON object.")
    table = options.get("table")
    data = options.get("data")
    if not table or not isinstance(data, dict):
        raise RuntimeError("upsert-data requires 'table' and a JSON object 'data'.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "upsert_data.py"),
        "--repo-root",
        str(repo),
        "--mode",
        str(options.get("mode") or "upsert"),
        "--table",
        str(table),
        "--data",
        json.dumps(data),
    ]
    if value := options.get("id"):
        command.extend(["--id", str(value)])
    if value := options.get("key"):
        command.extend(["--key", json.dumps(value)])
    if options.get("verify"):
        command.append("--verify")
    command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_solution_version_helper(options: dict[str, Any], *, repo: Path, connection: dict[str, Any] | None) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("solution-version options must be a JSON object.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "solution_version.py"),
        "--repo-root",
        str(repo),
    ]
    if value := options.get("solutionPath"):
        command.extend(["--solution-path", str(resolve_repo_path(repo, value))])
    if value := options.get("version"):
        command.extend(["--version", str(value)])
    if value := options.get("increment"):
        command.extend(["--increment", str(value)])
    if value := options.get("buildVersion"):
        command.extend(["--build-version", str(value)])
    if value := options.get("revisionVersion"):
        command.extend(["--revision-version", str(value)])
    if options.get("online"):
        command.append("--online")

    solution_name = options.get("solutionName")
    if not solution_name and connection:
        solution_name = connection.get("solution_unique_name")
    if solution_name:
        command.extend(["--solution-name", str(solution_name)])

    environment_url = options.get("environmentUrl")
    if not environment_url and connection:
        environment_url = connection.get("environment_url")
    if environment_url:
        command.extend(["--environment-url", str(environment_url)])

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_deploy_solution_helper(options: dict[str, Any], *, repo: Path, connection: dict[str, Any] | None) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("deploy-solution options must be a JSON object.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "deploy_solution.py"),
        "--repo-root",
        str(repo),
    ]
    if value := options.get("solutionFolder"):
        command.extend(["--solution-folder", str(resolve_repo_path(repo, value))])
    if value := options.get("zipfile"):
        command.extend(["--zipfile", str(resolve_repo_path(repo, value))])
    if value := options.get("packageType"):
        command.extend(["--package-type", str(value)])
    if value := options.get("settingsFile"):
        command.extend(["--settings-file", str(resolve_repo_path(repo, value))])
    if options.get("publishChanges"):
        command.append("--publish-changes")
    if options.get("activatePlugins"):
        command.append("--activate-plugins")
    if options.get("forceOverwrite"):
        command.append("--force-overwrite")
    if options.get("skipDependencyCheck"):
        command.append("--skip-dependency-check")
    if options.get("importAsHolding"):
        command.append("--import-as-holding")
    if options.get("stageAndUpgrade"):
        command.append("--stage-and-upgrade")
    if options.get("convertToManaged"):
        command.append("--convert-to-managed")
    if options.get("runCheck"):
        command.append("--run-check")
    if value := options.get("checkerOutput"):
        command.extend(["--checker-output", str(resolve_repo_path(repo, value))])
    if value := options.get("changeScope") or options.get("change_scope"):
        command.extend(["--change-scope", str(value)])
    if options.get("sharedUnmanagedEnvironment") or options.get("shared_unmanaged_environment"):
        command.append("--shared-unmanaged-environment")
    if options.get("allowBroadImport") or options.get("allow_broad_import"):
        command.append("--allow-broad-import")
    if value := options.get("changeSummary") or options.get("change_summary"):
        command.extend(["--change-summary", str(value)])
    if options.get("skipPack"):
        command.append("--skip-pack")
    if options.get("artifactGeneratedThisSession") or options.get("artifact_generated_this_session"):
        command.append("--artifact-generated-this-session")
    if options.get("explicitArtifactSelection") or options.get("explicit_artifact_selection"):
        command.append("--explicit-artifact-selection")
    if options.get("skipImport"):
        command.append("--skip-import")
    if value := options.get("lockRetries"):
        command.extend(["--lock-retries", str(value)])
    if value := options.get("lockWaitSeconds"):
        command.extend(["--lock-wait-seconds", str(value)])
    if value := options.get("maxRuntimeSeconds") or options.get("max_runtime_seconds"):
        command.extend(["--max-runtime-seconds", str(value)])

    environment_url = options.get("environmentUrl")
    if not environment_url and connection:
        environment_url = connection.get("environment_url")
    if environment_url:
        command.extend(["--environment-url", str(environment_url)])

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def run_validate_delivery_helper(
    options: dict[str, Any],
    *,
    repo: Path,
    connection: dict[str, Any] | None,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> Any:
    if not isinstance(options, dict):
        raise RuntimeError("validate-delivery options must be a JSON object.")

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "validate_delivery.py"),
        "--repo-root",
        str(repo),
    ]
    if value := options.get("pluginProject"):
        command.extend(["--plugin-project", str(resolve_repo_path(repo, value))])
    for project in options.get("pcfProjects", []) if isinstance(options.get("pcfProjects"), list) else []:
        command.extend(["--pcf-project", str(resolve_repo_path(repo, project))])
    if value := options.get("wordTemplatesPath"):
        command.extend(["--word-templates-path", str(resolve_repo_path(repo, value))])
    if value := options.get("solutionFolder"):
        command.extend(["--solution-folder", str(resolve_repo_path(repo, value))])
    if value := options.get("zipfile"):
        command.extend(["--zipfile", str(resolve_repo_path(repo, value))])
    if value := options.get("checkerOutput"):
        command.extend(["--checker-output", str(resolve_repo_path(repo, value))])
    if value := options.get("solutionName"):
        command.extend(["--solution-name", str(value)])
    elif connection and connection.get("solution_unique_name"):
        command.extend(["--solution-name", str(connection["solution_unique_name"])])

    if options.get("livePreflight"):
        command.append("--live-preflight")
    if options.get("runSolutionCheck"):
        command.append("--run-solution-check")
    if options.get("skipPluginBuild"):
        command.append("--skip-plugin-build")
    if options.get("skipPcfBuild"):
        command.append("--skip-pcf-build")
    if options.get("skipWordTemplates"):
        command.append("--skip-word-templates")
    if options.get("skipSolutionPack"):
        command.append("--skip-solution-pack")
    if options.get("skipNpmInstall"):
        command.append("--skip-npm-install")

    if options.get("livePreflight"):
        command.extend(build_child_live_args(connection, auth_flow=auth_flow, force_prompt=force_prompt, verbose=verbose))

    completed = run_command(command, cwd=repo)
    return parse_command_output(completed.stdout)


def build_child_live_args(
    connection: dict[str, Any] | None,
    *,
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> list[str]:
    if not connection:
        raise RuntimeError("This step requires a live connection, but no connection was resolved.")

    args = [
        "--environment-url",
        str(connection["environment_url"]),
        "--username",
        str(connection["username"]),
        "--auth-flow",
        auth_flow,
    ]
    if connection.get("tenant_id"):
        args.extend(["--tenant-id", str(connection["tenant_id"])])
    if force_prompt:
        args.append("--force-prompt")
    if verbose:
        args.append("--verbose")
    return args


def parse_command_output(stdout: str) -> Any:
    stripped = stdout.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def resolve_repo_path(repo: Path, value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path.resolve()
    return (repo / path).resolve()


def script_name_to_step_type(script_name: str) -> str:
    mapping = {
        "create_table.py": "create-table",
        "create_field.py": "create-field",
        "create_lookup.py": "create-lookup",
        "inspect_flow.py": "inspect-flow",
        "create_flow.py": "create-flow",
        "update_flow.py": "update-flow",
        "get_flow_trigger_url.py": "get-flow-trigger-url",
        "patch_form_xml.py": "patch-form-xml",
        "patch_form_ribbon.py": "patch-form-ribbon",
        "inspect_environment_variable.py": "inspect-environment-variable",
        "set_environment_variable_value.py": "set-environment-variable-value",
        "set_table_icon.py": "set-table-icon",
        "bind_pcf_control.py": "bind-pcf-control",
        "sync_webresource.py": "sync-webresource",
        "create_custom_api.py": "create-custom-api",
        "inspect_security_role.py": "inspect-security-role",
        "create_security_role.py": "create-security-role",
        "update_security_role.py": "update-security-role",
        "inspect_plugin_steps.py": "inspect-plugin-steps",
        "ensure_plugin_step_state.py": "ensure-plugin-step-state",
        "add_solution_components.py": "add-solution-components",
        "register_plugin_headless.py": "register-plugin-assembly",
        "register_plugin_package_headless.py": "register-plugin-package",
    }
    return mapping[script_name]


def deep_copy_json(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value))


class temporary_json_file:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.path: Path | None = None

    def __enter__(self) -> Path:
        temporary = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        temporary.close()
        self.path = Path(temporary.name)
        self.path.write_text(json.dumps(self.payload, indent=2) + "\n", encoding="utf-8")
        return self.path

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.path:
            self.path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
