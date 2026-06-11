# Context And ALM

Use this reference first for environment-aware work, multi-project discovery, and `pac`-driven execution.

## Discovery Script

Start with:

`python scripts/discover_context.py --path .`

Add:

`--include-pac-auth`

only when the task depends on live Dataverse access and PAC CLI is available.

The script scans for:

- `.sln`
- `*.cdsproj`
- unpacked solution folders with `Other/Solution.xml`
- `customizations.xml`
- early-bound generator artifacts such as `builderSettings.json` and `EarlyBoundGenerator*.xml`
- plug-in `.csproj` files
- `ControlManifest.Input.xml`
- pipeline YAML files containing `pac` commands
- deployment settings JSON
- optional `pac auth list` profiles
- optional project profiles at `.codex/power-platform.project-profile.json` or `power-platform.project-profile.json`

Use the JSON output to identify:

- solution files and project lists
- layered repo areas such as `Business`, `Plugins`, `Data`, `WebResources`, `PCF`, and `Tools`
- source-area distinctions such as namespaced `*.Data` versus supplemental root `Data`, `Word Templates`, `Dataverse`, and `Reference`
- code-centric Dataverse repo archetypes such as `.sln + Business/Data/Plugins/WebResources`
- supporting local solution sources such as PCF packaging solutions versus main app metadata sources
- candidate solution unique names
- candidate publisher prefixes
- likely solution, plug-in, and PCF paths
- code namespace roots, web resource style, and plug-in packaging style
- candidate environment URLs
- the exact questions still missing

## Start With The Source Of Truth

Prefer the repository over live environment browsing. Look for:

- `*.cdsproj`
- unpacked solution folders containing `Other/Solution.xml`
- `.sln` files that organize `Business`, `Data`, `Plugins`, `WebResources`, and optional `PCF`
- plug-in `.sln` or `.csproj` files
- PCF `ControlManifest.Input.xml`
- web resource folders
- pipeline files that pack, import, publish, or register components

If the repo already contains an unpacked solution, keep edits within that structure and avoid re-cloning unless the user asks to resync from Dataverse.
If the repo is code-centric and does not contain unpacked solution source, keep the existing `.sln` structure and use the selected live Dataverse solution as the metadata and deployment target instead of treating the repo as incomplete.
When the repo has no local solution source and the task needs metadata context, clone the selected live solution into `Dataverse/<solution-unique-name>/` instead of creating a `Reference/` folder.
If the repo has a project profile, use it to interpret which local solution artifacts are supporting packages and which live solution is the main app target.

## Multi-Project Discovery

Assume the user may switch between projects often. The skill must adapt to the current repo instead of expecting one fixed setup.

Discover the current project in this order:

1. infer solution and folder structure from the repository
2. run `scripts/discover_context.py` when the repo is not immediately obvious
3. infer publisher prefix and naming patterns from schema names, manifests, solution files, or existing code
4. infer environment usage from pipeline files, deployment settings, or `pac auth` context only when needed
5. ask for the remaining missing values only for the current task

Do not store one project's environment URL, publisher prefix, or solution name as a global default for future work.

## Gather The Minimum Required Context

Before environment-bound work, confirm only the fields that matter:

- `DEV URL`
- `TEST URL` if deployment or comparison is involved
- `solution unique name`
- `publisher prefix`
- `managed or unmanaged strategy`
- target path inside the repo if there are multiple solution areas

Use [project-context-template.md](project-context-template.md) as the checklist.

If multiple candidate solutions or prefixes exist in the repo, present the ambiguity clearly and ask the user which one is the target.

## Default Repo Layout

If the repository has no existing convention, prefer:

```text
src/
  solution/
  plugins/
  pcf/
  webresources/
  automation/
tests/
artifacts/
```

Keep one solution project as the root of truth, then add plug-in and PCF project references to it when needed.

## PAC Workflow

Use `pac` as the default backbone for solution-based work.

- Authenticate: `pac auth create --environment <dev-url>`
- Select profile when multiple environments exist: `pac auth select`
- Initialize a new solution project when starting from nothing: `pac solution init --publisher-name <name> --publisher-prefix <prefix>`
- Clone an existing solution: `pac solution clone --name <solution-unique-name> --outputDirectory <path>`
- Sync an existing unpacked solution project: `pac solution sync --solution-folder <path>`
- Pack or unpack explicit solution zips when needed: `pac solution pack` and `pac solution unpack`
- Run solution analysis when useful: `pac solution check`
- Create deployment settings for connection references and environment variables: `pac solution create-settings`
- Publish only with user approval: `pac solution publish`
- Import only with user approval: `pac solution import`

Prefer `clone` or `sync` over inventing local structure by hand when the user wants repo-backed ALM.

When a task is repo-only and no environment action is required, avoid forcing an environment URL question.

When the reusable auth dialog is used for live Dataverse work, treat it as an environment gate plus solution gate:

- first confirm the target environment
- then require the user to select the working solution in that environment
- do not start live Dataverse mutations before that solution is explicit
- if the selected solution is a patch, do not assume merge or parent-solution targeting unless the user explicitly asks for it

When live work still depends on PAC context:

- compare the requested live target against the active `pac auth` profile
- warn immediately if they differ
- do not silently assume the currently selected PAC environment is the intended one just because it is active

## Solution Discipline

- Surface the selected solution name and current version before applying changes when the auth dialog is part of the flow.
- Keep new tables, columns, views, forms, web resources, PCF controls, plug-ins, and custom APIs inside the named unmanaged solution.
- When adding a plug-in or PCF project to a solution project, use `pac solution add-reference` if the repo follows that pattern.
- Avoid editing the default solution unless the user explicitly asks for it.
- Keep managed output as a release artifact, not as the source-controlled working format.

## Dataverse MCP

Use Dataverse MCP only when it is already configured for the environment and the user allows it.

Use MCP for:

- inspecting tables, columns, and relationships
- understanding live data shape
- validating assumptions before writing code

Do not use MCP as a shortcut for destructive changes that should remain reviewable in source control.

## Safety Rules

- Never use production by default.
- Ask before delete, import, publish, register, push, or upgrade.
- If the repo and live environment disagree, stop and clarify which one is authoritative.
- Prefer small unpacked diffs over large zip-only changes.
