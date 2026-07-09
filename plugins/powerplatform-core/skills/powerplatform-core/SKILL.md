---
name: powerplatform-core
description: >
  Entry point and router for Microsoft Power Platform and Dataverse development. Use to
  discover repo context, choose the right development surface, and run the mandatory
  live-mutation preflight before any deploy/publish/import/registration/data-write. Start here
  when the request spans multiple areas, is ambiguous, or the repo shape is unknown, then DEFER
  to the matching domain skill for focused single-domain work (schema, data, flows, plug-ins,
  PCF/web resources, code apps, solution ALM, security roles, document generation, custom
  connectors, platform administration). Trigger when the user mentions Power Platform, Dataverse, Dynamics 365, Power
  Apps, Power Automate, model-driven apps, solutions, or the pac CLI without naming a specific
  asset - but let the domain skills lead on their specifics.
---

# Power Platform Core — Orchestrator

PowerPlatform-Core is a code-first coding-agent skill for Microsoft Power Platform and Dataverse development. This orchestrator is the entry point: it discovers repo context, routes to the right domain skill, and enforces the safety rules that every domain shares. It is intentionally generic — it does not assume one house repo convention, environment URL, publisher prefix, or folder layout.

Prefer executable, source-controlled surfaces (JavaScript, plug-ins, custom APIs, supported metadata APIs, SDK/Web API helpers, PAC CLI, repo-owned deploy wrappers) over Business Rules, portal memory, browser automation, or stale solution packages.

## How it works

1. **Discover first.** Run the discovery helper before asking broad setup questions; infer the project shape from existing artifacts (solutions, plug-ins, PCF, pipelines, project profile).
2. **Choose the surface.** Pick the lightest surface that fits — metadata, client script, plug-in, custom API, flow, PCF, web resource, config data, or solution ALM — then open the matching domain skill.
3. **Apply repo-backed changes first** so the result is source-controlled and reviewable.
4. **Run the live-mutation preflight** before any deploy, publish, import, registration, push, or data write.
5. **Validate and deliver through the approved targeted path** unless the user explicitly accepts a broader blast radius.

## Running the helper scripts

The Python helpers and the compiled `CodexPowerPlatform.DataverseOps` / `CodexPowerPlatform.AuthDialog` tools live in the plugin's **`scripts/`** and **`tools/`** directories at the plugin root — *not* inside each skill folder. Resolve the plugin root and invoke a helper like this:

- **Claude Code:** `python "$CLAUDE_PLUGIN_ROOT/scripts/discover_context.py" --path .`
- **Codex:** `python "$CODEX_PLUGIN_ROOT/scripts/discover_context.py" --path .` (also exposed as `$PLUGIN_ROOT`)
- **Installed as a standalone skill / unsure:** the `scripts/` and `tools/` folders sit beside this skill bundle; invoke them by their path within the install.

Shared references that several domains use (surface selection, verification, ALM, archetypes) live in the plugin's **`references/`** directory; domain skills point to the specific files they need.

## Mandatory live-mutation preflight

Before any live Dataverse mutation, print or capture a preflight gate. Use `scripts/validate_delivery.py --preflight-spec ...` when it fits; otherwise produce the same fields manually and stop if any required field is missing.

Required fields: target environment URL; active PAC profile and mismatch warning when PAC is involved; target solution unique name and whether it is a patch; mutation type; exact components touched; delivery primitive; for any ZIP/package — artifact path, creation/modification time, solution name/version, managed state, and component diff; blast radius (targeted, component subset, patch package, or full solution); rollback/recovery plan; timeout and fallback path; and explicit confirmation when the primitive is not targeted.

Do not import a ZIP from `bin`, `Release`, `Downloads`, or old temp folders unless it was generated in the current session or explicitly selected by the user. If multiple package candidates exist, stop and ask. Never silently escalate from a targeted helper to a whole-solution import.

## Dataverse MCP interop (optional companion)

Microsoft's **Dataverse MCP server** (hosted at `https://{org}.crm.dynamics.com/api/mcp`) is complementary, not competing: it lets an agent *talk to your data* conversationally; this plugin lets an agent *ship your solution*. When both are connected, route by intent instead of defaulting to either.

- **Prefer the Dataverse MCP** for interactive natural-language exploration where the user is asking, not shipping: ad-hoc "what rows look like this", schema questions (`describe`), and small read-only lookups (`search`, `search_data`, `read_query`). It has no repo context and no delivery safety, but it is the lowest-friction way to answer a data question in the moment.
- **Prefer this plugin's helpers** for anything **paged, keyed, verified, solution-aware, or mutating**: bounded paging with total counts (`read_data.py --mode list`), keyed retrieve/create/update/upsert/delete (`read_data.py`/`upsert_data.py`/`delete_data.py`), solution-scoped writes, flow/plug-in registration, deploys, and every path that must pass the live-mutation preflight. The MCP has no preflight gate, so never route a live mutation through it when a delivery contract matters.
- **Degrade gracefully around known MCP limits.** `read_query` returns a small capped page (community reports ~20 rows) and supports only a SQL subset — when a result is truncated or a query is rejected, fall back to `read_data.py`/`design_dataverse_query.py` (FetchXML with explicit paging and a `totalRecordCount`) rather than trusting a partial MCP result.
- **The MCP is optional.** If it is not connected, everything still works through the plugin helpers; do not tell the user they must install it. To run both, register the MCP alongside the plugin: `claude mcp add --transport http dataverse https://{org}.crm.dynamics.com/api/mcp`. The full trade-off analysis lives in the project repo at [docs/comparison-dataverse-mcp.md](https://github.com/satriotsubasa/PowerPlatform-Core/blob/main/docs/comparison-dataverse-mcp.md) (not shipped inside the installed bundle).

## Route to the right domain skill

| The task is about… | Open skill |
| --- | --- |
| Tables, columns, relationships, forms, views, ribbon, icons, schema design | `dataverse-schema` |
| Row create/update/upsert, query design (OData/FetchXML/Power Automate) | `data-operations` |
| Solution-aware cloud flows: create, update, inspect, lint, connector/hardening review, trigger URLs | `power-automate-flows` |
| Plug-ins, custom APIs, step registration, plug-in step state | `plugins-server-extensions` |
| PCF controls, web resources, client scripts, Power Fx | `pcf-and-web-resources` |
| Power Apps Code Apps (pro-code SPA model) | `code-apps` |
| Solution pack/import/deploy, versioning, patch/merge, components, standards, delivery validation | `solution-alm-delivery` |
| Security roles and privilege sets | `security-roles` |
| Word Templates and document generation | `document-generation` |
| Custom connectors and integration wrappers | `custom-connectors` |
| Power Platform tenant/environment administration (admin center): environments, tenant settings, DLP, managed environments, environment groups, capacity | `platform-administration` |

When a repo matches a documented overlay's conventions, suggest the specialized overlay skill if one is installed.

## Discovery and project context

- Run `scripts/discover_context.py --path .` first when the repo shape is not obvious. Add `--include-pac-auth` only when live access matters and PAC CLI is available.
- If the repo has `.codex/power-platform.project-profile.json` or `power-platform.project-profile.json`, treat that profile as the first override layer for main solution, source areas, and conventions. If it has a `deploymentDefaults` block, treat those values as the repo's operational deploy guidance (timeout budgets, manual-only surfaces, preferred primitives, plug-in step-state defaults, typed row-write coercion). See `references/project-profile.md`.
- If the repo matches a layered structure (`*.Business`, `*.Plugins`, `*.Data`, `WebResources`, `*.PCF`, `Word Templates`, `Dataverse`, `Tools`), follow that layout — see `references/repo-archetypes.md`.
- Open `references/execution-surface-guide.md` to choose between metadata, client script, plug-ins, custom APIs, flows, web resources, or PCF.
- Open `references/verification-and-recovery.md` for live-mutation work, deployment, or a precise completion standard before execution starts.
- Open `references/context-and-alm.md` for auth, source-control layout, `pac` workflows, and environment safety.
- For durable multi-session work, keep `README.md` and `CODEX_HANDOFF.md` current — see `references/thread-continuity.md`.

## Default operating assumptions

- For live SDK/Web API work, prefer the reusable auth dialog (`scripts/auth_context.py`) so the user confirms the target URL, completes a forced interactive sign-in, and selects the working solution before execution. The dialog is Windows-only; on macOS/Linux, sign-in uses the device-code flow (the tool prints a code to complete in a browser). Use `pac auth interactive` when the dialog is unavailable.
- Warn when the requested live target does not match the active PAC profile environment URL. Treat `DEV` as the working environment and `TEST` as deployment validation. Do not touch production.
- Ask before delete, import, publish, register, push, or upgrade. Do not delete business data unless explicitly requested and separately approved.
- Keep every change solution-scoped (add/update only the scoped components in the target unmanaged solution or selected patch) — this does not mean defaulting to solution import.
- Do not introduce Dataverse Business Rules. Use client script for form-scoped behavior and plug-ins or custom APIs for shared server-side behavior.
- Treat plug-in step enablement as explicit deployment state: after registration/push/import, verify critical steps stay enabled and intentionally disabled steps stay disabled.
- Treat browser automation as opt-in fallback only, after headless options are exhausted.
- Report exactly what changed, what was inferred, what was executed, what was verified, what still needs environment access, and which publish/import/registration steps were intentionally not performed.

## Closing out

Validate the narrowest relevant surface, prefer small reviewable diffs over large repacks, and never describe a change as "deployed" or "complete" beyond what was actually verified. If critical inputs are missing (environment URL, solution name, publisher prefix, managed strategy, target folder), ask concise questions instead of guessing.
