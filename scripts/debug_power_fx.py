#!/usr/bin/env python3
"""Inspect Power Fx formulas for delegation, reliability, and maintainability risks."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from powerplatform_common import read_json_argument, repo_root, write_json_output

FUNCTION_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
DELEGATION_FUNCTIONS = {"Search", "Distinct", "AddColumns", "GroupBy", "Ungroup", "ForAll"}
WRITE_FUNCTIONS = {"Patch", "SubmitForm", "Collect", "ClearCollect", "Remove", "RemoveIf", "UpdateIf"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect Power Fx formulas for delegation, reliability, and maintainability risks.",
    )
    parser.add_argument("--spec", help="JSON object or path to a JSON file describing one or more formulas.")
    parser.add_argument("--formula", help="Inline Power Fx formula text.")
    parser.add_argument("--path", help="Path to a text file that contains a Power Fx formula.")
    parser.add_argument("--name", default="formula-1", help="Display name used when --formula or --path is supplied directly.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve relative formula paths.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    repo = repo_root(Path(args.repo_root))
    items = resolve_items(args, repo)

    analyses = [analyze_formula_item(item) for item in items]
    payload = {
        "success": True,
        "mode": "debug-power-fx",
        "formulaCount": len(analyses),
        "riskLevel": compute_risk_level(analyses),
        "items": analyses,
    }
    write_json_output(payload, args.output)
    return 0


def resolve_items(args: argparse.Namespace, repo: Path) -> list[dict[str, str]]:
    if args.spec:
        spec = read_json_argument(args.spec)
        if not isinstance(spec, dict):
            raise RuntimeError("--spec must resolve to a JSON object.")
        items = spec.get("items")
        if isinstance(items, list) and items:
            resolved = []
            for index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    raise RuntimeError(f"Item {index} in 'items' must be a JSON object.")
                resolved.append(
                    {
                        "name": str(item.get("name") or f"formula-{index}"),
                        "formula": read_formula_source(item, repo),
                    }
                )
            return resolved
        return [
            {
                "name": str(spec.get("name") or args.name),
                "formula": read_formula_source(spec, repo),
            }
        ]

    if args.formula:
        return [{"name": args.name, "formula": args.formula}]
    if args.path:
        return [{"name": args.name, "formula": resolve_formula_path(args.path, repo).read_text(encoding="utf-8")}]
    raise RuntimeError("Provide either --spec, --formula, or --path.")


def read_formula_source(item: dict[str, Any], repo: Path) -> str:
    if isinstance(item.get("formula"), str) and item["formula"].strip():
        return item["formula"]
    if isinstance(item.get("path"), str) and item["path"].strip():
        return resolve_formula_path(item["path"], repo).read_text(encoding="utf-8")
    raise RuntimeError("Each Power Fx item must provide 'formula' or 'path'.")


def resolve_formula_path(raw_path: str, repo: Path) -> Path:
    path = Path(raw_path)
    return path.resolve() if path.is_absolute() else (repo / path).resolve()


def analyze_formula_item(item: dict[str, str]) -> dict[str, Any]:
    formula = item["formula"]
    normalized = collapse_whitespace(formula)
    functions = extract_functions(formula)
    findings = []
    findings.extend(find_delegation_risks(formula, functions))
    findings.extend(find_reliability_risks(formula, functions))
    findings.extend(find_maintainability_risks(formula, functions))
    findings = dedupe_findings(findings)
    return {
        "name": item["name"],
        "formulaLength": len(formula),
        "functions": functions,
        "riskLevel": severity_level(findings),
        "findingCount": len(findings),
        "findings": findings,
        "rewriteHints": build_rewrite_hints(findings),
        "testCases": build_test_cases(findings),
        "normalizedPreview": normalized[:240],
    }


def extract_functions(formula: str) -> list[str]:
    discovered = []
    for match in FUNCTION_RE.finditer(formula):
        name = match.group(1)
        if name not in discovered:
            discovered.append(name)
    return discovered


def find_delegation_risks(formula: str, functions: list[str]) -> list[dict[str, str]]:
    findings = []
    for function_name in DELEGATION_FUNCTIONS:
        if function_name in functions:
            findings.append(
                {
                    "severity": "medium" if function_name in {"Search", "Distinct", "ForAll"} else "low",
                    "code": "delegation-risk",
                    "message": f"{function_name} often needs delegation review against the connected data source.",
                }
            )
    lowered = formula.lower()
    if " exactin " in lowered or " in " in lowered:
        findings.append(
            {
                "severity": "medium",
                "code": "delegation-in-operator",
                "message": "The formula uses 'in' or 'exactin', which often needs delegation review on large data sources.",
            }
        )
    return findings


def find_reliability_risks(formula: str, functions: list[str]) -> list[dict[str, str]]:
    findings = []
    has_iferror = "IfError(" in formula
    for function_name in WRITE_FUNCTIONS:
        if function_name in functions and not has_iferror:
            findings.append(
                {
                    "severity": "medium",
                    "code": "missing-iferror",
                    "message": f"{function_name} is used without an obvious IfError wrapper.",
                }
            )
    if "Notify(" not in formula and any(function_name in functions for function_name in WRITE_FUNCTIONS):
        findings.append(
            {
                "severity": "low",
                "code": "missing-user-feedback",
                "message": "The formula writes data but does not show an obvious Notify or user-feedback path.",
            }
        )
    return findings


def find_maintainability_risks(formula: str, functions: list[str]) -> list[dict[str, str]]:
    findings = []
    if formula.count("If(") >= 3:
        findings.append(
            {
                "severity": "low",
                "code": "nested-if",
                "message": "The formula contains several nested If calls; Switch or helper variables may be easier to maintain.",
            }
        )
    if len(formula) > 400:
        findings.append(
            {
                "severity": "low",
                "code": "long-formula",
                "message": "The formula is long enough that extracting helper variables or named formulas may improve readability.",
            }
        )
    if "With(" not in formula and len(functions) >= 6:
        findings.append(
            {
                "severity": "low",
                "code": "missing-with",
                "message": "The formula uses many functions but no With blocks, so intermediate values may be harder to reason about.",
            }
        )
    return findings


def build_rewrite_hints(findings: list[dict[str, str]]) -> list[str]:
    hints = []
    codes = {finding["code"] for finding in findings}
    if "delegation-risk" in codes or "delegation-in-operator" in codes:
        hints.append("Validate the formula against the actual data source delegation rules and consider pre-filtering or delegable server-side alternatives.")
    if "missing-iferror" in codes:
        hints.append("Wrap write operations in IfError and route failure details to Notify or a reusable error handler.")
    if "nested-if" in codes:
        hints.append("Consider Switch, With, or named formulas to flatten nested conditional logic.")
    if "long-formula" in codes:
        hints.append("Split large formulas into helper variables, named formulas, or reusable component logic.")
    if "missing-user-feedback" in codes:
        hints.append("Add user feedback for success and failure paths when the formula performs data writes.")
    return hints


def build_test_cases(findings: list[dict[str, str]]) -> list[str]:
    tests = ["Blank input values", "Permission failure from the data source", "Unexpected null lookup or record reference"]
    codes = {finding["code"] for finding in findings}
    if "delegation-risk" in codes or "delegation-in-operator" in codes:
        tests.append("Large dataset beyond the delegation limit")
    if "missing-iferror" in codes:
        tests.append("Server-side error during Patch or SubmitForm")
    if "missing-user-feedback" in codes:
        tests.append("User action succeeds but gives no visible confirmation")
    return tests


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def dedupe_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding["code"], finding["message"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def severity_level(findings: list[dict[str, str]]) -> str:
    severities = {finding["severity"] for finding in findings}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if "low" in severities:
        return "low"
    return "minimal"


def compute_risk_level(items: list[dict[str, Any]]) -> str:
    levels = {str(item.get("riskLevel")) for item in items}
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    if "low" in levels:
        return "low"
    return "minimal"


if __name__ == "__main__":
    raise SystemExit(main())
