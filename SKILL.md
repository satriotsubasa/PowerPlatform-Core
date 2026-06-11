---
name: powerplatform-core
description: >
  Entry point for the PowerPlatform-Core plugin — a coding-agent skill for Microsoft Power
  Platform and Dataverse development: model-driven apps, plug-ins, PCF controls, web resources,
  form and ribbon metadata, solution-aware Power Automate flows, Dataverse schema, configuration
  data, custom APIs, security roles, document generation, and solution ALM. Use whenever the user
  works on Power Platform, Dataverse, Dynamics 365, Power Apps, Power Automate, or the pac CLI. The
  full capability is split into focused skills under `skills/`; start with the `powerplatform-core`
  orchestrator, which discovers repo context, routes to the right domain skill, and enforces the
  mandatory live-mutation preflight.
---

# PowerPlatform-Core

PowerPlatform-Core is packaged as a plugin made of **modular skills**. The capability lives under **`skills/`**, and the shared toolchain (`scripts/`, `tools/`, `references/`) sits at the plugin root and is resolved via `$CLAUDE_PLUGIN_ROOT` / `$CODEX_PLUGIN_ROOT`.

## Start here

Open the orchestrator: [`skills/powerplatform-core/SKILL.md`](skills/powerplatform-core/SKILL.md). It handles repo discovery, chooses the development surface, routes to the right domain skill, and enforces the shared safety rules.

## Domain skills (under `skills/`)

| Skill | For |
| --- | --- |
| `dataverse-schema` | tables, columns, lookups, forms, views, ribbon, icons, schema design |
| `data-operations` | row create/update/upsert, query design |
| `power-automate-flows` | solution-aware cloud flows: create/update/inspect/lint/review |
| `plugins-server-extensions` | plug-ins, custom APIs, step registration and state |
| `pcf-and-web-resources` | PCF controls, web resources, client scripts, Power Fx |
| `code-apps` | Power Apps Code Apps (pro-code SPA model) |
| `solution-alm-delivery` | solution pack/import/deploy, versioning, patch/merge, standards, delivery validation |
| `security-roles` | security roles and privilege sets |
| `document-generation` | Word Templates and document generation |
| `custom-connectors` | custom connectors and integration wrappers |

## Non-negotiable safety rule

Before ANY live Dataverse mutation (deploy, publish, import, registration, push, or data write), run the **mandatory live-mutation preflight** defined in the orchestrator skill. Never import a stale ZIP from `bin`, `Release`, `Downloads`, or temp folders unless it was generated in-session or explicitly selected, and never silently escalate a targeted change into a whole-solution import.

See [`README.md`](README.md) for installation (Claude Code / Codex) and [`docs/`](docs) for architecture.
