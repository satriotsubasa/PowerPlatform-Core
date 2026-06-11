---
name: solution-alm-delivery
description: >
  Use for whole-solution Dataverse ALM and safe delivery - pack/import/deploy a solution, add
  solution components, solution versioning, patch/merge/upgrade planning, repo standards review,
  and safe-delivery validation behind the live-mutation preflight gate. Fires on "deploy the
  solution", "import the solution", "pack and import", "bump the solution version", "create a
  patch", "merge the patch", "upgrade the solution", "add this component to the solution",
  "validate my delivery", "is my repo following standards", or a request for a managed/unmanaged
  solution package, even if no helper is named. For a single asset (web resource, plug-in, PCF,
  form/ribbon metadata, role, flow), prefer the targeted sibling skill; escalate to a solution
  package ONLY when no targeted primitive fits and the user accepts the broader blast radius.
  Blocks stale-artifact imports, refuses silent escalation, classifies blast radius, and treats
  solution import as a slow 10-30 minute path needing explicit approval. Always run the
  live-mutation preflight from the `powerplatform-core` orchestrator before any pack-to-import,
  publish, or component write.
---

# Solution ALM & Delivery — Pack, Import, Deploy, and Safe Promotion

This skill owns Dataverse solution application lifecycle management and the safe-delivery path: packing and importing an unpacked solution, running delivery validation behind the mandatory live-mutation preflight, adding scoped components to a solution, versioning, planning patch/merge/upgrade lifecycles, and reviewing the repo against solution and ALM standards. It is deliberately conservative — it prefers the narrowest delivery primitive, keeps every change solution-scoped, and never quietly broadens a targeted component update into a whole-solution import. It is intentionally generic about environment URL, publisher prefix, solution unique name, managed strategy, and folder layout — discover those per task rather than assuming a house convention.

## When to use this

- The user wants to pack, import, deploy, publish, or promote a solution, or convert it to managed.
- The user wants to add a component (table, column, web resource, flow, role, and so on) to a target solution.
- The solution version needs to be set or incremented locally, and optionally synced online.
- The user is deciding between continuing a patch, creating a new patch, merging, upgrading, or promoting work back to the main unmanaged solution.
- The user wants delivery validated before a live mutation, or wants the repo reviewed against solution/ALM standards.

Route here from the `powerplatform-core` orchestrator. For the targeted single-asset deploy paths (web resources, plug-ins, PCF, form/ribbon metadata), use the matching sibling skill first — only escalate to a solution package when no targeted primitive fits and the user accepts the broader blast radius.

## Helpers

The helpers live in the plugin's `scripts/` directory at the plugin root, not in this skill folder. Resolve the plugin root and invoke them like:

- `python "$CLAUDE_PLUGIN_ROOT/scripts/validate_delivery.py" --preflight-spec <spec.json>` (Claude Code)
- `python "$CODEX_PLUGIN_ROOT/scripts/validate_delivery.py" --preflight-spec <spec.json>` (also exposed as `$PLUGIN_ROOT`)
- Installed standalone / unsure: the `scripts/` folder sits beside this skill bundle — invoke by its path within the install.

| Helper | Purpose |
| --- | --- |
| `validate_delivery.py` | Run safe delivery validation across repo, build, pack, and an optional read-only live preflight — without importing or mutating Dataverse. Pass `--preflight-spec` to emit the live-mutation preflight gate; `--promotion-audit-spec` to run the managed promotion audit (source / package / target read-back evidence); add `--live-preflight` for a read-only WhoAmI connectivity check. Use this before any solution import. |
| `deploy_solution.py` | Pack, optionally run Power Apps Checker, import, and publish a solution. Blocks stale artifacts unless `--artifact-generated-this-session` or `--explicit-artifact-selection` is set, and enforces a blast-radius guard via `--change-scope {targeted-component,solution-subset,whole-solution}`; broadening to a whole-solution import on a `--shared-unmanaged-environment` requires explicit `--allow-broad-import`. Honors lock-retry and `--max-runtime-seconds` budgets. |
| `add_solution_components.py` | Add resolved components to a target solution through the shared SDK helper from a `--spec`. Adds only the scoped components named; does not pull in broad required components or subcomponents unless the spec/user accepts the expanded blast radius. |
| `solution_version.py` | Set or increment the 4-part solution version in the unpacked `Other/Solution.xml` (`--version`, `--increment {build,revision}`, or explicit parts), and optionally sync the version online with `--online`. Bump the version before re-importing a package. |
| `plan_solution_patch_merge.py` | Plan a patch/merge/upgrade workflow from structured solution context (`--spec`). Returns recommended strategy, target solution, next version, concrete next steps, and warnings when the chosen target does not line up with the selected patch or main solution. Planning only — local and safe. |
| `review_solution_standards.py` | Review the repo against solution, ALM, and house-style standards (continuity docs, project profile, publisher-prefix quality, main-vs-supporting solution ambiguity, PCF manifest/wrapper version alignment, generator-owned `*.Data` boundaries, `Reference` vs `Dataverse` intent). Returns findings, severity, recommendations, and an overall risk level. Read-only. |

## Domain workflow

1. **Plan the lifecycle first.** If the user is choosing between continuing a patch, a new patch, merge, upgrade, or returning to the main solution, run `plan_solution_patch_merge.py` before touching the environment. Treat the selected live solution as authoritative for the session; if it is a patch, do not silently redirect work to the parent.
2. **Audit component membership.** Before exporting a patch or packaging for validation, compare the expected issue-related components against live patch membership. Place missing scoped components with `add_solution_components.py`; do not add broad required subcomponents without accepting the wider blast radius.
3. **Version before re-importing.** Use `solution_version.py` to bump the version before a fresh package. Never retry importing the same version of a stale package — bump or switch to a targeted update path.
4. **Validate behind the preflight.** Run `validate_delivery.py` (with `--preflight-spec`) so the live-mutation gate is emitted and repo/build/pack evidence is gathered before any import.
5. **Deploy only the approved primitive.** Use `deploy_solution.py` only after blast-radius approval, with `--change-scope` set honestly and a freshly generated artifact. If a narrower targeted primitive exists in a sibling skill, prefer it.
6. **Verify at the narrowest true level.** After import/publish, confirm the intended component landed in the intended solution and app surface; run one focused live check if behavior changed. Do not call a change "deployed" beyond what was verified — see `references/verification-and-recovery.md`.

## Managed promotion audit

For managed promotion from a working environment (DEV) to a validation or later environment, a successful import and a bumped solution version are **not completion proof**. Before closeout, run the **Managed Promotion Audit** with `validate_delivery.py --promotion-audit-spec <spec.json>` (or produce the same fields manually).

Required evidence per release component: source or DEV expected state, managed-package evidence from the fresh ZIP, and a **target live read-back** after import and publish — with a per-component status (aligned, source mismatch, package mismatch, target stale, missing read-back, incomplete evidence, or needs review) and a remediation recommendation for anything not aligned. Always require an explicit target read-back for high-risk metadata in scope: command bars / RibbonDiffXml, table labels, forms, views, flows, security roles, plug-in steps, and configuration rows. If the solution version updated but live effective metadata is stale, do not re-import blindly — try a targeted publish and read-back first, inspect solution layers if it stays stale, then use the narrowest approved remediation. See `references/verification-and-recovery.md`.

## Safety and decision rules

This skill restates only the most critical gates. For the full required-field list, run the mandatory live-mutation preflight from the `powerplatform-core` orchestrator before any pack-to-import, publish, or component write — do not reconstruct it ad hoc here.

- **Block stale artifacts.** Do not import a ZIP from `bin`, `Release`, `Downloads`, or old temp folders unless it was generated in the current session or explicitly selected by the user. If multiple package candidates exist, stop and ask.
- **No silent escalation.** Never quietly broaden a targeted helper into a whole-solution import. If the required change exceeds the targeted surface, stop, explain the limitation, and ask whether the user accepts the broader blast radius.
- **Classify blast radius honestly.** Set `--change-scope` to the true scope (`targeted-component`, `solution-subset`, or `whole-solution`). Treat whole-solution import in a shared unmanaged environment as high risk because it can overwrite unrelated maker work — require explicit approval and `--allow-broad-import`.
- **Solution import is the slow path.** When the primitive becomes solution import, stop and state that this is no longer a fast targeted deploy and commonly takes 10-30 minutes including import, publish, cache refresh, and verification — and what narrower path was unavailable.
- **Respect import/publish locks.** If Dataverse reports another import or publish is already running, do not skip immediately. Use the helper retry window first; report failure only after the wait-and-retry path is exhausted.
- **Keep it solution-scoped, not solution-default.** Add or update only the scoped components in the target unmanaged solution or selected patch. Solution-scoped does not mean defaulting to a full solution package.
- **Ask before destructive lifecycle ops.** Do not merge, delete, clone, retire, or upgrade patches/solutions unless the user explicitly requests that lifecycle operation and approves it.

## References

- `references/solution-patches.md` — patch/merge/upgrade rules, planner inputs and intents, and the patch component audit before a TST export.
- `references/solution-standards.md` — what the standards review covers, expected output shape, and the repo-convention operating rules.
- `references/verification-and-recovery.md` — the completion standard, minimum evidence by layer, failure-recovery sequence, and the authority rules when repo and live Dataverse disagree.
