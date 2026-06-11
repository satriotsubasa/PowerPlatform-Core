# Server Extensions

Use this reference for Dataverse plug-ins, custom APIs, and early-bound generation.

## Plug-In Baseline

Prefer C# plug-ins for server-side business logic. Before writing code, identify:

- message
- primary table
- stage and mode
- filtering attributes
- pre or post images
- secure or unsecure configuration
- expected transaction and recursion behavior

Do not register steps blindly. Ask before registration or push.

## Current Runtime Assumption

Official Dataverse guidance currently requires plug-in projects to be SDK-style and target `.NET Framework 4.6.2`. Verify current Microsoft documentation before changing runtime assumptions or introducing newer framework requirements.

## Project And Tooling

Prefer these flows:

- scaffold a new project: `pac plugin init --outputDirectory <path>`
- launch Plug-in Registration Tool when needed: `pac tool prt`
- push an existing assembly or package when the target ID is known and the user approved it: `pac plugin push --pluginId <id>`
- generate early-bound classes after authenticating to Dataverse: `pac modelbuilder build`

Prefer official packaging guidance over `ILMerge`. If dependent assemblies are required, use the supported plug-in package approach.
If the repo already uses a layered `*.Business` + `*.Data` + `*.Plugins` structure or a comparable split with ILRepack or similar merging, preserve that existing delivery model unless the user explicitly asks to redesign it.

Reusable helper:

- use `scripts/register_plugin_headless.py` for assembly-based first registration of a Dataverse plug-in assembly plus steps and images
- use `scripts/register_plugin_package_headless.py` for package-based first registration of a Dataverse plug-in package plus steps and images
- use `scripts/inspect_plugin_steps.py` to inspect existing step state for an assembly or package
- use `scripts/ensure_plugin_step_state.py` to explicitly enable or disable existing steps to match source intent
- use `scripts/push_plugin.py` for repeatable build plus push flows when the target `pluginId` already exists, with post-push step-state verification and optional reconcile

## Registration Automation Position

- official Microsoft guidance still centers first registration flows around Plug-in Registration Tool
- `pac plugin push` is strong for repeatable import or update flows when the target package or assembly is already known
- fully headless registration is still technically possible through Dataverse tables such as `pluginassembly`, `plugintype`, `sdkmessageprocessingstep`, and `sdkmessageprocessingstepimage`
- this skill now packages an assembly-based headless first-registration helper around those Dataverse tables
- this skill now also packages a package-based headless first-registration helper around `pluginpackage` plus the related server-managed `pluginassembly` and `plugintype` records
- treat step enablement as explicit deployment state. Do not rely on push or registration flows to preserve enabled or disabled state implicitly.
- for repeatable update flows, capture step state before push, compare after push, and fail on unexpected drift unless the user explicitly asked for reconcile.
- if the repo has stable critical or intentionally disabled steps, encode them in the project profile rather than relying on memory.

## Plug-In Implementation Rules

- Keep each plug-in class focused on one message or behavior.
- Keep trigger or entry-point classes in `*.Plugins` thin when the repo already has a separate business or application layer.
- Put reusable business logic in that business or application layer.
- Keep early-bound entities and service context in `*.Data` or the repo's equivalent generated-model area.
- Treat generated files in `*.Data` or the repo's equivalent generated-model area as generator-owned. Do not hand-edit them unless the user explicitly asks for a manual fix.
- Use clear tracing with `ITracingService`.
- Throw actionable `InvalidPluginExecutionException` messages for business validation failures.
- Guard against recursion and unintended updates.
- Avoid broad updates when a targeted attribute update is sufficient.
- Respect execution context depth, images, and filtering attributes.
- When registering or updating steps, make `desiredState` explicit whenever the repo expects a step to remain disabled.

When a task asks to "build and register a plug-in", treat registration as a separate approval gate even if code creation and build are approved.

## Custom APIs

Use custom APIs for explicit developer-facing operations that should be callable from code or Power Automate.

Before implementing, define:

- unique name
- bound or unbound behavior
- request parameters
- response properties
- whether a plug-in backs the operation
- visibility and security expectations

Prefer a plug-in-backed custom API when business logic or validation belongs on the server.

Reusable helper:

- use `scripts/create_custom_api.py` for repeatable headless creation of a custom API plus its request parameters and response properties

## Early-Bound Code

Use early-bound generation when the repo already uses it or when the solution benefits from strong typing. Keep generated code clearly separated from hand-written plug-in logic.

If the repo is late-bound today, do not force an early-bound migration unless the user asks for it.

When a repo already has a namespaced `*.Data` or similar early-bound project:

- read it for types and metadata context
- keep custom logic out of it
- prefer changing `builderSettings.json`, `EarlyBoundGenerator*.xml`, or the repo's generation command instead of editing generated files by hand

## Validation

Before finishing:

- restore and build the plug-in solution
- confirm assembly, package, or step assumptions
- verify expected plug-in step enablement after registration, push, or solution import
- state what still needs registration, solution import, or publish
- call out any missing configuration values that prevent safe registration
