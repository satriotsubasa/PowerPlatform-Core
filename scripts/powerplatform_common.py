#!/usr/bin/env python3
"""Shared helpers for Codex Power Platform scripts."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ACTIVE_PROFILE_RE = re.compile(r"^\[(?P<index>\d+)\]\s+\*", re.MULTILINE)
ENVIRONMENT_URL_RE = re.compile(r"(https://\S+/?)\s*$", re.IGNORECASE)
AUTH_WHO_USER_RE = re.compile(r"^User:\s+(?P<value>.+)$", re.MULTILINE)
AUTH_WHO_CONNECTED_AS_RE = re.compile(r"^Connected as (?P<value>.+)$", re.MULTILINE)
AUTH_WHO_TENANT_RE = re.compile(r"^Tenant Id:\s+(?P<value>.+)$", re.MULTILINE)
IGNORED_PCF_PATH_PARTS = {"node_modules", "out", "bin", "obj", "dist", "coverage"}
DATAVERSE_LOCK_PATTERNS = (
    re.compile(r"cannot start another \[(import|publishall)\]", re.IGNORECASE),
    re.compile(r"previous \[(import|publishall)\] running", re.IGNORECASE),
)
PRIMARY_SOLUTION_ROLES = {"app-metadata", "dataverse-reference"}
FLOW_GUARD_PATHS = (
    Path(".codex") / "power-platform.flow-guards.json",
    Path("power-platform.flow-guards.json"),
)


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_root(start: Path) -> Path:
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return start.resolve()
        current = current.parent


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    resolved_args = list(args)
    resolved_args[0] = resolve_executable(args[0])
    try:
        completed = subprocess.run(
            resolved_args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_message = (
            f"Command timed out after {timeout_seconds} second(s): {' '.join(args)}\n"
            f"STDOUT:\n{exc.stdout or ''}\n"
            f"STDERR:\n{exc.stderr or ''}"
        )
        raise RuntimeError(timeout_message) from exc
    if check and completed.returncode != 0:
        message = (
            f"Command failed ({completed.returncode}): {' '.join(args)}\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )
        raise RuntimeError(message)
    return completed


def run_command_with_dataverse_lock_retry(
    args: list[str],
    *,
    cwd: Path | None = None,
    retries: int = 20,
    wait_seconds: int = 30,
    max_runtime_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    attempts = max(1, retries + 1)
    last_completed: subprocess.CompletedProcess[str] | None = None
    start_time = time.monotonic()
    runtime_budget_exhausted = False

    for attempt in range(1, attempts + 1):
        remaining_runtime = remaining_runtime_seconds(start_time, max_runtime_seconds)
        if remaining_runtime is not None and remaining_runtime <= 0:
            runtime_budget_exhausted = True
            break

        completed = run_command(
            args,
            cwd=cwd,
            check=False,
            timeout_seconds=remaining_runtime,
        )
        last_completed = completed
        if completed.returncode == 0:
            return completed

        if not is_dataverse_lock_error(completed.stdout, completed.stderr) or attempt >= attempts:
            break

        remaining_runtime = remaining_runtime_seconds(start_time, max_runtime_seconds)
        if remaining_runtime is not None and remaining_runtime <= 0:
            runtime_budget_exhausted = True
            break

        sleep_seconds = float(wait_seconds)
        if remaining_runtime is not None:
            sleep_seconds = min(sleep_seconds, remaining_runtime)
        if sleep_seconds <= 0:
            runtime_budget_exhausted = True
            break

        time.sleep(sleep_seconds)

    if runtime_budget_exhausted:
        raise RuntimeError(
            f"Command failed after exceeding runtime budget of {max_runtime_seconds} second(s): {' '.join(args)}\n"
            f"STDOUT:\n{last_completed.stdout if last_completed else ''}\n"
            f"STDERR:\n{last_completed.stderr if last_completed else ''}"
        )

    assert last_completed is not None
    raise RuntimeError(
        f"Command failed ({last_completed.returncode}) after {attempts} attempt(s): {' '.join(args)}\n"
        f"STDOUT:\n{last_completed.stdout}\n"
        f"STDERR:\n{last_completed.stderr}"
    )


def remaining_runtime_seconds(start_time: float, max_runtime_seconds: float | None) -> float | None:
    if max_runtime_seconds is None:
        return None
    elapsed = time.monotonic() - start_time
    return max_runtime_seconds - elapsed


def is_dataverse_lock_error(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}"
    return any(pattern.search(combined) for pattern in DATAVERSE_LOCK_PATTERNS)


def resolve_executable(command: str) -> str:
    command_path = Path(command)
    if command_path.is_absolute() or command_path.parent != Path():
        return command

    direct = shutil.which(command)
    if direct:
        return direct

    if os.name == "nt":
        for suffix in (".exe", ".cmd", ".bat"):
            candidate = shutil.which(command + suffix)
            if candidate:
                return candidate

    return command


def read_json_argument(value: str) -> Any:
    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(value)


def write_json_output(payload: Any, output_path: str | None) -> None:
    output_text = json.dumps(payload, indent=2)
    if output_path:
        path = Path(output_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)


def apply_selected_solution_to_spec(spec: dict[str, Any], connection: dict[str, Any]) -> dict[str, Any]:
    if spec.get("solutionUniqueName"):
        return spec

    selected_solution_name = connection.get("solution_unique_name")
    if selected_solution_name:
        spec["solutionUniqueName"] = selected_solution_name
    return spec


def discover_repo_context(scan_path: Path) -> dict[str, Any]:
    script_path = skill_root() / "scripts" / "discover_context.py"
    completed = run_command(
        [sys.executable, str(script_path), "--path", str(scan_path.resolve())],
        cwd=skill_root(),
    )
    return json.loads(completed.stdout)


def has_local_solution_source_in_context(context: dict[str, Any]) -> bool:
    return bool(authoritative_solution_projects(context) or authoritative_unpacked_solutions(context))


def has_local_unpacked_solution_source_in_context(context: dict[str, Any]) -> bool:
    return bool(authoritative_unpacked_solutions(context))


def authoritative_unpacked_solutions(context: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = context.get("artifacts", {})
    return [
        item
        for item in artifacts.get("unpacked_solutions", [])
        if solution_role_is_authoritative(item.get("solution_role"))
    ]


def authoritative_solution_projects(context: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = context.get("artifacts", {})
    return [
        item
        for item in artifacts.get("solution_projects", [])
        if solution_role_is_authoritative(item.get("solution_role"))
    ]


def solution_role_is_authoritative(role: Any) -> bool:
    normalized = str(role or "app-metadata").strip().lower()
    return normalized in PRIMARY_SOLUTION_ROLES


def resolve_authoritative_unpacked_solution(
    context: dict[str, Any],
    *,
    target_repo_root: Path,
) -> dict[str, Any]:
    unpacked = authoritative_unpacked_solutions(context)
    if not unpacked:
        raise RuntimeError(
            f"Could not infer an authoritative unpacked solution folder under {target_repo_root}. "
            "Pass the solution folder or Solution.xml path explicitly."
        )
    if len(unpacked) > 1:
        candidates = ", ".join(
            str(item.get("solution_folder_relative_path") or item.get("unique_name") or "<unknown>")
            for item in unpacked
        )
        raise RuntimeError(
            "More than one authoritative unpacked solution was found. "
            f"Pass the solution folder or Solution.xml path explicitly. Candidates: {candidates}"
        )
    return unpacked[0]


def active_pac_profile() -> dict[str, str | None]:
    try:
        auth_who = run_command(["pac", "auth", "who"], check=False)
        auth_list = run_command(["pac", "auth", "list"], check=False)
    except OSError:
        return {
            "user": None,
            "tenant_id": None,
            "environment_url": None,
        }

    user = None
    tenant_id = None
    if auth_who.returncode == 0:
        user_match = AUTH_WHO_USER_RE.search(auth_who.stdout) or AUTH_WHO_CONNECTED_AS_RE.search(auth_who.stdout)
        if user_match:
            user = user_match.group("value").strip()
        tenant_match = AUTH_WHO_TENANT_RE.search(auth_who.stdout)
        if tenant_match:
            tenant_id = tenant_match.group("value").strip()

    environment_url = None
    if auth_list.returncode == 0:
        for line in auth_list.stdout.splitlines():
            if ACTIVE_PROFILE_RE.match(line):
                url_match = ENVIRONMENT_URL_RE.search(line)
                if url_match:
                    environment_url = url_match.group(1).strip()
                break

    return {
        "user": user,
        "tenant_id": tenant_id,
        "environment_url": environment_url,
    }


def resolve_environment_url(explicit_value: str | None) -> str:
    if explicit_value:
        return explicit_value
    profile = active_pac_profile()
    if profile["environment_url"]:
        return profile["environment_url"]
    raise RuntimeError(
        "No environment URL was supplied and the active PAC profile does not expose one. "
        "Pass --environment-url explicitly or run 'pac auth select' first."
    )


def resolve_username(explicit_value: str | None) -> str:
    if explicit_value:
        return explicit_value
    profile = active_pac_profile()
    if profile["user"]:
        return profile["user"]
    raise RuntimeError(
        "No username was supplied and the active PAC profile does not expose one. "
        "Pass --username explicitly or authenticate with 'pac auth create'."
    )


def resolve_tenant_id(explicit_value: str | None) -> str | None:
    if explicit_value:
        return explicit_value
    profile = active_pac_profile()
    return profile["tenant_id"]


def normalize_environment_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    if "://" not in raw:
        return raw.rstrip("/").lower()

    parts = urlsplit(raw)
    path = parts.path.rstrip("/")
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            parts.query,
            parts.fragment,
        )
    )


def build_pac_environment_mismatch_warning(
    *,
    requested_environment_url: str | None,
    pac_environment_url: str | None,
) -> str:
    normalized_requested = normalize_environment_url(requested_environment_url)
    normalized_pac = normalize_environment_url(pac_environment_url)
    if not normalized_requested or not normalized_pac or normalized_requested == normalized_pac:
        return ""

    return (
        "WARNING: The active PAC profile targets a different environment than the requested live target. "
        f"Requested: {normalized_requested}. Active PAC profile: {normalized_pac}. "
        "Run 'pac auth select' or pass the target environment explicitly if this is unintended."
    )


def dataverse_tool_project() -> Path:
    return skill_root() / "tools" / "CodexPowerPlatform.DataverseOps" / "CodexPowerPlatform.DataverseOps.csproj"


def dataverse_tool_dll() -> Path:
    return (
        skill_root()
        / "tools"
        / "CodexPowerPlatform.DataverseOps"
        / "bin"
        / "Debug"
        / "net8.0-windows"
        / "CodexPowerPlatform.DataverseOps.dll"
    )


def auth_dialog_project() -> Path:
    return skill_root() / "tools" / "CodexPowerPlatform.AuthDialog" / "CodexPowerPlatform.AuthDialog.csproj"


def auth_dialog_exe() -> Path:
    return (
        skill_root()
        / "tools"
        / "CodexPowerPlatform.AuthDialog"
        / "bin"
        / "Debug"
        / "net8.0-windows"
        / "CodexPowerPlatform.AuthDialog.exe"
    )


def build_dotnet_project(project_path: Path) -> None:
    run_command(["dotnet", "build", str(project_path)], cwd=skill_root())


def run_dataverse_tool(command_args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    args = ["dotnet", "run", "--project", str(dataverse_tool_project()), "--"] + command_args
    return run_command(args, cwd=cwd or skill_root())


def infer_unpacked_solution_folder(target_repo_root: Path) -> Path:
    context = discover_repo_context(target_repo_root)
    unpacked = resolve_authoritative_unpacked_solution(context, target_repo_root=target_repo_root)
    relative_path = unpacked["solution_folder_relative_path"]
    return target_repo_root / relative_path


def has_local_solution_source(target_repo_root: Path) -> bool:
    context = discover_repo_context(target_repo_root)
    return has_local_solution_source_in_context(context)


def has_local_unpacked_solution_source(target_repo_root: Path) -> bool:
    context = discover_repo_context(target_repo_root)
    return has_local_unpacked_solution_source_in_context(context)


def ensure_dataverse_solution_reference(
    target_repo_root: Path,
    *,
    environment_url: str,
    solution_unique_name: str,
    package_type: str = "Unmanaged",
) -> dict[str, Any]:
    if not environment_url:
        raise RuntimeError("An environment URL is required to clone a Dataverse solution reference.")
    if not solution_unique_name:
        raise RuntimeError("A selected solution unique name is required to clone a Dataverse solution reference.")

    context = discover_repo_context(target_repo_root)
    if has_local_solution_source_in_context(context):
        unpacked = authoritative_unpacked_solutions(context)
        relative_folder = unpacked[0].get("solution_folder_relative_path") if len(unpacked) == 1 else None
        return {
            "success": True,
            "created": False,
            "skipped": True,
            "reason": "Local Dataverse solution source already exists in this repo.",
            "solutionFolder": str((target_repo_root / relative_folder).resolve()) if relative_folder else None,
        }

    dataverse_root = target_repo_root / "Dataverse"
    dataverse_root.mkdir(parents=True, exist_ok=True)
    output_directory = dataverse_root / solution_unique_name

    existing_markers = list(output_directory.glob("*.cdsproj"))
    if (output_directory / "Other" / "Solution.xml").exists() or existing_markers:
        return {
            "success": True,
            "created": False,
            "skipped": True,
            "reason": "Dataverse reference folder already exists.",
            "solutionFolder": str(output_directory.resolve()),
        }

    if output_directory.exists() and any(output_directory.iterdir()):
        raise RuntimeError(
            f"Dataverse reference target already exists and is not empty: {output_directory}. "
            "Clear it first or choose a different target."
        )

    completed = run_command(
        [
            "pac",
            "solution",
            "clone",
            "--environment",
            environment_url,
            "--name",
            solution_unique_name,
            "--outputDirectory",
            str(output_directory),
            "--packagetype",
            package_type,
        ],
        cwd=target_repo_root,
    )

    refreshed_context = discover_repo_context(target_repo_root)
    refreshed_unpacked = refreshed_context.get("artifacts", {}).get("unpacked_solutions", [])
    matched_folder = None
    for item in refreshed_unpacked:
        if item.get("unique_name") == solution_unique_name and item.get("solution_folder_relative_path"):
            matched_folder = target_repo_root / item["solution_folder_relative_path"]
            break

    return {
        "success": True,
        "created": True,
        "skipped": False,
        "solutionUniqueName": solution_unique_name,
        "packageType": package_type,
        "solutionFolder": str((matched_folder or output_directory).resolve()),
        "dataverseRoot": str(dataverse_root.resolve()),
        "stdout": completed.stdout.strip(),
    }


def infer_plugin_project(target_repo_root: Path) -> Path:
    context = discover_repo_context(target_repo_root)
    relative_path = context.get("inferred", {}).get("plugin_project")
    if not relative_path:
        raise RuntimeError(
            f"Could not infer a plug-in project under {target_repo_root}. "
            "Pass --project explicitly."
        )
    return target_repo_root / relative_path


def infer_publisher_prefix(target_repo_root: Path) -> str:
    context = discover_repo_context(target_repo_root)
    publisher_prefix = context.get("inferred", {}).get("publisher_prefix")
    if not publisher_prefix:
        raise RuntimeError(
            f"Could not infer a publisher prefix under {target_repo_root}. "
            "Pass it explicitly."
        )
    return str(publisher_prefix)


def infer_pcf_projects(target_repo_root: Path) -> list[Path]:
    manifests = sorted(
        manifest
        for manifest in target_repo_root.rglob("ControlManifest.Input.xml")
        if not path_has_ignored_part(manifest)
    )
    return [manifest.parent for manifest in manifests]


def infer_single_pcf_project(target_repo_root: Path) -> Path:
    projects = infer_pcf_projects(target_repo_root)
    if not projects:
        raise RuntimeError(
            f"Could not infer a PCF project under {target_repo_root}. "
            "Pass --project explicitly."
        )
    if len(projects) > 1:
        candidates = ", ".join(str(path) for path in projects)
        raise RuntimeError(
            "More than one PCF project was found. Pass --project explicitly. "
            f"Candidates: {candidates}"
        )
    return projects[0]


def infer_pcf_package_roots(target_repo_root: Path) -> list[Path]:
    package_roots = []
    for project_file in target_repo_root.rglob("*.pcfproj"):
        if path_has_ignored_part(project_file):
            continue
        package_roots.append(project_file.parent)
    return sorted(set(package_roots))


def read_pcf_manifest(project_path: Path) -> dict[str, Any]:
    manifest_path = project_path / "ControlManifest.Input.xml"
    if not manifest_path.exists():
        raise RuntimeError(f"PCF manifest not found: {manifest_path}")

    root = ET.parse(manifest_path).getroot()
    control = root.find("./control")
    if control is None:
        raise RuntimeError(f"PCF manifest does not contain a <control> node: {manifest_path}")

    namespace = (control.get("namespace") or "").strip()
    constructor = (control.get("constructor") or "").strip()
    version = (control.get("version") or "").strip() or None
    control_type = (control.get("control-type") or "").strip() or None
    if not namespace or not constructor:
        raise RuntimeError(
            f"PCF manifest is missing namespace or constructor information: {manifest_path}"
        )

    properties = []
    for property_node in root.findall("./control/property"):
        properties.append(
            {
                "name": (property_node.get("name") or "").strip(),
                "ofType": (property_node.get("of-type") or "").strip() or None,
                "usage": (property_node.get("usage") or "").strip() or None,
                "required": property_node.get("required"),
            }
        )

    datasets = []
    for dataset_node in root.findall("./control/data-set"):
        datasets.append(
            {
                "name": (dataset_node.get("name") or "").strip(),
            }
        )

    return {
        "manifest_path": str(manifest_path),
        "namespace": namespace,
        "constructor": constructor,
        "version": version,
        "control_name": f"{namespace}.{constructor}",
        "control_type": control_type,
        "properties": properties,
        "datasets": datasets,
    }


def resolve_pcf_context(target_repo_root: Path, raw_project: str | Path | None = None) -> dict[str, Any]:
    repo = target_repo_root.resolve()
    package_root: Path | None = None
    control_project: Path | None = None
    pcf_project_file: Path | None = None

    if raw_project is not None:
        candidate = Path(raw_project).resolve() if Path(raw_project).is_absolute() else (repo / Path(raw_project)).resolve()
        if candidate.is_file():
            if candidate.suffix.lower() == ".pcfproj":
                package_root = candidate.parent
                pcf_project_file = candidate
            elif candidate.name.lower() == "controlmanifest.input.xml":
                control_project = candidate.parent
                package_root = find_pcf_package_root(control_project, repo)
            else:
                raise RuntimeError(
                    f"Unsupported PCF project path: {candidate}. Pass a .pcfproj file, a control folder, or a ControlManifest.Input.xml path."
                )
        elif candidate.is_dir():
            if (candidate / "ControlManifest.Input.xml").exists():
                control_project = candidate
                package_root = find_pcf_package_root(control_project, repo)
            elif list(candidate.glob("*.pcfproj")):
                package_root = candidate
            else:
                package_root = find_pcf_package_root(candidate, repo)
        else:
            raise RuntimeError(f"PCF project path does not exist: {candidate}")
    else:
        package_roots = infer_pcf_package_roots(repo)
        if not package_roots:
            raise RuntimeError(f"Could not infer a PCF package root under {repo}. Pass --project explicitly.")
        if len(package_roots) > 1:
            candidates = ", ".join(str(path) for path in package_roots)
            raise RuntimeError(
                "More than one PCF package root was found. Pass --project explicitly. "
                f"Candidates: {candidates}"
            )
        package_root = package_roots[0]

    if package_root is None:
        raise RuntimeError("Could not resolve a PCF package root.")

    pcf_project_files = sorted(package_root.glob("*.pcfproj"))
    if pcf_project_file is None:
        if not pcf_project_files:
            raise RuntimeError(f"Could not find a .pcfproj file under {package_root}.")
        if len(pcf_project_files) > 1:
            candidates = ", ".join(str(path) for path in pcf_project_files)
            raise RuntimeError(
                f"More than one .pcfproj file exists under {package_root}. Pass the intended project explicitly. Candidates: {candidates}"
            )
        pcf_project_file = pcf_project_files[0]

    control_projects = [
        manifest.parent
        for manifest in package_root.rglob("ControlManifest.Input.xml")
        if not path_has_ignored_part(manifest)
    ]
    control_projects = sorted(set(control_projects))
    if control_project is None:
        if len(control_projects) == 1:
            control_project = control_projects[0]

    manifests = [read_pcf_manifest(project) for project in control_projects]
    solution_root = package_root / "Solutions" if (package_root / "Solutions").exists() else None
    solution_project = None
    solution_xml = None
    if solution_root is not None:
        solution_projects = sorted(solution_root.glob("*.cdsproj"))
        if len(solution_projects) == 1:
            solution_project = solution_projects[0]
        solution_xml_candidate = solution_root / "src" / "Other" / "Solution.xml"
        if solution_xml_candidate.exists():
            solution_xml = solution_xml_candidate

    solution_context = read_solution_xml_context(solution_xml) if solution_xml else None

    return {
        "repo_root": str(repo),
        "package_root": str(package_root),
        "pcf_project_file": str(pcf_project_file),
        "control_project": str(control_project) if control_project else None,
        "control_projects": [str(path) for path in control_projects],
        "manifests": manifests,
        "solution_root": str(solution_root) if solution_root else None,
        "solution_project": str(solution_project) if solution_project else None,
        "solution_xml": str(solution_xml) if solution_xml else None,
        "solution_context": solution_context,
        "debug_output": str(solution_root / "bin" / "Debug") if solution_root else None,
        "release_output": str(solution_root / "bin" / "Release") if solution_root else None,
    }


def find_pcf_solution_artifact(
    pcf_context: dict[str, Any],
    *,
    configuration: str,
    managed_preferred: bool = True,
) -> Path:
    solution_root = pcf_context.get("solution_root")
    if not solution_root:
        raise RuntimeError("This PCF package does not expose a wrapper solution root.")

    output_dir = Path(solution_root) / "bin" / configuration
    if not output_dir.exists():
        raise RuntimeError(f"PCF solution output directory does not exist yet: {output_dir}")

    zip_candidates = sorted(output_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not zip_candidates:
        raise RuntimeError(f"No PCF solution zip artifact was found under {output_dir}")

    if managed_preferred:
        managed_candidates = [path for path in zip_candidates if path.name.lower().endswith("_managed.zip")]
        if managed_candidates:
            return managed_candidates[0]

    named_candidates = [path for path in zip_candidates if path.name.lower() != "solutions.zip"]
    if named_candidates:
        return named_candidates[0]
    return zip_candidates[0]


def read_solution_xml_context(solution_xml_path: Path | None) -> dict[str, Any] | None:
    if solution_xml_path is None or not solution_xml_path.exists():
        return None

    xml_text = solution_xml_path.read_text(encoding="utf-8")
    unique_name_match = re.search(r"<UniqueName>(?P<value>[^<]+)</UniqueName>", xml_text, re.IGNORECASE)
    version_match = re.search(r"<Version>(?P<value>\d+\.\d+\.\d+\.\d+)</Version>", xml_text, re.IGNORECASE)
    return {
        "solution_xml": str(solution_xml_path),
        "unique_name": unique_name_match.group("value").strip() if unique_name_match else None,
        "version": version_match.group("value").strip() if version_match else None,
    }


def path_has_ignored_part(path: Path) -> bool:
    return any(part.lower() in IGNORED_PCF_PATH_PARTS for part in path.parts)


def find_pcf_package_root(start: Path, repo_root_path: Path) -> Path:
    current = start.resolve()
    repo_root_resolved = repo_root_path.resolve()
    while True:
        if list(current.glob("*.pcfproj")):
            return current
        if current == repo_root_resolved or current.parent == current:
            break
        current = current.parent
    raise RuntimeError(
        f"Could not locate a PCF package root above {start}. Expected a parent folder containing a .pcfproj file."
    )


def infer_plugin_assembly_file(project_path: Path, *, configuration: str, framework: str | None = None) -> Path:
    xml_root = ET.parse(project_path).getroot()
    assembly_name = read_msbuild_property(xml_root, "AssemblyName") or project_path.stem
    target_framework = framework or read_msbuild_property(xml_root, "TargetFramework") or first_framework(
        read_msbuild_property(xml_root, "TargetFrameworks")
    )
    if not target_framework:
        raise RuntimeError(f"Could not infer target framework from {project_path}. Pass --framework explicitly.")

    output_path = project_path.parent / "bin" / configuration / target_framework / f"{assembly_name}.dll"
    if not output_path.exists():
        raise RuntimeError(f"Inferred plug-in assembly does not exist: {output_path}")
    return output_path


def infer_plugin_package_file(project_path: Path, *, configuration: str) -> Path:
    configuration_root = project_path.parent / "bin" / configuration
    candidates = sorted(
        (
            path
            for path in configuration_root.rglob("*.nupkg")
            if not path.name.endswith(".snupkg")
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(
            f"Could not infer a plug-in NuGet package under {configuration_root}. "
            "Build or pack the project first, or pass --package-file explicitly."
        )
    return candidates[0]


def read_nuget_metadata(package_path: Path) -> dict[str, str | None]:
    with zipfile.ZipFile(package_path) as package:
        nuspec_name = next(
            (name for name in package.namelist() if name.lower().endswith(".nuspec")),
            None,
        )
        if not nuspec_name:
            raise RuntimeError(f"Could not find a .nuspec file inside {package_path}.")
        with package.open(nuspec_name) as handle:
            xml_root = ET.fromstring(handle.read())

    metadata = None
    for child in list(xml_root):
        local_name = child.tag.split("}", 1)[-1]
        if local_name == "metadata":
            metadata = child
            break
    if metadata is None:
        raise RuntimeError(f"Could not find a metadata node inside {package_path}.")

    return {
        "id": read_xml_child_text(metadata, "id"),
        "version": read_xml_child_text(metadata, "version"),
        "title": read_xml_child_text(metadata, "title"),
        "description": read_xml_child_text(metadata, "description"),
    }


def read_xml_child_text(parent: ET.Element, name: str) -> str | None:
    for child in list(parent):
        local_name = child.tag.split("}", 1)[-1]
        if local_name == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def read_msbuild_property(xml_root: ET.Element, name: str) -> str | None:
    for group in xml_root.findall(".//{*}PropertyGroup"):
        for child in list(group):
            local_name = child.tag.split("}", 1)[-1]
            if local_name == name and child.text and child.text.strip():
                return child.text.strip()
    return None


def first_framework(value: str | None) -> str | None:
    if not value:
        return None
    return next((item.strip() for item in value.split(";") if item.strip()), None)


def launch_auth_dialog(
    *,
    target_url: str | None = None,
    username: str | None = None,
    tenant_id: str | None = None,
    auto_validate: bool = False,
) -> dict[str, Any]:
    build_dotnet_project(dataverse_tool_project())
    build_dotnet_project(auth_dialog_project())

    temporary = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    temporary.close()
    output_path = Path(temporary.name)

    args = [
        str(auth_dialog_exe()),
        "--output-path",
        str(output_path),
        "--tool-dll-path",
        str(dataverse_tool_dll()),
    ]
    if target_url:
        args.extend(["--initial-target-url", target_url])
    if username:
        args.extend(["--initial-username", username])
    if tenant_id:
        args.extend(["--initial-tenant-id", tenant_id])
    if auto_validate:
        args.append("--auto-validate")

    completed = run_command(args, cwd=skill_root(), check=False)
    if not output_path.exists():
        raise RuntimeError("Authentication dialog did not produce an output payload.")

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    finally:
        output_path.unlink(missing_ok=True)

    if payload.get("cancelled"):
        raise RuntimeError(payload.get("message") or "Authentication dialog was cancelled.")
    if not payload.get("success"):
        error_message = payload.get("message") or "Authentication dialog did not complete successfully."
        if completed.returncode != 0:
            error_message = f"{error_message} (dialog exit code: {completed.returncode})"
        raise RuntimeError(error_message)
    return payload


def resolve_live_connection(
    *,
    environment_url: str | None = None,
    username: str | None = None,
    tenant_id: str | None = None,
    auth_dialog: bool = False,
    target_url: str | None = None,
    auto_validate: bool = False,
) -> dict[str, Any]:
    profile = active_pac_profile()
    requested_environment_url = environment_url or target_url
    if warning := build_pac_environment_mismatch_warning(
        requested_environment_url=requested_environment_url,
        pac_environment_url=profile.get("environment_url"),
    ):
        print(warning, file=sys.stderr)

    if auth_dialog:
        try:
            resolved_username = resolve_username(username)
        except RuntimeError:
            resolved_username = username
        resolved_tenant_id = resolve_tenant_id(tenant_id)
        payload = launch_auth_dialog(
            target_url=target_url or environment_url,
            username=resolved_username,
            tenant_id=resolved_tenant_id,
            auto_validate=auto_validate,
        )
        environment_value = payload.get("environmentUrl") or payload.get("EnvironmentUrl")
        username_value = payload.get("username") or payload.get("Username") or resolved_username
        tenant_value = payload.get("tenantId") or payload.get("TenantId") or resolved_tenant_id
        selected_solution = payload.get("selectedSolution") or payload.get("SelectedSolution") or {}
        return {
            "environment_url": environment_value,
            "username": username_value,
            "tenant_id": tenant_value,
            "solution_id": selected_solution.get("solutionId") or selected_solution.get("SolutionId"),
            "solution_unique_name": selected_solution.get("uniqueName") or selected_solution.get("UniqueName"),
            "solution_friendly_name": selected_solution.get("friendlyName") or selected_solution.get("FriendlyName"),
            "solution_version": selected_solution.get("version") or selected_solution.get("Version"),
            "solution_is_managed": selected_solution.get("isManaged")
            if "isManaged" in selected_solution
            else selected_solution.get("IsManaged"),
            "solution_is_patch": selected_solution.get("isPatch")
            if "isPatch" in selected_solution
            else selected_solution.get("IsPatch"),
            "solution_parent_id": selected_solution.get("parentSolutionId") or selected_solution.get("ParentSolutionId"),
            "solution_parent_unique_name": selected_solution.get("parentSolutionUniqueName")
            or selected_solution.get("ParentSolutionUniqueName"),
            "auth_payload": payload,
        }

    return {
        "environment_url": resolve_environment_url(environment_url),
        "username": resolve_username(username),
        "tenant_id": resolve_tenant_id(tenant_id),
        "solution_id": None,
        "solution_unique_name": None,
        "solution_friendly_name": None,
        "solution_version": None,
        "solution_is_managed": None,
        "solution_is_patch": None,
        "solution_parent_id": None,
        "solution_parent_unique_name": None,
        "auth_payload": None,
    }


def load_plugin_step_state_contract(target_repo_root: Path) -> list[dict[str, Any]]:
    return build_plugin_step_state_contract_from_profile(load_project_profile_raw(target_repo_root))


def load_project_profile_raw(target_repo_root: Path) -> dict[str, Any]:
    context = discover_repo_context(target_repo_root)
    project_profile = context.get("artifacts", {}).get("project_profile", {})
    raw_profile = project_profile.get("raw") if isinstance(project_profile, dict) else {}
    return raw_profile if isinstance(raw_profile, dict) else {}


def load_deployment_defaults(target_repo_root: Path) -> dict[str, Any]:
    raw_profile = load_project_profile_raw(target_repo_root)
    deployment_defaults = raw_profile.get("deploymentDefaults")
    if not isinstance(deployment_defaults, dict):
        return {}
    return json.loads(json.dumps(deployment_defaults))


def load_flow_guard_contract(target_repo_root: Path) -> dict[str, Any]:
    raw_profile = load_project_profile_raw(target_repo_root)

    candidate_paths: list[Path] = []
    if isinstance(raw_profile, dict):
        configured = (
            raw_profile.get("flowGuardSpecPath")
            or raw_profile.get("flowGuardsPath")
            or raw_profile.get("flow_guard_spec_path")
            or raw_profile.get("flow_guards_path")
        )
        if isinstance(configured, str) and configured.strip():
            configured_path = Path(configured.strip())
            candidate_paths.append(
                configured_path.resolve() if configured_path.is_absolute() else (target_repo_root / configured_path).resolve()
            )

    candidate_paths.extend((target_repo_root / relative).resolve() for relative in FLOW_GUARD_PATHS)

    seen_paths: set[Path] = set()
    for candidate in candidate_paths:
        if candidate in seen_paths:
            continue
        seen_paths.add(candidate)
        if not candidate.exists():
            continue
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "path": str(candidate),
                "load_error": "invalid-json",
                "raw": {},
            }
        if not isinstance(raw, dict):
            return {
                "path": str(candidate),
                "load_error": "expected-object",
                "raw": {},
            }
        return {
            "path": str(candidate),
            "raw": raw,
        }

    return {}


def build_plugin_step_state_contract_from_profile(raw_profile: dict[str, Any]) -> list[dict[str, Any]]:
    contract: list[dict[str, Any]] = []
    for item in ensure_list_value(raw_profile.get("criticalPluginSteps")):
        normalized = normalize_plugin_step_state_contract_entry(item, desired_state="Enabled")
        if normalized:
            contract.append(normalized)
    for item in ensure_list_value(raw_profile.get("intentionallyDisabledPluginSteps")):
        normalized = normalize_plugin_step_state_contract_entry(item, desired_state="Disabled")
        if normalized:
            contract.append(normalized)
    return contract


def normalize_plugin_step_state_contract_entry(value: Any, *, desired_state: str) -> dict[str, Any] | None:
    canonical_state = normalize_plugin_step_state(desired_state)
    if not canonical_state:
        raise RuntimeError(f"Unsupported desired plug-in step state: {desired_state}")

    if isinstance(value, str):
        normalized_name = value.strip()
        if not normalized_name:
            return None
        return {"name": normalized_name, "desiredState": canonical_state}

    if not isinstance(value, dict):
        return None

    entry: dict[str, Any] = {}
    if step_id := normalize_guid_string(value.get("sdkMessageProcessingStepId") or value.get("stepId")):
        entry["sdkMessageProcessingStepId"] = step_id

    for source_key, target_key in [
        ("name", "name"),
        ("pluginTypeName", "pluginTypeName"),
        ("messageName", "messageName"),
        ("primaryEntityLogicalName", "primaryEntityLogicalName"),
    ]:
        raw_item = value.get(source_key)
        if isinstance(raw_item, str) and raw_item.strip():
            entry[target_key] = raw_item.strip()

    stage = canonical_plugin_step_stage(value.get("stage"))
    if stage:
        entry["stage"] = stage

    mode = canonical_plugin_step_mode(value.get("mode"))
    if mode:
        entry["mode"] = mode

    if not entry:
        return None

    entry["desiredState"] = canonical_state
    return entry


def apply_plugin_step_state_defaults_to_registration_spec(
    spec: dict[str, Any],
    contract: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = json.loads(json.dumps(spec))
    steps = updated.get("steps")
    if not isinstance(steps, list):
        return updated

    for step in steps:
        if not isinstance(step, dict):
            continue

        if current_state := normalize_plugin_step_state(step.get("desiredState")):
            step["desiredState"] = current_state
            continue

        matched = next((item for item in contract if plugin_step_matches_selector(step, item)), None)
        step["desiredState"] = matched["desiredState"] if matched else "Enabled"

    return updated


def plugin_step_matches_selector(step: dict[str, Any], selector: dict[str, Any]) -> bool:
    selector_id = normalize_guid_string(selector.get("sdkMessageProcessingStepId") or selector.get("stepId"))
    step_id = normalize_guid_string(step.get("sdkMessageProcessingStepId") or step.get("stepId"))
    if selector_id and selector_id != step_id:
        return False

    for key in ("name", "pluginTypeName", "messageName", "primaryEntityLogicalName"):
        selector_value = selector.get(key)
        if selector_value is None:
            continue
        if normalize_casefold(selector_value) != normalize_casefold(step.get(key)):
            return False

    selector_stage = canonical_plugin_step_stage(selector.get("stage"))
    if selector_stage and selector_stage != canonical_plugin_step_stage(step.get("stage") or step.get("stageLabel")):
        return False

    selector_mode = canonical_plugin_step_mode(selector.get("mode"))
    if selector_mode and selector_mode != canonical_plugin_step_mode(step.get("mode") or step.get("modeLabel")):
        return False

    return True


def plugin_step_selector_from_payload(step: dict[str, Any]) -> dict[str, Any]:
    selector: dict[str, Any] = {}
    for key in ("name", "pluginTypeName", "messageName", "primaryEntityLogicalName"):
        value = step.get(key)
        if isinstance(value, str) and value.strip():
            selector[key] = value.strip()

    stage = canonical_plugin_step_stage(step.get("stage") or step.get("stageLabel"))
    if stage:
        selector["stage"] = stage

    mode = canonical_plugin_step_mode(step.get("mode") or step.get("modeLabel"))
    if mode:
        selector["mode"] = mode

    if not selector and (step_id := normalize_guid_string(step.get("sdkMessageProcessingStepId") or step.get("stepId"))):
        selector["sdkMessageProcessingStepId"] = step_id
    return selector


def normalize_plugin_step_state(value: Any) -> str | None:
    if isinstance(value, bool):
        return "Enabled" if value else "Disabled"
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    return {
        "0": "Enabled",
        "enabled": "Enabled",
        "enable": "Enabled",
        "active": "Enabled",
        "1": "Disabled",
        "disabled": "Disabled",
        "disable": "Disabled",
        "inactive": "Disabled",
    }.get(lowered)


def canonical_plugin_step_stage(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower().replace(" ", "").replace("-", "")
    return {
        "10": "PreValidation",
        "prevalidation": "PreValidation",
        "20": "PreOperation",
        "preoperation": "PreOperation",
        "pre": "PreOperation",
        "30": "MainOperation",
        "mainoperation": "MainOperation",
        "main": "MainOperation",
        "40": "PostOperation",
        "postoperation": "PostOperation",
        "post": "PostOperation",
    }.get(lowered, text)


def canonical_plugin_step_mode(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower().replace(" ", "").replace("-", "")
    return {
        "0": "Synchronous",
        "sync": "Synchronous",
        "synchronous": "Synchronous",
        "1": "Asynchronous",
        "async": "Asynchronous",
        "asynchronous": "Asynchronous",
    }.get(lowered, text)


def normalize_guid_string(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.lower()


def normalize_casefold(value: Any) -> str | None:
    text = str(value or "").strip()
    return text.casefold() if text else None


def ensure_list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def coerce_dataverse_row_data(
    table_logical_name: str,
    data: dict[str, Any],
    deployment_defaults: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(data, dict):
        return data

    typed_columns = (
        deployment_defaults.get("dataWrites", {}).get("typedColumns")
        if isinstance(deployment_defaults.get("dataWrites"), dict)
        else None
    )
    if not isinstance(typed_columns, dict):
        return data

    table_config = find_case_insensitive_mapping_value(typed_columns, table_logical_name)
    if not isinstance(table_config, dict):
        return data

    coerced = json.loads(json.dumps(data))
    for configured_column, column_type in table_config.items():
        if not isinstance(configured_column, str):
            continue
        actual_column = find_case_insensitive_key(coerced, configured_column)
        if not actual_column:
            continue
        coerced[actual_column] = coerce_dataverse_column_value(coerced[actual_column], column_type)
    return coerced


def coerce_dataverse_column_value(value: Any, column_type: Any) -> Any:
    normalized_type = normalize_typed_column_kind(column_type)
    if normalized_type == "choice" and isinstance(value, int) and not isinstance(value, bool):
        return {"type": "choice", "value": value}
    return value


def normalize_typed_column_kind(column_type: Any) -> str | None:
    if isinstance(column_type, str):
        text = column_type.strip()
        return text.casefold() if text else None
    if isinstance(column_type, dict):
        for key in ("type", "kind", "columnType"):
            value = column_type.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().casefold()
    return None


def find_case_insensitive_key(mapping: dict[str, Any], expected_key: str) -> str | None:
    expected = expected_key.casefold()
    for key in mapping:
        if isinstance(key, str) and key.casefold() == expected:
            return key
    return None


def find_case_insensitive_mapping_value(mapping: dict[str, Any], expected_key: str) -> Any:
    actual_key = find_case_insensitive_key(mapping, expected_key)
    return mapping.get(actual_key) if actual_key is not None else None
