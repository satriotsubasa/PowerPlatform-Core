---
name: powerplatform-core
description: General-purpose Power Platform and Dataverse development skill for code-first, repo-backed execution in coding-agent workflows across model-driven apps, Dynamics 365, plug-ins, custom APIs, PCF controls, web resources, solution-aware cloud flows, Dataverse metadata, Dataverse data operations, PAC CLI workflows, and headless Dataverse automation through CLI, SDK, Web API, and solution import flows. Use when Codex needs to inspect an unfamiliar or varied repo layout, infer the active project context, and implement or troubleshoot changes without assuming one house project structure or one company's repo conventions.
---

# Power Platform Development

Plan and implement solution-based Dataverse changes for model-driven apps and Dynamics 365 without assuming one fixed repo shape, naming scheme, or team convention. Keep the skill reusable across repositories, publishers, solution names, and environments. This skill is designed to maximize source-controlled, reviewable, testable, and maintainable execution in coding-agent workflows. Prefer source-controlled, supported customizations and reliable headless paths when they exist, keep durable thread continuity, and open only the smallest reference set needed for the task. This skill is intentionally code-first for executable logic: it prefers JavaScript, plug-ins, and custom APIs over Dataverse Business Rules.

## Workflow

1. Treat project context as runtime input, not fixed skill configuration. Do not assume one permanent environment URL, publisher prefix, solution name, or folder layout.
2. Run `python scripts/discover_context.py --path .` first when the repo shape is not already obvious. Add `--include-pac-auth` only when live environment access matters and PAC CLI is available. The discovery output includes an `overlay_skills` section listing any installed skill whose `skill-package.json` declares `"extends": "powerplatform-core"`. If the repo matches an overlay's conventions, inform the user that a specialized extension is available and suggest using it.
3. Read repo context first. If the repository already contains a solution file, solution project, unpacked solution files, plug-in code, PCF code, pipeline files, deployment settings, README architecture notes, or a project profile, infer the current project shape from those artifacts before asking questions.
4. Check repo continuity docs early. If the repo lacks a useful root `README.md`, lacks `CODEX_HANDOFF.md`, or the user wants durable thread continuation, open [references/thread-continuity.md](references/thread-continuity.md) and create or update those files before deep implementation. Preserve any strong existing `README.md`; only merge a compact `Start Here` block near the top.
5. If the repo matches a layered structure like `*.Business`, `*.Plugins`, `*.Data`, `WebResources`, `*.PCF`, `Word Templates`, `Dataverse`, or `Tools`, open [references/repo-archetypes.md](references/repo-archetypes.md) and follow that layout instead of forcing a new one. If the repo has strong documented local conventions, project profiles, or architecture notes, preserve those patterns instead of forcing a new house style.
6. If the repo contains `.codex/power-platform.project-profile.json` or `power-platform.project-profile.json`, open [references/project-profile.md](references/project-profile.md) and treat that profile as the first clarification layer for main live solution, source areas, and repo conventions before falling back to broader inference.
7. If environment URL, solution unique name, publisher prefix, managed strategy, or repo layout is still missing, gather only the missing values in [references/project-context-template.md](references/project-context-template.md) before any environment-bound or destructive work.
8. Open [references/context-and-alm.md](references/context-and-alm.md) for auth, source-control layout, project discovery, `pac` workflows, environment safety, and Dataverse MCP guidance.
9. Open [references/execution-automation.md](references/execution-automation.md) when the user wants Codex to execute the change end to end instead of only generating code or instructions.
10. Open [references/helper-strategy.md](references/helper-strategy.md) when deciding whether to add a new reusable helper, when expanding the automation library, or when a capability is still workflow-driven and needs to be categorized.
11. Open [references/execution-surface-guide.md](references/execution-surface-guide.md) when deciding between metadata, client script, plug-ins, custom APIs, flows, HTML web resources, or PCF.
12. Open [references/verification-and-recovery.md](references/verification-and-recovery.md) when the task will mutate live Dataverse state, includes deployment, publish, import, registration, or repo-versus-live reconciliation work, or needs a precise completion standard before execution starts.
13. Open only the task-specific references you need:
   - [references/dataverse-design.md](references/dataverse-design.md) for requirement-to-schema design, alternate keys, and query-shape planning before metadata execution.
   - [references/dataverse-metadata.md](references/dataverse-metadata.md) for tables, columns, relationships, forms, views, and icons.
   - [references/data-operations.md](references/data-operations.md) for Dataverse row create, update, and upsert work.
   - [references/security-roles.md](references/security-roles.md) for Dataverse security role inspection, creation, update, privilege-set design, and ALM cautions.
   - [references/client-customization.md](references/client-customization.md) for form scripts, client APIs, and HTML/CSS/JS/TS web resources.
   - [references/server-extensions.md](references/server-extensions.md) for plug-ins, custom APIs, and early-bound generation.
   - [references/pcf-controls.md](references/pcf-controls.md) for PCF control design and delivery.
   - [references/power-automate-flows.md](references/power-automate-flows.md) for solution-aware cloud flow creation, inspection, linting, hardening review, and ALM delivery.
   - [references/solution-patches.md](references/solution-patches.md) for patch, merge, upgrade, and main-solution targeting decisions.
   - [references/solution-standards.md](references/solution-standards.md) for repo standards review and convention enforcement.
   - [references/power-fx.md](references/power-fx.md) for formula debugging, delegation review, and rewrite guidance.
   - [references/custom-connectors.md](references/custom-connectors.md) for custom connector and integration-wrapper design.
   - [references/document-generation.md](references/document-generation.md) for Word Templates, content controls, and document-generation change planning.
   - [references/queries-and-xml.md](references/queries-and-xml.md) for Power Automate Dataverse queries, OData, FetchXML, LayoutXML, and solution XML.
   - [references/code-apps.md](references/code-apps.md) for Power Apps Code Apps — architecture, Vite scaffold, Dataverse data source integration, CRUD patterns, ALM, and admin setup.
14. Keep every change solution-scoped. Add or update artifacts in the target unmanaged solution instead of editing the environment without source control unless the user explicitly asks for a portal-only change.
15. Prefer the automation ladder in [references/execution-automation.md](references/execution-automation.md): repo edits, SDK or Web API, solution XML, `pac` CLI, and direct deployment tools. Do not choose browser automation unless the user explicitly approves a fallback after headless options are exhausted.
16. Prefer reusable helper scripts in `scripts/` when they already cover the task. Current helpers include `discover_context.py`, `auth_context.py`, `ensure_dataverse_reference.py`, `apply_requirement_spec.py`, `whoami.py`, `upsert_data.py`, `create_table.py`, `create_field.py`, `create_lookup.py`, `inspect_flow.py`, `lint_flow.py`, `review_flow_hardening.py`, `review_flow_connectors.py`, `create_flow.py`, `update_flow.py`, `get_flow_trigger_url.py`, `inspect_environment_variable.py`, `set_environment_variable_value.py`, `design_dataverse_schema.py`, `design_dataverse_query.py`, `review_solution_standards.py`, `debug_power_fx.py`, `design_custom_connector.py`, `plan_document_generation.py`, `plan_solution_patch_merge.py`, `update_main_form.py`, `patch_form_xml.py`, `patch_form_ribbon.py`, `update_form_events.py`, `bind_pcf_control.py`, `update_view.py`, `set_table_icon.py`, `sync_webresource.py`, `sync_webresources_batch.py`, `inspect_word_templates.py`, `create_custom_api.py`, `inspect_security_role.py`, `create_security_role.py`, `update_security_role.py`, `inspect_plugin_steps.py`, `ensure_plugin_step_state.py`, `register_plugin_headless.py`, `register_plugin_package_headless.py`, `scaffold_pcf_control.py`, `deploy_pcf.py`, `version_pcf_solution.py`, `add_solution_components.py`, `solution_version.py`, `deploy_solution.py`, `validate_delivery.py`, and `push_plugin.py`, and `push_code_app.py`.
17. When a capability is not yet a helper, decide explicitly whether it belongs in:
   - a deterministic dedicated helper
   - a carefully designed helper with a stronger spec format
   - the workflow layer with existing helpers underneath
   Use [references/helper-strategy.md](references/helper-strategy.md) instead of leaving the boundary implicit.
18. Prefer supported makers tools, CLI, SDK, and client APIs over unsupported DOM hacks or direct database assumptions. Edit raw XML only when the task explicitly requires it or when the source-controlled artifact is already XML.
19. Validate the narrowest relevant surface:
   - Solution work: inspect unpacked diffs, or run `pac solution sync`, `pack`, `unpack`, or `check` when appropriate.
   - Plug-ins: restore and build, then confirm step registration assumptions.
   - PCF: install dependencies, build, confirm manifest metadata, and when a wrapper `Solutions` project exists confirm the package artifact path and version alignment.
   - Client scripts: verify handler signatures, logical names, and build output if TypeScript is used.
   - Query or automation changes: verify logical names, null handling, and filter syntax.
20. Keep `CODEX_HANDOFF.md` current when work spans major milestones, architecture decisions, environment execution, or repo structure changes.
21. If the thread becomes long or context feels tight, notify the user before any recap or compaction and update `CODEX_HANDOFF.md` first. Do not pretend an exact context percentage is available; use a conservative heuristic.
22. Report exactly what changed, what was inferred from the repo or discovery script, what was executed automatically, what was verified, what still requires environment access, and which publish, import, or registration steps were intentionally not performed.

## Default Operating Assumptions

- For live Dataverse SDK or Web API work, prefer the reusable auth dialog in `scripts/auth_context.py` so the user can confirm the target URL, complete a forced interactive sign-in, and select the exact working solution before execution starts.
- Use `pac auth interactive` when the auth dialog is unavailable or the user explicitly wants PAC-only auth.
- Warn when the requested live target does not match the active PAC profile environment URL. Do not silently continue without surfacing that mismatch.
- Treat `DEV` as the working environment and `TEST` as deployment validation. Do not touch production.
- Ask before delete, import, publish, register, push, or upgrade.
- If Dataverse reports that another `Import` or `PublishAll` is already running, do not skip the step immediately. Prefer the helper retry window first, then report failure only after that wait-and-retry path is exhausted.
- Do not hardcode one project's URL, publisher prefix, solution name, or folder layout into the skill. Discover or request them per task.
- Treat the selected solution as authoritative for live work in that session. If the selected solution is a patch, do not assume merge or parent-solution targeting unless the user explicitly asks for it.
- Prefer repo conventions first. If no structure exists, use the default layout in [references/context-and-alm.md](references/context-and-alm.md). Treat code-centric `.sln + Business/Data/Plugins/WebResources` repos as first-class Dataverse implementations, not partial failures.
- Treat hybrid enterprise repos as normal. `Business`, `Plugins`, `Data`, `WebResources`, `Word Templates`, and `PCF` can all be source-of-truth areas while `Dataverse/` remains a metadata reference area and `Reference/` remains docs-only.
- Do not introduce new Dataverse Business Rules as an implementation surface. For executable logic, prefer client script for form-scoped behavior and plug-ins or custom APIs for shared or server-side behavior.
- Treat plug-in step enablement as explicit deployment state. After plug-in registration, push, or import work, verify that critical steps are still enabled and intentionally disabled steps remain disabled.
- When the repo has a namespaced `*.Data` or similar project that is generated from early-bound tooling, treat it as generator-owned. Read it for context, build against it, and regenerate it when required, but do not hand-edit generated files there unless the user explicitly asks for a manual fix.
- When a PCF package root contains a wrapper `Solutions` project, prefer that package flow for deployable artifacts. `Debug` artifacts normally come from `Solutions\bin\Debug`; `Release` artifacts normally come from `Solutions\bin\Release`.
- Prefer repo-root continuity docs. Keep `README.md` as the entry point and `CODEX_HANDOFF.md` as the running state file when the work is expected to span multiple sessions or threads.
- If the repo has a strong architecture README or technical guide, read the relevant sections before making structural changes.
- Use best-practice naming: stable publisher prefix, explicit schema names, readable logical names, clear namespaces, and consistent casing.
- Handle errors explicitly. Return actionable messages in plug-ins, custom APIs, scripts, and automation expressions.
- Dataverse data create, update, and upsert are in scope when the user asks for them. Do not delete business data unless the user explicitly requests deletion and separately approves the action.
- Treat solution-aware cloud flows as Dataverse workflow records for create or update work, but keep cross-environment promotion in the solution ALM path with connection references and environment variables.
- Remember that PCF versioning usually has two surfaces: the `version` attribute in `ControlManifest.Input.xml` and the wrapper solution version in `Solutions\src\Other\Solution.xml`. Update both together with `scripts/version_pcf_solution.py` unless the repo clearly uses a different convention.
- When the user asks for "latest", or the task depends on current CLI or runtime support, verify against official Microsoft documentation before assuming.
- Prefer Dataverse MCP only for inspection or guided development when it is configured and the user allows it. Do not use it as a shortcut for destructive changes.
- Treat browser automation as opt-in fallback only, not a default implementation path.
- Do not rely on silent auto-compaction for continuity when a repo-level handoff file can be refreshed first.
- If the repo has only supporting local solution source, such as a PCF packaging solution, do not present that supporting solution as the main app solution unless a project profile or the user confirms it.
- The long-term goal is helper-first execution for deterministic operations and workflow-driven composition for repo-specific judgment. Do not leave that split implicit.

## Reference Guide

- [references/project-context-template.md](references/project-context-template.md)
- [references/project-profile.md](references/project-profile.md)
- [references/context-and-alm.md](references/context-and-alm.md)
- [references/helper-strategy.md](references/helper-strategy.md)
- [references/repo-archetypes.md](references/repo-archetypes.md)
- [references/execution-automation.md](references/execution-automation.md)
- [references/execution-surface-guide.md](references/execution-surface-guide.md)
- [references/verification-and-recovery.md](references/verification-and-recovery.md)
- [references/thread-continuity.md](references/thread-continuity.md)
- [references/dataverse-design.md](references/dataverse-design.md)
- [references/dataverse-metadata.md](references/dataverse-metadata.md)
- [references/data-operations.md](references/data-operations.md)
- [references/security-roles.md](references/security-roles.md)
- [references/client-customization.md](references/client-customization.md)
- [references/server-extensions.md](references/server-extensions.md)
- [references/pcf-controls.md](references/pcf-controls.md)
- [references/power-automate-flows.md](references/power-automate-flows.md)
- [references/solution-patches.md](references/solution-patches.md)
- [references/solution-standards.md](references/solution-standards.md)
- [references/power-fx.md](references/power-fx.md)
- [references/custom-connectors.md](references/custom-connectors.md)
- [references/document-generation.md](references/document-generation.md)
- [references/queries-and-xml.md](references/queries-and-xml.md)
- [references/code-apps.md](references/code-apps.md)

## Execution Notes

- Follow existing solution layering and do not rename established schema artifacts without a migration reason.
- Do not manually edit generated early-bound files in namespaced `*.Data` or similar generator-owned projects. Change generator settings or regenerate instead.
- Use `scripts/discover_context.py` as the default repo triage tool before asking broad setup questions.
- Use `scripts/auth_context.py` before live environment work when the user wants the forced-popup auth path or when the target environment needs explicit confirmation. The dialog should not release live context until the user has selected the working solution.
- If the repo has a project profile, treat it as the first override layer for main live solution, source areas, and repo conventions before asking broad setup questions.
- If the repo has a flow guard contract in `.codex/power-platform.flow-guards.json`, `power-platform.flow-guards.json`, or a project-profile `flowGuardSpecPath`, treat it as the semantic safety contract for critical flow updates.
- If the repo has no local Dataverse solution source and the task needs live Dataverse work, prefer hydrating `Dataverse/<solution-unique-name>/` with `scripts/ensure_dataverse_reference.py` or the orchestration preflight instead of creating a `Reference/` folder.
- Treat `Reference/` as external or human reference material, not as the default source of truth for deployment work. Treat `Word Templates/` as a first-class source area when the repo uses document-generation plug-ins or content-control-based templates.
- Use `scripts/apply_requirement_spec.py` when the user gives a multi-step requirement or wants a coordinated end-to-end execution flow instead of a single isolated helper action.
- Use `scripts/whoami.py` for a read-only Dataverse SDK connectivity check before higher-risk live operations when auth or environment targeting is uncertain.
- Prefer `scripts/apply_requirement_spec.py` first for coordinated requirement execution, then fall back to `scripts/upsert_data.py`, `scripts/create_table.py`, `scripts/create_field.py`, `scripts/create_lookup.py`, `scripts/inspect_flow.py`, `scripts/lint_flow.py`, `scripts/review_flow_hardening.py`, `scripts/review_flow_connectors.py`, `scripts/create_flow.py`, `scripts/update_flow.py`, `scripts/get_flow_trigger_url.py`, `scripts/inspect_environment_variable.py`, `scripts/set_environment_variable_value.py`, `scripts/design_dataverse_schema.py`, `scripts/design_dataverse_query.py`, `scripts/review_solution_standards.py`, `scripts/debug_power_fx.py`, `scripts/design_custom_connector.py`, `scripts/plan_document_generation.py`, `scripts/plan_solution_patch_merge.py`, `scripts/update_main_form.py`, `scripts/patch_form_xml.py`, `scripts/patch_form_ribbon.py`, `scripts/update_form_events.py`, `scripts/bind_pcf_control.py`, `scripts/update_view.py`, `scripts/set_table_icon.py`, `scripts/sync_webresource.py`, `scripts/sync_webresources_batch.py`, `scripts/inspect_word_templates.py`, `scripts/create_custom_api.py`, `scripts/inspect_security_role.py`, `scripts/create_security_role.py`, `scripts/update_security_role.py`, `scripts/inspect_plugin_steps.py`, `scripts/ensure_plugin_step_state.py`, `scripts/register_plugin_headless.py`, `scripts/register_plugin_package_headless.py`, `scripts/scaffold_pcf_control.py`, `scripts/deploy_pcf.py`, `scripts/version_pcf_solution.py`, `scripts/add_solution_components.py`, `scripts/solution_version.py`, `scripts/deploy_solution.py`, `scripts/validate_delivery.py`, and `scripts/push_plugin.py` for narrower tasks.
- For security-role work, prefer `scripts/inspect_security_role.py` for list or inspect, `scripts/create_security_role.py` for new custom roles, and `scripts/update_security_role.py` for privilege-set or metadata changes. Do not update system-generated roles unless the user explicitly approves it.
- If the repo already has a safe deploy wrapper or deploy script for the current asset type, prefer that repo-owned entry point over reconstructing the same deployment sequence ad hoc. Otherwise fall back to the generic helpers and official tools in this skill.
- Use repo-root `README.md` plus `CODEX_HANDOFF.md` as the durable project memory layer when work is expected to continue across threads.
- If the repo already has a strong `README.md`, do not overwrite it. Insert or update a compact "Start Here" block near the top, typically after the title and first summary paragraph.
- Prefer headless implementation for forms, views, library registration, web resource deployment, PCF deployment, and metadata changes through solution files, Dataverse APIs, or CLI before considering any browser flow.
- Do not silently escalate from a targeted helper to `deploy_solution.py` or another whole-solution import. If the required metadata or ribbon change exceeds the supported targeted helper surface, stop, explain the limitation, and ask whether the user wants to accept the broader deployment blast radius.
- Treat whole-solution import in shared unmanaged environments as high risk because it can overwrite unrelated maker work. Require explicit approval before broadening a targeted-component or solution-subset change into a solution import.
- For Dataverse row operations, prefer safe create, keyed update, or upsert through SDK or Web API. Do not choose delete paths unless the user explicitly asked for deletion and approved it.
- For executable logic, do not choose Dataverse Business Rules. Use form script for form-session behavior, and use synchronous plug-ins or custom APIs for shared server-side behavior.
- When creating new assets, choose the lightest supported option that fits the requirement without falling back to Dataverse Business Rules: metadata change, form script, web resource, PCF, plug-in, custom API, flow, then XML-only edit as a last resort.
- For flow work, prefer inspecting or linting the live solution-aware cloud flow first, then update only the `workflow` properties that need to change. Use solution deployment for environment promotion instead of treating live create or update as the deployment mechanism.
- For flow updates that change `clientData`, treat semantic regression as a deployment blocker by default. Do not accept emptied critical branches, removed switch cases, or missing required branch actions unless the user explicitly approves semantic drift.
- For HTTP-trigger flow delivery, prefer a deterministic chain: create or update the solution-aware flow, resolve the signed callback URL with `scripts/get_flow_trigger_url.py`, set the environment variable value with `scripts/set_environment_variable_value.py`, then smoke test the endpoint if the user asked for validation.
- Keep generated output reviewable. Small diffs beat large repacks when the repo already uses unpacked solutions.
- If critical project inputs are still missing, ask concise questions instead of guessing on environment URLs, solution names, publisher prefixes, managed strategy, or target folder paths.
