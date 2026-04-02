#!/usr/bin/env python3
"""Pack, optionally check, import, and publish a Dataverse solution."""

from __future__ import annotations

import argparse
from pathlib import Path

from powerplatform_common import (
    infer_unpacked_solution_folder,
    load_deployment_defaults,
    repo_root,
    resolve_environment_url,
    run_command,
    run_command_with_dataverse_lock_retry,
    write_json_output,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack and deploy a Dataverse solution with PAC CLI.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect when inferring the solution folder.")
    parser.add_argument("--solution-folder", help="Root unpacked solution folder. Defaults from discovery.")
    parser.add_argument("--zipfile", help="Output solution zip path. Defaults to <repo>\\out\\solution.zip.")
    parser.add_argument("--package-type", default="Unmanaged", choices=["Unmanaged", "Managed", "Both"])
    parser.add_argument("--environment-url", help="Target Dataverse environment URL for import and checker runs.")
    parser.add_argument("--settings-file", help="Optional deployment settings JSON for import.")
    parser.add_argument("--publish-changes", action="store_true", help="Publish changes as part of the import.")
    parser.add_argument("--activate-plugins", action="store_true", help="Activate plug-ins and workflows on import.")
    parser.add_argument("--force-overwrite", action="store_true", help="Force overwrite unmanaged customizations on import.")
    parser.add_argument("--skip-dependency-check", action="store_true", help="Skip dependency checks for product update dependencies.")
    parser.add_argument("--import-as-holding", action="store_true", help="Import the solution as a holding solution.")
    parser.add_argument("--stage-and-upgrade", action="store_true", help="Import and upgrade the solution.")
    parser.add_argument("--convert-to-managed", action="store_true", help="Convert to managed during import.")
    parser.add_argument("--run-check", action="store_true", help="Run Power Apps Checker against the packed zip before import.")
    parser.add_argument("--checker-output", help="Output directory for solution checker results.")
    parser.add_argument(
        "--change-scope",
        choices=["unknown", "targeted-component", "solution-subset", "whole-solution"],
        default="unknown",
        help="Blast-radius classification for the intended deployment primitive.",
    )
    parser.add_argument(
        "--shared-unmanaged-environment",
        action="store_true",
        help="Treat the target as a shared unmanaged environment and block broad imports more aggressively.",
    )
    parser.add_argument(
        "--allow-broad-import",
        action="store_true",
        help="Explicitly allow whole-solution import even when the change scope is narrower.",
    )
    parser.add_argument("--change-summary", help="Short human-readable summary of what is being deployed.")
    parser.add_argument("--lock-retries", type=int, default=20, help="Number of retry waits for Dataverse import or publish locks before failing.")
    parser.add_argument("--lock-wait-seconds", type=int, default=30, help="Seconds to wait between Dataverse import or publish lock retries.")
    parser.add_argument("--max-runtime-seconds", type=int, help="Hard local runtime ceiling for the import command and lock-retry window.")
    parser.add_argument("--skip-pack", action="store_true")
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    deployment_defaults = load_deployment_defaults(repo)
    resolved_max_runtime_seconds = resolve_solution_import_timeout(args.max_runtime_seconds, deployment_defaults)
    solution_folder = Path(args.solution_folder).resolve() if args.solution_folder else infer_unpacked_solution_folder(repo)
    zipfile = Path(args.zipfile).resolve() if args.zipfile else (repo / "out" / "solution.zip")
    zipfile.parent.mkdir(parents=True, exist_ok=True)

    enforce_deployment_scope_guard(
        change_scope=args.change_scope,
        skip_import=args.skip_import,
        allow_broad_import=args.allow_broad_import,
        shared_unmanaged_environment=args.shared_unmanaged_environment,
        change_summary=args.change_summary,
    )

    executed_steps: list[str] = []
    if not args.skip_pack:
        pack_command = [
            "pac",
            "solution",
            "pack",
            "--folder",
            str(solution_folder),
            "--zipfile",
            str(zipfile),
            "--packagetype",
            args.package_type,
            "--allowWrite",
            "true",
        ]
        run_command(pack_command, cwd=repo)
        executed_steps.append("pack")

    if args.run_check:
        checker_output = Path(args.checker_output).resolve() if args.checker_output else (repo / "out" / "checker")
        checker_output.mkdir(parents=True, exist_ok=True)
        check_command = [
            "pac",
            "solution",
            "check",
            "--path",
            str(zipfile),
            "--outputDirectory",
            str(checker_output),
        ]
        if args.environment_url:
            check_command.extend(["--environment", resolve_environment_url(args.environment_url)])
        run_command(check_command, cwd=repo)
        executed_steps.append("check")

    if not args.skip_import:
        import_command = [
            "pac",
            "solution",
            "import",
            "--path",
            str(zipfile),
            "--environment",
            resolve_environment_url(args.environment_url),
        ]
        if args.settings_file:
            import_command.extend(["--settings-file", str(Path(args.settings_file).resolve())])
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
            max_runtime_seconds=resolved_max_runtime_seconds,
        )
        executed_steps.append("import")

    write_json_output(
        {
            "success": True,
            "solution_folder": str(solution_folder),
            "zipfile": str(zipfile),
            "package_type": args.package_type,
            "change_scope": args.change_scope,
            "executed_steps": executed_steps,
            "max_runtime_seconds": resolved_max_runtime_seconds,
        },
        args.output,
    )
    return 0


def resolve_solution_import_timeout(configured_timeout: int | None, deployment_defaults: dict[str, object]) -> int:
    if configured_timeout is not None:
        return configured_timeout
    timeouts = deployment_defaults.get("timeouts")
    if isinstance(timeouts, dict):
        value = timeouts.get("solutionImportSeconds")
        if isinstance(value, int) and value > 0:
            return value
    return 900


def enforce_deployment_scope_guard(
    *,
    change_scope: str,
    skip_import: bool,
    allow_broad_import: bool,
    shared_unmanaged_environment: bool,
    change_summary: str | None,
) -> None:
    if skip_import or allow_broad_import:
        return

    summary_text = f" Change summary: {change_summary.strip()}." if isinstance(change_summary, str) and change_summary.strip() else ""
    if change_scope == "targeted-component":
        raise RuntimeError(
            "Broad solution import is blocked for a targeted-component change."
            " Use targeted helpers such as update-main-form, sync-webresource, or another component-scoped path instead."
            " If you intentionally want a whole-solution import, rerun with --allow-broad-import after explicit approval."
            f"{summary_text}"
        )

    if shared_unmanaged_environment and change_scope == "solution-subset":
        raise RuntimeError(
            "Broad solution import is blocked for a solution-subset change in a shared unmanaged environment."
            " Prefer the narrowest reviewed deployment primitive, or rerun with --allow-broad-import after explicit approval."
            f"{summary_text}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
