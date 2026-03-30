#!/usr/bin/env python3
"""Update local and optional online Dataverse solution versions."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from powerplatform_common import (
    infer_unpacked_solution_folder,
    repo_root,
    resolve_live_connection,
    resolve_environment_url,
    run_command,
    write_json_output,
)

VERSION_RE = re.compile(r"(<Version>)(\d+\.\d+\.\d+\.\d+)(</Version>)", re.IGNORECASE)
UNIQUENAME_RE = re.compile(r"<UniqueName>(?P<value>[^<]+)</UniqueName>", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(description="Update local solution version and optionally sync it to Dataverse.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect when inferring the solution folder.")
    parser.add_argument(
        "--solution-path",
        help="Path to the unpacked solution folder or to Other/Solution.xml. Defaults from discovery.",
    )
    parser.add_argument("--version", help="Explicit 4-part solution version to set.")
    parser.add_argument("--increment", choices=["build", "revision"], help="Increment one part of the current version by 1.")
    parser.add_argument("--build-version", type=int, help="Set the build part of the version explicitly.")
    parser.add_argument("--revision-version", type=int, help="Set the revision part of the version explicitly.")
    parser.add_argument("--online", action="store_true", help="Also update the solution version in the target Dataverse environment.")
    parser.add_argument("--solution-name", help="Solution unique name for the online update. Defaults from Solution.xml.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL for the online update.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before online versioning.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    solution_xml = resolve_solution_xml(repo, args.solution_path)
    xml_text = solution_xml.read_text(encoding="utf-8")
    match = VERSION_RE.search(xml_text)
    if not match:
        raise RuntimeError(f"Could not find a <Version> element in {solution_xml}.")

    current_version = match.group(2)
    new_version = calculate_new_version(
        current_version=current_version,
        explicit_version=args.version,
        increment=args.increment,
        build_version=args.build_version,
        revision_version=args.revision_version,
    )
    updated_text = VERSION_RE.sub(rf"\g<1>{new_version}\g<3>", xml_text, count=1)
    solution_xml.write_text(updated_text, encoding="utf-8")

    online_updated = False
    connection = None
    if args.auth_dialog:
        connection = resolve_live_connection(
            environment_url=args.environment_url,
            username=args.username,
            tenant_id=args.tenant_id,
            auth_dialog=True,
            target_url=args.target_url,
            auto_validate=args.auto_validate,
        )

    solution_name = args.solution_name or (connection["solution_unique_name"] if connection else None) or infer_solution_name(updated_text)
    if args.online:
        if not solution_name:
            raise RuntimeError("Could not infer the solution unique name for online versioning. Pass --solution-name.")
        environment_url = connection["environment_url"] if connection else resolve_environment_url(args.environment_url)
        command = [
            "pac",
            "solution",
            "online-version",
            "--solution-name",
            solution_name,
            "--solution-version",
            new_version,
            "--environment",
            environment_url,
        ]
        run_command(command, cwd=repo)
        online_updated = True

    write_json_output(
        {
            "success": True,
            "solution_xml": str(solution_xml),
            "previous_version": current_version,
            "new_version": new_version,
            "solution_name": solution_name,
            "selected_solution_version": connection["solution_version"] if connection else None,
            "online_updated": online_updated,
        },
        args.output,
    )
    return 0


def resolve_solution_xml(repo: Path, explicit_path: str | None) -> Path:
    if explicit_path:
        path = Path(explicit_path).resolve()
        if path.is_file():
            return path
        candidate = path / "Other" / "Solution.xml"
        if candidate.exists():
            return candidate
        raise RuntimeError(f"Could not find Other/Solution.xml under {path}.")

    solution_folder = infer_unpacked_solution_folder(repo)
    return solution_folder / "Other" / "Solution.xml"


def calculate_new_version(
    *,
    current_version: str,
    explicit_version: str | None,
    increment: str | None,
    build_version: int | None,
    revision_version: int | None,
) -> str:
    if explicit_version:
        validate_version(explicit_version)
        return explicit_version

    major, minor, build, revision = parse_version(current_version)
    if build_version is not None:
        build = build_version
    if revision_version is not None:
        revision = revision_version

    if increment == "build":
        build += 1
        revision = 0
    elif increment == "revision":
        revision += 1

    new_version = f"{major}.{minor}.{build}.{revision}"
    validate_version(new_version)
    return new_version


def parse_version(value: str) -> tuple[int, int, int, int]:
    validate_version(value)
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def validate_version(value: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value):
        raise RuntimeError(f"Solution version '{value}' is not a valid 4-part version.")


def infer_solution_name(xml_text: str) -> str | None:
    match = UNIQUENAME_RE.search(xml_text)
    if match:
        return match.group("value").strip()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
