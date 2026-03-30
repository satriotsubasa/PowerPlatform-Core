#!/usr/bin/env python3
"""Build or pack and first-register a Dataverse plug-in package headlessly."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from powerplatform_common import (
    apply_selected_solution_to_spec,
    apply_plugin_step_state_defaults_to_registration_spec,
    infer_plugin_package_file,
    infer_plugin_project,
    load_plugin_step_state_contract,
    read_json_argument,
    read_nuget_metadata,
    repo_root,
    resolve_live_connection,
    run_command,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or pack and first-register a Dataverse plug-in package headlessly.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the registration.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect when inferring the plug-in project.")
    parser.add_argument("--project", help="Path to the plug-in .csproj. Defaults from discovery.")
    parser.add_argument("--package-file", help="NuGet package file to register. Inferred from the project when omitted.")
    parser.add_argument("--configuration", default="Debug", help="Build configuration used when inferring the package path.")
    parser.add_argument("--skip-pack", action="store_true", help="Skip dotnet pack before registration.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before registration.")
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
    project_path = Path(args.project).resolve() if args.project else infer_plugin_project(repo)
    if not project_path.exists():
        raise RuntimeError(f"Plug-in project not found: {project_path}")

    if not args.skip_pack:
        run_command(["dotnet", "pack", str(project_path), "-c", args.configuration], cwd=repo)

    package_file = Path(args.package_file).resolve() if args.package_file else infer_plugin_package_file(
        project_path,
        configuration=args.configuration,
    )
    package_metadata = read_nuget_metadata(package_file)

    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )
    spec = apply_selected_solution_to_spec(spec, connection)
    spec = apply_plugin_step_state_defaults_to_registration_spec(spec, load_plugin_step_state_contract(repo))
    spec["packagePath"] = str(package_file)
    spec.setdefault("uniqueName", package_metadata.get("id"))
    spec.setdefault("name", package_metadata.get("title") or package_metadata.get("id"))
    spec.setdefault("version", package_metadata.get("version"))
    if package_metadata.get("description") and not spec.get("description"):
        spec["description"] = package_metadata["description"]

    command = [
        "plugin",
        "--mode",
        "register-package",
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
