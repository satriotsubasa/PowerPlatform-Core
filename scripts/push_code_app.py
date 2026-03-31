#!/usr/bin/env python3
"""Build and push a Power Apps code app to a Power Platform environment.

Wraps the npm-based Power Apps CLI (`npx power-apps push`) and the legacy
`pac code push` command. Runs `npm run build` before pushing unless
--skip-build is supplied.

Usage examples
--------------
# Build and push a single app (npm CLI, recommended)
python scripts/push_code_app.py --path ./CodeApp/CustomerPortal

# Push all apps found under a parent folder (e.g. CodeApp/)
python scripts/push_code_app.py --path ./CodeApp --all

# Push all apps, targeting a specific solution (pac CLI)
python scripts/push_code_app.py --path ./CodeApp --all --cli pac --solution-name MySolution

# Skip build (re-push last build)
python scripts/push_code_app.py --path ./CodeApp/CustomerPortal --skip-build

# Dry run — show what would be executed without running it
python scripts/push_code_app.py --path ./CodeApp --all --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import subprocess


CONFIG_FILE = "power.config.json"


def find_config(app_path: Path) -> Path | None:
    """Locate power.config.json in the app directory or its parent."""
    candidate = app_path / CONFIG_FILE
    if candidate.is_file():
        return candidate
    candidate = app_path.parent / CONFIG_FILE
    if candidate.is_file():
        return candidate
    return None


def load_config(config_path: Path) -> dict:
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: Could not read {config_path}: {exc}", file=sys.stderr)
        return {}


def discover_app_paths(root: Path) -> list[Path]:
    """Find all direct subdirectories of root that contain a power.config.json.

    Each subdirectory represents one code app (e.g. CodeApp/CustomerPortal/).
    Also returns root itself if it directly contains a power.config.json.
    """
    apps: list[Path] = []
    if (root / CONFIG_FILE).is_file():
        apps.append(root)
        return apps
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / CONFIG_FILE).is_file():
            apps.append(child)
    return apps


def check_node_available() -> bool:
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def check_pac_available() -> bool:
    try:
        subprocess.run(["pac", "help"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def run_command(cmd: list[str], cwd: Path, dry_run: bool) -> int:
    print(f"\n> {' '.join(cmd)}")
    if dry_run:
        print("  [dry-run: skipped]")
        return 0
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def push_single_app(app_path: Path, cli: str, solution_name: str | None,
                    skip_build: bool, dry_run: bool) -> int:
    """Build and push one code app. Returns exit code."""
    config_path = find_config(app_path)
    if config_path:
        config = load_config(config_path)
        display_name = config.get("displayName") or config.get("name", "<unknown>")
        environment_id = config.get("environmentId", "<unknown>")
        print(f"  App        : {display_name}")
        print(f"  Environment: {environment_id}")
        print(f"  Config     : {config_path}")
    else:
        print(
            f"  WARNING: No {CONFIG_FILE} found in {app_path}. "
            "Run 'npx power-apps init' first.",
            file=sys.stderr,
        )

    package_json = app_path / "package.json"
    if not package_json.is_file():
        print(f"  ERROR: No package.json found in {app_path}.", file=sys.stderr)
        return 2

    # Build
    if not skip_build:
        print("\n  ── Build ──────────────────────────────────────────────")
        rc = run_command(["npm", "run", "build"], cwd=app_path, dry_run=dry_run)
        if rc != 0:
            print(f"\n  ERROR: Build failed (exit {rc}).", file=sys.stderr)
            return rc
        print("  Build complete.")
    else:
        print("\n  Skipping build (--skip-build).")

    # Push
    print("\n  ── Push ───────────────────────────────────────────────")
    if cli == "npm":
        push_cmd = ["npx", "power-apps", "push"]
    else:
        push_cmd = ["pac", "code", "push"]
        if solution_name:
            push_cmd += ["--solutionName", solution_name]

    rc = run_command(push_cmd, cwd=app_path, dry_run=dry_run)
    if rc != 0:
        print(f"\n  ERROR: Push failed (exit {rc}).", file=sys.stderr)
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and push Power Apps code app(s) to Power Platform.",
    )
    parser.add_argument(
        "--path",
        default=".",
        help=(
            "Path to a single code app directory, or to a parent folder such as "
            "CodeApp/ when used with --all. Defaults to current directory."
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Discover and push all code apps found as immediate subdirectories of "
            "--path (each must contain a power.config.json). Use this when --path "
            "points to a CodeApp/ parent folder containing multiple apps."
        ),
    )
    parser.add_argument(
        "--cli",
        choices=["npm", "pac"],
        default="npm",
        help="CLI to use for push. 'npm' uses 'npx power-apps push' (recommended). 'pac' uses 'pac code push'. Defaults to npm.",
    )
    parser.add_argument(
        "--solution-name",
        help="Target solution unique name (pac CLI only). Omit to use the preferred solution.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip 'npm run build' and push the last compiled output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands that would be executed without running them.",
    )
    args = parser.parse_args()

    base_path = Path(args.path).resolve()
    if not base_path.is_dir():
        print(f"ERROR: Path does not exist or is not a directory: {base_path}", file=sys.stderr)
        return 2

    if not check_node_available():
        print("ERROR: Node.js is not available on PATH. Install Node.js (LTS).", file=sys.stderr)
        return 2

    if args.cli == "pac" and not check_pac_available():
        print("ERROR: PAC CLI is not available on PATH. Install the Power Platform CLI.", file=sys.stderr)
        return 2

    print(f"CLI mode : {args.cli}")
    if args.dry_run:
        print("Mode     : DRY RUN — no commands will be executed")

    # Multi-app mode
    if args.all:
        app_paths = discover_app_paths(base_path)
        if not app_paths:
            print(
                f"ERROR: No code apps found under {base_path}.\n"
                "Each app subfolder must contain a power.config.json.",
                file=sys.stderr,
            )
            return 2

        print(f"\nFound {len(app_paths)} code app(s) under {base_path}:")
        for p in app_paths:
            print(f"  - {p.name}")

        failed: list[str] = []
        for i, app_path in enumerate(app_paths, 1):
            print(f"\n{'═' * 60}")
            print(f"[{i}/{len(app_paths)}] {app_path.name}")
            print("═" * 60)
            rc = push_single_app(
                app_path, args.cli, args.solution_name, args.skip_build, args.dry_run
            )
            if rc != 0:
                failed.append(app_path.name)

        print(f"\n{'═' * 60}")
        if failed:
            print(f"COMPLETED WITH ERRORS — {len(failed)} app(s) failed:")
            for name in failed:
                print(f"  ✗ {name}")
            return 1
        else:
            print(f"All {len(app_paths)} app(s) pushed successfully.")
            if not args.dry_run:
                print("\nNext steps:")
                print("  1. Verify each app runs at the URL shown above.")
                print("  2. Add apps to a solution: Power Apps → Solutions → Add existing → App → Code app")
                print("  3. Use Power Platform Pipelines to promote to Test or Prod.")
            return 0

    # Single-app mode
    print(f"\nApp path : {base_path}")
    rc = push_single_app(
        base_path, args.cli, args.solution_name, args.skip_build, args.dry_run
    )
    if not args.dry_run and rc == 0:
        print("\nPush complete. The app URL is shown above.")
        print("Next steps:")
        print("  1. Verify the app runs correctly at the returned URL.")
        print("  2. Add the app to a solution if not already done:")
        print("     Power Apps → Solutions → Add existing → App → Code app")
        print("  3. Use Power Platform Pipelines to promote to Test or Prod.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
