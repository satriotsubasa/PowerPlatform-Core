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
