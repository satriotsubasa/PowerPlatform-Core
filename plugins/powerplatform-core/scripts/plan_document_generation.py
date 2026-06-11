#!/usr/bin/env python3
"""Plan template-aware document-generation changes from Word templates and structured mappings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from inspect_word_templates import collect_template_files, inspect_template, resolve_target_path
from powerplatform_common import discover_repo_context, read_json_argument, repo_root, write_json_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan template-aware document-generation changes from Word templates and structured mappings.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the template plan.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to infer the Word Templates area.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    payload = build_document_plan(spec, repo)
    write_json_output(payload, args.output)
    return 0


def build_document_plan(spec: dict[str, Any], repo: Path) -> dict[str, Any]:
    target = resolve_target_path(repo, spec.get("path"))
    template_name = spec.get("templateName")
    if template_name:
        files = resolve_named_template_files(target, str(template_name))
    else:
        files = collect_template_files(target, recurse=bool(spec.get("recurse")))

    mappings = require_mapping_list(spec.get("placeholderMappings"))
    documents = [inspect_template(path, repo=repo, summary_only=False) for path in files]
    context = discover_repo_context(repo)
    inferred = context.get("inferred", {})
    document_plans = [plan_single_document(document, mappings) for document in documents]
    findings = collect_document_findings(document_plans)

    return {
        "success": True,
        "mode": "plan-document-generation",
        "target": str(target),
        "documentCount": len(document_plans),
        "documents": document_plans,
        "findingCount": len(findings),
        "riskLevel": compute_risk_level(findings),
        "findings": findings,
        "sourceAreas": {
            "wordTemplates": inferred.get("word_templates_area"),
            "business": inferred.get("business_area"),
            "plugins": inferred.get("plugin_project"),
            "data": inferred.get("data_area"),
        },
        "recommendedNextSteps": [
            "Update the template only after confirming the placeholder mapping against the related Business and Plugins code.",
            "Keep Word Templates as source-controlled assets and avoid treating Reference copies as deployable source.",
            "When a placeholder changes meaning, review document-generation plug-ins and placeholder configuration together.",
        ],
    }


def plan_single_document(document: dict[str, Any], mappings: list[dict[str, str]]) -> dict[str, Any]:
    controls = document.get("controls") or []
    tag_map = {
        str(control.get("tag")): control
        for control in controls
        if isinstance(control, dict) and control.get("tag")
    }
    alias_map = {
        str(control.get("alias")): control
        for control in controls
        if isinstance(control, dict) and control.get("alias")
    }

    mapped = []
    missing = []
    for mapping in mappings:
        key = mapping["tag"]
        control = tag_map.get(key) or alias_map.get(key)
        item = {
            "tag": key,
            "source": mapping["source"],
            "required": mapping["required"],
            "matched": control is not None,
        }
        if control is not None:
            item["controlType"] = control.get("type")
            item["textSample"] = control.get("textSample")
            mapped.append(item)
        else:
            missing.append(item)

    unused_controls = sorted(
        {
            str(control.get("tag") or control.get("alias"))
            for control in controls
            if isinstance(control, dict)
            and (control.get("tag") or control.get("alias"))
            and str(control.get("tag") or control.get("alias")) not in {mapping["tag"] for mapping in mappings}
        }
    )

    return {
        "fileName": document.get("fileName"),
        "relativePath": document.get("relativePath"),
        "controlCount": document.get("controlCount"),
        "duplicateTags": document.get("duplicateTags"),
        "duplicateAliases": document.get("duplicateAliases"),
        "requiredMappingCount": sum(1 for item in mappings if item["required"]),
        "missingRequiredCount": sum(1 for item in missing if item["required"]),
        "mappedPlaceholders": mapped,
        "missingMappings": missing,
        "unusedControls": unused_controls,
    }


def resolve_named_template_files(target: Path, template_name: str) -> list[Path]:
    normalized_name = template_name.strip()
    if not normalized_name:
        raise RuntimeError("templateName must be a non-empty string when provided.")

    if target.is_file():
        if target.name.lower() != normalized_name.lower():
            raise RuntimeError(f"Template name '{template_name}' does not match the explicit template path {target.name}.")
        return [target]

    if not target.is_dir():
        raise RuntimeError(f"Target path does not exist: {target}")

    matches = [
        path
        for path in collect_template_files(target, recurse=True)
        if path.name.lower() == normalized_name.lower()
    ]
    if not matches:
        raise RuntimeError(f"Could not find template '{template_name}' under {target}.")
    return matches


def collect_document_findings(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for document in documents:
        relative_path = str(document.get("relativePath") or document.get("fileName") or "template")
        for tag in document.get("duplicateTags") or []:
            findings.append(make_finding("medium", "duplicate-tag", f"{relative_path} contains duplicate content-control tag '{tag}'."))
        for alias in document.get("duplicateAliases") or []:
            findings.append(make_finding("low", "duplicate-alias", f"{relative_path} contains duplicate content-control alias '{alias}'."))
        missing_required = [item for item in document.get("missingMappings") or [] if item.get("required")]
        for mapping in missing_required:
            findings.append(make_finding("high", "missing-required-mapping", f"{relative_path} does not contain required placeholder '{mapping.get('tag')}'."))
    return findings


def make_finding(severity: str, code: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def compute_risk_level(findings: list[dict[str, Any]]) -> str:
    severities = {str(finding.get("severity")) for finding in findings}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if "low" in severities:
        return "low"
    return "minimal"


def require_mapping_list(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError("Expected 'placeholderMappings' to be a JSON array when present.")
    results = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Placeholder mapping {index} must be a JSON object.")
        tag = item.get("tag") or item.get("alias")
        source = item.get("source")
        if not isinstance(tag, str) or not tag.strip():
            raise RuntimeError(f"Placeholder mapping {index} must include a non-empty 'tag' or 'alias'.")
        if not isinstance(source, str) or not source.strip():
            raise RuntimeError(f"Placeholder mapping {index} must include a non-empty 'source'.")
        results.append(
            {
                "tag": tag.strip(),
                "source": source.strip(),
                "required": bool(item.get("required", True)),
            }
        )
    return results


if __name__ == "__main__":
    raise SystemExit(main())
