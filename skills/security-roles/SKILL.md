---
name: security-roles
description: >
  Use for ANY Dataverse security role task — list or inspect roles, create custom roles, and
  update privilege sets or role metadata as code-first desired state. Fires whenever the user
  says "create a security role", "give this role access", "update the privileges", "what can
  this role do", "list the roles", "copy a role and adjust it", "set table permissions", or
  asks about depth/scope (basic/local/deep/global), privilege names like `prvRead...`, or which
  role a model-driven app needs — even if no helper is named. It is solution-aware and ALM-cautious:
  it prefers custom roles over editing predefined or system-generated roles, copies a baseline
  before adjusting, keeps role changes in the owning unmanaged solution, and warns about the
  managed-import merge caveat where manually added privileges can be dropped. Run the live-mutation
  preflight from the `powerplatform-core` orchestrator before any create or update.
---

# Security Roles — Dataverse Roles and Privilege Sets

This skill handles Dataverse security role inspection, creation, and updates as reviewable, code-first desired state rather than ad hoc portal clicks. It lists and inspects roles (including their privilege sets and business unit), creates custom roles — optionally seeded by copying a baseline role — and applies privilege-set and metadata deltas through structured JSON specs. It is solution-aware: when a role belongs to your app or managed delivery path, the change stays scoped to the owning unmanaged solution. It is intentionally generic about environment URL, business unit, publisher prefix, and solution name — discover those per task.

## When to use this

- The user wants to create a custom role, or copy an existing role and adjust it.
- The user wants to inspect or list roles, confirm whether a role is system-generated, or read its current privilege set before editing.
- A privilege set needs to change (add, remove, or replace privileges, adjust depth, or apply a record filter).
- Role metadata needs updating (name, description, applies-to, core-table permission summary, inheritance mode, auto-assign).
- You need to confirm the minimum privileges a model-driven app or solution feature requires before granting access.

Route here from the `powerplatform-core` orchestrator. For broader solution packaging, versioning, or promotion of the owning solution, use the `solution-alm-delivery` sibling skill.

## Helpers

The helpers live in the plugin's `scripts/` directory at the plugin root, not in this skill folder. Resolve the plugin root and invoke them like:

- `python "$CLAUDE_PLUGIN_ROOT/scripts/inspect_security_role.py" --spec <spec.json>` (Claude Code)
- `python "$CODEX_PLUGIN_ROOT/scripts/inspect_security_role.py" --spec <spec.json>` (also exposed as `$PLUGIN_ROOT`)
- Installed standalone / unsure: the `scripts/` folder sits beside this skill bundle — invoke by its path within the install.

| Helper | Purpose |
| --- | --- |
| `inspect_security_role.py` | List solution-scoped or business-unit roles, or inspect one role in detail, through the shared SDK helper. Drive it with a `--spec` whose `mode` is `list` or `inspect`; set `includePrivileges` to pull the current privilege set. Use this before editing when the business unit, system-generated status, or current privileges are unclear. |
| `create_security_role.py` | Create a custom role from a `--spec`. Use `copyFromRoleName`/`copyFromRoleId` to seed from a baseline, then layer `additionalPrivileges`; supplying `privileges` replaces the baseline with that full desired set. Set `solutionUniqueName` to add the role to the owning unmanaged solution. |
| `update_security_role.py` | Update role metadata and privilege sets from a `--spec`. Select by `roleId` or by `name` plus a business-unit selector; apply `additionalPrivileges`, `removePrivileges`, or a full `privileges` replacement, plus metadata fields like `newName`, `description`, `appliesTo`, and `inheritanceMode`. |

The shared SDK tool exposes the same surface as `securityrole --mode list|inspect|create|update`. Privilege specs are code-first: each entry carries `privilegeId` or `privilegeName`, a `depth` (`basic`, `local`, `deep`, `global`, or `record-filter`), and an optional `recordFilterId`.

## Domain workflow

1. **Inspect before editing.** Run `inspect_security_role.py` when the exact business unit is unclear, when you must confirm whether a role is system-generated, when you need the current privilege set for review, or when you need to confirm the role is already in the selected solution.
2. **Prefer a baseline copy.** Do not assume a new role can start from zero privileges and still be usable. For app access, navigation, or standard Dataverse usage, copy an appropriate baseline role (`copyFromRole...`) and apply a small declarative delta, or include the required minimum privileges explicitly.
3. **Create as code-first desired state.** Use `create_security_role.py` with a reviewable JSON spec. Set `solutionUniqueName` so the role ships through ALM, and prefer the same unmanaged solution for later updates to the same role.
4. **Update with explicit deltas.** Use `update_security_role.py` with `additionalPrivileges`/`removePrivileges` for targeted changes, or a full `privileges` set when replacing the desired state. Treat privilege changes as configuration, not one-off UI clicks.
5. **Validate the final state.** Inspect the role after the change, confirm the intended privilege names and depths, confirm whether the role and its privileges were added to the target unmanaged solution, and state whether user/team assignment was intentionally not performed.

## Safety and decision rules

- **Do not edit predefined or system-generated roles by default.** Copy the baseline first and manage the copy. Only modify a system-generated role when the user explicitly approves it.
- **Keep app-owned roles in their solution.** If the role is app-owned, keep later updates in the same custom unmanaged solution so the desired state stays source-controlled and promotable.
- **Mind the managed-import merge caveat.** Managed solution imports merge security-role privileges differently from many other component types: when a managed solution updates a role, manually added privileges can be removed while privilege-level changes are retained. Manage role updates through the owning solution rather than relying on out-of-band manual additions.
- **Call out environment-only changes.** If the user asks for a one-off live security change with no solution ownership, state that the change is environment-only and not yet captured in ALM.
- **Grant the minimum that works.** Start from an appropriate baseline or include the explicit minimum privileges; avoid over-granting global depth where local or basic suffices.
- **Preflight gate.** Run the mandatory live-mutation preflight from the `powerplatform-core` orchestrator before any role create or update. Do not restate the full preflight here — invoke it there.

## References

- `references/security-roles.md` — default position, before-you-change checklist, privilege spec shape, create/update/inspect spec patterns, ALM and merge cautions, and the validation checklist.
