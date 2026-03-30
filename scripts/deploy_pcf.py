#!/usr/bin/env python3
"""Build, package, and deploy a PCF control or wrapper solution."""

from __future__ import annotations

import argparse
from pathlib import Path

from powerplatform_common import (
    find_pcf_solution_artifact,
    infer_publisher_prefix,
    repo_root,
    resolve_live_connection,
    resolve_pcf_context,
    run_command,
    run_command_with_dataverse_lock_retry,
    write_json_output,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build, package, and deploy a PCF control through its package root or wrapper solution.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect when inferring the PCF package.")
    parser.add_argument("--project", help="Path to a control folder, package root, ControlManifest.Input.xml, or .pcfproj file.")
    parser.add_argument("--publisher-prefix", help="Publisher prefix for direct pac pcf push flows. Defaults from discovery when possible.")
    parser.add_argument("--solution-name", help="Solution unique name. Defaults from the selected auth-dialog solution when available.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before deployment.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument("--skip-install", action="store_true", help="Skip npm install before build.")
    parser.add_argument("--skip-build", action="store_true", help="Skip npm build before packaging or push.")
    parser.add_argument("--skip-solution-build", action="store_true", help="Skip building the wrapper solution project in solution-package mode.")
    parser.add_argument("--production", action="store_true", help="Build the PCF package in production mode.")
    parser.add_argument("--incremental", action="store_true", help="Use incremental pac pcf push in direct push mode.")
    parser.add_argument("--mode", choices=["auto", "push", "solution-package"], default="auto", help="Deployment mode. Auto prefers wrapper solution packaging when available.")
    parser.add_argument("--configuration", choices=["Debug", "Release"], default="Release", help="Wrapper solution build configuration for solution-package mode.")
    parser.add_argument("--artifact-file", help="Explicit solution zip artifact to import in solution-package mode.")
    parser.add_argument("--allow-version-mismatch", action="store_true", help="Allow PCF manifest version and wrapper Solution.xml version to differ in solution-package mode.")
    parser.add_argument("--run-check", action="store_true", help="Run Power Apps Checker against the packaged solution zip before import.")
    parser.add_argument("--checker-output", help="Output directory for solution checker results.")
    parser.add_argument("--skip-import", action="store_true", help="Skip importing the packaged solution in solution-package mode.")
    parser.add_argument("--publish-changes", action="store_true", help="Publish changes during solution import in solution-package mode.")
    parser.add_argument("--activate-plugins", action="store_true", help="Activate plug-ins and workflows during solution import in solution-package mode.")
    parser.add_argument("--force-overwrite", action="store_true", help="Force overwrite unmanaged customizations during solution import in solution-package mode.")
    parser.add_argument("--skip-dependency-check", action="store_true", help="Skip dependency checks during solution import in solution-package mode.")
    parser.add_argument("--import-as-holding", action="store_true", help="Import the solution as a holding solution in solution-package mode.")
    parser.add_argument("--stage-and-upgrade", action="store_true", help="Import and upgrade the solution in solution-package mode.")
    parser.add_argument("--convert-to-managed", action="store_true", help="Convert to managed during solution import in solution-package mode.")
    parser.add_argument("--lock-retries", type=int, default=20, help="Number of retry waits for Dataverse import or publish locks before failing.")
    parser.add_argument("--lock-wait-seconds", type=int, default=30, help="Seconds to wait between Dataverse import or publish lock retries.")
    parser.add_argument("--verbosity", choices=["minimal", "normal", "detailed", "diagnostic"], help="PAC PCF push verbosity.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    pcf_context = resolve_pcf_context(repo, args.project)
    package_root = Path(pcf_context["package_root"])

    if not args.skip_install:
        run_command(["npm", "install"], cwd=package_root)

    if not args.skip_build:
        build_command = ["npm", "run", "build"]
        if args.production:
            build_command.extend(["--", "--buildMode", "production"])
        run_command(build_command, cwd=package_root)

    mode = resolve_mode(args.mode, pcf_context)
    version_alignment = evaluate_version_alignment(pcf_context)
    if mode == "solution-package" and not version_alignment["aligned"] and not args.allow_version_mismatch:
        raise RuntimeError(
            "PCF wrapper solution version does not match the source control manifest version(s). "
            f"Manifest versions: {', '.join(version_alignment['manifest_versions']) or '(none)'}. "
            f"Solution version: {version_alignment['solution_version'] or '(none)'}. "
            "Update both version surfaces first or pass --allow-version-mismatch."
        )

    connection = None
    if should_resolve_live_connection(args, mode):
        connection = resolve_live_connection(
            environment_url=args.environment_url,
            username=args.username,
            tenant_id=args.tenant_id,
            auth_dialog=args.auth_dialog,
            target_url=args.target_url,
            auto_validate=args.auto_validate,
        )

    if mode == "push":
        payload = execute_direct_push(args, repo=repo, package_root=package_root, pcf_context=pcf_context, connection=connection)
    else:
        payload = execute_solution_package(
            args,
            repo=repo,
            package_root=package_root,
            pcf_context=pcf_context,
            connection=connection,
            version_alignment=version_alignment,
        )

    write_json_output(payload, args.output)
    return 0


def should_resolve_live_connection(args: argparse.Namespace, mode: str) -> bool:
    if mode == "push":
        return True
    if mode != "solution-package":
        return False
    if not args.skip_import:
        return True
    return bool(args.auth_dialog)


def resolve_mode(raw_mode: str, pcf_context: dict[str, object]) -> str:
    if raw_mode != "auto":
        return raw_mode
    return "solution-package" if pcf_context.get("solution_project") else "push"


def evaluate_version_alignment(pcf_context: dict[str, object]) -> dict[str, object]:
    manifests = pcf_context.get("manifests", [])
    manifest_versions = []
    if isinstance(manifests, list):
        for manifest in manifests:
            if isinstance(manifest, dict):
                version = manifest.get("version")
                if isinstance(version, str) and version:
                    manifest_versions.append(version)

    manifest_versions = sorted(set(manifest_versions))
    solution_context = pcf_context.get("solution_context")
    solution_version = None
    if isinstance(solution_context, dict):
        version = solution_context.get("version")
        if isinstance(version, str) and version:
            solution_version = version

    normalized_solution_manifest_version = None
    if solution_version:
        parts = solution_version.split(".")
        if len(parts) >= 3:
            normalized_solution_manifest_version = ".".join(parts[:3])

    aligned = (
        bool(solution_version and manifest_versions)
        and len(manifest_versions) == 1
        and manifest_versions[0] == normalized_solution_manifest_version
    )
    if not manifest_versions and not solution_version:
        aligned = True

    return {
        "aligned": aligned,
        "manifest_versions": manifest_versions,
        "solution_version": solution_version,
        "normalized_solution_manifest_version": normalized_solution_manifest_version,
    }


def execute_direct_push(
    args: argparse.Namespace,
    *,
    repo: Path,
    package_root: Path,
    pcf_context: dict[str, object],
    connection: dict[str, object] | None,
) -> dict[str, object]:
    if connection is None:
        raise RuntimeError("Direct PCF push requires a live connection.")

    solution_name = args.solution_name or connection.get("solution_unique_name")
    if not solution_name:
        raise RuntimeError(
            "No solution unique name was supplied and no selected solution is available from the auth dialog."
        )
    publisher_prefix = args.publisher_prefix or infer_publisher_prefix(repo)

    command = [
        "pac",
        "pcf",
        "push",
        "--publisher-prefix",
        publisher_prefix,
        "--solution-unique-name",
        str(solution_name),
        "--environment",
        str(connection["environment_url"]),
    ]
    if args.incremental:
        command.append("--incremental")
    if args.verbosity:
        command.extend(["--verbosity", args.verbosity])

    run_command_with_dataverse_lock_retry(
        command,
        cwd=package_root,
        retries=args.lock_retries,
        wait_seconds=args.lock_wait_seconds,
    )

    return {
        "success": True,
        "mode": "push",
        "package_root": str(package_root),
        "pcf_project_file": pcf_context["pcf_project_file"],
        "solution_unique_name": solution_name,
        "publisher_prefix": publisher_prefix,
        "environment_url": connection["environment_url"],
        "installed": not args.skip_install,
        "built": not args.skip_build,
        "production": args.production,
        "incremental": args.incremental,
        "pushed": True,
        "version_alignment": evaluate_version_alignment(pcf_context),
    }


def execute_solution_package(
    args: argparse.Namespace,
    *,
    repo: Path,
    package_root: Path,
    pcf_context: dict[str, object],
    connection: dict[str, object] | None,
    version_alignment: dict[str, object],
) -> dict[str, object]:
    solution_project = pcf_context.get("solution_project")
    if not solution_project:
        raise RuntimeError(
            "Solution-package mode requires a wrapper solution project under <package root>\\Solutions\\*.cdsproj."
        )

    executed_steps: list[str] = []
    if not args.skip_solution_build:
        build_solution_wrapper(Path(str(solution_project)), configuration=args.configuration, cwd=repo)
        executed_steps.append(f"build-solution-{args.configuration.lower()}")

    artifact_file = Path(args.artifact_file).resolve() if args.artifact_file else find_pcf_solution_artifact(
        pcf_context,
        configuration=args.configuration,
        managed_preferred=args.configuration.lower() == "release",
    )

    if args.run_check:
        checker_output = Path(args.checker_output).resolve() if args.checker_output else (repo / "out" / "pcf-checker")
        checker_output.mkdir(parents=True, exist_ok=True)
        command = [
            "pac",
            "solution",
            "check",
            "--path",
            str(artifact_file),
            "--outputDirectory",
            str(checker_output),
        ]
        checker_environment_url = args.environment_url
        if not checker_environment_url and connection and connection.get("environment_url"):
            checker_environment_url = str(connection["environment_url"])
        if checker_environment_url:
            command.extend(["--environment", str(checker_environment_url)])
        run_command(command, cwd=repo)
        executed_steps.append("check")

    imported = False
    if not args.skip_import:
        if connection is None:
            connection = resolve_live_connection(
                environment_url=args.environment_url,
                username=args.username,
                tenant_id=args.tenant_id,
                auth_dialog=args.auth_dialog,
                target_url=args.target_url,
                auto_validate=args.auto_validate,
            )

        import_command = [
            "pac",
            "solution",
            "import",
            "--path",
            str(artifact_file),
            "--environment",
            str(connection["environment_url"]),
        ]
        if args.publish_changes:
            import_command.append("--publish-changes")
        if args.activate_plugins:
            import_command.append("--activate-plugins")
        if args.force_overwrite:
            import_command.append("--force-overwrite")
        if args.skip_dependency_check:
            import_command.append("--skip-dependency-check")
        if args.import_as_holding:
            import_command.append("--import-as-holding")
        if args.stage_and_upgrade:
            import_command.append("--stage-and-upgrade")
        if args.convert_to_managed:
            import_command.append("--convert-to-managed")
        run_command_with_dataverse_lock_retry(
            import_command,
            cwd=repo,
            retries=args.lock_retries,
            wait_seconds=args.lock_wait_seconds,
        )
        executed_steps.append("import")
        imported = True

    solution_context = pcf_context.get("solution_context") or {}
    return {
        "success": True,
        "mode": "solution-package",
        "package_root": str(package_root),
        "pcf_project_file": pcf_context["pcf_project_file"],
        "solution_project": solution_project,
        "solution_unique_name": solution_context.get("unique_name"),
        "artifact_file": str(artifact_file),
        "configuration": args.configuration,
        "installed": not args.skip_install,
        "built": not args.skip_build,
        "solution_built": not args.skip_solution_build,
        "production": args.production,
        "checked": args.run_check,
        "imported": imported,
        "environment_url": connection["environment_url"] if connection else None,
        "version_alignment": version_alignment,
        "executed_steps": executed_steps,
    }


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


if __name__ == "__main__":
    raise SystemExit(main())
