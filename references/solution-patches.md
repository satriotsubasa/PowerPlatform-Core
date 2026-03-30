# Solution Patches

Use this reference when the task is about continuing a patch, planning a new patch, merging a patch back into the parent solution, or deciding whether to switch work back to the main unmanaged solution.

## Primary Helper

- `scripts/plan_solution_patch_merge.py`

## Operating Rules

- Treat the selected live solution as authoritative for the current session.
- If the selected solution is a patch, do not silently redirect work to the parent solution.
- Prefer explicit patch planning before environment changes when the user is deciding between:
  - continue current patch
  - create a new patch
  - merge or upgrade
  - promote work back to the main solution

## Inputs The Planner Expects

- `mainSolutionUniqueName`
- `selectedSolutionUniqueName`
- `selectedSolutionFriendlyName`
- `selectedIsPatch`
- `selectedVersion`
- `parentSolutionUniqueName`
- `intent`

## Intent Values

- `continue-current-patch`
- `create-new-patch`
- `merge`
- `merge-upgrade`
- `promote-main`
- `work-main`

## Expected Output

The helper should return:

- recommended strategy
- target solution recommendation
- recommended next version when possible
- concrete next steps
- warnings when the chosen target does not line up with the selected patch or main solution

## Safety

- Planning is safe and local.
- Live merge, upgrade, or parent-target switching still requires explicit user approval before environment changes.
