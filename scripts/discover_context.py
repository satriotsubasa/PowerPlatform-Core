#!/usr/bin/env python3
"""Discover likely Power Platform project context from a repository."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

EXCLUDED_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".vs",
    ".vscode",
    "bin",
    "coverage",
    "dist",
    "node_modules",
    "obj",
    "out",
    "packages",
    "target",
}
IGNORED_DISCOVERY_DIRS = {
    "test",
    "tests",
    "fixture",
    "fixtures",
    "example",
    "examples",
    "sample",
    "samples",
}

PIPELINE_SUFFIXES = {".yml", ".yaml"}
DATAVERSE_URL_RE = re.compile(r"https://[A-Za-z0-9._-]+(?:\.crm\d*|\.api)\.[A-Za-z0-9.-]+/?", re.IGNORECASE)
OPTION_VALUE_PATTERNS = {
    "environment": re.compile(r"--environment\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s`]+))", re.IGNORECASE),
    "publisher_prefix": re.compile(r"--publisher-prefix\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s`]+))", re.IGNORECASE),
    "solution_unique_name": re.compile(r"--solution-unique-name\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s`]+))", re.IGNORECASE),
    "solution_name": re.compile(r"\bpac\s+solution\s+\S+.*?--name\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s`]+))", re.IGNORECASE),
}
PAC_COMMAND_RE = re.compile(r"\bpac\s+([a-z-]+)\s+([a-z-]+)", re.IGNORECASE)
SLN_PROJECT_RE = re.compile(
    r'^Project\("\{[^"]+\}"\)\s*=\s*"([^"]+)",\s*"([^"]+)",\s*"\{[^"]+\}"$',
    re.MULTILINE,
)
PLUGIN_PACKAGE_MARKERS = {
    "microsoft.crmsdk.coreassemblies",
    "microsoft.powerplatform.dataverse.client",
    "microsoft.xrm.sdk",
}
PLUGIN_CODE_MARKERS = {
    "iplugin": "IPlugin",
    "microsoft.xrm.sdk": "Microsoft.Xrm.Sdk",
    "invalidpluginexecutionexception": "InvalidPluginExecutionException",
    "itracingservice": "ITracingService",
}
PROJECT_ROLE_SUFFIXES = {
    ".business": "business",
    ".data": "data",
    ".plugins": "plugins",
    ".pcf": "pcf",
}
LOGICAL_NAME_PREFIX_RE = re.compile(r"\b([a-z][a-z0-9]{1,15})_[a-z0-9][a-z0-9_]*\b")
COMMON_SYSTEM_PREFIXES = {
    "aib",
    "bco",
    "bot",
    "cr",
    "msdyn",
    "msdynce",
    "msfsi",
    "msft",
    "mspp",
    "mpa",
    "adx",
}
CLASSIC_JS_NAMESPACE_MARKERS = (
    "Xrm.Page",
)
MODULE_JS_MARKERS = (
    "export ",
    "import ",
)
PROJECT_PROFILE_PATHS = (
    Path(".codex") / "power-platform.project-profile.json",
    Path("power-platform.project-profile.json"),
)
GENERIC_AREA_NAMES = {
    "business",
    "codeapp",
    "codeapps",
    "code app",
    "code apps",
    "data",
    "plugins",
    "webresources",
    "web resources",
    "pcf",
    "tools",
    "dataverse",
    "reference",
    "word templates",
    "word_templates",
}
REPO_AREA_KEYS = (
    "business",
    "codeapp",
    "data",
    "supplemental_data",
    "plugins",
    "webresources",
    "pcf",
    "tools",
    "dataverse",
    "reference",
    "word_templates",
)
PRIMARY_SOLUTION_ROLES = {"app-metadata", "dataverse-reference"}
SUPPORTING_SOLUTION_ROLES = {"pcf-packaging", "reference-only"}


def discover_overlay_skills(skills_root: str | None = None) -> list[dict[str, str]]:
    """Scan installed skills for any that extend powerplatform-core."""
    if skills_root is None:
        skills_root = os.path.join(os.path.expanduser("~"), ".codex", "skills")
    overlays: list[dict[str, str]] = []
    if not os.path.isdir(skills_root):
        return overlays
    for name in os.listdir(skills_root):
        pkg_path = os.path.join(skills_root, name, "skill-package.json")
        if not os.path.isfile(pkg_path):
            continue
        try:
            with open(pkg_path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("extends") == "powerplatform-core":
                overlays.append({
                    "name": name,
                    "description": data.get("description", ""),
                })
        except (json.JSONDecodeError, OSError):
            continue
    return overlays


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan a repo and infer likely Power Platform / Dataverse project context.",
    )
    parser.add_argument("--path", default=".", help="Path to scan. Defaults to the current directory.")
    parser.add_argument(
        "--include-pac-auth",
        action="store_true",
        help="Also inspect local 'pac auth list' output if PAC CLI is available.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum directory depth to scan beneath the provided path. Defaults to 10.",
    )
    parser.add_argument(
        "--output",
        help="Optional file path to write JSON output to.",
    )
    args = parser.parse_args()

    scan_root = Path(args.path).resolve()
    if not scan_root.exists():
        print(f"ERROR: Scan path does not exist: {scan_root}", file=sys.stderr)
        return 2
    if not scan_root.is_dir():
        print(f"ERROR: Scan path is not a directory: {scan_root}", file=sys.stderr)
        return 2

    repo_root = find_repo_root(scan_root)
    artifacts = {
        "solution_files": [],
        "solution_projects": [],
        "unpacked_solutions": [],
        "customization_files": [],
        "early_bound_configs": [],
        "plugin_projects": [],
        "pcf_controls": [],
        "pipeline_files": [],
        "deployment_settings": [],
        "code_apps": [],
        "pac_auth_profiles": [],
        "repo_areas": detect_repo_areas(scan_root),
        "project_profile": load_project_profile(scan_root),
    }

    for path in iter_files(scan_root, args.max_depth):
        name = path.name.lower()
        if name.endswith(".sln"):
            parsed = parse_solution_file(path, scan_root)
            if parsed:
                artifacts["solution_files"].append(parsed)
        elif name.endswith(".cdsproj"):
            artifacts["solution_projects"].append(parse_solution_project(path, scan_root))
        elif name == "solution.xml" and path.parent.name.lower() == "other":
            artifacts["unpacked_solutions"].append(parse_unpacked_solution(path, scan_root))
        elif name == "customizations.xml":
            parsed = parse_customizations_file(path, scan_root)
            if parsed:
                artifacts["customization_files"].append(parsed)
        elif name == "buildersettings.json" or (
            name.startswith("earlyboundgenerator") and name.endswith(".xml")
        ):
            parsed = parse_early_bound_config(path, scan_root)
            if parsed:
                artifacts["early_bound_configs"].append(parsed)
        elif name == "controlmanifest.input.xml":
            artifacts["pcf_controls"].append(parse_pcf_manifest(path, scan_root))
        elif name.endswith(".csproj"):
            parsed = parse_plugin_project(path, scan_root)
            if parsed:
                artifacts["plugin_projects"].append(parsed)
        elif path.suffix.lower() in PIPELINE_SUFFIXES:
            parsed = parse_pipeline_file(path, scan_root)
            if parsed:
                artifacts["pipeline_files"].append(parsed)
        elif name == "power.config.json":
            parsed = parse_code_app_config(path, scan_root)
            if parsed:
                artifacts["code_apps"].append(parsed)
        elif name.endswith(".json"):
            parsed = parse_deployment_settings(path, scan_root)
            if parsed:
                artifacts["deployment_settings"].append(parsed)

    annotate_solution_source_roles(artifacts)
    if args.include_pac_auth:
        artifacts["pac_auth_profiles"] = inspect_pac_auth()
    artifacts["repo_profile"] = build_repo_profile(scan_root, artifacts)

    candidates = collect_candidates(artifacts)
    inferred = infer_context(artifacts, candidates)
    warnings = build_warnings(artifacts, candidates)
    questions = build_questions(artifacts, candidates, inferred)

    overlay_skills = discover_overlay_skills()

    result = {
        "scan_root": str(scan_root),
        "repo_root": str(repo_root),
        "inferred": inferred,
        "candidates": candidates,
        "recommended_questions": questions,
        "warnings": warnings,
        "overlay_skills": overlay_skills,
        "artifacts": artifacts,
    }

    output_text = json.dumps(result, indent=2)
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


def find_repo_root(start: Path) -> Path:
    current = start
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return start
        current = current.parent


def iter_files(root: Path, max_depth: int) -> Iterable[Path]:
    root_parts = len(root.parts)
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        depth = len(current_path.parts) - root_parts
        dirnames[:] = [
            name
            for name in dirnames
            if name.lower() not in EXCLUDED_DIRS
            and name.lower() not in IGNORED_DISCOVERY_DIRS
            and not name.startswith(".terraform")
        ]
        if depth >= max_depth:
            dirnames[:] = []
        for filename in filenames:
            yield current_path / filename


def relative_path(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root))


def safe_read_text(path: Path, max_bytes: int = 1_500_000) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            return None
    except OSError:
        return None


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_xml(path: Path) -> ET.Element | None:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError:
        return None
    except OSError:
        return None


def xml_texts(root: ET.Element, *names: str) -> list[str]:
    wanted = {name.lower() for name in names}
    values = []
    for element in root.iter():
        if local_name(element.tag).lower() in wanted:
            text = (element.text or "").strip()
            if text:
                values.append(text)
    return dedupe(values)


def property_values(root: ET.Element, *names: str) -> dict[str, list[str]]:
    wanted = {name.lower() for name in names}
    values: dict[str, list[str]] = {name: [] for name in names}
    for prop_group in root.findall(".//{*}PropertyGroup"):
        for child in list(prop_group):
            child_name = local_name(child.tag)
            if child_name.lower() in wanted:
                text = (child.text or "").strip()
                if text:
                    values[child_name] = values.get(child_name, []) + [text]
    return {key: dedupe(val) for key, val in values.items() if val}


def dedupe(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def parse_solution_project(path: Path, root: Path) -> dict[str, object]:
    parsed = {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "name": path.stem,
        "target_frameworks": [],
        "solution_package_types": [],
        "assembly_name": None,
        "root_namespace": None,
        "project_references": [],
    }
    xml_root = parse_xml(path)
    if xml_root is None:
        return parsed

    props = property_values(
        xml_root,
        "TargetFramework",
        "TargetFrameworks",
        "SolutionPackageType",
        "AssemblyName",
        "RootNamespace",
    )
    parsed["target_frameworks"] = dedupe(
        split_framework_values(props.get("TargetFramework", []) + props.get("TargetFrameworks", []))
    )
    parsed["solution_package_types"] = props.get("SolutionPackageType", [])
    parsed["assembly_name"] = first_or_none(props.get("AssemblyName", []))
    parsed["root_namespace"] = first_or_none(props.get("RootNamespace", []))
    parsed["project_references"] = dedupe(
        [
            element.get("Include", "").strip()
            for element in xml_root.iter()
            if local_name(element.tag) == "ProjectReference" and element.get("Include")
        ]
    )
    return parsed


def parse_solution_file(path: Path, root: Path) -> dict[str, object] | None:
    text = safe_read_text(path, max_bytes=1_000_000)
    if not text:
        return None
    projects = [
        {
            "name": match.group(1),
            "path": match.group(2).replace("\\\\", "\\"),
        }
        for match in SLN_PROJECT_RE.finditer(text)
    ]
    return {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "project_count": len(projects),
        "projects": projects,
    }


def parse_unpacked_solution(path: Path, root: Path) -> dict[str, object]:
    parsed = {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "solution_folder": str(path.parent.parent),
        "solution_folder_relative_path": relative_path(path.parent.parent, root),
        "unique_name": None,
        "version": None,
        "publisher_prefix": None,
        "managed_flag": None,
    }
    xml_root = parse_xml(path)
    if xml_root is None:
        return parsed
    parsed["unique_name"] = first_or_none(xml_texts(xml_root, "UniqueName"))
    parsed["version"] = first_or_none(xml_texts(xml_root, "Version"))
    parsed["publisher_prefix"] = first_or_none(xml_texts(xml_root, "CustomizationPrefix"))
    parsed["managed_flag"] = first_or_none(xml_texts(xml_root, "Managed"))
    return parsed


def parse_customizations_file(path: Path, root: Path) -> dict[str, object] | None:
    xml_root = parse_xml(path)
    if xml_root is None:
        return None
    entity_names = xml_texts(xml_root, "Name")
    entity_names = [name for name in entity_names if re.match(r"^[a-zA-Z0-9_]+$", name)]
    return {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "entity_name_samples": entity_names[:10],
    }


def parse_early_bound_config(path: Path, root: Path) -> dict[str, object] | None:
    text = safe_read_text(path, max_bytes=1_000_000)
    if not text:
        return None
    lower_name = path.name.lower()
    if lower_name != "buildersettings.json" and not lower_name.startswith("earlyboundgenerator"):
        return None
    prefix_counts = extract_logical_name_prefix_counts(text)
    namespace_match = re.search(r"<Namespace>([^<]+)</Namespace>", text, re.IGNORECASE)
    return {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "namespace": normalize_space(namespace_match.group(1)) if namespace_match else None,
        "prefix_candidates": select_prefix_candidates_from_counts(prefix_counts),
    }


def parse_plugin_project(path: Path, root: Path) -> dict[str, object] | None:
    xml_root = parse_xml(path)
    text = safe_read_text(path, max_bytes=800_000)
    package_refs: list[str] = []
    target_frameworks: list[str] = []
    assembly_name = None
    root_namespace = None
    project_references: list[str] = []
    if xml_root is not None:
        props = property_values(xml_root, "TargetFramework", "TargetFrameworks", "AssemblyName", "RootNamespace")
        target_frameworks = dedupe(
            split_framework_values(props.get("TargetFramework", []) + props.get("TargetFrameworks", []))
        )
        assembly_name = first_or_none(props.get("AssemblyName", []))
        root_namespace = first_or_none(props.get("RootNamespace", []))
        package_refs = dedupe(
            [
                (element.get("Include") or element.get("Update") or "").strip()
                for element in xml_root.iter()
                if local_name(element.tag) == "PackageReference" and (element.get("Include") or element.get("Update"))
            ]
        )
        project_references = dedupe(
            [
                (element.get("Include") or "").strip()
                for element in xml_root.iter()
                if local_name(element.tag) == "ProjectReference" and element.get("Include")
            ]
        )
    elif text is None:
        return None

    lower_packages = {package.lower() for package in package_refs}
    package_signals = sorted(package for package in lower_packages if package in PLUGIN_PACKAGE_MARKERS)
    code_signals = scan_plugin_code_signals(path.parent)
    plugin_name_hint = "plugin" in path.stem.lower() or "plugin" in path.parent.name.lower()
    likely_plugin_project = bool(
        package_signals
        or (plugin_name_hint and (code_signals or project_references))
    )
    if not likely_plugin_project:
        return None
    uses_ilrepack = bool(text and "ILRepack" in text)

    return {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "target_frameworks": target_frameworks,
        "assembly_name": assembly_name,
        "root_namespace": root_namespace,
        "package_references": package_refs,
        "project_references": project_references,
        "uses_ilrepack": uses_ilrepack,
        "plugin_signals": package_signals + code_signals,
    }


def scan_plugin_code_signals(project_dir: Path) -> list[str]:
    matches = set()
    scanned_files = 0
    for current_root, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [name for name in dirnames if name.lower() not in EXCLUDED_DIRS]
        for filename in filenames:
            if not filename.lower().endswith(".cs"):
                continue
            scanned_files += 1
            if scanned_files > 30:
                return sorted(matches)
            text = safe_read_text(Path(current_root) / filename, max_bytes=300_000)
            if not text:
                continue
            lowered = text.lower()
            for token, label in PLUGIN_CODE_MARKERS.items():
                if token in lowered:
                    matches.add(label)
    return sorted(matches)


def parse_pcf_manifest(path: Path, root: Path) -> dict[str, object]:
    parsed = {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "namespace": None,
        "control_name": None,
        "version": None,
        "control_kind": None,
    }
    xml_root = parse_xml(path)
    if xml_root is None:
        return parsed
    control = None
    for element in xml_root.iter():
        if local_name(element.tag).lower() == "control":
            control = element
            break
    if control is not None:
        parsed["namespace"] = control.get("namespace")
        parsed["control_name"] = control.get("constructor")
        parsed["version"] = control.get("version")

    control_kind = "field"
    for element in xml_root.iter():
        tag_name = local_name(element.tag).lower()
        if tag_name == "data-set":
            control_kind = "dataset"
            break
    parsed["control_kind"] = control_kind
    return parsed


def parse_pipeline_file(path: Path, root: Path) -> dict[str, object] | None:
    text = safe_read_text(path, max_bytes=1_000_000)
    if not text:
        return None
    commands = dedupe([" ".join(match.groups()).lower() for match in PAC_COMMAND_RE.finditer(text)])
    if not commands:
        return None
    environments = dedupe(
        extract_option_values(text, "environment") + [value for value in DATAVERSE_URL_RE.findall(text)]
    )
    publisher_prefixes = dedupe(extract_option_values(text, "publisher_prefix"))
    solution_names = dedupe(
        extract_option_values(text, "solution_unique_name") + extract_option_values(text, "solution_name")
    )
    managed_strategy_hints = []
    lowered = text.lower()
    if "--managed true" in lowered:
        managed_strategy_hints.append("managed-release")
    if "--managed false" in lowered:
        managed_strategy_hints.append("unmanaged")
    if "packagetype managed" in lowered:
        managed_strategy_hints.append("managed")
    if "packagetype unmanaged" in lowered:
        managed_strategy_hints.append("unmanaged")
    return {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "pac_commands": commands,
        "solution_names": solution_names,
        "publisher_prefixes": publisher_prefixes,
        "environment_urls": environments,
        "managed_strategy_hints": dedupe(managed_strategy_hints),
    }


def parse_code_app_config(path: Path, root: Path) -> dict[str, object] | None:
    """Parse a power.config.json file and return code app metadata."""
    text = safe_read_text(path, max_bytes=200_000)
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    # Require at least one known code app field to avoid false positives
    if not any(k in data for k in ("displayName", "environmentId", "appId", "name")):
        return None
    return {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "display_name": data.get("displayName") or data.get("name", ""),
        "environment_id": data.get("environmentId", ""),
        "app_id": data.get("appId", ""),
    }


def parse_deployment_settings(path: Path, root: Path) -> dict[str, object] | None:
    text = safe_read_text(path, max_bytes=800_000)
    if not text:
        return None
    if "ConnectionReferences" not in text and "EnvironmentVariables" not in text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    connection_references = data.get("ConnectionReferences", [])
    environment_variables = data.get("EnvironmentVariables", [])
    if not connection_references and not environment_variables:
        return None
    return {
        "path": str(path),
        "relative_path": relative_path(path, root),
        "connection_reference_count": len(connection_references),
        "environment_variable_count": len(environment_variables),
    }


def inspect_pac_auth() -> list[dict[str, object]]:
    try:
        completed = subprocess.run(
            ["pac", "auth", "list"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except FileNotFoundError:
        return []
    if completed.returncode != 0:
        return []

    profiles = []
    for line in completed.stdout.splitlines():
        line = line.rstrip()
        url_match = DATAVERSE_URL_RE.search(line)
        if not url_match:
            continue
        line_without_url = line.replace(url_match.group(0), " ")
        prefix_match = re.match(r"^\[(\d+)\]\s+(\*)?\s*(\S+)\s+(.*)$", line_without_url)
        profile = {
            "raw": line.strip(),
            "url": url_match.group(0),
        }
        if prefix_match:
            profile["index"] = int(prefix_match.group(1))
            profile["active"] = bool(prefix_match.group(2))
            profile["kind"] = prefix_match.group(3)
            profile["name"] = normalize_space(prefix_match.group(4))
        profiles.append(profile)
    return profiles


def detect_repo_areas(scan_root: Path) -> dict[str, list[str]]:
    areas = {key: [] for key in REPO_AREA_KEYS}
    try:
        directories = [path for path in scan_root.iterdir() if path.is_dir()]
    except OSError:
        return areas

    for directory in directories:
        name = directory.name.lower()
        relative = str(directory.relative_to(scan_root))
        if name.endswith(".business") or name == "business":
            areas["business"].append(relative)
        if name.endswith(".data"):
            areas["data"].append(relative)
        elif name == "data":
            areas["supplemental_data"].append(relative)
        if name.endswith(".plugins") or name == "plugins":
            areas["plugins"].append(relative)
        if "webresource" in name:
            areas["webresources"].append(relative)
        if name.endswith(".pcf") or name == "pcf":
            areas["pcf"].append(relative)
        if name == "tools":
            areas["tools"].append(relative)
        if name == "dataverse":
            areas["dataverse"].append(relative)
        if name == "reference":
            areas["reference"].append(relative)
        if name == "word templates" or name == "word_templates":
            areas["word_templates"].append(relative)

    return {key: sorted(dedupe(values)) for key, values in areas.items()}


def load_project_profile(scan_root: Path) -> dict[str, object]:
    for relative in PROJECT_PROFILE_PATHS:
        profile_path = scan_root / relative
        if not profile_path.exists():
            continue
        try:
            raw = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "path": str(profile_path),
                "relative_path": str(relative),
                "load_error": "invalid-json",
            }
        if not isinstance(raw, dict):
            return {
                "path": str(profile_path),
                "relative_path": str(relative),
                "load_error": "expected-object",
            }
        return {
            "path": str(profile_path),
            "relative_path": str(relative),
            "repo_solution_name": profile_scalar(raw, "repoSolutionName", "repo_solution_name"),
            "main_solution_unique_name": profile_scalar(raw, "mainSolutionUniqueName", "main_solution_unique_name"),
            "publisher_prefix": normalize_prefix_value(
                profile_scalar(raw, "publisherPrefix", "publisher_prefix")
            ),
            "managed_strategy": profile_scalar(raw, "managedStrategy", "managed_strategy"),
            "repo_archetype": profile_scalar(raw, "repoArchetype", "repo_archetype"),
            "solution_source_model": profile_scalar(raw, "solutionSourceModel", "solution_source_model"),
            "namespace_root": profile_scalar(raw, "namespaceRoot", "namespace_root"),
            "local_supporting_solutions": profile_list(
                raw,
                "localSupportingSolutions",
                "local_supporting_solutions",
            ),
            "source_areas": normalize_profile_source_areas(raw),
            "raw": raw,
        }
    return {}


def profile_scalar(raw: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str):
            normalized = normalize_space(value)
            if normalized:
                return normalized
    return None


def profile_list(raw: dict[str, object], *keys: str) -> list[str]:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str):
            normalized = normalize_space(value)
            return [normalized] if normalized else []
        if isinstance(value, list):
            return dedupe(str(item).strip() for item in value if str(item).strip())
    return []


def normalize_profile_source_areas(raw: dict[str, object]) -> dict[str, list[str]]:
    areas = raw.get("sourceAreas") or raw.get("source_areas")
    if not isinstance(areas, dict):
        return {}

    aliases = {
        "business": "business",
        "data": "data",
        "supplementalData": "supplemental_data",
        "supplemental_data": "supplemental_data",
        "plugins": "plugins",
        "webResources": "webresources",
        "web_resources": "webresources",
        "webresources": "webresources",
        "pcf": "pcf",
        "tools": "tools",
        "dataverse": "dataverse",
        "reference": "reference",
        "wordTemplates": "word_templates",
        "word_templates": "word_templates",
    }
    normalized: dict[str, list[str]] = {}
    for key, canonical in aliases.items():
        if key not in areas:
            continue
        value = areas[key]
        if isinstance(value, str):
            normalized[canonical] = [normalize_space(value)] if normalize_space(value) else []
        elif isinstance(value, list):
            normalized[canonical] = dedupe(str(item).strip() for item in value if str(item).strip())
    return {key: value for key, value in normalized.items() if value}


def normalize_prefix_value(value: str | None) -> str | None:
    if not value:
        return None
    return value.lower()


def merge_repo_areas(
    detected_areas: dict[str, list[str]],
    project_profile: dict[str, object],
) -> dict[str, list[str]]:
    merged = {key: list(detected_areas.get(key, [])) for key in REPO_AREA_KEYS}
    configured_areas = project_profile.get("source_areas", {}) if project_profile else {}
    if not isinstance(configured_areas, dict):
        return {key: dedupe(values) for key, values in merged.items()}

    for key in REPO_AREA_KEYS:
        configured_values = configured_areas.get(key, []) if isinstance(configured_areas, dict) else []
        if configured_values:
            merged[key] = dedupe([*configured_values, *merged.get(key, [])])
    return {key: dedupe(values) for key, values in merged.items()}


def annotate_solution_source_roles(artifacts: dict[str, object]) -> None:
    repo_areas = artifacts.get("repo_areas", {})
    for item in artifacts.get("unpacked_solutions", []):
        item["solution_role"] = infer_solution_role(item.get("solution_folder_relative_path"), repo_areas)
    for item in artifacts.get("solution_projects", []):
        item["solution_role"] = infer_solution_role(item.get("relative_path"), repo_areas)


def infer_solution_role(relative_path: object, repo_areas: object) -> str:
    if not isinstance(relative_path, str) or not isinstance(repo_areas, dict):
        return "app-metadata"
    if path_is_under_any(relative_path, repo_areas.get("pcf", [])):
        return "pcf-packaging"
    if path_is_under_any(relative_path, repo_areas.get("dataverse", [])):
        return "dataverse-reference"
    if path_is_under_any(relative_path, repo_areas.get("reference", [])):
        return "reference-only"
    return "app-metadata"


def path_is_under_any(relative_path: str, candidate_roots: object) -> bool:
    if not isinstance(candidate_roots, list):
        return False
    lowered_path = normalize_relative_repo_path(relative_path).lower()
    for root in candidate_roots:
        if not isinstance(root, str):
            continue
        lowered_root = normalize_relative_repo_path(root).lower()
        if lowered_path == lowered_root or lowered_path.startswith(lowered_root + "/"):
            return True
    return False


def build_repo_profile(scan_root: Path, artifacts: dict[str, object]) -> dict[str, object]:
    project_profile = artifacts.get("project_profile", {})
    detected_repo_areas = artifacts["repo_areas"]
    repo_areas = merge_repo_areas(detected_repo_areas, project_profile)
    repo_solution_names = dedupe([Path(item["relative_path"]).stem for item in artifacts["solution_files"]])
    namespace_roots = collect_namespace_root_candidates(artifacts)
    repo_archetype = None
    solution_source_model = None
    local_solution_sources = collect_local_solution_sources(artifacts)
    has_primary_solution_source = any(
        source.get("role") in PRIMARY_SOLUTION_ROLES for source in local_solution_sources
    )
    has_any_solution_source = bool(local_solution_sources)

    has_layered_code_layout = bool(
        repo_solution_names
        and (repo_areas.get("data") or repo_areas.get("supplemental_data"))
        and repo_areas.get("plugins")
        and repo_areas.get("webresources")
    )
    if has_layered_code_layout:
        repo_archetype = project_profile.get("repo_archetype") or "layered-dotnet-dataverse"
        if has_primary_solution_source:
            solution_source_model = "hybrid-code-and-solution-source"
        elif has_any_solution_source:
            solution_source_model = "hybrid-code-and-supporting-solution-source"
        else:
            solution_source_model = "code-centric-no-unpacked-solution"
    elif has_any_solution_source:
        repo_archetype = project_profile.get("repo_archetype") or "solution-centric-dataverse"
        solution_source_model = project_profile.get("solution_source_model") or "unpacked-solution-source"

    publisher_prefixes = []
    for item in artifacts["early_bound_configs"]:
        publisher_prefixes.extend(item.get("prefix_candidates", []))
    publisher_prefixes.extend(
        scan_paths_for_prefixes(
            scan_root,
            repo_areas.get("data", []) + repo_areas.get("supplemental_data", []),
            allowed_suffixes={".json", ".xml", ".cs"},
            max_files=40,
        )
    )
    publisher_prefixes.extend(
        scan_paths_for_prefixes(
            scan_root,
            repo_areas.get("webresources", []),
            allowed_suffixes={".js", ".html"},
            max_files=40,
        )
    )
    configured_prefix = project_profile.get("publisher_prefix")
    if configured_prefix:
        publisher_prefixes.insert(0, str(configured_prefix))

    if project_profile.get("repo_solution_name"):
        repo_solution_names = dedupe([str(project_profile["repo_solution_name"]), *repo_solution_names])
    if project_profile.get("namespace_root"):
        namespace_roots = dedupe([str(project_profile["namespace_root"]), *namespace_roots])

    return {
        "project_profile_path": project_profile.get("relative_path"),
        "project_profile_detected": bool(project_profile),
        "repo_solution_names": repo_solution_names,
        "namespace_roots": namespace_roots,
        "repo_archetype": project_profile.get("repo_archetype") or repo_archetype,
        "solution_source_model": project_profile.get("solution_source_model") or solution_source_model,
        "publisher_prefixes": dedupe(prefix.lower() for prefix in publisher_prefixes),
        "webresource_style": infer_webresource_style(scan_root, repo_areas.get("webresources", [])),
        "plugin_packaging_style": infer_plugin_packaging_style(artifacts["plugin_projects"]),
        "preferred_repo_areas": repo_areas,
        "local_solution_sources": local_solution_sources,
        "repo_features": collect_repo_features(repo_areas),
        "main_solution_unique_name": project_profile.get("main_solution_unique_name"),
        "managed_strategy": project_profile.get("managed_strategy"),
        "local_supporting_solutions": project_profile.get("local_supporting_solutions", []),
    }


def collect_namespace_root_candidates(artifacts: dict[str, object]) -> list[str]:
    counts: dict[str, int] = {}

    for item in artifacts["solution_files"]:
        for project in item.get("projects", []):
            root = strip_project_role_suffix(str(project.get("name") or ""))
            if root:
                counts[root] = counts.get(root, 0) + 1

    for item in artifacts["plugin_projects"]:
        root = strip_project_role_suffix(str(item.get("root_namespace") or ""))
        if root:
            counts[root] = counts.get(root, 0) + 1

    for role in ("business", "data", "plugins", "pcf"):
        for relative in artifacts["repo_areas"].get(role, []):
            root = strip_project_role_suffix(Path(relative).name)
            if root:
                counts[root] = counts.get(root, 0) + 1

    return [name for name, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def strip_project_role_suffix(value: str) -> str | None:
    lowered = value.lower().strip()
    for suffix in PROJECT_ROLE_SUFFIXES:
        if lowered.endswith(suffix):
            trimmed = value[: -len(suffix)].strip()
            return trimmed or None
    return None


def scan_paths_for_prefixes(
    scan_root: Path,
    relative_dirs: list[str],
    *,
    allowed_suffixes: set[str],
    max_files: int,
) -> list[str]:
    prefix_counts: dict[str, int] = {}
    scanned_files = 0
    for relative in relative_dirs:
        base_path = scan_root / relative
        if not base_path.exists():
            continue
        for current_root, dirnames, filenames in os.walk(base_path):
            dirnames[:] = [name for name in dirnames if name.lower() not in EXCLUDED_DIRS]
            for filename in filenames:
                if scanned_files >= max_files:
                    return select_prefix_candidates_from_counts(prefix_counts)
                file_path = Path(current_root) / filename
                if file_path.suffix.lower() not in allowed_suffixes:
                    continue
                text = safe_read_text(file_path, max_bytes=350_000)
                if not text:
                    continue
                scanned_files += 1
                for prefix, count in extract_logical_name_prefix_counts(text).items():
                    prefix_counts[prefix] = prefix_counts.get(prefix, 0) + count
    return select_prefix_candidates_from_counts(prefix_counts)


def extract_logical_name_prefix_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for prefix in LOGICAL_NAME_PREFIX_RE.findall(text):
        normalized = prefix.lower()
        if normalized in COMMON_SYSTEM_PREFIXES:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def select_prefix_candidates_from_counts(prefix_counts: dict[str, int]) -> list[str]:
    if not prefix_counts:
        return []
    highest = max(prefix_counts.values())
    minimum_hits = 2 if highest >= 2 else 1
    ordered = sorted(prefix_counts.items(), key=lambda item: (-item[1], item[0]))
    return [prefix for prefix, count in ordered if count >= minimum_hits][:5]


def infer_webresource_style(scan_root: Path, relative_dirs: list[str]) -> str | None:
    classic_hits = 0
    module_hits = 0
    scanned = 0
    for relative in relative_dirs:
        base_path = scan_root / relative
        if not base_path.exists():
            continue
        for current_root, dirnames, filenames in os.walk(base_path):
            dirnames[:] = [name for name in dirnames if name.lower() not in EXCLUDED_DIRS]
            for filename in filenames:
                if scanned >= 20:
                    break
                file_path = Path(current_root) / filename
                if file_path.suffix.lower() not in {".js", ".ts"}:
                    continue
                text = safe_read_text(file_path, max_bytes=300_000)
                if not text:
                    continue
                scanned += 1
                if any(marker in text for marker in CLASSIC_JS_NAMESPACE_MARKERS):
                    classic_hits += 1
                if file_path.suffix.lower() == ".ts" or any(marker in text for marker in MODULE_JS_MARKERS):
                    module_hits += 1
    if classic_hits and classic_hits >= module_hits:
        return "classic-namespace-js"
    if module_hits:
        return "module-ts-or-bundled-js"
    return None


def infer_plugin_packaging_style(plugin_projects: list[dict[str, object]]) -> str | None:
    if not plugin_projects:
        return None
    if any(item.get("uses_ilrepack") for item in plugin_projects):
        return "ilrepack-merged-assembly"
    if any(item.get("project_references") for item in plugin_projects):
        return "multi-project-assembly"
    return "single-project-assembly"


def extract_option_values(text: str, option_key: str) -> list[str]:
    pattern = OPTION_VALUE_PATTERNS[option_key]
    values = []
    for match in pattern.finditer(text):
        value = next(group for group in match.groups() if group)
        values.append(value.strip())
    return dedupe(values)


def collect_local_solution_sources(artifacts: dict[str, object]) -> list[dict[str, object]]:
    sources = []
    for item in artifacts["unpacked_solutions"]:
        sources.append(
            {
                "name": item.get("unique_name"),
                "relative_path": item.get("solution_folder_relative_path"),
                "source_type": "unpacked-solution",
                "role": item.get("solution_role") or "app-metadata",
                "version": item.get("version"),
            }
        )
    for item in artifacts["solution_projects"]:
        sources.append(
            {
                "name": item.get("name"),
                "relative_path": item.get("relative_path"),
                "source_type": "solution-project",
                "role": item.get("solution_role") or "app-metadata",
                "version": None,
            }
        )
    return sources


def collect_repo_features(repo_areas: dict[str, list[str]]) -> list[str]:
    features = []
    if repo_areas.get("dataverse"):
        features.append("dataverse-folder")
    if repo_areas.get("reference"):
        features.append("reference-folder")
    if repo_areas.get("word_templates"):
        features.append("word-templates")
    if repo_areas.get("supplemental_data"):
        features.append("supplemental-data")
    if repo_areas.get("pcf"):
        features.append("pcf")
    return features


def collect_candidates(artifacts: dict[str, list[dict[str, object]]]) -> dict[str, list[str]]:
    project_profile = artifacts.get("project_profile", {})
    explicit_solution_names = []
    fallback_solution_names = []
    supporting_solution_names = []
    local_solution_names = []
    publisher_prefixes = []
    environment_urls = []
    managed_strategies = []
    role_hints = []

    configured_main_solution = project_profile.get("main_solution_unique_name")
    if configured_main_solution:
        explicit_solution_names.append(str(configured_main_solution))
    configured_prefix = project_profile.get("publisher_prefix")
    if configured_prefix:
        publisher_prefixes.append(str(configured_prefix))
    configured_strategy = project_profile.get("managed_strategy")
    if configured_strategy:
        managed_strategies.append(str(configured_strategy))

    for item in artifacts["unpacked_solutions"]:
        unique_name = item.get("unique_name")
        role = item.get("solution_role") or "app-metadata"
        if unique_name:
            local_solution_names.append(str(unique_name))
        role_hints.append(f"{unique_name or item.get('solution_folder_relative_path')}: {role}")
        if role in PRIMARY_SOLUTION_ROLES:
            explicit_solution_names.extend(filter(None, [unique_name]))
        elif unique_name:
            supporting_solution_names.append(str(unique_name))
        publisher_prefixes.extend(filter(None, [item.get("publisher_prefix")]))
        if item.get("managed_flag") == "1":
            managed_strategies.append("managed")
        elif item.get("managed_flag") == "0":
            managed_strategies.append("unmanaged")
        elif item.get("managed_flag") == "2":
            managed_strategies.append("both")

    for item in artifacts["solution_projects"]:
        name = item.get("name")
        role = item.get("solution_role") or "app-metadata"
        meaningful_name = name if isinstance(name, str) and not is_generic_solution_project_name(name) else None
        if meaningful_name:
            local_solution_names.append(str(meaningful_name))
        role_hints.append(f"{meaningful_name or name or item.get('relative_path')}: {role}")
        if role in PRIMARY_SOLUTION_ROLES:
            fallback_solution_names.extend(filter(None, [meaningful_name]))
        elif meaningful_name:
            supporting_solution_names.append(str(meaningful_name))
        managed_strategies.extend(item.get("solution_package_types", []))

    for item in artifacts["pipeline_files"]:
        explicit_solution_names.extend(item.get("solution_names", []))
        publisher_prefixes.extend(item.get("publisher_prefixes", []))
        environment_urls.extend(item.get("environment_urls", []))
        managed_strategies.extend(item.get("managed_strategy_hints", []))

    for item in artifacts["early_bound_configs"]:
        publisher_prefixes.extend(item.get("prefix_candidates", []))

    if not publisher_prefixes:
        for item in artifacts["pcf_controls"]:
            namespace = item.get("namespace")
            if namespace:
                prefix = namespace.split(".", 1)[0]
                if re.match(r"^[A-Za-z][A-Za-z0-9]{1,7}$", prefix):
                    publisher_prefixes.append(prefix.lower())

    if not publisher_prefixes:
        publisher_prefixes.extend(artifacts.get("repo_profile", {}).get("publisher_prefixes", []))

    for item in artifacts["pac_auth_profiles"]:
        environment_urls.extend(filter(None, [item.get("url")]))

    managed_strategies = normalize_managed_strategy_values(managed_strategies)
    solution_names = explicit_solution_names if explicit_solution_names else fallback_solution_names
    return {
        "solution_unique_names": sorted(dedupe(solution_names)),
        "local_solution_unique_names": sorted(dedupe(local_solution_names)),
        "supporting_solution_unique_names": sorted(dedupe(supporting_solution_names)),
        "publisher_prefixes": sorted(dedupe(prefix.lower() for prefix in publisher_prefixes)),
        "environment_urls": sorted(dedupe(environment_urls)),
        "managed_strategies": sorted(dedupe(managed_strategies)),
        "solution_role_hints": dedupe(role_hints),
    }


def infer_context(
    artifacts: dict[str, list[dict[str, object]]],
    candidates: dict[str, list[str]],
) -> dict[str, object]:
    repo_profile = artifacts.get("repo_profile", {})
    project_profile = artifacts.get("project_profile", {})
    repo_areas = repo_profile.get("preferred_repo_areas", artifacts["repo_areas"])
    namespace_roots = repo_profile.get("namespace_roots", [])
    solution_folder = single_or_none(
        [
            item["solution_folder_relative_path"]
            for item in artifacts["unpacked_solutions"]
            if item.get("solution_folder_relative_path") and item.get("solution_role") in PRIMARY_SOLUTION_ROLES
        ]
    )
    plugin_paths = [item["relative_path"] for item in artifacts["plugin_projects"]]
    plugin_path = prefer_plugin_project(plugin_paths, repo_areas.get("plugins", []), repo_areas.get("tools", []))
    pcf_paths = [item["relative_path"] for item in artifacts["pcf_controls"]]
    managed_strategy = project_profile.get("managed_strategy") or repo_profile.get("managed_strategy") or infer_managed_strategy(
        candidates["managed_strategies"]
    )
    primary_data_area = select_primary_area(repo_areas.get("data", []), namespace_roots)
    supplemental_data_area = select_primary_area(repo_areas.get("supplemental_data", []), namespace_roots)

    return {
        "solution_unique_name": single_or_none(candidates["solution_unique_names"]),
        "local_solution_unique_name": single_or_none(candidates["local_solution_unique_names"]),
        "supporting_solution_unique_names": candidates["supporting_solution_unique_names"],
        "publisher_prefix": first_or_none(candidates["publisher_prefixes"]),
        "dev_url": active_or_single_auth_url(artifacts["pac_auth_profiles"], candidates["environment_urls"]),
        "managed_strategy": managed_strategy,
        "repo_archetype": repo_profile.get("repo_archetype"),
        "solution_source_model": repo_profile.get("solution_source_model"),
        "repo_solution_name": first_or_none(repo_profile.get("repo_solution_names", [])),
        "code_namespace_root": first_or_none(repo_profile.get("namespace_roots", [])),
        "solution_file": single_or_none([item["relative_path"] for item in artifacts["solution_files"]]),
        "solution_folder": solution_folder,
        "business_area": select_primary_area(repo_areas.get("business", []), namespace_roots),
        "data_area": primary_data_area or supplemental_data_area,
        "supplemental_data_area": supplemental_data_area,
        "plugin_project": plugin_path,
        "webresources_area": select_primary_area(repo_areas.get("webresources", []), namespace_roots),
        "webresource_style": repo_profile.get("webresource_style"),
        "pcf_area": select_primary_area(repo_areas.get("pcf", []), namespace_roots),
        "pcf_manifest": single_or_none(pcf_paths),
        "pcf_manifests": sorted(pcf_paths),
        "tools_area": select_primary_area(repo_areas.get("tools", []), namespace_roots),
        "dataverse_area": select_primary_area(repo_areas.get("dataverse", []), namespace_roots),
        "reference_area": select_primary_area(repo_areas.get("reference", []), namespace_roots),
        "word_templates_area": select_primary_area(repo_areas.get("word_templates", []), namespace_roots),
        "plugin_packaging_style": repo_profile.get("plugin_packaging_style"),
        "project_profile_path": repo_profile.get("project_profile_path"),
        "repo_features": repo_profile.get("repo_features", []),
        "local_solution_sources": repo_profile.get("local_solution_sources", []),
    }


def active_or_single_auth_url(
    auth_profiles: list[dict[str, object]],
    environment_urls: list[str],
) -> str | None:
    for profile in auth_profiles:
        if profile.get("active") and profile.get("url"):
            return str(profile["url"])
    return single_or_none(environment_urls)


def build_warnings(
    artifacts: dict[str, list[dict[str, object]]],
    candidates: dict[str, list[str]],
) -> list[str]:
    warnings = []
    repo_profile = artifacts.get("repo_profile", {})
    project_profile = artifacts.get("project_profile", {})
    artifact_keys = {
        "solution_files",
        "solution_projects",
        "unpacked_solutions",
        "customization_files",
        "early_bound_configs",
        "plugin_projects",
        "pcf_controls",
        "pipeline_files",
        "deployment_settings",
    }
    if not any(artifacts[key] for key in artifact_keys):
        warnings.append("No Power Platform solution, plug-in, PCF, pipeline, or deployment artifacts were detected in the scan path.")
    if repo_profile.get("solution_source_model") == "code-centric-no-unpacked-solution":
        warnings.append(
            "This repo appears to be a code-centric Dataverse implementation repo without unpacked solution source. Treat the .sln and layered code projects as authoritative for code assets, and use the selected live solution for metadata or deployment work."
        )
    if repo_profile.get("solution_source_model") == "hybrid-code-and-supporting-solution-source":
        warnings.append(
            "This repo appears to be a hybrid code-centric Dataverse repo where the local solution source is only partial or supporting. Treat the .sln and layered code projects as authoritative for code assets, and confirm the main live Dataverse solution before metadata or deployment work."
        )
    if project_profile.get("load_error") == "invalid-json":
        warnings.append(f"Project profile exists at {project_profile.get('relative_path')} but is not valid JSON.")
    if project_profile.get("load_error") == "expected-object":
        warnings.append(f"Project profile exists at {project_profile.get('relative_path')} but does not contain a JSON object.")
    if len(candidates["solution_unique_names"]) > 1:
        warnings.append(f"Multiple candidate solution names were detected: {', '.join(candidates['solution_unique_names'])}.")
    if len(candidates["publisher_prefixes"]) > 1:
        warnings.append(f"Multiple candidate publisher prefixes were detected: {', '.join(candidates['publisher_prefixes'])}.")
    if len(candidates["environment_urls"]) > 1:
        warnings.append("Multiple candidate environment URLs were detected from pipeline files or PAC auth profiles.")
    if candidates.get("supporting_solution_unique_names") and not candidates["solution_unique_names"]:
        warnings.append(
            "Local solution source was detected only in supporting areas such as PCF packaging or reference folders. Do not assume those supporting solutions are the main app solution."
        )
    return warnings


def build_questions(
    artifacts: dict[str, list[dict[str, object]]],
    candidates: dict[str, list[str]],
    inferred: dict[str, object],
) -> list[str]:
    questions = []
    repo_profile = artifacts.get("repo_profile", {})
    solution_source_model = repo_profile.get("solution_source_model")
    is_code_centric_repo = solution_source_model in {
        "code-centric-no-unpacked-solution",
        "hybrid-code-and-supporting-solution-source",
    }
    if not candidates["solution_unique_names"]:
        if is_code_centric_repo:
            if candidates.get("supporting_solution_unique_names"):
                questions.append(
                    "This repo appears to be code-centric and only has supporting local solution source. Which live Dataverse solution should I target for the main app work?"
                )
            else:
                questions.append(
                    "This repo appears to be code-centric without unpacked Dataverse solution source. Which live Dataverse solution should I target for this task?"
                )
        else:
            questions.append("What is the target solution unique name for this task?")
    elif len(candidates["solution_unique_names"]) > 1:
        questions.append(
            f"Which solution should I target for this task: {', '.join(candidates['solution_unique_names'])}?"
        )

    if not candidates["publisher_prefixes"]:
        questions.append("What is the publisher prefix for this task?")
    elif len(candidates["publisher_prefixes"]) > 1:
        questions.append(
            f"Which publisher prefix should I use for this task: {', '.join(candidates['publisher_prefixes'])}?"
        )

    has_solution_artifacts = bool(artifacts["solution_projects"] or artifacts["unpacked_solutions"])
    if not has_solution_artifacts and not is_code_centric_repo:
        questions.append("Which folder or repository contains the Dataverse solution source for this task?")

    if not inferred.get("dev_url"):
        questions.append("If live environment access is required, which DEV environment URL should I use?")

    if not inferred.get("managed_strategy") and not candidates["managed_strategies"]:
        questions.append("Should I treat this project as unmanaged source only, or unmanaged source with managed release artifacts?")

    return questions


def split_framework_values(values: list[str]) -> list[str]:
    frameworks = []
    for value in values:
        frameworks.extend([part.strip() for part in value.split(";") if part.strip()])
    return frameworks


def normalize_managed_strategy_values(values: list[str]) -> list[str]:
    normalized = []
    for value in values:
        lowered = value.strip().lower()
        if not lowered:
            continue
        if lowered in {"managed", "unmanaged", "both", "managed-release"}:
            normalized.append(lowered)
        elif lowered == "true":
            normalized.append("managed")
        elif lowered == "false":
            normalized.append("unmanaged")
    return dedupe(normalized)


def infer_managed_strategy(values: list[str]) -> str | None:
    value_set = set(values)
    if not value_set:
        return None
    if value_set == {"unmanaged"}:
        return "unmanaged"
    if value_set == {"managed"}:
        return "managed"
    if value_set == {"both"}:
        return "both"
    if "managed-release" in value_set and ("unmanaged" in value_set or "both" in value_set):
        return "unmanaged-source-with-managed-release"
    if len(value_set) == 1:
        return next(iter(value_set))
    return None


def is_generic_solution_project_name(value: str) -> bool:
    return value.strip().lower() in {"solution", "solutions"}


def select_primary_area(values: list[str], namespace_roots: list[str] | None = None) -> str | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]

    normalized_roots = [value.lower() for value in (namespace_roots or []) if isinstance(value, str)]
    normalized_candidates = {
        value: (strip_project_role_suffix(Path(value).name) or Path(value).name).lower()
        for value in values
    }
    for root in normalized_roots:
        preferred = [value for value, candidate in normalized_candidates.items() if candidate == root]
        if preferred:
            return first_or_none(preferred)

    non_generic = [value for value in values if Path(value).name.lower() not in GENERIC_AREA_NAMES]
    return first_or_none(non_generic) or first_or_none(values)


def first_or_none(values: list[str]) -> str | None:
    return values[0] if values else None


def single_or_none(values: list[str]) -> str | None:
    return values[0] if len(values) == 1 else None


def prefer_paths_under(paths: list[str], parent_paths: list[str]) -> str | None:
    if not paths:
        return None
    if not parent_paths:
        return single_or_none(paths)
    matching = []
    lowered_parents = [normalize_relative_repo_path(parent).lower() for parent in parent_paths]
    for path in paths:
        lowered_path = normalize_relative_repo_path(path).lower()
        if any(lowered_path.startswith(parent + "/") or lowered_path == parent for parent in lowered_parents):
            matching.append(path)
    if len(matching) == 1:
        return matching[0]
    return single_or_none(paths)


def filter_paths_under(paths: list[str], parent_paths: list[str]) -> list[str]:
    if not paths or not parent_paths:
        return []
    lowered_parents = [normalize_relative_repo_path(parent).lower() for parent in parent_paths]
    matching = []
    for path in paths:
        lowered_path = normalize_relative_repo_path(path).lower()
        if any(lowered_path.startswith(parent + "/") or lowered_path == parent for parent in lowered_parents):
            matching.append(path)
    return matching


def prefer_plugin_project(paths: list[str], plugin_parent_paths: list[str], tool_parent_paths: list[str]) -> str | None:
    if not paths:
        return None

    plugin_matches = filter_paths_under(paths, plugin_parent_paths)
    if plugin_matches:
        return single_or_none(plugin_matches)

    tool_matches = set(filter_paths_under(paths, tool_parent_paths))
    non_tool_paths = [path for path in paths if path not in tool_matches]
    if non_tool_paths:
        return single_or_none(non_tool_paths)
    return None


def normalize_relative_repo_path(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


if __name__ == "__main__":
    raise SystemExit(main())
