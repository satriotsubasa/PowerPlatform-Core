# CODEX Handoff

Last updated: 2026-06-12

## Purpose

This file is the current continuity note for `PowerPlatform-Core`.

If work resumes in a new Codex thread:

1. read this file
2. read `README.md`
3. run `python .\verify_repo.py` if files changed

## Repo Role

This repo is the generic source of truth for the public Power Platform Codex skill runtime.

It owns:

- generic skill behavior
- generic references
- generic helper scripts
- generic tools
- generic regression tests
- generic packaging and install behavior

It does not own:

- overlay-specific conventions
- overlay-specific prompts or examples
- house-style reference files

Overlay repos can layer on top of this runtime to add house-style conventions.

## Current State

Clean state after production-ready rename and scrub:

- Skill ID: `powerplatform-core`
- GitHub: `satriotsubasa/PowerPlatform-Core`
- All company-specific references removed from test fixtures, templates, and documentation
- Core overlay discovery supports any extension via `"extends": "powerplatform-core"` in overlay `skill-package.json`

## Plugin & Multi-Agent Restructure (merged to `main`)

Merged to `main` via PR #2 on 2026-06-12. The skill is now a multi-agent plugin.

- Packaged as a plugin installable on both Claude Code (`.claude-plugin/`) and OpenAI Codex (`.codex-plugin/` + `.agents/plugins/marketplace.json`) from one shared source; both manifests point at `skills/`.
- The monolithic guidance is decomposed into 11 modular skills under `skills/` (orchestrator `powerplatform-core` + 10 domain skills). The shared toolchain (`scripts/`, `tools/`, `references/`) stays at the plugin root, resolved via `$CLAUDE_PLUGIN_ROOT` / `$CODEX_PLUGIN_ROOT`. There is no root `SKILL.md`: the capability lives entirely under `skills/<name>/`, matching the canonical multi-skill plugin layout (e.g. Superpowers) so Claude Code enumerates all the skills on the `/plugin` install page. For Claude, the `.claude-plugin/plugin.json` must NOT carry a `skills` field (it double-registers and collides); the `.codex-plugin/plugin.json` keeps `"skills": "./skills/"` (Codex expects it).
- Cross-platform: `CodexPowerPlatform.DataverseOps` multi-targets `net8.0` + `net8.0-windows`; the WAM broker is Windows-only (runtime-guarded), macOS/Linux use device-code sign-in. The WPF `AuthDialog` stays Windows-only.
- Phase 1 robustness pass landed: security-role paging fix, requirement-spec step-type fix, FetchXML escaping, Windows exec resolution in `push_code_app`, timeouts/leak-safety, FormXml DTD hardening, plus regression tests. `verify_repo.py` now also validates skill structure and skips Windows-only .NET builds off-Windows.
- Note: the role `issytemgenerated` filter is the real (misspelled) Dataverse logical name — verified against MS docs; do not "fix" it.
- Done: merged to `main` (PR #2, merge commit `8d797f5`). The managed promotion audit gate (`validate_delivery.py --promotion-audit-spec`), which landed on `main` in parallel, is integrated into the `solution-alm-delivery` skill.
- Codex plugin layout fix (branch `fix/codex-plugin-layout`): Codex requires each plugin under `plugins/<name>/` with the marketplace `source.path` pointing there (verified against `openai/plugins`). The whole plugin was moved into `plugins/powerplatform-core/` as the single source for **both** Claude and Codex; the repo root keeps only the two marketplace catalogs (`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`) plus repo meta (`README.md`, `docs/`, `verify_repo.py`, this file). `verify_repo.py` resolves the plugin via `PLUGIN_ROOT = ROOT/plugins/powerplatform-core`. Install on Codex via the `/plugins` TUI (there is no `codex plugin add` command; `marketplace add` only registers the source). The classic `~/.codex/skills` copy-install is deprecated.
- Multi-platform manifests (branch `feature/multi-platform-and-descriptions`, PR #4): added Cursor (`.cursor-plugin/plugin.json` + root `.cursor-plugin/marketplace.json`) and Gemini (`gemini-extension.json` + `GEMINI.md`); Copilot reuses the existing `.claude-plugin/marketplace.json`. All checked **firsthand** against each platform's published docs/schema. Cursor: `source` accepts a subfolder path and `plugin.json` supports `skills`/`logo` (confirmed). Copilot: reads `.claude-plugin/marketplace.json` with a subfolder `source` (confirmed). Gemini: only auto-discovers a repo-root `skills/` folder, so from our subfolder layout it loads the **orchestrator as context** and the agent reads the rest as files. **OpenCode pulled back**: its docs contradict the planned approach on three points (no git-URL install, no documented `config` hook, no `config.skills.paths`), so the root `package.json` + `.opencode/` plugin were removed; the documented workaround is to copy `skills/` into a workspace-root `.opencode/skills/`.
- Skill-description tightening pass is done: all 11 frontmatter descriptions sharpened with cross-skill boundaries and the orchestrator reframed as a router; `test_skill_messaging` realigned accordingly.
- v1.3.0 (branch `feature/crud-read-delete`): completed Dataverse row CRUD on the SDK path. `DataverseOps` gained `row --mode retrieve|delete` plus a new `query` verb (FetchXML list with bounded paging and total-count via `returntotalrecordcount`, which Dataverse caps at 5000 — `totalRecordCountLimitExceeded` flags >5000; `--exact-total` uses `RetrieveTotalRecordCount`, an unfiltered snapshot up to ~24h stale). New Python helpers `read_data.py` (read-only, no preflight) and `delete_data.py` (delete, preflight-gated); `design_dataverse_query.py` stays offline. `data-operations` skill + reference updated; `FetchXmlPaging` unit-tested. Also added cloud flow **run-history read-back**: `flow --mode runs` + `inspect_flow_runs.py` query the Dataverse `flowrun` elastic table (status/start/end/duration/error) by the parent `workflow` lookup, with an enablement precheck (`Organization.FlowRunTimeToLiveInSeconds`) and the solution-only / best-effort / 28-day caveats surfaced (Microsoft documents `api.flow.microsoft.com` as unsupported, so we use the Dataverse path on the same token); `power-automate-flows` skill + reference updated.
- v1.3.0 also fixes headless plug-in **assembly** registration. The classic database-assembly path does NOT auto-create `plugintype` records (the Plug-in Registration Tool creates them via reflection), so `register-assembly` now creates them **explicitly** from the step type names via `EnsureAssemblyPluginTypes` (it was polling 60s in `WaitForAssemblyPluginTypes` for an auto-discovery that never happens, then dead-ending; re-runs hit "assembly already exists"). New `reuseExistingAssembly` spec flag / `--reuse-existing` reconciles an assembly left by a partial run (idempotent types + steps; skips existing steps by plugintype+message+stage) without re-uploading content. The package path is unchanged (Dataverse creates types server-side) and is now positioned as the more reliable default. `plugins-server-extensions` skill + reference updated; `PluginTypeRegistration.BuildPluginTypeEntity` unit-tested. No version change - this lands inside the still-untagged 1.3.0. The general Web API executor is deferred to a planned v1.4.0 — the plugin still makes NO direct Web API calls (SDK `ServiceClient` + `pac` CLI only).

## Architecture State

Important current decisions:

- Core is generic and should not assume one house structure.
- Core is explicitly code-first for executable logic and should not choose Dataverse Business Rules as an implementation surface.
- Layered `.sln + Business/Data/Plugins/WebResources` repos are supported as one archetype among several.
- Discovery handles layered, ambiguous, tool-only, and sparse repos.
- Surface selection routes through `references/execution-surface-guide.md`.
- Live-affecting work routes through `references/verification-and-recovery.md`.
- Core auto-discovers overlay extensions at runtime and suggests them when relevant.
- Project profiles can now carry generic `deploymentDefaults` for timeout budgets, manual-only surfaces, preferred deployment primitives, plug-in step-state defaults, and typed row-write coercion.
- `apply_requirement_spec.py` now emits a separate `deploymentPreflight` block and can stop early when a repo marks a surface as manual-only.
- Public README/SKILL wording now positions Core as a coding-agent skill for Microsoft Power Platform and Dataverse development.
- Live mutation safety now has an explicit required preflight gate through `validate_delivery.py --preflight-spec`.
- `deploy_solution.py` blocks stale existing solution ZIP imports from `bin`, `Release`, `Downloads`, or old temp-style paths unless the artifact was generated in-session or explicitly selected.

## Overlay Relationship

Core supports a composition model for house-style extensions:

- Core installs directly as `powerplatform-core`
- Overlay extensions install separately and layer on top of this runtime
- Any overlay declaring `"extends": "powerplatform-core"` in its `skill-package.json` is discovered at runtime

## Resume Checklist

When resuming:

1. read this file
2. read `README.md`
3. run `python .\verify_repo.py`
4. inspect `git status`
5. if continuing the same batch, review the local uncommitted changes before starting new edits
