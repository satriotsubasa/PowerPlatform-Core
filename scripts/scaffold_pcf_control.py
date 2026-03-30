#!/usr/bin/env python3
"""Scaffold a new PCF control through PAC CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from powerplatform_common import discover_repo_context, repo_root, write_json_output, run_command


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new Power Apps component framework control.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect when inferring the PCF area.")
    parser.add_argument("--output-dir", help="Directory where the new PCF control should be created.")
    parser.add_argument("--namespace", required=True, help="PCF namespace.")
    parser.add_argument("--name", required=True, help="PCF control name.")
    parser.add_argument("--template", default="field", choices=["field", "dataset"], help="PCF template type.")
    parser.add_argument("--framework", choices=["none", "react"], default="none", help="PCF framework option.")
    parser.add_argument("--run-npm-install", action="store_true", help="Run npm install during pac pcf init.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    output_dir = Path(args.output_dir).resolve() if args.output_dir else infer_pcf_output_dir(repo, args.name)
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "pac",
        "pcf",
        "init",
        "--namespace",
        args.namespace,
        "--name",
        args.name,
        "--template",
        args.template,
        "--outputDirectory",
        str(output_dir),
    ]
    if args.framework == "react":
        command.extend(["--framework", "react"])
    if args.run_npm_install:
        command.append("--run-npm-install")

    run_command(command, cwd=repo)

    manifest_path = output_dir / "ControlManifest.Input.xml"
    write_json_output(
        {
            "success": True,
            "namespace": args.namespace,
            "name": args.name,
            "template": args.template,
            "framework": None if args.framework == "none" else args.framework,
            "project": str(output_dir),
            "manifest": str(manifest_path),
            "npm_installed": args.run_npm_install,
        },
        args.output,
    )
    return 0


def infer_pcf_output_dir(repo: Path, control_name: str) -> Path:
    context = discover_repo_context(repo)
    pcf_area = context.get("inferred", {}).get("pcf_area")
    if pcf_area:
        return repo / pcf_area / control_name
    return repo / control_name


if __name__ == "__main__":
    raise SystemExit(main())
