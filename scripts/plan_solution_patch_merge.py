#!/usr/bin/env python3
"""Plan a Dataverse patch, merge, or upgrade workflow from structured solution context."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from powerplatform_common import read_json_argument, write_json_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan a Dataverse patch, merge, or upgrade workflow from structured solution context.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the solution patch or merge scenario.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    payload = build_patch_plan(spec)
    write_json_output(payload, args.output)
    return 0


def build_patch_plan(spec: dict[str, Any]) -> dict[str, Any]:
    main_solution = text_value(spec, "mainSolutionUniqueName")
    selected_solution = text_value(spec, "selectedSolutionUniqueName")
    selected_friendly_name = text_value(spec, "selectedSolutionFriendlyName")
    parent_solution = text_value(spec, "parentSolutionUniqueName")
    selected_is_patch = bool(spec.get("selectedIsPatch"))
    intent = (text_value(spec, "intent") or infer_intent(selected_is_patch, parent_solution)).lower()
    version = text_value(spec, "selectedVersion")

    if intent == "create-new-patch":
        recommended = "Create a new patch from the main solution and keep the current selected patch unchanged."
        steps = [
            "Confirm the main unmanaged solution.",
            "Create a new patch solution from the main solution.",
            "Add only the scoped components to the new patch.",
            "Apply changes in the patch and validate there.",
        ]
    elif intent == "merge-upgrade":
        recommended = "Prepare to merge the selected patch back into the parent solution through a controlled upgrade path."
        steps = [
            "Validate the patch contents and current parent-solution version.",
            "Export or snapshot the parent solution before merge.",
            "Apply the patch merge or upgrade in a controlled non-production environment first.",
            "Confirm the parent solution version after merge and retire obsolete patch layers.",
        ]
    elif intent == "continue-current-patch":
        recommended = "Continue delivering into the currently selected patch solution."
        steps = [
            "Keep the selected patch as the working solution for this change set.",
            "Add or update only the intended components in that patch.",
            "Version the patch predictably before deployment.",
            "Re-evaluate merge only after the patch scope is complete.",
        ]
    elif intent == "merge":
        recommended = "Plan a controlled patch merge into the parent main solution after validating the patch contents."
        steps = [
            "Confirm the patch is complete and no additional scoped changes are waiting.",
            "Validate the parent solution version and export or snapshot it before merge.",
            "Run the merge or upgrade path in TEST first and validate component layering afterward.",
            "Retire the patch layer only after the merged parent solution is confirmed.",
        ]
    elif intent == "promote-main":
        recommended = "Switch the working target back to the main unmanaged solution before continuing."
        steps = [
            "Confirm the main unmanaged solution is unlocked and intended for the next changes.",
            "Stop adding new scope to the current patch.",
            "Re-target the change set to the main solution and version it predictably.",
            "Use the patch only as a release artifact if that is still required by the ALM strategy.",
        ]
    else:
        recommended = "Work directly in the main unmanaged solution without introducing a new patch."
        steps = [
            "Confirm the main unmanaged solution is the intended working target.",
            "Apply the scoped changes directly to that solution.",
            "Version and validate the main solution before deployment.",
        ]

    next_version = bump_version(version, patch=selected_is_patch or intent == "create-new-patch")
    warnings = []
    requires_user_decision = False
    if selected_is_patch and intent == "continue-current-patch" and parent_solution and main_solution and parent_solution != main_solution:
        warnings.append("The selected patch parent does not match the declared main solution. Confirm the intended target before changing anything.")
    if selected_is_patch and intent == "work-main":
        warnings.append("The selected solution is a patch, but the plan intent points to the main solution. Confirm the user really wants to switch targets.")
    if selected_is_patch and not parent_solution:
        warnings.append("The selected solution is marked as a patch but no parent solution unique name was supplied.")
        requires_user_decision = True
    if not main_solution and intent in {"create-new-patch", "work-main", "promote-main", "merge", "merge-upgrade"}:
        warnings.append("The main solution unique name is missing, so patch planning cannot fully validate the target strategy.")
        requires_user_decision = True
    if intent in {"merge", "merge-upgrade"} and not selected_is_patch:
        warnings.append("A merge intent was requested, but the selected solution is not flagged as a patch.")
    if not version:
        warnings.append("No selected solution version was provided, so the next-version recommendation may be incomplete.")

    return {
        "success": True,
        "mode": "plan-solution-patch-merge",
        "mainSolutionUniqueName": main_solution,
        "selectedSolutionUniqueName": selected_solution,
        "selectedSolutionFriendlyName": selected_friendly_name,
        "parentSolutionUniqueName": parent_solution,
        "selectedIsPatch": selected_is_patch,
        "selectedVersion": version,
        "intent": intent,
        "recommendedStrategy": recommended,
        "targetRecommendation": determine_target_recommendation(intent, main_solution, selected_solution, parent_solution),
        "recommendedNextVersion": next_version,
        "requiresUserDecision": requires_user_decision,
        "steps": steps,
        "warnings": warnings,
    }


def infer_intent(selected_is_patch: bool, parent_solution: str | None) -> str:
    if selected_is_patch and parent_solution:
        return "continue-current-patch"
    return "work-main"


def determine_target_recommendation(
    intent: str,
    main_solution: str | None,
    selected_solution: str | None,
    parent_solution: str | None,
) -> str | None:
    if intent in {"continue-current-patch", "create-new-patch"}:
        return selected_solution or parent_solution or main_solution
    if intent in {"merge", "merge-upgrade", "promote-main", "work-main"}:
        return parent_solution or main_solution
    return selected_solution or main_solution


def text_value(source: dict[str, Any], key: str) -> str | None:
    value = source.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def bump_version(version: str | None, *, patch: bool) -> str | None:
    if not version:
        return None
    parts = version.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return None
    major, minor, build, revision = [int(part) for part in parts]
    if patch:
        revision += 1
    else:
        build += 1
        revision = 0
    return f"{major}.{minor}.{build}.{revision}"


if __name__ == "__main__":
    raise SystemExit(main())
