---
name: code-apps
description: >
  Use for Power Apps Code Apps - the pro-code model where a standalone Vite-built React/Vue/TS
  single-page app uses the `@microsoft/power-apps` client library and is pushed into a Power
  Platform environment with no server to manage. Covers scaffolding from the official Vite
  template, initializing with `power.config.json`, adding Dataverse data sources that generate
  typed model/service files, local dev, building, and pushing via `npx power-apps push` (npm CLI)
  or legacy `pac code push`. Trigger whenever the user mentions a code app, `power.config.json`,
  `@microsoft/power-apps`, `pac code` / `power-apps` CLI, a `CodeApp/` folder, or wants to build,
  run, or push a custom SPA into Power Platform, even if no helper is named. Not for PCF controls
  embedded in model-driven forms (use pcf-and-web-resources) or Canvas/maker apps.
---

# Power Apps Code Apps

Power Apps Code Apps is the code-first SPA hosting model: a standard web app (React/Vue/TS, built with Vite) that imports the `@microsoft/power-apps` client library and is published into a Power Platform environment, where the platform handles Entra authentication, DLP, sharing, and Conditional Access. It is distinct from PCF (components inside model-driven forms) and Canvas apps (built in maker studio). Keep the app source-controlled, build before every push, and treat `power.config.json` as the bridge between the local project and the target environment.

## When to use this

- Scaffold a new code app from the Microsoft Vite template and initialize it against an environment.
- Add Dataverse (or connector) data sources and use the generated typed services for CRUD.
- Run the app locally, build it, and push it to a Power Platform environment.
- Work in a repo that uses the multi-app `CodeApp/` folder pattern (several code apps side by side).
- Plan ALM promotion (Dev → Test → Prod) via solutions, pipelines, and connection references.

For a control embedded inside a model-driven form, use `pcf-and-web-resources`. For Dataverse schema or data operations behind the app, use `dataverse-schema` and `data-operations`.

## Helpers

Helpers live in the plugin's `scripts/` directory at the plugin root, not inside this skill folder. Resolve the plugin root and invoke them:

- Claude Code: `python "$CLAUDE_PLUGIN_ROOT/scripts/push_code_app.py" --help`
- Codex: `python "$CODEX_PLUGIN_ROOT/scripts/push_code_app.py" --help` (also exposed as `$PLUGIN_ROOT`)
- Standalone / unsure: the `scripts/` folder sits beside this skill bundle; invoke by its path within the install.

| Helper | Use it to |
| --- | --- |
| `push_code_app.py` | Build (`npm run build`) and push a code app. Defaults to the npm CLI (`npx power-apps push`); pass `--cli pac` for legacy `pac code push` and `--solution-name <unique>` to target a specific solution. Use `--path <dir>` to point at one app, `--all` to push every app under a `CodeApp/` folder in sequence, `--dry-run` to preview, and `--skip-build` only when pushing already-compiled output. |

Discovery: the orchestrator's `discover_context.py` reports detected code-app roots (and their display names / environment IDs) in its `code_apps` key. A repo is a code app when `power.config.json` exists at the root or in a subdirectory.

## Workflow

1. **Scaffold.** `npx degit github:microsoft/PowerAppsCodeApps/templates/vite my-app`, then `npm install`. Do not introduce a second app toolchain if the template already provides one.
2. **Initialize.** `npx power-apps init` (or `--displayName`/`--environmentId` non-interactively) writes `power.config.json` and authenticates against the environment.
3. **Add data sources.** `pac code add-data-source -a dataverse -t <table>` generates typed `…Model.ts` and `…Service.ts` files under `/generated/services/`. Do not hand-edit generated files — regenerate instead. Use `select` to limit columns; exclude system-managed fields from create payloads; send only changed fields on update.
4. **Develop locally.** `npm run dev`, opening the Local Play URL in the same browser profile as the tenant. Note that Chrome/Edge block public-origin requests to localhost by default (since Dec 2025) — grant the prompt or configure `allow="local-network-access"`.
5. **Build, then push.** `npm run build` (`tsc -b && vite build`), then push with `push_code_app.py`. The push returns a Power Apps URL to run and share the app.
6. **Promote via ALM.** Add the app to a solution (maker portal → Add existing → App → Code app) and promote through Power Platform Pipelines. Use connection references instead of hardcoded connector credentials so the solution moves across environments cleanly.

## Safety and decision rules

- Before any push or other live mutation, run the **mandatory live-mutation preflight from the `powerplatform-core` orchestrator** and stop if any required field is missing. A push publishes into a live environment — treat it as a mutation, not a build step.
- **Build, then push.** Never push without a fresh `npm run build` unless the user explicitly asks to push existing compiled output (`--skip-build`), and say so when you do.
- **List multiple apps before pushing.** If discovery returns more than one entry in `code_apps` (the multi-app `CodeApp/` pattern), list them and confirm the target before running any build or push. Use `--all` only when the user wants every app pushed in sequence; otherwise scope with `--path`.
- Prefer the npm CLI (`npx power-apps push`) going forward; `pac code push` is legacy and being deprecated. Use `--cli pac` only when the repo or task requires it.
- Confirm the active environment matches `power.config.json` (`environmentId`) and the intended target before pushing; warn on any mismatch. Treat the dev environment as the working target and do not push to production without explicit approval.
- Respect the known limitations: no `pac solution pack/unpack` for code apps, no FetchXML / alternate keys / polymorphic lookups / Dataverse actions via generated services, no Power Platform Git integration, and no Power Apps mobile/Windows support. End users need a Power Apps Premium license, and an admin must enable the Code Apps feature on the environment.
- Code Apps is in preview; verify current CLI and runtime support against official Microsoft docs when the task depends on "latest" behavior.
- Report what was built, which app(s) were pushed, the returned app URL(s), and any ALM/admin steps still pending.

## References

- `references/code-apps.md` — architecture, Vite scaffold, npm vs pac CLI, Dataverse data-source integration and CRUD patterns, ALM, admin/security, known limitations, and the multi-app detection model.
