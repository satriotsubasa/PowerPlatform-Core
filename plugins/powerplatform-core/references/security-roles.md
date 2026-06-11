# Security Roles

Use this reference for Dataverse security role inspection, creation, update, privilege-set design, and ALM handling.

## Default Position

- Prefer custom roles over editing predefined or system-generated roles.
- When the safest baseline already exists, prefer copying that role's privilege set and then applying a small declarative delta.
- Keep security-role changes solution-aware when the role belongs to your app or managed delivery path.
- Use the same unmanaged solution to manage later updates to the same custom role whenever possible.

## Current Helpers

Reusable helpers:

- `scripts/inspect_security_role.py` for `list` and `inspect`
- `scripts/create_security_role.py` for creating a role and optionally seeding or replacing its privilege set
- `scripts/update_security_role.py` for updating role metadata and privilege sets

The shared SDK tool now exposes `securityrole --mode list|inspect|create|update`.

## Before You Change A Role

Confirm:

- target environment
- working unmanaged solution, if the role should ship through ALM
- exact role name and business unit
- whether the role is custom or system-generated
- whether the role should start from a copied baseline
- minimum privileges required for the model-driven app or solution features

Do not assume a new role can start from zero privileges and still be usable. If the requirement is app access, navigation, or standard Dataverse usage, start from an appropriate baseline role or explicitly include the required minimum privileges.

## Role Update Rules

- Do not update predefined or system-generated roles by default.
- If the role is app-owned, keep later updates in the same custom solution.
- Treat privilege changes as desired-state configuration, not one-off UI clicks.
- Prefer reviewable JSON specs over ad hoc manual edits.

## Privilege Spec Shape

The helpers use a code-first privilege spec.

Common fields:

- `privilegeId` or `privilegeName`
- `depth`
- optional `recordFilterId`

Supported depth values:

- `basic`
- `local`
- `deep`
- `global`
- `record-filter`

## Create Spec Pattern

Use `copyFromRoleId` or `copyFromRoleName` when you want a baseline role first, then adjust it.

Example:

```json
{
  "name": "Contoso App User",
  "copyFromRoleName": "App Opener",
  "businessUnitName": "Contoso",
  "solutionUniqueName": "ContosoApp",
  "additionalPrivileges": [
    { "privilegeName": "prvReadnew_contosoorder", "depth": "local" },
    { "privilegeName": "prvWritenew_contosoorder", "depth": "local" }
  ]
}
```

If `privileges` is supplied, it is treated as the full desired set to replace the current or copied baseline.

## Update Spec Pattern

Selectors:

- `roleId`
- or `name` plus optional business-unit selector

Typical update fields:

- `newName`
- `description`
- `appliesTo`
- `summaryOfCoreTablePermissions`
- `inheritanceMode`
- `isAutoAssigned`
- `privileges`
- `additionalPrivileges`
- `removePrivileges`

Example:

```json
{
  "name": "Contoso App User",
  "businessUnitName": "Contoso",
  "solutionUniqueName": "ContosoApp",
  "additionalPrivileges": [
    { "privilegeName": "prvAppendnew_contosoorder", "depth": "local" }
  ],
  "removePrivileges": [
    { "privilegeName": "prvDeleteold_legacyentity" }
  ]
}
```

## Inspection Pattern

Use list or inspect before editing when:

- the exact business unit is unclear
- you need to confirm whether the role is system-generated
- you need the current privilege set for review
- you need to confirm whether the role is already in the selected solution

Example list spec:

```json
{
  "mode": "list",
  "solutionUniqueName": "ContosoApp",
  "includePrivileges": false
}
```

Example inspect spec:

```json
{
  "mode": "inspect",
  "name": "Contoso App User",
  "businessUnitName": "Contoso",
  "includePrivileges": true
}
```

## ALM And Merge Cautions

- Managed solution imports merge security role privileges differently from many other component types.
- When a managed solution updates a security role, manually added privileges can be removed while privilege-level changes are retained.
- Use the same custom solution to manage later updates to the same role.
- Do not use custom solutions to modify predefined roles; copy them first and manage the copy.

If the user asks for a one-off live security change with no solution ownership, call out that the change is environment-only and not yet captured in ALM.

## Validation

Before finishing:

- inspect the final role state
- confirm the intended privilege names and depths
- confirm whether the role and current role privileges were added to the target unmanaged solution
- state whether user or team assignment was intentionally not performed
