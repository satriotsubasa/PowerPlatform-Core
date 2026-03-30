#!/usr/bin/env python3
"""Ensure a repo has a local Dataverse solution reference under Dataverse/<solution-unique-name>."""

from __future__ import annotations

import argparse
from pathlib import Path

from powerplatform_common import (
    ensure_dataverse_solution_reference,
    repo_root,
    resolve_live_connection,
    write_json_output,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure a local Dataverse reference clone exists under Dataverse/<solution-unique-name>. "
            "When the repo has no unpacked solution source, clone the selected live solution there."
        ),
    )
    parser.add_argument("--repo-root", default=".", help="Repository root where the Dataverse folder should live.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL when bypassing the auth dialog.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before cloning.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--package-type",
        choices=["Managed", "Unmanaged", "Both"],
        default="Unmanaged",
        help="Solution package type to request from pac solution clone. Defaults to Unmanaged.",
    )
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    target_repo = repo_root(Path(args.repo_root))
    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )
    result = ensure_dataverse_solution_reference(
        target_repo,
        environment_url=connection["environment_url"],
        solution_unique_name=connection["solution_unique_name"],
        package_type=args.package_type,
    )
    payload = {
        "success": True,
        "repoRoot": str(target_repo),
        "environmentUrl": connection["environment_url"],
        "solutionUniqueName": connection["solution_unique_name"],
        "reference": result,
    }
    write_json_output(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
