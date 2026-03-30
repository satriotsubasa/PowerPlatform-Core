# Core Capability Matrix

This is a repo-only maintainer document for `PowerPlatform-Core`.

It is intentionally more comprehensive than the installed skill README. The installed runtime skill stays lean; this file exists so maintainers still have one place to review capability coverage, helper boundaries, and current limitations.

## Packaging Category Labels

- `Infrastructure`: foundational skill capability, not primarily a helper-packaging decision
- `Category 1`: straightforward dedicated helper
- `Category 2`: helper candidate that needs careful design
- `Category 3`: better kept partly workflow-driven

## Type Labels

The `Type` column is a rough capability family, not a strict architectural boundary. It is there to make the matrix easier to scan by area.

- `Auth`
- `Continuity`
- `Core`
- `Custom API`
- `Custom Connector`
- `Dataverse`
- `Discovery`
- `Document Generation`
- `Forms & Views`
- `JavaScript`
- `PCF`
- `Plug-in`
- `Power Automate`
- `Power Fx`
- `Repo`
- `Security`
- `Solution / ALM`
- `Verification`

## Implemented Directly In Core

| Type | Capability | Current status | Packaging category | Notes |
| --- | --- | --- | --- | --- |
| Auth | Forced-popup auth and solution selection dialog | Implemented | Infrastructure | `scripts/auth_context.py` and `tools/CodexPowerPlatform.AuthDialog` collect the target URL, force interactive sign-in, load selectable solutions, and require the user to choose the working solution before live context is released. |
| Auth | PAC-target mismatch warning | Implemented | Infrastructure | `scripts/powerplatform_common.py` now warns when the requested live environment URL does not match the active PAC profile target before live helpers continue. |
| Continuity | README plus handoff continuity mechanism | Implemented | Infrastructure | Core guidance preserves repo-root `README.md`, uses `CODEX_HANDOFF.md` as the running state file, and routes continuity behavior through `references/thread-continuity.md`. |
| Core | Execution-surface decision guidance | Implemented | Infrastructure | `references/execution-surface-guide.md` helps choose between metadata, client script, plug-ins, custom APIs, flows, HTML web resources, and PCF, and now makes the code-first no-business-rules policy explicit. |
| Core | Focused Power Platform reference set | Implemented | Infrastructure | References cover discovery, ALM, metadata, client customization, server extensions, PCF, flows, XML, continuity, execution-surface choice, and verification or recovery guidance. |
| Core | Headless-first execution policy | Implemented | Infrastructure | Core defaults to repo edits, SDK, Web API, solution files, PAC CLI, and direct deployment tools before any browser automation fallback. |
| Core | Multi-project runtime context handling | Implemented | Infrastructure | Core is designed to discover or ask per task instead of hardcoding one environment, one solution, or one publisher prefix. |
| Core | Requirement orchestration helper | Implemented | Category 2 | `scripts/apply_requirement_spec.py` resolves repo context, compares local and selected solution state, opens the auth dialog by default for live steps, and chains the existing helper scripts from one JSON requirement spec. |
| Core | Verification and recovery guidance | Implemented | Infrastructure | `references/verification-and-recovery.md` defines evidence expectations, reconciliation authority, and partial-failure handling for live-affecting work. |
| Custom API | Dataverse custom API create helper | Implemented for custom API contract creation | Category 1 | `scripts/create_custom_api.py` creates a custom API plus request parameters and response properties, and can optionally resolve a backing plug-in type before creating the records in the selected solution. |
| Custom Connector | Custom connector design helper | Implemented | Category 2 | `scripts/design_custom_connector.py` reviews OpenAPI or structured integration input, summarizes operations and auth, and recommends direct connector versus facade patterns. |
| Dataverse | Dataverse metadata create helpers | Implemented for table, field, and lookup creation | Category 1 | `scripts/create_table.py`, `scripts/create_field.py`, and `scripts/create_lookup.py` call shared SDK metadata commands for initial metadata creation flows. |
| Dataverse | Dataverse query design helper | Implemented | Category 2 | `scripts/design_dataverse_query.py` turns structured query requirements into OData, FetchXML, and Power Automate `List rows` parameters with warnings about weak filters or missing entity set names. |
| Dataverse | Dataverse reference hydration helper | Implemented | Category 1 | `scripts/ensure_dataverse_reference.py` clones the selected live solution into `Dataverse/<solution-unique-name>/` when the repo does not already contain local solution source. |
| Dataverse | Dataverse row create, update, and upsert helper | Implemented | Category 1 | `scripts/upsert_data.py` uses the shared SDK tool and supports primary-key or alternate-key writes with verify mode. |
| Dataverse | Dataverse schema design helper | Implemented | Category 2 | `scripts/design_dataverse_schema.py` turns structured requirements into suggested tables, fields, lookups, alternate keys, query examples, and helper-ready metadata specs before live execution starts. |
| Dataverse | Dataverse SDK `whoami` smoke-test helper | Implemented | Category 1 | `scripts/whoami.py` runs a read-only live connectivity check through the shared SDK tool. |
| Dataverse | Environment variable inspect and live value-set helpers | Implemented | Category 1 | `scripts/inspect_environment_variable.py` inspects or reads current values, and `scripts/set_environment_variable_value.py` creates or updates live `environmentvariablevalue` rows through the shared SDK tool. |
| Dataverse | Dataverse SDK and Web API execution paths | Implemented as skill behavior | Infrastructure | These remain core execution paths in the skill workflow and references beyond the explicit helper list. |
| Dataverse | Dataverse SDK execution tool | Implemented | Infrastructure | `tools/CodexPowerPlatform.DataverseOps` provides the shared SDK-based execution path for connection checks, row operations, metadata operations, flows, plug-ins, web resources, and solution work. |
| Dataverse | Dataverse table icon helper | Implemented | Category 1 | `scripts/set_table_icon.py` updates table icon metadata such as `IconVectorName`, `IconSmallName`, and `IconLargeName`. |
| Dataverse | Stable-key and dry-run-boundary guidance | Implemented | Infrastructure | `references/data-operations.md` and `references/dataverse-metadata.md` now explicitly cover immutable rerun keys, source-qualified provenance, and honest dry-run boundaries. |
| Discovery | Repo context discovery | Implemented | Infrastructure | `scripts/discover_context.py` scans repo structure, solution artifacts, plug-ins, PCF, pipelines, deployment settings, project profiles, and source areas such as `Word Templates`, `Dataverse`, `Reference`, and `Tools`. |
| Document Generation | Document-generation planning helper | Implemented | Category 2 | `scripts/plan_document_generation.py` maps required placeholders against real Word template content controls, flags missing required controls, and identifies the repo source areas that should be reviewed together. |
| Document Generation | Word Template inspection helper | Implemented | Category 1 | `scripts/inspect_word_templates.py` scans `.docx` or `.dotx` templates, extracts content controls, and summarizes duplicate tags, aliases, and control names for document-generation repos. |
| Forms & Views | Dataverse main form update helper | Implemented for broader layout mutation | Category 1 | `scripts/update_main_form.py` updates `systemform.formxml` for a targeted main form, can create missing tabs or sections, move existing fields, control prepend or append placement, and set section column counts. |
| Forms & Views | Dataverse targeted form XML patch helper | Implemented for lower-level form XML surgery | Category 1 | `scripts/patch_form_xml.py` applies targeted XML patch operations against `systemform.formxml` for a named main form, including replace, insert, remove, child replacement, and attribute patching. |
| Forms & Views | Dataverse targeted form ribbon patch helper | Implemented for form `RibbonDiffXml` mutation | Category 1 | `scripts/patch_form_ribbon.py` applies targeted XML patch operations against a form's `RibbonDiffXml`, creating the node when approved by spec and avoiding whole-solution import for narrow command-bar updates. |
| Forms & Views | Dataverse system view update helper | Implemented for broader view mutation | Category 1 | `scripts/update_view.py` updates `savedquery.fetchxml` and `savedquery.layoutxml` for a targeted view, including columns, linked entities, filters, sort, and jump-column changes. |
| JavaScript | Dataverse batch web resource sync helper | Implemented | Category 1 | `scripts/sync_webresources_batch.py` applies multiple web resource sync specs in one run and can publish all changed resources in one batch. |
| JavaScript | Dataverse form event binding helper | Implemented for library registration and `OnLoad` / `OnSave` / `OnChange` registration | Category 1 | `scripts/update_form_events.py` updates `systemform.formxml` to register form libraries plus named JavaScript handlers without opening the maker form designer. |
| JavaScript | Dataverse web resource sync helper | Implemented for file upsert and optional publish | Category 1 | `scripts/sync_webresource.py` uploads or updates a local JS, HTML, CSS, XML, or image file into Dataverse as a web resource and can optionally publish it. |
| PCF | Dataverse PCF binding helper | Implemented | Category 1 | `scripts/bind_pcf_control.py` updates `systemform.formxml` to attach a named PCF control to an existing field or control, and can infer control name and version from a local `ControlManifest.Input.xml`. |
| PCF | PCF deploy helper | Implemented | Category 1 | `scripts/deploy_pcf.py` supports both direct `pac pcf push` and wrapper-solution packaging or import. In `auto` mode it prefers the repo's `Solutions` wrapper project when one exists. |
| PCF | PCF package versioning helper | Implemented | Category 1 | `scripts/version_pcf_solution.py` updates both PCF version surfaces together: the manifest `version` attribute and the wrapper `Solutions\\src\\Other\\Solution.xml` version. |
| PCF | PCF scaffold helper | Implemented | Category 1 | `scripts/scaffold_pcf_control.py` creates a new PCF control in the inferred or explicit PCF area by wrapping `pac pcf init`. |
| Plug-in | Dataverse first-time plug-in registration helper | Implemented for assembly-based registration | Category 1 | `scripts/register_plugin_headless.py` builds a plug-in project, registers a new assembly in Dataverse, waits for its plug-in types to appear, and creates approved steps and images without opening PRT. |
| Plug-in | Dataverse package-based first plug-in registration helper | Implemented for package-based registration | Category 1 | `scripts/register_plugin_package_headless.py` packs a plug-in project into a NuGet package, registers a new `pluginpackage`, waits for Dataverse to surface the related plug-in types, and creates approved steps and images headlessly. |
| Plug-in | Plug-in build and push helper | Implemented for repeatable update flows | Category 1 | `scripts/push_plugin.py` builds a plug-in project, calls `pac plugin push` for an existing assembly or package ID, then can verify or reconcile post-push step enablement. |
| Plug-in | Plug-in step inspection helper | Implemented | Category 1 | `scripts/inspect_plugin_steps.py` lists existing `sdkmessageprocessingstep` records for an assembly or package and returns state, message, entity, mode, stage, and other execution metadata. |
| Plug-in | Plug-in step-state reconcile helper | Implemented | Category 1 | `scripts/ensure_plugin_step_state.py` explicitly enables or disables existing steps to match a desired-state selector contract. |
| Power Automate | Solution-aware cloud flow connector review helper | Implemented | Category 2 | `scripts/review_flow_connectors.py` inspects live or local flow definitions for Dataverse, SharePoint, and Outlook connector-specific read or write patterns and returns focused findings plus recommendations. |
| Power Automate | Solution-aware cloud flow create and update helpers | Implemented | Category 1 | `scripts/create_flow.py` and `scripts/update_flow.py` create or patch solution-aware cloud flows by writing Dataverse `workflow` records and keeping them in the selected working solution. `scripts/update_flow.py` now also performs semantic preflight and post-deploy verification when `clientData` changes. |
| Power Automate | Solution-aware cloud flow semantic guard contract | Implemented | Category 2 | Repo-owned flow guard files such as `.codex/power-platform.flow-guards.json` can require named switch cases and branch actions so critical flows fail fast instead of silently deploying empty branches. |
| Power Automate | Solution-aware cloud flow hardening review helper | Implemented | Category 2 | `scripts/review_flow_hardening.py` adds a reliability checklist for retry policy, concurrency, pagination, idempotency, error handling, and maintainability on top of the base lint pass. |
| Power Automate | Solution-aware cloud flow inspect and list helper | Implemented | Category 1 | `scripts/inspect_flow.py` inspects one live solution-aware flow or lists solution-scoped flows, returning identifiers, state, connection-reference summaries, and definition summaries from the Dataverse `workflow` record. |
| Power Automate | Solution-aware cloud flow lint helper | Implemented | Category 2 | `scripts/lint_flow.py` lints live or local flow definitions for missing connection references, missing triggers or actions, broken `runAfter`, and environment-specific hardcoding. |
| Power Automate | Solution-aware HTTP trigger callback URL helper | Implemented | Category 2 | `scripts/get_flow_trigger_url.py` inspects the Dataverse flow, maps it to the Power Automate admin flow identity, and resolves a signed callback URL through the Power Apps admin surface. |
| Power Fx | Power Fx debugging helper | Implemented | Category 2 | `scripts/debug_power_fx.py` inventories functions, flags delegation and reliability risks, and returns rewrite hints plus test-case suggestions for one or more formulas. |
| Repo | Generic project-profile starter template | Implemented | Infrastructure | `references/project-profile.template.json` provides the generic starter profile for repos that want to reduce discovery ambiguity. |
| Repo | Generic repo-shape support | Implemented | Infrastructure | Core supports layered code-centric repos, unpacked-solution repos, ambiguous mixed repos, tool-only repos, and sparse repos with little or no existing structure. |
| Repo | Layered repo archetype support | Implemented | Infrastructure | Core recognizes patterns such as `*.Business`, `*.Data`, `*.Plugins`, `WebResources`, `*.PCF`, `Word Templates`, `Dataverse`, and `Tools` without forcing them as the only valid shape. |
| Repo | Optional repo project profile support | Implemented | Infrastructure | Discovery supports `.codex/power-platform.project-profile.json` or `power-platform.project-profile.json` to pin the main solution, source areas, and stable repo conventions. |
| Security | Dataverse security role create and update helpers | Implemented | Category 1 | `scripts/create_security_role.py` and `scripts/update_security_role.py` create or update Dataverse security roles, apply declarative privilege-set changes, and keep role plus role-privilege components in the target solution when `solutionUniqueName` is supplied. |
| Security | Dataverse security role inspect helper | Implemented | Category 1 | `scripts/inspect_security_role.py` lists or inspects security roles with business-unit selectors and optional privilege expansion through the shared SDK tool. |
| Solution / ALM | Dataverse delivery validation helper | Implemented | Category 1 | `scripts/validate_delivery.py` runs safe repo, build, solution pack or checker, Word Template, and optional live read-only validation without importing solutions. |
| Solution / ALM | Dataverse solution component placement helper | Implemented | Category 1 | `scripts/add_solution_components.py` resolves supported component types such as tables, columns, relationships, security roles, role privileges, workflows, forms, views, web resources, custom controls, plug-in assemblies, and steps, then adds them to the selected solution through SDK requests. |
| Solution / ALM | Deployment closeout guidance | Implemented | Infrastructure | `references/execution-automation.md` now distinguishes repo-ready state from environment-updated state and tells Core to say which one was actually achieved. |
| Solution / ALM | Solution deployment helper | Implemented | Category 1 | `scripts/deploy_solution.py` packs, optionally runs checker, and imports solutions with PAC CLI. |
| Solution / ALM | Solution patch and merge planning helper | Implemented | Category 2 | `scripts/plan_solution_patch_merge.py` turns selected-solution context into a recommended patch, merge, or main-solution strategy with warnings and suggested version progression. |
| Solution / ALM | Solution standards review helper | Implemented | Category 2 | `scripts/review_solution_standards.py` reviews repo continuity, project-profile presence, supporting-solution ambiguity, generator-owned data boundaries, and PCF version alignment. |
| Solution / ALM | Solution versioning helper | Implemented | Category 1 | `scripts/solution_version.py` updates local `Solution.xml`, can sync the version online through `pac solution online-version`, and can reuse the selected solution from the auth dialog for online versioning. |
| Verification | Canonical repo verification entry point | Implemented | Infrastructure | `verify_repo.py` is the maintainer verification flow for Python syntax, unit tests, .NET builds, and `quick_validate.py` when available. |
| Verification | Helper regression suite | Implemented | Infrastructure | The test suite covers requirement expansion, discovery, executable resolution, query design, flow connector review, document-generation planning, patch planning, PCF versioning, and acceptance-scenario contracts. |
| Verification | Lightweight acceptance scenarios | Implemented | Infrastructure | `tests/acceptance_scenarios.json` and `tests/test_skill_acceptance_scenarios.py` validate representative repo-shape decisions across layered, unpacked-solution-first, ambiguous, tool-only, and sparse repos. |

## Mixed Coverage: Packaged Helpers Plus Workflow-Driven Areas

| Type | Capability area | Current status | Packaging category | Notes |
| --- | --- | --- | --- | --- |
| Custom Connector | Custom connectors and integration wrappers | Partially implemented as dedicated helpers | Category 2 + Category 3 | A dedicated design helper now covers OpenAPI review, auth shape, operation inventory, and direct-versus-facade recommendations. Publishing and Azure delivery still depend on project-specific implementation. |
| Dataverse | Dataverse business data create and update | Implemented and supported | Category 1 | Safe row creation, keyed update, and upsert are in scope through SDK or Web API, and now have an initial reusable helper. |
| Dataverse | Power Automate Dataverse queries and OData | Partially implemented as dedicated helpers | Category 2 + Category 3 | `scripts/design_dataverse_query.py` now covers structured OData, FetchXML, and `List rows` design. Broader expression rewriting and repo-specific query packaging still rely on workflow and references. |
| Dataverse | Tables, columns, and relationships | Partially implemented as dedicated helpers | Category 1 + Category 2 + Category 3 | Table creation, field creation, and lookup creation now have reusable helper scripts, and structured schema design now has its own helper. Broader metadata shaping still relies on workflow and references. |
| Document Generation | Word Templates and document-generation work | Partially implemented as dedicated helpers | Category 1 + Category 2 + Category 3 | Template inspection and document-generation planning now have reusable helpers. Template authoring, content-control redesign, and repo-specific generation logic still rely on workflow and references. |
| Forms & Views | Forms and views | Partially implemented as dedicated helpers | Category 1 + Category 3 | Main-form layout mutation, lower-level form XML patching, form ribbon patching, form library registration, and system-view column, link, filter, sort, and jump-column updates now have reusable helper scripts. Fully generic designer-shape changes still rely on workflow and references. |
| JavaScript | JS, TS, HTML, CSS web resources | Partially implemented as dedicated helpers | Category 1 + Category 3 | Single-file sync plus batch sync and publish now have reusable helpers. Broader packaging conventions and manifest-generation flows still rely on workflow and references. |
| PCF | PCF controls | Partially implemented as dedicated helpers | Category 1 + Category 2 | Scaffolding, direct push, wrapper-solution packaging or import, dual-surface PCF versioning, and form-control binding now have reusable helpers. Some advanced binding and packaging edge cases still rely on workflow and references. |
| Plug-in | Plug-ins | Partially implemented as dedicated helpers | Category 1 + Category 2 | Assembly-based and package-based first registration, step inspection, step-state reconcile, and existing assembly or package update flows now have reusable helpers. Broader packaging variants still rely on workflow and references. |
| Power Automate | Power Automate cloud flows | Partially implemented as dedicated helpers | Category 1 + Category 2 | Solution-aware flow inspect, lint, hardening review, connector review, create, update, and HTTP trigger callback URL retrieval now have reusable helpers. Broader connector-specific authoring patterns, connection-reference shaping, and non-solution flows still rely on workflow and references. |
| Power Fx | Power Fx formulas | Partially implemented as dedicated helpers | Category 2 + Category 3 | A dedicated debugger helper now covers delegation-risk, reliability, and maintainability review. Full app-specific formula remediation still needs workflow judgment. |
| Security | Security roles and privilege sets | Partially implemented as dedicated helpers | Category 1 + Category 3 | Role list, inspect, create, update, and solution-aware privilege sync now have reusable helpers. Minimum-privilege baseline selection, user or team assignment strategy, and environment-specific access reviews still rely on workflow judgment. |
| Solution / ALM | Solution review and standards enforcement | Partially implemented as dedicated helpers | Category 2 + Category 3 | Repo and solution standards review now has a reusable helper, while architecture-specific convention calls still rely on workflow judgment. |
| Solution / ALM | Solution XML and customization XML work | Partially implemented as dedicated helpers | Category 1 + Category 3 | Solution component placement and deployment or validation helpers now cover deterministic solution-backed operations. XML-specialized edge cases still rely on workflow and references. |

## Next Helper Backlog

1. live environment validation for the newest design and review helpers
2. direct patch, merge, and solution-upgrade execution helpers
3. richer Power Automate connector-specific authoring helpers
4. document-template authoring helpers for stable repo patterns
5. broader repo-profile adoption guidance across more repo archetypes

## Known Limitations Today

| Type | Area | Current limitation |
| --- | --- | --- |
| Auth | Cross-surface auth unification | Still incomplete. Dataverse SDK helpers, PAC CLI, and Power Apps admin flows still use separate auth stacks, so one extra Power Apps login can still happen for helper paths such as trigger-URL retrieval. |
| Core | Dedicated reusable action-script library | Partially implemented. The helper set now covers auth preflight, requirement orchestration, data writes, metadata creation, schema and query design, solution-aware flow inspect, lint, hardening review, connector review, create, update, and HTTP trigger URL retrieval, environment-variable inspect and value-set work, security role inspect, create, and update, solution standards review, Power Fx debugging, custom connector design, document-generation planning, patch and merge planning, broader main-form mutation, lower-level form XML surgery, form ribbon patching, form event binding, broader system-view mutation, table icon updates, single-file and batch web resource sync, Word Template inspection, custom API creation, assembly-based and package-based first plug-in registration, PCF scaffolding, binding, and deployment, solution component placement, delivery validation, solution versioning, deployment, and repeatable plug-in push. Highly bespoke designer-shape, template-authoring, direct role-assignment helpers, and direct patch-execution helpers beyond the current XML patch model are still not packaged yet. |
| Core | Exact context-pressure detection | Not available. The skill can only use heuristics, not a real percentage meter. |
| Plug-in | First-time plug-in registration | Implemented for the current two primary flows. Assembly-based and package-based first registration now have reusable helpers, and they can apply explicit or profile-derived desired step state during registration. These flows are still primarily repo- and build-validated in this repo rather than broadly live-write regression-tested. |
| Security | User and team role assignment | Not packaged yet. Core can now inspect, create, and update security roles themselves, but direct assignment of roles to users or teams is still workflow-driven. |
| Verification | Fully generic deployment and testing library | Still not complete. `scripts/validate_delivery.py` plus the repo-local regression suite cover safe validation much better, but environment-specific acceptance test helpers and broader live validation are still needed. |
