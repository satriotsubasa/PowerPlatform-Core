#!/usr/bin/env python3
"""Review a repo against solution, ALM, and house-style standards."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from powerplatform_common import discover_repo_context, infer_pcf_package_roots, repo_root, resolve_pcf_context, write_json_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review a repo against Power Platform solution, ALM, and house-style standards.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root to review.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    context = discover_repo_context(repo)
    findings = build_findings(repo, context)
    payload = {
        "success": True,
        "mode": "review-solution-standards",
        "repoRoot": str(repo),
        "summary": build_summary(context),
        "findingCount": len(findings),
        "riskLevel": compute_risk_level(findings),
        "findings": findings,
        "recommendations": build_recommendations(findings),
    }
    write_json_output(payload, args.output)
    return 0


def build_summary(context: dict[str, Any]) -> dict[str, Any]:
    inferred = context.get("inferred", {})
    return {
        "repoArchetype": inferred.get("repo_archetype"),
        "solutionSourceModel": inferred.get("solution_source_model"),
        "publisherPrefix": inferred.get("publisher_prefix"),
        "mainSolutionUniqueName": inferred.get("solution_unique_name"),
        "supportingSolutionUniqueNames": inferred.get("supporting_solution_unique_names"),
        "projectProfilePath": inferred.get("project_profile_path"),
        "pluginProject": inferred.get("plugin_project"),
        "dataArea": inferred.get("data_area"),
        "webresourcesArea": inferred.get("webresources_area"),
        "pcfArea": inferred.get("pcf_area"),
        "wordTemplatesArea": inferred.get("word_templates_area"),
        "dataverseArea": inferred.get("dataverse_area"),
        "referenceArea": inferred.get("reference_area"),
    }


def build_findings(repo: Path, context: dict[str, Any]) -> list[dict[str, Any]]:
    inferred = context.get("inferred", {})
    findings: list[dict[str, Any]] = []
    is_power_platform_repo = any(
        inferred.get(key)
        for key in (
            "repo_archetype",
            "solution_source_model",
            "solution_unique_name",
            "supporting_solution_unique_names",
            "business_area",
            "data_area",
            "webresources_area",
            "pcf_area",
            "word_templates_area",
            "dataverse_area",
        )
    )

    if not (repo / "README.md").exists():
        findings.append(make_finding("high", "missing-readme", "Repo root README.md is missing.", "Add or restore a repo-root README.md entry point."))
    if not (repo / "CODEX_HANDOFF.md").exists():
        findings.append(make_finding("medium", "missing-handoff", "CODEX_HANDOFF.md is missing.", "Add CODEX_HANDOFF.md for thread continuity."))
    if is_power_platform_repo and not inferred.get("publisher_prefix"):
        findings.append(make_finding("high", "missing-publisher-prefix", "The discovery pass could not infer a publisher prefix.", "Add a repo project profile or include clearer solution or metadata artifacts."))

    solution_source_model = inferred.get("solution_source_model")
    has_profile = bool(inferred.get("project_profile_path"))
    if solution_source_model in {"hybrid-code-and-supporting-solution-source", "code-centric-no-unpacked-solution"} and not has_profile:
        findings.append(
            make_finding(
                "medium",
                "missing-project-profile",
                "This repo shape would benefit from an explicit power-platform project profile.",
                "Add .codex/power-platform.project-profile.json to pin the main live solution and source areas.",
            )
        )

    supporting = inferred.get("supporting_solution_unique_names") or []
    if supporting and not inferred.get("solution_unique_name") and not has_profile:
        findings.append(
            make_finding(
                "medium",
                "ambiguous-main-solution",
                "The repo exposes supporting local solutions but no confirmed main live solution.",
                "Use a repo project profile to declare the main live solution unique name explicitly.",
            )
        )

    if inferred.get("data_area") and str(inferred.get("data_area")).endswith(".Data"):
        findings.append(
            make_finding(
                "info",
                "generated-data-project",
                "The repo has a namespaced *.Data project that should remain generator-owned.",
                "Regenerate early-bound output instead of hand-editing generated files there.",
            )
        )

    if inferred.get("reference_area") and not inferred.get("dataverse_area"):
        findings.append(
            make_finding(
                "info",
                "reference-without-dataverse",
                "Reference material exists without a Dataverse metadata folder.",
                "Keep Reference docs-only and hydrate Dataverse/<solution> only when live metadata work needs it.",
            )
        )

    if inferred.get("word_templates_area") and not inferred.get("plugin_project"):
        findings.append(
            make_finding(
                "low",
                "templates-without-plugin-project",
                "Word Templates were detected but no plug-in project was inferred.",
                "Confirm where document-generation logic lives so template automation has the right code source area.",
            )
        )

    findings.extend(review_pcf_version_alignment(repo))
    return findings


def review_pcf_version_alignment(repo: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for package_root in infer_pcf_package_roots(repo):
        context = resolve_pcf_context(repo, package_root)
        manifests = context.get("manifests", [])
        solution_context = context.get("solution_context") or {}
        solution_version = str(solution_context.get("version") or "")
        manifest_versions = sorted(
            {
                str(manifest.get("version"))
                for manifest in manifests
                if isinstance(manifest, dict) and manifest.get("version")
            }
        )
        if len(manifest_versions) > 1:
            findings.append(
                make_finding(
                    "medium",
                    "pcf-manifest-version-mismatch",
                    f"PCF package {package_root.name} contains multiple manifest versions: {', '.join(manifest_versions)}.",
                    "Align all control manifests before packaging the wrapper solution.",
                    area=str(package_root),
                )
            )
        if manifest_versions and solution_version:
            manifest_version = manifest_versions[0]
            if not solution_version.startswith(manifest_version + "."):
                findings.append(
                    make_finding(
                        "medium",
                        "pcf-wrapper-version-mismatch",
                        f"PCF package {package_root.name} has manifest version {manifest_version} but wrapper solution version {solution_version}.",
                        "Update both version surfaces together with version_pcf_solution.py.",
                        area=str(package_root),
                    )
                )
    return findings


def build_recommendations(findings: list[dict[str, Any]]) -> list[str]:
    ordered = []
    for finding in findings:
        recommendation = str(finding.get("recommendation") or "").strip()
        if recommendation and recommendation not in ordered:
            ordered.append(recommendation)
    return ordered


def make_finding(severity: str, code: str, message: str, recommendation: str, *, area: str | None = None) -> dict[str, Any]:
    finding = {
        "severity": severity,
        "code": code,
        "message": message,
        "recommendation": recommendation,
    }
    if area:
        finding["area"] = area
    return finding


def compute_risk_level(findings: list[dict[str, Any]]) -> str:
    severities = {str(finding.get("severity")) for finding in findings}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if "low" in severities:
        return "low"
    return "minimal"


if __name__ == "__main__":
    raise SystemExit(main())
