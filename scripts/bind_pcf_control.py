#!/usr/bin/env python3
"""Bind a PCF control to an existing form control through Dataverse form XML."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from powerplatform_common import (
    read_json_argument,
    read_pcf_manifest,
    repo_root,
    resolve_live_connection,
    run_dataverse_tool,
)


FORM_FACTOR_ALIASES = {
    "web": 0,
    "desktop": 0,
    "phone": 1,
    "mobile": 1,
    "tablet": 2,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind a PCF control to a Dataverse form control through the shared SDK metadata helper.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the PCF binding.")
    parser.add_argument("--repo-root", default=".", help="Repository root used when resolving a relative --project path.")
    parser.add_argument("--project", help="Path to the PCF control folder containing ControlManifest.Input.xml.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before the binding update.")
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
    project_path = resolve_project_path(repo, args.project or spec.get("project"))
    if project_path is not None:
        manifest = read_pcf_manifest(project_path)
        spec.setdefault("pcfControlName", manifest["control_name"])
        spec.setdefault("pcfControlVersion", manifest["version"])
        spec["pcfManifest"] = manifest["manifest_path"]

    normalize_form_factors(spec)

    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )
    command = [
        "metadata",
        "bind-pcf-control",
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


def resolve_project_path(repo: Path, raw_value: object | None) -> Path | None:
    if raw_value is None:
        return None
    path = Path(str(raw_value))
    return path.resolve() if path.is_absolute() else (repo / path).resolve()


def normalize_form_factors(spec: dict[str, object]) -> None:
    raw_values = spec.get("formFactors")
    if raw_values is None:
        return
    if not isinstance(raw_values, list):
        raise RuntimeError("'formFactors' must be an array when present.")

    normalized: list[int] = []
    for value in raw_values:
        normalized.append(normalize_form_factor(value))
    spec["formFactors"] = normalized


def normalize_form_factor(value: object) -> int:
    if isinstance(value, bool):
        raise RuntimeError("Boolean values are not valid form factors.")
    if isinstance(value, int):
        return value

    text = str(value).strip().lower()
    if text.isdigit():
        return int(text)
    if text in FORM_FACTOR_ALIASES:
        return FORM_FACTOR_ALIASES[text]
    raise RuntimeError(f"Unsupported form factor '{value}'. Use 0/web, 1/phone, or 2/tablet.")


if __name__ == "__main__":
    raise SystemExit(main())
