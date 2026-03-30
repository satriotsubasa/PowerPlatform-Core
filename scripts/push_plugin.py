#!/usr/bin/env python3
"""Build and push an existing Dataverse plug-in assembly or package."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from powerplatform_common import (
    build_plugin_step_state_contract_from_profile,
    canonical_plugin_step_mode,
    canonical_plugin_step_stage,
    infer_plugin_assembly_file,
    infer_plugin_project,
    load_plugin_step_state_contract,
    normalize_plugin_step_state,
    plugin_step_matches_selector,
    plugin_step_selector_from_payload,
    read_json_argument,
    repo_root,
    resolve_environment_url,
    resolve_live_connection,
    run_command,
    run_dataverse_tool,
    write_json_output,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a plug-in project and push it to Dataverse.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect when inferring the plug-in project.")
    parser.add_argument("--project", help="Path to the plug-in .csproj. Defaults from discovery.")
    parser.add_argument("--plugin-id", required=True, help="Existing Dataverse plug-in assembly or package ID.")
    parser.add_argument("--plugin-file", help="Assembly DLL or NuGet package file to push. Inferred for Assembly type.")
    parser.add_argument("--type", default="Assembly", choices=["Assembly", "Nuget"])
    parser.add_argument("--configuration", default="Debug")
    parser.add_argument("--framework", help="Override target framework when inferring the assembly output path.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before verifying or reconciling step state.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool when plug-in step verification is enabled.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--verify-step-state", action="store_true", help="Capture step state before and after push and fail on unexpected drift.")
    parser.add_argument("--step-state-spec", help="JSON object or path describing explicit desired plug-in step states.")
    parser.add_argument("--auto-reconcile-step-state", action="store_true", help="Reapply expected step enablement when verification detects drift.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    project_path = Path(args.project).resolve() if args.project else infer_plugin_project(repo)
    if not project_path.exists():
        raise RuntimeError(f"Plug-in project not found: {project_path}")

    if not args.skip_build:
        run_command(["dotnet", "build", str(project_path), "-c", args.configuration], cwd=repo)

    plugin_file = Path(args.plugin_file).resolve() if args.plugin_file else infer_plugin_file(
        project_path,
        configuration=args.configuration,
        plugin_type=args.type,
        framework=args.framework,
    )

    explicit_contract = load_explicit_step_state_contract(args.step_state_spec)
    profile_contract = load_plugin_step_state_contract(repo)
    should_verify = args.verify_step_state or args.auto_reconcile_step_state or bool(explicit_contract) or bool(profile_contract)

    connection: dict[str, Any] | None = None
    before_snapshot: dict[str, Any] | None = None
    if should_verify:
        connection = resolve_live_connection(
            environment_url=args.environment_url,
            username=args.username,
            tenant_id=args.tenant_id,
            auth_dialog=args.auth_dialog,
            target_url=args.target_url,
            auto_validate=args.auto_validate,
        )
        before_snapshot = inspect_plugin_steps_payload(
            repo=repo,
            plugin_id=args.plugin_id,
            plugin_type=args.type,
            connection=connection,
            auth_flow=args.auth_flow,
            force_prompt=args.force_prompt,
            verbose=args.verbose,
        )

    push_environment_url = connection["environment_url"] if connection else resolve_environment_url(args.environment_url)
    command = [
        "pac",
        "plugin",
        "push",
        "--pluginId",
        args.plugin_id,
        "--pluginFile",
        str(plugin_file),
        "--type",
        args.type,
        "--configuration",
        args.configuration,
        "--environment",
        push_environment_url,
    ]
    run_command(command, cwd=repo)

    verification: dict[str, Any] | None = None
    if should_verify:
        assert connection is not None
        assert before_snapshot is not None
        after_snapshot = inspect_plugin_steps_payload(
            repo=repo,
            plugin_id=args.plugin_id,
            plugin_type=args.type,
            connection=connection,
            auth_flow=args.auth_flow,
            force_prompt=args.force_prompt,
            verbose=args.verbose,
        )
        expectations = build_step_state_expectations(
            before_snapshot.get("steps", []),
            explicit_contract=explicit_contract,
            profile_contract=profile_contract,
        )
        drift = detect_step_state_drift(expectations, after_snapshot.get("steps", []))
        reconciled = None
        final_snapshot = after_snapshot
        if drift and args.auto_reconcile_step_state:
            reconcile_spec = build_reconcile_spec(args.plugin_id, args.type, expectations, drift)
            if reconcile_spec["steps"]:
                reconciled = ensure_plugin_step_state_payload(
                    repo=repo,
                    spec=reconcile_spec,
                    connection=connection,
                    auth_flow=args.auth_flow,
                    force_prompt=args.force_prompt,
                    verbose=args.verbose,
                )
                final_snapshot = inspect_plugin_steps_payload(
                    repo=repo,
                    plugin_id=args.plugin_id,
                    plugin_type=args.type,
                    connection=connection,
                    auth_flow=args.auth_flow,
                    force_prompt=args.force_prompt,
                    verbose=args.verbose,
                )
                drift = detect_step_state_drift(expectations, final_snapshot.get("steps", []))

        verification = {
            "verified": True,
            "expectedStepCount": len(expectations),
            "before": before_snapshot,
            "after": after_snapshot,
            "final": final_snapshot,
            "drift": drift,
            "reconciled": reconciled,
        }
        if drift:
            raise RuntimeError(format_step_state_drift_message(drift))

    write_json_output(
        {
            "success": True,
            "project": str(project_path),
            "plugin_file": str(plugin_file),
            "plugin_id": args.plugin_id,
            "type": args.type,
            "configuration": args.configuration,
            "built": not args.skip_build,
            "pushed": True,
            "stepStateVerification": verification,
        },
        args.output,
    )
    return 0


def infer_plugin_file(project_path: Path, *, configuration: str, plugin_type: str, framework: str | None) -> Path:
    if plugin_type.lower() == "nuget":
        raise RuntimeError("Nuget push requires --plugin-file explicitly.")
    return infer_plugin_assembly_file(project_path, configuration=configuration, framework=framework)


def load_explicit_step_state_contract(raw_value: str | None) -> list[dict[str, Any]]:
    if not raw_value:
        return []
    payload = read_json_argument(raw_value)
    if isinstance(payload, dict):
        if "steps" in payload and isinstance(payload["steps"], list):
            items = payload["steps"]
        else:
            items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        raise RuntimeError("--step-state-spec must resolve to a JSON object or array.")

    contract = []
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("--step-state-spec items must be JSON objects.")
        normalized = build_plugin_step_state_contract_from_profile({"criticalPluginSteps": [item]})
        if not normalized:
            raise RuntimeError("Each step-state spec item must contain a selector and desiredState.")
        desired_state = normalize_plugin_step_state(item.get("desiredState"))
        if not desired_state:
            raise RuntimeError("Each step-state spec item requires desiredState: Enabled or Disabled.")
        normalized_item = dict(normalized[0])
        normalized_item["desiredState"] = desired_state
        contract.append(normalized_item)
    return contract


def inspect_plugin_steps_payload(
    *,
    repo: Path,
    plugin_id: str,
    plugin_type: str,
    connection: dict[str, Any],
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> dict[str, Any]:
    spec = {
        "pluginId": plugin_id,
        "pluginType": plugin_type,
    }
    if connection.get("solution_unique_name"):
        spec["solutionUniqueName"] = connection["solution_unique_name"]

    with temporary_spec_file(spec) as spec_path:
        command = [
            "plugin",
            "--mode",
            "list-steps",
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
            command.extend(["--tenant-id", connection["tenant_id"]])
        if force_prompt:
            command.append("--force-prompt")
        if verbose:
            command.append("--verbose")
        completed = run_dataverse_tool(command, cwd=repo)
    return json.loads(completed.stdout)


def ensure_plugin_step_state_payload(
    *,
    repo: Path,
    spec: dict[str, Any],
    connection: dict[str, Any],
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
) -> dict[str, Any]:
    with temporary_spec_file(spec) as spec_path:
        command = [
            "plugin",
            "--mode",
            "ensure-step-state",
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
            command.extend(["--tenant-id", connection["tenant_id"]])
        if force_prompt:
            command.append("--force-prompt")
        if verbose:
            command.append("--verbose")
        completed = run_dataverse_tool(command, cwd=repo)
    return json.loads(completed.stdout)


def build_step_state_expectations(
    before_steps: list[Any],
    *,
    explicit_contract: list[dict[str, Any]],
    profile_contract: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expectations = [dict(item) for item in explicit_contract] + [dict(item) for item in profile_contract]
    for item in before_steps:
        if not isinstance(item, dict):
            continue
        if any(plugin_step_matches_selector(item, selector) for selector in expectations):
            continue
        selector = plugin_step_selector_from_payload(item)
        if not selector:
            continue
        selector["desiredState"] = normalize_plugin_step_state(item.get("stateLabel") or item.get("stateCode")) or "Enabled"
        expectations.append(selector)
    return expectations


def detect_step_state_drift(expectations: list[dict[str, Any]], current_steps: list[Any]) -> list[dict[str, Any]]:
    typed_steps = [item for item in current_steps if isinstance(item, dict)]
    drift: list[dict[str, Any]] = []
    for expectation in expectations:
        matches = [item for item in typed_steps if plugin_step_matches_selector(item, expectation)]
        if not matches:
            drift.append(
                {
                    "selector": summarize_selector(expectation),
                    "expectedState": expectation["desiredState"],
                    "actualState": "Missing",
                }
            )
            continue

        if len(matches) > 1:
            drift.append(
                {
                    "selector": summarize_selector(expectation),
                    "expectedState": expectation["desiredState"],
                    "actualState": f"Ambiguous ({len(matches)} matches)",
                }
            )
            continue

        actual_state = normalize_plugin_step_state(matches[0].get("stateLabel") or matches[0].get("stateCode")) or "Unknown"
        if actual_state != expectation["desiredState"]:
            drift.append(
                {
                    "selector": summarize_selector(expectation),
                    "expectedState": expectation["desiredState"],
                    "actualState": actual_state,
                }
            )
    return drift


def build_reconcile_spec(
    plugin_id: str,
    plugin_type: str,
    expectations: list[dict[str, Any]],
    drift: list[dict[str, Any]],
) -> dict[str, Any]:
    steps = []
    drift_selectors = {item["selector"] for item in drift if item.get("actualState") != "Missing" and not str(item.get("actualState", "")).startswith("Ambiguous")}
    for expectation in expectations:
        selector = summarize_selector(expectation)
        if selector not in drift_selectors:
            continue
        step = {
            key: value
            for key, value in expectation.items()
            if key in {
                "sdkMessageProcessingStepId",
                "name",
                "pluginTypeName",
                "messageName",
                "primaryEntityLogicalName",
                "stage",
                "mode",
                "desiredState",
            }
        }
        steps.append(step)
    return {
        "pluginId": plugin_id,
        "pluginType": plugin_type,
        "steps": steps,
    }


def summarize_selector(selector: dict[str, Any]) -> str:
    parts = []
    for key in ("name", "pluginTypeName", "messageName", "primaryEntityLogicalName"):
        value = selector.get(key)
        if value:
            parts.append(f"{key}={value}")
    if stage := canonical_plugin_step_stage(selector.get("stage")):
        parts.append(f"stage={stage}")
    if mode := canonical_plugin_step_mode(selector.get("mode")):
        parts.append(f"mode={mode}")
    if not parts and selector.get("sdkMessageProcessingStepId"):
        parts.append(f"id={selector['sdkMessageProcessingStepId']}")
    return ", ".join(parts) if parts else "<unknown-step>"


def format_step_state_drift_message(drift: list[dict[str, Any]]) -> str:
    details = "; ".join(
        f"{item['selector']} expected {item['expectedState']} but found {item['actualState']}"
        for item in drift
    )
    return f"Plug-in step state drift detected after push: {details}"


class temporary_spec_file:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.path: Path | None = None

    def __enter__(self) -> Path:
        temporary = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8")
        temporary.write(json.dumps(self.payload, indent=2))
        temporary.close()
        self.path = Path(temporary.name)
        return self.path

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.path:
            self.path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
