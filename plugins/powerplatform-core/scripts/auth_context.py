#!/usr/bin/env python3
"""Launch the reusable Power Platform auth dialog and return the selected live context."""

from __future__ import annotations

import argparse
from pathlib import Path

from powerplatform_common import (
    ensure_dataverse_solution_reference,
    launch_auth_dialog,
    repo_root,
    resolve_tenant_id,
    resolve_username,
    write_json_output,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Launch the reusable Power Platform auth dialog, force an interactive sign-in validation, "
            "require working-solution selection, and return the resolved live context as JSON."
        ),
    )
    parser.add_argument("--target-url", help="Target org URL, Power Apps environment URL, or Power Apps solution URL.")
    parser.add_argument("--username", help="Default username hint for the dialog.")
    parser.add_argument("--tenant-id", help="Default tenant ID hint for the dialog.")
    parser.add_argument("--auto-validate", action="store_true", help="Start validation immediately when the dialog opens.")
    parser.add_argument("--repo-root", default=".", help="Repository root used when creating a Dataverse reference clone.")
    parser.add_argument(
        "--ensure-dataverse-reference",
        action="store_true",
        help="After a successful auth and solution selection, clone the selected solution into Dataverse/<solution-unique-name> when the repo does not already contain local solution source.",
    )
    parser.add_argument(
        "--reference-package-type",
        choices=["Managed", "Unmanaged", "Both"],
        default="Unmanaged",
        help="Solution package type to request when creating a Dataverse reference clone. Defaults to Unmanaged.",
    )
    parser.add_argument("--output", help="Optional path to write the JSON payload.")
    args = parser.parse_args()

    try:
        username = resolve_username(args.username)
    except RuntimeError:
        username = args.username

    payload = launch_auth_dialog(
        target_url=args.target_url,
        username=username,
        tenant_id=resolve_tenant_id(args.tenant_id),
        auto_validate=args.auto_validate,
    )
    if args.ensure_dataverse_reference:
        target_repo = repo_root(Path(args.repo_root))
        selected_solution = payload.get("selectedSolution") or payload.get("SelectedSolution") or {}
        solution_unique_name = selected_solution.get("uniqueName") or selected_solution.get("UniqueName")
        environment_url = payload.get("environmentUrl") or payload.get("EnvironmentUrl")
        if solution_unique_name and environment_url:
            payload["dataverseReference"] = ensure_dataverse_solution_reference(
                target_repo,
                environment_url=environment_url,
                solution_unique_name=solution_unique_name,
                package_type=args.reference_package_type,
            )
    write_json_output(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
