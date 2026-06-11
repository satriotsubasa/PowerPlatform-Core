---
name: plugins-server-extensions
description: >
  Use for Dataverse server-side logic in C# - plug-ins and custom APIs. Covers headless first
  registration of a plug-in assembly or package, repeatable build-and-push, SDK
  message-processing step and image inspection, reconciling step enable/disable state to source
  intent, and creating a custom API with its request parameters and response properties. Fires
  whenever the user mentions a plug-in, plugin step, SDKMessage, pre/post image, plug-in
  assembly or package, "register my plug-in", "push the plug-in", "why is my step disabled",
  step-state drift, or a custom API / unbound action backed by a plug-in, even if no helper is
  named. Treats step enablement as explicit deployment state and registration as a separate
  approval gate. Not for Power Automate cloud flows - use power-automate-flows. Run the
  live-mutation preflight from the `powerplatform-core` orchestrator before any registration,
  push, or step-state write.
---

# Plug-Ins & Server Extensions

This skill handles Dataverse server-side logic — C# plug-ins and custom APIs — with a code-first, headless-first posture. It registers and pushes plug-in assemblies and plug-in packages, inspects SDK message-processing steps and images, reconciles step enable/disable state against source intent, and creates custom APIs with their parameters and properties. It treats step enablement as explicit deployment state and registration as an approval gate separate from build, even when code creation and build were already approved. It is intentionally generic about environment URL, publisher prefix, solution name, and project layout — read or request them per task and preserve any existing layered `*.Business`/`*.Data`/`*.Plugins` delivery model.

## When to use this

- The user wants to register, push, or update a plug-in (assembly or package) and its steps/images.
- A step needs inspecting, or its enabled/disabled state must be reconciled to match what the source intends.
- You are diagnosing step-state drift after a push, registration, or solution import.
- The user wants a custom API (bound or unbound) created, optionally backed by a plug-in.
- You need to confirm critical steps stayed enabled and intentionally disabled steps stayed disabled.

Route here from the `powerplatform-core` orchestrator. For flows, schema, PCF/web resources, or solution packaging, use the matching sibling skill instead.

## Helpers

The helpers live in the plugin's `scripts/` directory at the plugin root, not in this skill folder. Resolve the plugin root and invoke them like:

- `python "$CLAUDE_PLUGIN_ROOT/scripts/inspect_plugin_steps.py" --spec <spec.json>` (Claude Code)
- `python "$CODEX_PLUGIN_ROOT/scripts/inspect_plugin_steps.py" --spec <spec.json>` (also exposed as `$PLUGIN_ROOT`)
- Installed standalone / unsure: the `scripts/` folder sits beside this skill bundle — invoke by its path within the install.

| Helper | Purpose |
| --- | --- |
| `register_plugin_headless.py` | Assembly-based first registration of a Dataverse plug-in assembly plus its steps and images, via `pluginassembly`, `plugintype`, `sdkmessageprocessingstep`, and `sdkmessageprocessingstepimage`. |
| `register_plugin_package_headless.py` | Package-based first registration of a Dataverse plug-in package plus steps and images, via `pluginpackage` and the related server-managed `pluginassembly`/`plugintype` records. |
| `push_plugin.py` | Repeatable build-and-push when the target `pluginId` already exists; captures step state before, compares after, and fails on unexpected drift unless reconcile is requested. |
| `inspect_plugin_steps.py` | Inspect existing step state for an assembly or package — messages, stages, modes, filtering attributes, images, and enabled/disabled state. |
| `ensure_plugin_step_state.py` | Explicitly enable or disable existing steps so live state matches source intent (`desiredState`). |
| `create_custom_api.py` | Repeatable headless creation of a custom API plus its request parameters and response properties. |

## Domain workflow

1. **Build.** Restore and build the plug-in solution. Keep trigger/entry-point classes in `*.Plugins` thin, reusable business logic in the business layer, and early-bound types in the generated `*.Data` (generator-owned — do not hand-edit).
2. **Capture baseline state.** Before any push or re-registration of an existing plug-in, run `inspect_plugin_steps.py` so you have the pre-change step/image picture to compare against.
3. **Register or push (separate approval gate).**
   - First registration: `register_plugin_headless.py` (assembly) or `register_plugin_package_headless.py` (package). Official Microsoft guidance still centers first registration on the Plug-in Registration Tool (`pac tool prt`); headless is offered for automation when you confirm the targets.
   - Repeatable update when `pluginId` exists: `push_plugin.py`.
   - Ask before registration or push even if code and build were approved.
4. **Verify step state.** Re-run `inspect_plugin_steps.py` (or rely on `push_plugin.py`'s post-push check) and confirm critical steps stayed enabled and intentionally disabled steps stayed disabled. Treat unexpected drift as a failure.
5. **Reconcile if needed.** Use `ensure_plugin_step_state.py` with an explicit `desiredState` to bring steps back to source intent. Do not rely on push/registration to preserve enable/disable state implicitly.
6. **Custom APIs.** Define unique name, bound/unbound behavior, request parameters, response properties, backing plug-in, and visibility/security first, then create with `create_custom_api.py`. Prefer a plug-in-backed custom API when business logic or validation belongs on the server.

## Safety and decision rules

- **Registration is a separate approval gate.** Building and pushing are distinct steps; ask before registration or push, and never register steps blindly.
- **Step enablement is explicit deployment state.** Always verify it after registration, push, or solution import. Encode stable critical or intentionally disabled steps in the project profile rather than relying on memory.
- **Fail on drift by default.** `push_plugin.py` compares step state before and after and fails on unexpected drift unless the user explicitly asks for reconcile.
- **Runtime assumption.** Dataverse guidance currently requires SDK-style plug-in projects targeting `.NET Framework 4.6.2`; verify current Microsoft docs before changing it.
- **Packaging.** Prefer the supported plug-in package approach over `ILMerge` when dependent assemblies are needed, and preserve an existing layered/ILRepack delivery model unless the user asks to redesign it.
- **Generated code is generator-owned.** Do not hand-edit `*.Data` early-bound files; change generator settings or regenerate instead.
- **Preflight gate.** Run the mandatory live-mutation preflight from the `powerplatform-core` orchestrator before any registration, push, or step-state write. Do not restate the full preflight here — invoke it there.

## References

- `references/server-extensions.md` — plug-in baseline, registration automation position, custom APIs, early-bound code, and validation checklist.
