<p align="center">
  <img src="plugins/powerplatform-core/assets/logo.png" alt="PowerPlatform-Core logo" width="150">
</p>

<h1 align="center">PowerPlatform-Core</h1>

<p align="center">
  <strong>A code-first coding-agent plugin that turns Microsoft Power Platform &amp; Dataverse work into a safe, source-controlled, repo-first workflow.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/License-Apache--2.0-blue.svg"></a>
  <a href="#install"><img alt="Claude Code" src="https://img.shields.io/badge/Claude%20Code-plugin-d97757.svg"></a>
  <a href="#install"><img alt="OpenAI Codex" src="https://img.shields.io/badge/OpenAI%20Codex-plugin-412991.svg"></a>
  <a href="#requirements"><img alt="Cross-platform" src="https://img.shields.io/badge/Cross--platform-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-2ea44f.svg"></a>
  <a href="#how-its-built"><img alt="Built with" src="https://img.shields.io/badge/Built%20with-Python%20%C2%B7%20.NET%208-149CA1.svg"></a>
</p>

---

## What & why

Power Platform changes are easy to make and hard to make *safely* — a single stale ZIP or an accidental whole-solution import can quietly overwrite other people's work. PowerPlatform-Core gives a coding agent the judgment to avoid that: it reads your repo, understands your model-driven app and solution structure, picks the right development surface, makes reviewable source-controlled edits, and ships them through the narrowest delivery path behind a **mandatory live-mutation preflight**.

It is deliberately generic. It works across unfamiliar repos — layered code-centric, unpacked-solution, mixed, or near-empty — without assuming any one team's house convention, publisher prefix, or folder layout.

## Highlights

- 🧭 **11 modular skills that trigger precisely** — an orchestrator routes each task (schema, data, flows, plug-ins, PCF, code apps, ALM, security, docs, connectors) to exactly the right specialist.
- 🛡️ **Safe by default** — every live mutation passes a preflight gate; stale artifacts are blocked; targeted delivery is preferred over whole-solution imports.
- ⌨️ **Headless / code-first** — repo edits, SDK/Web API, solution files, and the `pac` CLI come first; browser automation is an opt-in last resort.
- 🤝 **Multi-agent** — one shared source installs as both a **Claude Code** plugin and an **OpenAI Codex** plugin.
- 🌐 **Cross-platform live path** — the runtime works on Windows *and* macOS/Linux (WAM broker sign-in on Windows, device-code flow elsewhere).

## Install

PowerPlatform-Core installs from one shared source into either agent.

### Claude Code

```text
/plugin marketplace add satriotsubasa/PowerPlatform-Core
/plugin install powerplatform-core@powerplatform-core
```

> The marketplace commands above resolve once the plugin is on the repo's default branch. To try a **local checkout** instead, launch with `claude --plugin-dir "<path-to-repo>"`, or run `/plugin marketplace add "<path-to-repo>"` pointed at your clone.

### OpenAI Codex

```text
codex plugin marketplace add satriotsubasa/PowerPlatform-Core
```

Then **install from inside Codex** — there is no `codex plugin add` shell command. Launch `codex`, run `/plugins`, open **powerplatform-core** in the list, choose **Install plugin**, then **restart Codex**.

> `marketplace add` only *registers* the source; it never installs — installation happens in the `/plugins` browser. If the plugin doesn't appear there, run `codex plugin marketplace upgrade` and retry.

### More agents (experimental)

The same source also ships manifests for more agents. **Cursor** and **Copilot** are confirmed against each platform's published plugin schema; **Gemini** and **OpenCode** are partial because their skill discovery expects a repo-root layout that the Codex-required `plugins/` subfolder doesn't match. None are end-to-end tested here yet, so treat them as experimental and please report issues.

- **Cursor** - add this repo as a plugin marketplace (Settings -> Plugins -> Team Marketplaces -> Import from Repo), then install `powerplatform-core`. (Cursor installs from its marketplace UI; there is no `owner/repo` shell command.)
- **GitHub Copilot CLI** - `copilot plugin marketplace add satriotsubasa/PowerPlatform-Core` then `copilot plugin install powerplatform-core@powerplatform-core` (Copilot reuses the same `.claude-plugin/marketplace.json` catalog; verify the verb with `copilot plugin --help`).
- **Gemini CLI** - `gemini extensions install https://github.com/satriotsubasa/PowerPlatform-Core`. Loads the **orchestrator** as always-on context, which then reads the domain skills as files on demand. (Gemini only auto-discovers a `skills/` folder at the repo root; our subfolder layout doesn't expose one, so the other ten skills aren't registered natively.)
- **OpenCode** - not a one-line install yet. OpenCode discovers skills from a workspace-root dir (`.opencode/skills/`, `.claude/skills/`, or `.agents/skills/`); ours live in `plugins/powerplatform-core/skills/`, so copy or symlink that folder's contents into `.opencode/skills/` in your workspace. (OpenCode's `plugin` array installs npm packages only - no git URL - and has no documented hook to add skill paths.)

### Requirements

The skills are code-first, so the live path needs a small local toolchain:

| Tool | Why |
| --- | --- |
| **Python 3.10+** | Runs the helper scripts that drive every live operation. |
| **.NET 8 SDK** | Builds and runs the shared `DataverseOps` execution tool (and plug-in projects). |
| **Node.js** | Required for PCF controls and Power Apps Code Apps (`npm` / `npx`). |
| **Microsoft Power Platform CLI (`pac`)** | Authentication, solution, and deployment operations. |

Interactive sign-in is platform-aware: on **Windows** it uses the WAM broker; on **macOS/Linux** it falls back to the **device-code flow** (the tool prints a code to complete in a browser).

> **Migrating from the classic skill?** The old `~/.codex/skills/powerplatform-core` copy-install is deprecated; the plugin replaces it. Once the plugin loads in Codex, delete that folder to avoid a duplicate `powerplatform-core` skill.

## The skills

Start with the **orchestrator** — `powerplatform-core` — which discovers repo context, chooses the development surface, enforces the safety rules, and routes to the right specialist below. You rarely need to name a skill yourself; the agent picks one from your prompt.

| Skill | What it does |
| --- | --- |
| **`powerplatform-core`** | 🧭 Orchestrator. Discovers repo context, picks the surface, enforces the live-mutation preflight, and routes to the right domain skill. |
| **`dataverse-schema`** | Tables, columns, lookups, choices, alternate keys, forms, views, the form ribbon (RibbonDiffXml), and table icons — plus up-front schema/query design. |
| **`data-operations`** | Row create / read / update / upsert / delete, config-data seeding and sync, and query design **and execution** (FetchXML/OData) with bounded paging and match counts. |
| **`power-automate-flows`** | Solution-aware cloud flows: create, update, inspect, **run-history read-back**, lint, connector & hardening review, and HTTP-trigger callback URL resolution. |
| **`plugins-server-extensions`** | C# plug-ins and custom APIs: headless registration, repeatable build-and-push, step inspection, and step-state reconciliation. |
| **`pcf-and-web-resources`** | PCF controls, web resources, client form scripts, and Power Fx review — scaffold, version, build, deploy, and bind. |
| **`code-apps`** | Power Apps Code Apps (the pro-code Vite + `@microsoft/power-apps` SPA model): scaffold, add data sources, build, and push. |
| **`solution-alm-delivery`** | The safety-critical delivery skill: pack/import/deploy, component placement, versioning, patch/merge/upgrade planning, and standards review. |
| **`security-roles`** | Inspect, create, and update Dataverse security roles and privilege sets as reviewable, solution-aware desired state. |
| **`document-generation`** | Word Template document generation: inventory content controls, map placeholders, and plan template-aware changes. |
| **`custom-connectors`** | Design custom connectors and integration wrappers — auth shape, operation inventory, and direct-connector vs. Azure-facade recommendation. |

## Quickstart

Just describe the outcome you want. The agent discovers context, opens the matching skill, and runs the preflight before any live change.

```text
Add a Dataverse table for "Service Visit" and surface it in the target model-driven app.
```
> Routes to `dataverse-schema`, designs the table/columns, then checks solution and app exposure — preflight before any write.

```text
Package and deploy this PCF control from the repo.
```
> Routes to `pcf-and-web-resources`, syncs the manifest + wrapper versions, builds, and deploys via the targeted path — not a whole-solution import.

```text
Harden this cloud flow and resolve its HTTP trigger URL.
```
> Routes to `power-automate-flows`, runs the hardening review, patches only the changed `workflow` properties, and resolves the signed callback URL — preflight before the update.

## Safety by default

The thing that makes this plugin different from "an agent with `pac` access" is its refusal to do the dangerous-but-easy thing:

- **Mandatory live-mutation preflight.** Before *any* deploy, publish, import, registration, push, or data write, the agent prints a gate naming the target environment, PAC profile (and any mismatch), target solution, exact components, delivery primitive, artifact provenance, blast radius, rollback plan, and timeout. If a required field is missing, it stops.
- **Stale-artifact blocking.** It will not import a ZIP from `bin`, `Release`, `Downloads`, or a temp folder unless that package was generated in-session or you explicitly selected it. Multiple candidate packages → it stops and asks.
- **Targeted delivery first.** It prefers the narrowest primitive — web-resource sync, plug-in push, form/ribbon patch, PCF wrapper deploy, keyed upsert — and **never silently escalates** a targeted change into a whole-solution import (a slow, high-blast-radius path that needs explicit approval).
- **Managed-promotion audit.** A successful import and a bumped solution version are **not completion proof** for high-risk metadata (command bars, forms, views, flows, roles, plug-in steps) — the agent confirms alignment from source/package evidence plus a **target live read-back** before calling a managed promotion done.

## How it's built

PowerPlatform-Core is packaged as a plugin of modular skills over a shared toolchain:

- **An orchestrator + 10 domain skills** under `skills/`, each with a focused, precisely triggering description.
- **A shared toolchain at the plugin root**, resolved via `$CLAUDE_PLUGIN_ROOT` / `$CODEX_PLUGIN_ROOT`:
  - **`scripts/`** — Python helper entry points that drive every live operation.
  - **`tools/`** — a .NET 8 `DataverseOps` execution tool (connection checks, row/metadata ops, flows, plug-ins, web resources, solutions) plus a Windows auth dialog.
  - **`references/`** — a knowledge base on surface selection, ALM, metadata, verification, and repo archetypes that the skills cite as needed.

For the full picture, see [`docs/core-overlay-architecture.md`](docs/core-overlay-architecture.md) and the maintainer-oriented [`docs/capability-matrix.md`](docs/capability-matrix.md).

## Standalone vs. overlay

PowerPlatform-Core is the public, **repo-agnostic base** and is designed to be used directly — install it and point it at any Power Platform or Dataverse repo, no configuration required. That is the right choice for most users and unfamiliar repos.

An **overlay** is a separate skill that layers one team's house-style conventions, references, and defaults on top of Core, bundling Core's runtime into a single merged skill. If your repo follows a specific team's conventions and an overlay exists, use that team's skill token; otherwise use Core. Building your own overlay is covered in [`docs/core-overlay-architecture.md`](docs/core-overlay-architecture.md).

## Develop & verify

Contributing or running a local checkout? One command verifies the whole repo:

```bash
python verify_repo.py
```

It runs Python syntax checks, the `unittest` suite, the skill-structure and manifest checks, the .NET build/tests for `DataverseOps`, and the skill-creator quick validator when available. Cross-platform: the Windows-only WPF auth dialog is skipped automatically on macOS/Linux.

Maintainer detail — capability boundaries, current limitations, and the helper backlog — lives in [`docs/development.md`](docs/development.md).

## License

Apache-2.0 — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

© 2026 Satrio Tsubasa.
