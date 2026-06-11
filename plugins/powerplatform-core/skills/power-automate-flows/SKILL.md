---
name: power-automate-flows
description: >
  Use for solution-aware Power Automate cloud flows in Dataverse - create, update, inspect,
  lint, connector governance review, hardening review (retry/concurrency/pagination/idempotency/
  error handling), HTTP-trigger callback URL resolution, and the environment variables flows
  read. Fires whenever the user mentions a cloud flow, Power Automate, a workflow record, flow
  connection references, a flow trigger URL or webhook callback, "lint my flow", "harden this
  flow", "review the connectors", or "why did my flow change behavior", even if no helper is
  named. Patches only the changed `workflow` properties and blocks semantic drift (emptied
  branches, dropped switch cases, removed required actions) by default. Not for C# plug-ins or
  custom APIs - use plugins-server-extensions. Run the live-mutation preflight from the
  `powerplatform-core` orchestrator before any create, update, activate, or environment-variable
  write.
---

# Power Automate Flows — Solution-Aware Cloud Flows

This skill handles solution-aware Power Automate cloud flows as first-class Dataverse `workflow` records (`category = 5`). It inspects, lints, and reviews live flows, then makes the smallest correct change — patching only the `workflow` properties that need to move — and resolves HTTP-trigger callback URLs and the environment variables flows depend on. It is code-first and ALM-aware: live edits are for authoring and validation, while cross-environment promotion stays in the solution export/import path with connection references and environment variables kept explicit. It is intentionally generic about environment URL, publisher prefix, solution name, and folder layout — discover those per task.

## When to use this

- The user wants to create, update, or analyze a cloud flow, or asks you to "look at", "fix", "enhance", or "troubleshoot" one.
- The task asks for a lint pass, a connector governance review, or a hardening review (retry policy, concurrency, pagination, idempotency, error handling, maintainability).
- An HTTP-trigger flow needs its signed callback URL resolved, stored in an environment variable, or smoke-tested.
- A flow reads an environment variable whose value must be inspected or set for the target environment.
- You must guard a critical flow against losing a switch case, branch, or required action during an edit.

Route here from the `powerplatform-core` orchestrator. For schema, plug-ins, PCF, or solution packaging, use the matching sibling skill instead.

## Helpers

The helpers live in the plugin's `scripts/` directory at the plugin root, not in this skill folder. Resolve the plugin root and invoke them like:

- `python "$CLAUDE_PLUGIN_ROOT/scripts/inspect_flow.py" --spec <spec.json>` (Claude Code)
- `python "$CODEX_PLUGIN_ROOT/scripts/inspect_flow.py" --spec <spec.json>` (also exposed as `$PLUGIN_ROOT`)
- Installed standalone / unsure: the `scripts/` folder sits beside this skill bundle — invoke by its path within the install.

| Helper | Purpose |
| --- | --- |
| `inspect_flow.py` | Inspect one flow or list solution-scoped flows; return identifiers, state, connection-reference summary, and definition summary. |
| `lint_flow.py` | Detect missing connection references, missing triggers/actions, broken `runAfter`, hardcoded GUIDs, and hardcoded Dataverse URLs. Works from live Dataverse or a local `clientData`/`definition`/JSON file. |
| `review_flow_connectors.py` | Review connector-specific read/write patterns (Dataverse, SharePoint, Outlook action shapes). Same live-or-local sources as the linter. |
| `review_flow_hardening.py` | Hardening checklist for retry policy, concurrency, pagination, idempotency, error handling, and maintainability. Same live-or-local sources. |
| `create_flow.py` | Create a new solution-aware flow from `clientData`, or from `definition` plus `connectionReferences`; add it to the selected solution. New flows start draft/off unless `activate` is set. |
| `update_flow.py` | Update an existing flow by `workflowId`, `workflowUniqueId`, `uniqueName`, or `name`. When `clientData` is supplied, it inspects the live baseline, runs semantic regression checks, updates, then re-inspects the live result. Auto-loads a repo flow-guard contract. |
| `get_flow_trigger_url.py` | Resolve the signed callback URL for an HTTP-trigger flow. **Windows-only / optional:** depends on Windows PowerShell plus the PowerApps admin module, and may prompt for a separate Power Apps sign-in. Skip gracefully where unavailable and tell the user. |
| `inspect_environment_variable.py` | Inspect an environment variable definition or read the current value that applies in the target environment. |
| `set_environment_variable_value.py` | Create or update the live `environmentvariablevalue` record for an existing definition. Prefer this over manual maker-portal edits when wiring a flow endpoint or environment-specific value. |

## Domain workflow

1. **Inspect first.** Run `inspect_flow.py` whenever the user wants to analyze, troubleshoot, or enhance a flow, so you work from the live baseline rather than assumptions.
2. **Lint before large edits.** Run `lint_flow.py` to catch missing connection references, broken `runAfter`, hardcoded GUIDs, and hardcoded Dataverse URLs.
3. **Review when quality matters.** Run `review_flow_hardening.py` for retry/concurrency/pagination/idempotency/error-handling concerns and `review_flow_connectors.py` for connector-specific patterns.
4. **Change only what must change.** Use `update_flow.py` and patch only the `workflow` properties that need to move (typically `clientData`, plus name/description/owner/state). Prefer `create_flow.py` only for genuinely new flows. Do not recreate a flow to deploy it.
5. **Resolve and wire HTTP triggers.** For an HTTP-trigger flow: create/update the flow, resolve the signed URL with `get_flow_trigger_url.py`, store it with `set_environment_variable_value.py`, then smoke-test only if the user asked. `apply_requirement_spec.py` can orchestrate this chain.
6. **Promote through solution ALM.** Keep the flow in the selected unmanaged solution and promote via solution export/import with connection references and environment variables — not by re-authoring per environment.

## Safety and decision rules

- **Semantic drift is a blocker by default.** `update_flow.py` blocks updates that empty a previously non-empty switch case, remove previously existing branch actions, or violate a repo-owned flow-guard contract. Only pass `--allow-semantic-drift` when the branch/action removal is genuinely intended and the user accepts it.
- **Keep a flow-guard contract for critical flows.** `update_flow.py` auto-loads a guard contract from the repo's flow-guard path or the project-profile `flowGuardSpecPath`. For critical flows, add a real contract in the repo rather than leaving the safeguard only in chat. Start from `references/power-platform.flow-guards.template.json`.
- **Keep environment-specific values out of the definition.** Use connection references and environment variables; do not hardcode URLs or GUIDs into the flow definition.
- **Do not delete flows** unless the user explicitly requests it. Ask before any publish/import step that affects the environment.
- **Mind the dual auth surfaces.** Dataverse and the Power Apps admin surface use separate auth stacks, so trigger-URL retrieval can trigger one extra Power Apps sign-in prompt.
- **Preflight gate.** Run the mandatory live-mutation preflight from the `powerplatform-core` orchestrator before any create, update, activate, or environment-variable write. Do not restate the full preflight here — invoke it there.

## References

- `references/power-automate-flows.md` — working model, preferred execution path, helper intent, and spec patterns.
- `references/queries-and-xml.md` — Power Automate Dataverse queries, OData, and FetchXML inside flow actions.
- `references/power-platform.flow-guards.template.json` — starting template for a repo flow-guard contract protecting critical switch branches.
