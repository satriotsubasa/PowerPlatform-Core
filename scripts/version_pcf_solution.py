#!/usr/bin/env python3
"""Update PCF manifest version(s) and wrapper solution version together."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from powerplatform_common import resolve_pcf_context, repo_root, write_json_output

MANIFEST_VERSION_RE = re.compile(r'(<control\b[^>]*\bversion=")(\d+\.\d+\.\d+)(")', re.IGNORECASE)
SOLUTION_VERSION_RE = re.compile(r"(<Version>)(\d+\.\d+\.\d+\.\d+)(</Version>)", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update a PCF package version across manifest files and the wrapper solution version.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root used when resolving a relative --project path.")
    parser.add_argument("--project", help="Path to a control folder, package root, ControlManifest.Input.xml, or .pcfproj file.")
    parser.add_argument("--version", help="Explicit version to set. Supports either 3-part manifest form or 4-part solution form.")
    parser.add_argument("--increment", choices=["patch", "revision"], help="Increment the patch or revision version.")
    parser.add_argument("--update-all-manifests", action="store_true", help="Update every source manifest in the package root. Defaults to true when multiple manifests exist.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    pcf_context = resolve_pcf_context(repo, args.project)
    manifests = pcf_context.get("manifests", [])
    if not isinstance(manifests, list) or not manifests:
        raise RuntimeError("Could not resolve any source PCF manifests for versioning.")

    source_manifest_paths = [
        Path(str(item["manifest_path"]))
        for item in manifests
        if isinstance(item, dict) and item.get("manifest_path")
    ]
    source_manifest_versions = sorted({
        str(item.get("version"))
        for item in manifests
        if isinstance(item, dict) and item.get("version")
    })
    solution_context = pcf_context.get("solution_context")
    solution_xml_path = Path(str(pcf_context["solution_xml"])) if pcf_context.get("solution_xml") else None
    current_solution_version = None
    if isinstance(solution_context, dict):
        current_solution_version = solution_context.get("version")

    current_version = current_solution_version or first_manifest_version(source_manifest_versions)
    if not current_version:
        raise RuntimeError("Could not infer a current PCF version from the manifests or wrapper solution.")

    new_solution_version, new_manifest_version = calculate_new_versions(
        current_version=str(current_version),
        explicit_version=args.version,
        increment=args.increment,
    )

    updated_manifest_paths = []
    update_all = args.update_all_manifests or len(source_manifest_paths) > 1
    for manifest_path in source_manifest_paths:
        if not update_all and manifest_path != Path(str(source_manifest_paths[0])):
            continue
        update_manifest_version(manifest_path, new_manifest_version)
        updated_manifest_paths.append(str(manifest_path))

    updated_solution = None
    if solution_xml_path and solution_xml_path.exists():
        update_solution_version(solution_xml_path, new_solution_version)
        updated_solution = str(solution_xml_path)

    write_json_output(
        {
            "success": True,
            "package_root": pcf_context["package_root"],
            "pcf_project_file": pcf_context["pcf_project_file"],
            "previous_manifest_versions": source_manifest_versions,
            "previous_solution_version": current_solution_version,
            "new_manifest_version": new_manifest_version,
            "new_solution_version": new_solution_version,
            "updated_manifest_paths": updated_manifest_paths,
            "updated_solution_xml": updated_solution,
        },
        args.output,
    )
    return 0


def first_manifest_version(values: list[str]) -> str | None:
    return values[0] if values else None


def calculate_new_versions(*, current_version: str, explicit_version: str | None, increment: str | None) -> tuple[str, str]:
    solution_major, solution_minor, solution_patch, solution_revision = parse_solution_version(normalize_solution_version(current_version))

    if explicit_version:
        solution_version = normalize_solution_version(explicit_version)
        major, minor, patch, revision = parse_solution_version(solution_version)
        return solution_version, f"{major}.{minor}.{patch}"

    if increment == "patch":
        solution_patch += 1
        solution_revision = 0
    elif increment == "revision":
        solution_revision += 1

    solution_version = f"{solution_major}.{solution_minor}.{solution_patch}.{solution_revision}"
    return solution_version, f"{solution_major}.{solution_minor}.{solution_patch}"


def normalize_solution_version(value: str) -> str:
    stripped = value.strip()
    if re.fullmatch(r"\d+\.\d+\.\d+", stripped):
        return f"{stripped}.0"
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", stripped):
        return stripped
    raise RuntimeError(f"PCF version '{value}' must be either a 3-part or 4-part dotted version.")


def parse_solution_version(value: str) -> tuple[int, int, int, int]:
    parts = normalize_solution_version(value).split(".")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def update_manifest_version(path: Path, new_version: str) -> None:
    text = path.read_text(encoding="utf-8")
    if not MANIFEST_VERSION_RE.search(text):
        raise RuntimeError(f"Could not find a PCF control version attribute in {path}.")
    updated = MANIFEST_VERSION_RE.sub(rf"\g<1>{new_version}\g<3>", text, count=1)
    path.write_text(updated, encoding="utf-8")


def update_solution_version(path: Path, new_version: str) -> None:
    text = path.read_text(encoding="utf-8")
    if not SOLUTION_VERSION_RE.search(text):
        raise RuntimeError(f"Could not find a <Version> element in {path}.")
    updated = SOLUTION_VERSION_RE.sub(rf"\g<1>{new_version}\g<3>", text, count=1)
    path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
