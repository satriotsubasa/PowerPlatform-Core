#!/usr/bin/env python3
"""Run safe delivery validation across repo, build, and optional live preflight checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from powerplatform_common import (
    discover_repo_context,
    find_pcf_solution_artifact,
    has_local_unpacked_solution_source,
    infer_pcf_package_roots,
    infer_plugin_project,
    repo_root,
    resolve_live_connection,
    resolve_pcf_context,
    run_command,
    write_json_output,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Power Platform repo delivery path without importing or mutating Dataverse.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root to validate.")
    parser.add_argument("--plugin-project", help="Optional explicit plug-in project path.")
    parser.add_argument("--pcf-project", action="append", dest="pcf_projects", help="Optional PCF project path. Can be repeated.")
    parser.add_argument("--word-templates-path", help="Optional explicit Word Templates folder or file path.")
    parser.add_argument("--solution-folder", help="Optional unpacked solution folder for pack/check validation.")
    parser.add_argument("--zipfile", help="Optional output solution zip path used for pack/check validation.")
    parser.add_argument("--checker-output", help="Optional output directory for solution checker results.")
    parser.add_argument("--solution-name", help="Optional solution unique name to report alongside live preflight results.")
    parser.add_argument("--pcf-solution-configuration", choices=["Debug", "Release"], default="Release", help="Wrapper solution build configuration used for PCF package validation.")
    parser.add_argument("--live-preflight", action="store_true", help="Run a read-only Dataverse WhoAmI validation.")
    parser.add_argument("--run-solution-check", action="store_true", help="Run Power Apps Checker after packing the solution.")
    parser.add_argument("--skip-plugin-build", action="store_true", help="Skip plug-in build validation.")
    parser.add_argument("--skip-pcf-build", action="store_true", help="Skip PCF build validation.")
    parser.add_argument("--skip-word-templates", action="store_true", help="Skip Word Template inspection.")
    parser.add_argument("--skip-solution-pack", action="store_true", help="Skip solution pack validation.")
    parser.add_argument("--skip-npm-install", action="store_true", help="Skip npm install before PCF build validation.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog for live preflight.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the read-only Dataverse preflight when the auth dialog is not used.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt during live preflight.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr for live preflight.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    discovery = discover_repo_context(repo)
    checks: list[dict[str, Any]] = []
    success = True

    connection = None
    if args.live_preflight:
        connection = resolve_live_connection(
            environment_url=args.environment_url,
            username=args.username,
            tenant_id=args.tenant_id,
            auth_dialog=args.auth_dialog,
            target_url=args.target_url,
            auto_validate=args.auto_validate,
        )
        live_check = run_live_preflight(
            repo=repo,
            connection=connection,
            auth_flow=args.auth_flow,
            force_prompt=args.force_prompt,
            verbose=args.verbose,
            solution_name=args.solution_name,
        )
        checks.append(live_check)
        success &= live_check["success"]

    if not args.skip_plugin_build:
        plugin_check = run_plugin_build_check(repo, args.plugin_project)
        checks.append(plugin_check)
        success &= plugin_check["success"]

    if not args.skip_pcf_build:
        for pcf_check in run_pcf_build_checks(
            repo,
            args.pcf_projects or [],
            skip_npm_install=args.skip_npm_install,
            pcf_solution_configuration=args.pcf_solution_configuration,
        ):
            checks.append(pcf_check)
            success &= pcf_check["success"]

    if not args.skip_word_templates:
        word_template_check = run_word_template_check(repo, args.word_templates_path)
        checks.append(word_template_check)
        success &= word_template_check["success"]

    if not args.skip_solution_pack:
        solution_check = run_solution_pack_check(
            repo,
            solution_folder=args.solution_folder,
            zipfile=args.zipfile,
            checker_output=args.checker_output,
            run_solution_check=args.run_solution_check,
            environment_url=connection["environment_url"] if connection else args.environment_url,
        )
        checks.append(solution_check)
        success &= solution_check["success"]

    warnings = [check["message"] for check in checks if check.get("status") == "warning" and check.get("message")]
    payload = {
        "success": success,
        "mode": "validate-delivery",
        "repoRoot": str(repo),
        "discovery": build_discovery_summary(discovery),
        "checks": checks,
        "warnings": warnings,
    }
    write_json_output(payload, args.output)
    return 0 if success else 1


def build_discovery_summary(discovery: dict[str, Any]) -> dict[str, Any]:
    inferred = discovery.get("inferred", {})
    return {
        "repoArchetype": inferred.get("repo_archetype"),
        "solutionSourceModel": inferred.get("solution_source_model"),
        "inferred": inferred,
    }


def run_live_preflight(
    *,
    repo: Path,
    connection: dict[str, Any],
    auth_flow: str,
    force_prompt: bool,
    verbose: bool,
    solution_name: str | None,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "whoami.py"),
        "--environment-url",
        str(connection["environment_url"]),
        "--username",
        str(connection["username"]),
        "--auth-flow",
        auth_flow,
    ]
    if connection.get("tenant_id"):
        command.extend(["--tenant-id", str(connection["tenant_id"])])
    if force_prompt:
        command.append("--force-prompt")
    if verbose:
        command.append("--verbose")

    try:
        completed = run_command(command, cwd=repo)
        result = json.loads(completed.stdout)
        return {
            "name": "live-preflight",
            "success": True,
            "status": "passed",
            "environmentUrl": connection["environment_url"],
            "solutionUniqueName": solution_name or connection.get("solution_unique_name"),
            "result": result,
        }
    except Exception as exc:
        return {
            "name": "live-preflight",
            "success": False,
            "status": "failed",
            "environmentUrl": connection["environment_url"],
            "solutionUniqueName": solution_name or connection.get("solution_unique_name"),
            "message": str(exc),
        }


def run_plugin_build_check(repo: Path, raw_project: str | None) -> dict[str, Any]:
    try:
        project = resolve_optional_repo_path(repo, raw_project) if raw_project else infer_plugin_project(repo)
    except Exception as exc:
        return {
            "name": "plugin-build",
            "success": False,
            "status": "failed",
            "message": str(exc),
        }

    try:
        completed = run_command(["dotnet", "build", str(project)], cwd=repo)
        return {
            "name": "plugin-build",
            "success": True,
            "status": "passed",
            "project": str(project),
            "stdout": completed.stdout.strip(),
        }
    except Exception as exc:
        return {
            "name": "plugin-build",
            "success": False,
            "status": "failed",
            "project": str(project),
            "message": str(exc),
        }


def run_pcf_build_checks(
    repo: Path,
    raw_projects: list[str],
    *,
    skip_npm_install: bool,
    pcf_solution_configuration: str,
) -> list[dict[str, Any]]:
    explicit_projects = [resolve_optional_repo_path(repo, value) for value in raw_projects]
    projects = explicit_projects or infer_pcf_package_roots(repo)
    if not projects:
        return [
            {
                "name": "pcf-build",
                "success": True,
                "status": "warning",
                "message": "No PCF projects were discovered in this repo.",
            }
        ]

    checks: list[dict[str, Any]] = []
    for project in projects:
        try:
            pcf_context = resolve_pcf_context(repo, project)
            package_root = Path(str(pcf_context["package_root"]))
            package_json = package_root / "package.json"
            if not package_json.exists():
                raise RuntimeError(f"PCF package.json not found: {package_json}")

            if not skip_npm_install:
                run_command(["npm", "install"], cwd=package_root)
            run_command(["npm", "run", "build"], cwd=package_root)

            solution_project = pcf_context.get("solution_project")
            artifact_file = None
            if solution_project:
                build_solution_wrapper(
                    Path(str(solution_project)),
                    configuration=pcf_solution_configuration,
                    cwd=repo,
                )
                artifact_file = find_pcf_solution_artifact(
                    pcf_context,
                    configuration=pcf_solution_configuration,
                    managed_preferred=pcf_solution_configuration.lower() == "release",
                )
            checks.append(
                {
                    "name": "pcf-build",
                    "success": True,
                    "status": "passed",
                    "project": str(project),
                    "packageRoot": str(package_root),
                    "controlNames": [manifest.get("control_name") for manifest in pcf_context.get("manifests", [])],
                    "versions": sorted(
                        {
                            str(manifest.get("version"))
                            for manifest in pcf_context.get("manifests", [])
                            if isinstance(manifest, dict) and manifest.get("version")
                        }
                    ),
                    "solutionProject": solution_project,
                    "artifactFile": str(artifact_file) if artifact_file else None,
                    "npmInstalled": not skip_npm_install,
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "name": "pcf-build",
                    "success": False,
                    "status": "failed",
                    "project": str(project),
                    "message": str(exc),
                }
            )
    return checks


def build_solution_wrapper(solution_project: Path, *, configuration: str, cwd: Path) -> None:
    msbuild_command = [
        "msbuild",
        str(solution_project),
        "/restore",
        "/t:Build",
        f"/p:Configuration={configuration}",
    ]
    try:
        run_command(msbuild_command, cwd=cwd)
        return
    except Exception as msbuild_error:
        dotnet_command = [
            "dotnet",
            "build",
            str(solution_project),
            "--configuration",
            configuration,
        ]
        try:
            run_command(dotnet_command, cwd=cwd)
            return
        except Exception as dotnet_error:
            raise RuntimeError(
                "Could not build the PCF wrapper solution project with either msbuild or dotnet build.\n"
                f"msbuild error:\n{msbuild_error}\n\n"
                f"dotnet build error:\n{dotnet_error}"
            ) from dotnet_error


def run_word_template_check(repo: Path, raw_path: str | None) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "inspect_word_templates.py"),
        "--repo-root",
        str(repo),
        "--summary-only",
    ]
    if raw_path:
        command.extend(["--path", str(resolve_optional_repo_path(repo, raw_path))])

    try:
        completed = run_command(command, cwd=repo)
        result = json.loads(completed.stdout)
        return {
            "name": "word-templates",
            "success": True,
            "status": "passed",
            "result": result,
        }
    except Exception as exc:
        return {
            "name": "word-templates",
            "success": False,
            "status": "failed",
            "message": str(exc),
        }


def run_solution_pack_check(
    repo: Path,
    *,
    solution_folder: str | None,
    zipfile: str | None,
    checker_output: str | None,
    run_solution_check: bool,
    environment_url: str | None,
) -> dict[str, Any]:
    if not solution_folder and not has_local_unpacked_solution_source(repo):
        return {
            "name": "solution-pack",
            "success": True,
            "status": "warning",
            "message": "No local unpacked Dataverse solution source was discovered for pack/check validation.",
        }

    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "deploy_solution.py"),
        "--repo-root",
        str(repo),
        "--skip-import",
    ]
    if solution_folder:
        command.extend(["--solution-folder", str(resolve_optional_repo_path(repo, solution_folder))])
    if zipfile:
        command.extend(["--zipfile", str(resolve_optional_repo_path(repo, zipfile))])
    if run_solution_check:
        command.append("--run-check")
    if checker_output:
        command.extend(["--checker-output", str(resolve_optional_repo_path(repo, checker_output))])
    if environment_url:
        command.extend(["--environment-url", str(environment_url)])

    try:
        completed = run_command(command, cwd=repo)
        result = json.loads(completed.stdout)
        return {
            "name": "solution-pack",
            "success": True,
            "status": "passed",
            "result": result,
        }
    except Exception as exc:
        return {
            "name": "solution-pack",
            "success": False,
            "status": "failed",
            "message": str(exc),
        }


def resolve_optional_repo_path(repo: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
