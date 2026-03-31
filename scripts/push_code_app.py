#!/usr/bin/env python3
"""Build and push a Power Apps code app to a Power Platform environment.

Wraps the npm-based Power Apps CLI (`npx power-apps push`) and the legacy
`pac code push` command. Runs `npm run build` before pushing unless
--skip-build is supplied.

Usage examples
--------------
# Build and push using npm CLI (recommended, requires @microsoft/power-apps >= 1.0.4)
python scripts/push_code_app.py --path ./my-app

# Push into a specific solution via pac CLI
python scripts/push_code_app.py --path ./my-app --cli pac --solution-name MySolution

# Skip build (re-push last build)
python scripts/push_code_app.py --path ./my-app --skip-build

# Dry run — show what would be executed without running it
python scripts/push_code_app.py --path ./my-app --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and push a Power Apps code app to Power Platform.",
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Path to the code app directory (must contain power.config.json or package.json). Defaults to current directory.",
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

    app_path = Path(args.path).resolve()
    if not app_path.is_dir():
        print(f"ERROR: App path does not exist or is not a directory: {app_path}", file=sys.stderr)
        return 2

    # Locate and read power.config.json
    config_path = find_config(app_path)
    if config_path:
        config = load_config(config_path)
        display_name = config.get("displayName") or config.get("name", "<unknown>")
        environment_id = config.get("environmentId", "<unknown>")
        print(f"Code app   : {display_name}")
        print(f"Environment: {environment_id}")
        print(f"Config     : {config_path}")
    else:
        print(
            f"WARNING: No {CONFIG_FILE} found at or above {app_path}.\n"
            "Run 'npx power-apps init' first to initialise the app.",
            file=sys.stderr,
        )

    # Validate package.json exists
    package_json = app_path / "package.json"
    if not package_json.is_file():
        print(f"ERROR: No package.json found in {app_path}. Is this a Node.js project?", file=sys.stderr)
        return 2

    # Check tooling availability
    if not check_node_available():
        print("ERROR: Node.js is not available on PATH. Install Node.js (LTS) before continuing.", file=sys.stderr)
        return 2

    if args.cli == "pac" and not check_pac_available():
        print("ERROR: PAC CLI is not available on PATH. Install the Power Platform CLI before continuing.", file=sys.stderr)
        return 2

    print(f"\nCLI mode   : {args.cli}")
    if args.dry_run:
        print("Mode       : DRY RUN — no commands will be executed\n")

    # Step 1: Build
    if not args.skip_build:
        print("\n── Step 1: Build ──────────────────────────────────────────")
        rc = run_command(["npm", "run", "build"], cwd=app_path, dry_run=args.dry_run)
        if rc != 0:
            print(f"\nERROR: Build failed with exit code {rc}. Fix build errors before pushing.", file=sys.stderr)
            return rc
        print("Build complete.")
    else:
        print("\nSkipping build (--skip-build supplied).")

    # Step 2: Push
    print("\n── Step 2: Push ───────────────────────────────────────────")
    if args.cli == "npm":
        push_cmd = ["npx", "power-apps", "push"]
    else:
        push_cmd = ["pac", "code", "push"]
        if args.solution_name:
            push_cmd += ["--solutionName", args.solution_name]

    rc = run_command(push_cmd, cwd=app_path, dry_run=args.dry_run)
    if rc != 0:
        print(f"\nERROR: Push failed with exit code {rc}.", file=sys.stderr)
        return rc

    if not args.dry_run:
        print("\nPush complete. The app URL is shown above.")
        print("Next steps:")
        print("  1. Verify the app runs correctly at the returned URL.")
        print("  2. Add the app to a solution if not already done:")
        print("     Power Apps → Solutions → Add existing → App → Code app")
        print("  3. Use Power Platform Pipelines to promote to Test or Prod.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
