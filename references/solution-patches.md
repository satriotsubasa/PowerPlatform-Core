# Solution Patches

Use this reference when the task is about continuing a patch, planning a new patch, merging a patch back into the parent solution, or deciding whether to switch work back to the main unmanaged solution.

## Primary Helper

- `scripts/plan_solution_patch_merge.py`

## Operating Rules

- Treat the selected live solution as authoritative for the current session.
- If the selected solution is a patch, do not silently redirect work to the parent solution.
- If an existing unmanaged patch is selected, add or update only the scoped components there unless the user explicitly changes the target.
- If importing the same patch version fails, do not retry stale packages. Bump the patch version or switch to a supported targeted component update path.
- If the parent solution has active patches, do not attempt parent export/import as a workaround. Work in the selected patch or stop for explicit lifecycle direction.
- Export a managed TST package only from a freshly verified DEV state or from a package generated in the current session after component membership is audited.
- Never merge, delete, clone, or retire patches unless the user explicitly requests that lifecycle operation.
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

## Patch Component Audit

Before the user exports a patch for TST, compare expected issue-related components against the live patch membership.

Required audit output:

- expected components by type and name
- components present in the patch
- missing expected components
- stale or redundant components
- components excluded because they are managed separately, such as a PCF package solution

Use `scripts/add_solution_components.py` to place missing scoped components when the component can be resolved safely. Do not add broad required components or subcomponents unless the user accepts the expanded blast radius.

## Safety

- Planning is safe and local.
- Live merge, upgrade, or parent-target switching still requires explicit user approval before environment changes.
