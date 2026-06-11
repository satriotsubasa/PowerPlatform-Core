#!/usr/bin/env python3
"""Canonical local verification entry point for this skill repo."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IS_WINDOWS = os.name == "nt"
# DataverseOps multi-targets net8.0 (+ net8.0-windows on Windows) and builds everywhere.
CROSS_PLATFORM_DOTNET_PROJECTS = (
    ROOT / "tools" / "CodexPowerPlatform.DataverseOps" / "CodexPowerPlatform.DataverseOps.csproj",
)
# AuthDialog is a WPF (net8.0-windows) app; it only builds on Windows.
WINDOWS_ONLY_DOTNET_PROJECTS = (
    ROOT / "tools" / "CodexPowerPlatform.AuthDialog" / "CodexPowerPlatform.AuthDialog.csproj",
)
# The .NET test project targets net8.0-windows.
WINDOWS_ONLY_DOTNET_TEST_PROJECTS = (
    ROOT / "tools" / "CodexPowerPlatform.DataverseOps.Tests" / "CodexPowerPlatform.DataverseOps.Tests.csproj",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the canonical local verification flow for this repo.")
    parser.add_argument("--skip-python", action="store_true", help="Skip Python syntax checks.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unit tests.")
    parser.add_argument("--skip-dotnet", action="store_true", help="Skip .NET builds.")
    parser.add_argument(
        "--skip-quick-validate",
        action="store_true",
        help="Skip skill-creator quick validation.",
    )
    args = parser.parse_args()

    if not args.skip_python:
        run_step("Python syntax", verify_python_sources)
    if not args.skip_tests:
        run_step("Unit tests", lambda: run_command([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]))
    if not args.skip_dotnet:
        run_step("Dotnet build", verify_dotnet_projects)
        run_step("Dotnet tests", verify_dotnet_test_projects)
    if not args.skip_quick_validate:
        run_step("Skill quick validation", verify_skill_contract)

    print("Verification completed.")
    return 0


def run_step(name: str, action: callable) -> None:
    print(f"== {name} ==")
    action()
    print(f"OK {name}")


def run_command(args: list[str]) -> None:
    completed = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(args)}")


def verify_python_sources() -> None:
    for path in iter_python_sources():
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def iter_python_sources() -> list[Path]:
    paths = [ROOT / "verify_repo.py"]
    for directory_name in ("scripts", "tests"):
        directory = ROOT / directory_name
        if not directory.exists():
            continue
        paths.extend(
            sorted(path for path in directory.rglob("*.py") if "__pycache__" not in path.parts)
        )
    return paths


def verify_dotnet_projects() -> None:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError("dotnet was not found on PATH. Install the .NET SDK or rerun with --skip-dotnet.")
    projects = list(CROSS_PLATFORM_DOTNET_PROJECTS)
    if IS_WINDOWS:
        projects.extend(WINDOWS_ONLY_DOTNET_PROJECTS)
    else:
        for project in WINDOWS_ONLY_DOTNET_PROJECTS:
            print(f"Skipping {project.name} (Windows-only WPF project) on this non-Windows host.")
    for project in projects:
        run_command([dotnet, "build", str(project), "--nologo"])


def verify_dotnet_test_projects() -> None:
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError("dotnet was not found on PATH. Install the .NET SDK or rerun with --skip-dotnet.")
    if not IS_WINDOWS:
        for project in WINDOWS_ONLY_DOTNET_TEST_PROJECTS:
            print(f"Skipping {project.name} (net8.0-windows test project) on this non-Windows host.")
        return
    for project in WINDOWS_ONLY_DOTNET_TEST_PROJECTS:
        run_command([dotnet, "test", str(project), "--nologo"])


def verify_skill_contract() -> None:
    quick_validate = locate_quick_validate()
    if not quick_validate:
        print(
            "Skipping quick_validate.py because the skill-creator validator was not found "
            "(looked under the Codex and Claude skill homes)."
        )
        return
    run_command([sys.executable, str(quick_validate), str(ROOT)])


def locate_quick_validate() -> Path | None:
    candidate_roots: list[Path] = []
    for env_var in ("CODEX_HOME", "CLAUDE_CONFIG_DIR"):
        value = os.environ.get(env_var)
        if value:
            candidate_roots.append(Path(value))
    candidate_roots.append(Path.home() / ".codex")
    candidate_roots.append(Path.home() / ".claude")
    for root in candidate_roots:
        candidate = root / "skills" / ".system" / "skill-creator" / "scripts" / "quick_validate.py"
        if candidate.exists():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
