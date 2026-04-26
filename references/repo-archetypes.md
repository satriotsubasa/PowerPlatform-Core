# Repo Archetypes

Use this reference when the repository already has a recognizable project structure.

## Layered Dataverse Repo Pattern

A common enterprise layout is:

```text
<Solution>.Business/
<Solution>.Plugins/
<Solution>.Data/
WebResources/
<Solution>.PCF/
Word Templates/
Dataverse/
Tools/
Reference/
<Solution>.sln
README.md
```

Treat that layout as intentional, not accidental.

This archetype is valid even when the repo does not contain an unpacked Dataverse solution. In that case, treat the code repo as the source of truth for code assets and the selected live solution as the source of truth for metadata and deployment targets.

## Responsibilities By Area

- `*.Business`: shared domain and orchestration logic used by plug-ins or custom APIs.
- `*.Plugins`: Dataverse step entry points and custom API handlers. Keep these thin and delegate business logic to `*.Business` where the repo already does that.
- `*.Data`: early-bound entities, option sets, service context, and metadata-generation settings.
- `WebResources`: source-controlled JavaScript, HTML, JSON, and other browser assets to publish to Dataverse.
- `*.PCF`: PCF control source, build tooling, and often a packaged solution subfolder.
- `Word Templates`: source-controlled `.docx` templates or supporting document assets used by plug-ins, content-control mapping, or document-generation flows.
- `Dataverse`: local metadata reference or working solution source hydrated from the selected live solution when the repo does not already carry full app metadata.
- `Tools`: repo-specific automation such as query helpers, build helpers, or deployment wrappers.
- `Reference`: external references, guides, recommendations, or scratch material. Treat this as human reference, not as the default deployment source.
- `README.md` or architecture docs: project-specific behavior, module boundaries, naming rules, and operational steps. Read the relevant sections before making structural changes.
- When `*.PCF` contains a nested `Solutions` wrapper project, expect development builds under `Solutions\bin\Debug` and deployable artifacts under `Solutions\bin\Release`.

## How To Use This Pattern

When this structure exists:

- keep shared business logic in `*.Business`
- keep step registration targets in `*.Plugins`
- keep generated Dataverse types in `*.Data`
- treat `*.Data` as generator-owned when it is produced by early-bound tooling; prefer regeneration over hand edits
- treat a root `Data/` folder, when present alongside `*.Data`, as supplemental source data rather than as the primary early-bound code project
- keep form libraries in `WebResources/JScript`
- keep HTML dialogs or side panels in `WebResources/HTML`
- keep PCF source and packaging inside `*.PCF`
- keep both PCF version surfaces aligned when a wrapper solution exists: manifest version in `ControlManifest.Input.xml` and wrapper solution version in `Solutions\src\Other\Solution.xml`
- treat `Word Templates` as source when document-generation plug-ins or placeholder mapping depend on those templates
- treat `Dataverse` as metadata reference or working solution source, not as the owner of plug-in or web-resource code
- when the same logical web resource appears under both `WebResources/` and `Dataverse/<solution>/WebResources/`, treat `WebResources/` as authored source and the `Dataverse/` copy as packaged/export mirror or drift evidence unless a project profile explicitly says otherwise
- edit authored source first, then sync the mirror or live webresource through the approved helper
- check `Tools` before inventing new helper scripts
- keep `Reference` out of the main deployment path unless the user explicitly says that a file there is authoritative
- do not insist on `*.cdsproj` or `Other/Solution.xml` before treating the repo as valid
- use the repo `.sln` and project names as primary signals for namespace roots and structure

Do not collapse these layers into one project unless the user explicitly asks for a repo redesign.

## Example Automation Implications

For a repo matching this pattern, a full task may involve:

1. editing `*.Business`, `*.Plugins`, or `*.Data`
2. editing `WebResources`, `Word Templates`, or `*.PCF`
3. hydrating or updating `Dataverse/<solution-unique-name>/` only when metadata reference is needed
4. building the affected project
5. pushing or importing the changed artifact into Dataverse
6. using maker portal automation only for the remaining design-only steps

## Layered Repo with Code Apps

A layered repo can include a `CodeApp/` folder at the same level as the other project areas. This is the pattern for repos that deliver both a model-driven app and one or more Power Apps Code Apps from the same solution.

```text
<Solution>.Business/
<Solution>.Plugins/
<Solution>.Data/
WebResources/
<Solution>.PCF/
Word Templates/
Dataverse/
CodeApp/
  ├── <AppName1>/          ← full code app: power.config.json, package.json, src/
  ├── <AppName2>/
  └── <AppName3>/
<Solution>.sln
README.md
```

### Rules for the CodeApp/ area

- Treat each immediate subdirectory of `CodeApp/` as a separate deployable code app. Each must contain its own `power.config.json` (written by `npx power-apps init`) and `package.json`.
- Do not merge multiple apps into a single subfolder. One subfolder = one code app = one Power Apps app record.
- `CodeApp/` is not a Dataverse solution component — it is a hosting unit deployed separately via `npx power-apps push` or `pac code push`. Its ALM path is: push to dev environment → add to solution in maker portal → promote via pipelines.
- The code app is a full Single-Page Application (SPA). It connects to Dataverse through generated service files under `src/generated/services/`, not through plug-ins or web resources.
- Do not hand-edit generated files in `src/generated/`. Regenerate them with `pac code add-data-source` when the Dataverse table schema changes.
- Code apps require **Power Apps Premium** licenses for end-users. Confirm this before delivery planning.
- Code apps in this repo coexist with the model-driven app. They are independent apps sharing the same Dataverse environment — they are not embedded inside the model-driven app unless explicitly embedded via iframe.

### Detecting this pattern

`scripts/discover_context.py` detects:
- `CodeApp/` as a recognised repo area (shown in `repo_areas`)
- each `power.config.json` found inside as a separate entry in `code_apps`, including display name, environment ID, and app ID

When discovery returns multiple `code_apps` entries, list them and ask the user which app to target before running any push or build operation.

### Pushing all apps at once

```powershell
# Build and push all apps under CodeApp/ in sequence
python scripts/push_code_app.py --path .\CodeApp --all

# Dry run first to confirm which apps will be pushed
python scripts/push_code_app.py --path .\CodeApp --all --dry-run

# Target a specific solution (pac CLI)
python scripts/push_code_app.py --path .\CodeApp --all --cli pac --solution-name MySolution
```

### Pushing a single app

```powershell
python scripts/push_code_app.py --path .\CodeApp\CustomerPortal
```
