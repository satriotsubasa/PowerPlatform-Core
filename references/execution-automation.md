# Execution Automation

Use this reference when the user wants Codex to execute the change end to end instead of only drafting code. Default to headless automation.

## Automation Ladder

Prefer this order:

1. edit source-controlled repo artifacts
2. use Dataverse SDK, Web API, or solution XML when deterministic
3. use `pac` CLI for build, sync, pack, push, and import flows
4. use direct deployment tools such as Plug-in Registration Tool only when the CLI path is insufficient
5. use browser automation only if the user explicitly approves a fallback after repo-backed, API-backed, CLI-backed, and direct deployment paths are exhausted

Do not jump to browser automation when a repo-backed, API-backed, or CLI-backed path exists. Browser automation is opt-in fallback only.

## Deployment Preflight Discipline

Before live deployment, classify the current step explicitly:

- target environment URL
- active PAC profile when PAC is involved
- target solution unique name and patch status
- mutation type
- exact components touched
- chosen deployment primitive
- artifact path, modified time, solution name/version, managed state, and component diff when a ZIP/package is involved
- blast radius: targeted, component subset, patch package, or full solution
- whether targeted delivery is supported
- whether the surface is configured as manual-only or high-risk
- timeout budget
- fallback and rollback path

Prefer `scripts/apply_requirement_spec.py` when the work spans multiple steps. Its `deploymentPreflight` output is the decision gate for whether Codex should proceed, stop, or escalate.
If the preflight marks a surface as manual-only, stop there instead of trying blind headless retries.
For a single live mutation gate, use `scripts/validate_delivery.py --preflight-spec ...` or emit the same fields manually before mutating Dataverse.

Do not import a package from `bin`, `Release`, `Downloads`, or old temp folders unless it was generated in the current session or explicitly selected by the user. Before package import, show the path, modified time, solution unique name, version, managed/unmanaged state, and component diff. If more than one package could be the candidate, stop and ask.

If the primitive becomes solution import, stop before import and tell the user that this is no longer a fast targeted deploy. State the expected 10-30 minute duration window, including import, publish, cache refresh, and read-back verification, then ask for explicit approval when a narrower path is unavailable.

## What "Fully Execute" Means

If the user asks for full execution, aim to:

- modify the repo
- build the affected projects
- generate or refresh derived artifacts when required
- deploy or push the change to the approved `DEV` environment
- publish or register components when approved
- capture what was done and what still requires human approval

When the task spans multiple coordinated steps, prefer `scripts/apply_requirement_spec.py` as the high-level entry point. It can resolve auth once, require working-solution selection, show preflight solution context, and then chain the narrower helpers in one requirement-driven run.
When a repo has no unpacked solution source yet, prefer creating a local reference clone under `Dataverse/<solution-unique-name>/` after auth and solution selection rather than inventing a `Reference/` structure.

Do not assume that all deployment work flows through `Dataverse/`.

- plug-ins deploy from `*.Business`, `*.Plugins`, and `*.Data`
- web resources deploy from `WebResources`
- PCF deploys from `*.PCF`, and when a wrapper `Solutions` project exists the importable artifact normally comes from `Solutions\bin\Debug` or `Solutions\bin\Release`
- document-template work deploys from `Word Templates` plus the related Dataverse data or plug-in logic
- `Dataverse/` is primarily for metadata reference, solution XML, forms, views, and component-level metadata work

If the repo uses different folder names, follow the source areas resolved by discovery or the project profile instead of forcing these example names.

## Deployment Scope And Escalation

Choose the narrowest reviewed deployment primitive that matches the actual change.

- Prefer component-scoped delivery such as `update_main_form.py`, `patch_form_xml.py`, `patch_form_ribbon.py`, `update_form_events.py`, `update_view.py`, `sync_webresource.py`, `sync_webresources_batch.py`, `bind_pcf_control.py`, direct metadata updates, or other helper-specific headless paths when the change only affects one form, one view, one web resource, one control binding, or another narrow component.
- Treat whole-solution import as a broad deployment primitive, not as a silent fallback when a targeted helper becomes inconvenient.
- If the current targeted helper cannot safely express the required change, stop and explain the gap. Do not automatically escalate to `deploy_solution.py` or another broad import path.
- Require explicit user approval before broadening a targeted-component or solution-subset change into a whole-solution import.
- In shared unmanaged environments, treat whole-solution import as high risk because it can overwrite unrelated live maker work. Block that escalation unless the user explicitly approves the broader blast radius.
- When broad import is explicitly approved, explain why the narrower helper path was insufficient and summarize the expected blast radius before running the import.
- Keep bounded waits explicit. If a plug-in push or solution import is still blocked after its timeout budget, stop and surface the blocker instead of continuing silent retries.

## Deployment And Pull Fast Paths

Use these defaults unless the repo profile or repo-owned wrapper says otherwise:

| Need | Prefer |
| --- | --- |
| one authored web resource | `sync_webresource.py` |
| multiple authored web resources | `sync_webresources_batch.py` |
| plug-in update | build, `push_plugin.py`, then step-state verification |
| PCF update | version/build, `deploy_pcf.py`, or wrapper `Solutions` package generated now |
| form XML update | `patch_form_xml.py`, `update_main_form.py`, or direct metadata update |
| existing command logic update | web-resource-only JavaScript `CustomRule` or action change when metadata already points at it |
| form-level ribbon metadata | `patch_form_ribbon.py` or direct metadata update |
| entity command bar/new button/new command/new display rule | fresh selected solution or patch export, overlay `Entities/<entity>/RibbonDiff.xml`, bump version before import, pack/import, targeted publish, read back |
| other RibbonDiffXml update | matching targeted metadata helper when it fits; otherwise package import only through the recovery path below |
| solution-aware flow update | `inspect_flow.py`, lint/review when needed, then `update_flow.py` |
| configuration rows | dry-run/diff first, then keyed SDK/Web API or `upsert_data.py` |
| hydrate missing metadata reference | `ensure_dataverse_reference.py` into `Dataverse/<solution>` |
| sync existing unpacked source from live | `pac solution sync` against the known folder |
| unpack a reviewed artifact | `pac solution unpack` after artifact freshness and identity are shown |
| broad solution import | fresh package, `validate_delivery.py`, explicit approval, then `deploy_solution.py` |

## Repo-Owned Deploy Entry Points

If the current repository already provides a safe, reviewed deploy wrapper or deploy script, prefer that repo-owned entry point over rebuilding the same sequence ad hoc.

Good candidates include:

- solution-pack or import wrappers
- repo-owned plug-in push or registration wrappers
- PCF package-and-import wrappers
- controlled publish wrappers that the repo already uses operationally

Before using one, confirm:

- it targets the approved environment or accepts the environment as input
- it fits the current asset type instead of bundling unrelated risky steps
- it is reviewable enough that you can explain what it will do

If the repo does not provide a safe deploy entry point, fall back to the generic helper stack and official tools in this skill.

## Reporting Expectations

When Codex is executing live work, report these explicitly instead of silently polling:

- current command or primitive
- expected duration class
- timeout budget
- current blocker
- next fallback

For long solution imports, distinguish between “still waiting on Dataverse-side import work” and “still trying local execution”.

## RibbonDiffXml Recovery Path

Use this only when a targeted helper or direct metadata update cannot safely express the command-bar change and the user has approved package import after preflight.

Do not use this path for existing command JavaScript-only changes; deploy the web resource instead. Do use this path by default for entity-level command bars, new buttons, new commands, new action bindings, and new display rules.

1. Export or obtain a fresh package from the approved live source or generate it in the current session.
2. Show package path, timestamp, solution identity, version, managed state, component list, and why a targeted route is unavailable.
3. Overlay only the target entity/form RibbonDiffXml and any directly related web resource changes.
4. Bump the solution or patch version before import when the operation is ribbon package recovery, because same-version imports can report success without applying the metadata.
5. Import the package through the approved wrapper or `deploy_solution.py`.
6. Publish only the affected entity and web resources with targeted publish where supported; avoid broad publish when not required.
7. Export or read back the target metadata and assert the expected command, rule, library, and action XML are present.
8. Complete a command-bar verification pass: hard refresh, select eligible and ineligible rows, and verify the expected visible/enabled matrix.

## Area-Specific Execution

### Plug-ins And Custom APIs

- update the repo's server-side source areas as needed
- treat `*.Data` or any comparable early-bound project as generator-owned when it contains generated entities; use it for types and build references, but do not hand-edit generated files there
- build the plug-in project
- prefer `scripts/register_plugin_headless.py` for first registration of assembly-based plug-ins when the repo uses classic DLL deployment and the user approved registration
- prefer `scripts/register_plugin_package_headless.py` for first registration of package-based plug-ins when the repo uses dependent assemblies or NuGet package delivery
- prefer `scripts/create_custom_api.py` for repeatable custom API creation when the task is creating a new API plus its request and response contract
- prefer `pac plugin push` or another repeatable deployment path when available for updates to an existing registered package or assembly
- note the current official Microsoft guidance still uses Plug-in Registration Tool for package upload and some first registration flows; keep that as a fallback, not the default
- fully headless first-time registration is possible through Dataverse component operations because `pluginassembly`, `plugintype`, `sdkmessageprocessingstep`, and `sdkmessageprocessingstepimage` support create and update operations

### Early-Bound Data

- if the repo already has generator settings such as `builderSettings.json`, `EarlyBoundGenerator.xml`, or similar, use the repo's existing generation path
- do not mix generation tools casually inside one repo
- keep generated files separate from hand-written code
- do not manually rewrite generated files inside namespaced `*.Data` or similar early-bound projects; change generator config or regenerate instead

### Business Data Rows

- Dataverse SDK and Dataverse Web API are both first-class execution paths for row-level data work
- use SDK `Create`, `Update`, or `UpsertRequest` when the repo already uses .NET integration or server-side code
- use Web API `POST` for create and `PATCH` for update or upsert when a direct HTTP path is simpler
- for update-only behavior with the Web API, use `If-Match: *` to prevent accidental record creation through upsert behavior
- prefer alternate keys for repeatable integration-style upserts
- do not delete business data by default; only perform delete paths when the user explicitly requested deletion and separately approved it

### Solution-Aware Cloud Flows

- treat solution-aware cloud flows as Dataverse `workflow` records with `category = 5`
- prefer `scripts/inspect_flow.py` before changing an existing flow so the current identifiers, state, connection references, and definition summary are visible
- prefer `scripts/lint_flow.py` before larger edits or deployment, especially when a flow may contain hardcoded GUIDs, environment URLs, or broken `runAfter` dependencies
- prefer `scripts/review_flow_hardening.py` when retry policy, concurrency, pagination, idempotency, or error-handling quality must be reviewed explicitly
- prefer `scripts/create_flow.py` or `scripts/update_flow.py` for deterministic create or patch work
- prefer `scripts/get_flow_trigger_url.py` when the task needs the signed callback URL for an HTTP-trigger flow
- prefer `scripts/inspect_environment_variable.py` or `scripts/set_environment_variable_value.py` for live environment-variable reads and writes instead of hand-editing values through the maker UI
- keep flow work in the selected unmanaged solution and keep connection references or environment variables explicit
- use solution deployment for cross-environment promotion rather than recreating the flow ad hoc in each environment
- treat non-solution flows as out of scope unless the user explicitly asks for that exception
- if the flow-delivery path crosses both Dataverse and Power Apps admin surfaces, expect at least one separate Power Apps auth session until those auth surfaces are unified; do not mislabel that as a flow-definition failure

### Web Resources

- treat `WebResources/JScript` and `WebResources/HTML` as the source of truth
- prefer `scripts/sync_webresource.py` for single-file push and `scripts/sync_webresources_batch.py` for multi-file sync or publish flows when those helpers fit the repo
- prefer solution-backed packaging, solution import, or direct `webresource` table updates through Dataverse APIs over copy-paste into maker portal
- the `webresource` table supports `POST` and `PATCH`, and the `content` column stores Base64 payloads; use that when a solution-import path is not available

### Document Templates

- treat `Word Templates` as source-controlled input when the repo already stores `.docx` templates there
- prefer `scripts/inspect_word_templates.py` before changing content controls so the current template structure is visible in a repeatable, reviewable way
- preserve the repo's existing linkage between templates, placeholder-configuration data, document-definition entities, and plug-in logic
- when a requirement changes content controls or document-generation behavior, inspect the related plug-in or business-layer code before changing the template blindly
- do not treat `Reference/` copies of templates or guides as deployable source unless the user explicitly says they are authoritative

### PCF

- edit the control source
- prefer `scripts/scaffold_pcf_control.py` when creating a new control from scratch
- run the repo's package manager install and build flow
- prefer `scripts/version_pcf_solution.py` when the task changes a PCF package version, because wrapper-based repos usually need both the manifest version and the wrapper `Solutions\src\Other\Solution.xml` version updated together
- prefer `scripts/deploy_pcf.py` in `auto` mode for dependency install, build, and deployment; it now prefers the repo's wrapper `Solutions` project when available and falls back to direct `pac pcf push` only when a wrapper project is absent or explicit push mode is requested
- use `Debug` wrapper builds for development validation and `Release` wrapper builds for deployable artifacts when the repo follows that pattern
- prefer `scripts/bind_pcf_control.py` when the task is attaching a deployed PCF control to an existing form control through headless `systemform.formxml` updates
- package or push through the repo's `Solutions` project or `pac pcf push`, depending on the repo convention
- if the control still must be added to the selected solution explicitly, prefer `scripts/add_solution_components.py` before considering any UI path

### Tables, Columns, Relationships, Forms, Views

- prefer metadata APIs, solution XML, or existing repo artifacts when the change is deterministic
- if the repo has no local solution source yet, hydrate `Dataverse/<solution-unique-name>/` first so the metadata work has a local reference point
- Dataverse metadata APIs can create and update tables, columns, and relationships without UI
- `systemform` supports `POST` and `PATCH`, with writable `formxml` and `formjson`
- `savedquery` supports `PATCH`, with `fetchxml` and `layoutxml`
- prefer `scripts/add_solution_components.py` when the task is deterministic solution scoping rather than freeform metadata design
- use these headless paths for form layout, library registration, handler wiring, and view definition before considering any UI path
- prefer `scripts/patch_form_xml.py` for targeted main-form XML surgery such as replacing header or body fragments, inserting known XML fragments, or setting attributes on named nodes
- prefer `scripts/patch_form_ribbon.py` for targeted form-level `RibbonDiffXml` updates on one form
- treat entity-level command bars, new buttons, new commands, new action bindings, and new display rules as package-recovery work unless the repo has a proven targeted helper for that surface
- if the required form or command-bar change still exceeds the supported helper surface, stop and surface that limitation instead of falling back to a whole-solution import automatically

## Delivery Validation

- prefer `scripts/validate_delivery.py` before import or publish steps when the user wants a safe build or readiness check
- this helper can validate plug-in builds, PCF builds, wrapper-solution artifacts, Word Templates, local solution pack or checker runs, and optional live read-only Dataverse connectivity
- use it to reduce environment risk before `deploy_solution.py`, `register_plugin_*`, `push_plugin.py`, or `deploy_pcf.py`
- when `deploy_solution.py` or `deploy_pcf.py` hits a Dataverse import or publish lock, prefer waiting and retrying within the helper's retry window instead of skipping the step immediately
- if the helper exhausts its timeout budget, stop and escalate instead of improvising a longer retry chain without user approval

## Deployment Closeout

After Dataverse-affecting work, report explicitly whether the approved target environment was updated yet.

Use clear closeout language such as:

- repo updated, environment not updated yet
- repo updated and target environment updated
- environment updated, but live behavior not yet verified

If the environment was not updated, make the next step explicit:

- deploy now through the approved path
- batch for later and stop at repo-ready state

Do not imply that deployment happened just because code was changed, packaged, or validated locally.

## Browser Automation

When the task requires maker portal UI work:

- use the `playwright` skill if available
- run headed when a visual check matters
- snapshot before acting on element refs
- keep the automation stepwise and reviewable
- re-snapshot after navigation or major UI changes

Browser automation is especially suitable for:

- creating tables or columns in the maker portal
- editing forms and views in designers
- attaching JS libraries and handler bindings
- importing or adding PCF controls to forms
- uploading web resources where no reliable CLI path exists

Do not use this section unless the user explicitly allows fallback or the headless route is proven impractical.

## Safety

- never run against production by default
- ask before delete, import, publish, register, push, or bulk designer changes
- if Dataverse reports that another `Import` or `PublishAll` is already running, wait and retry through the helper's configured lock window before declaring failure
- do not broaden a targeted-component change into a solution import without explicit approval, especially in shared unmanaged environments
- stop when the repo and environment disagree about the same component
- prefer idempotent or repeatable steps over one-off clicks whenever possible
