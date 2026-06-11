---
name: pcf-and-web-resources
description: >
  Use for Power Apps component framework (PCF) controls, model-driven web resources, client
  form scripts, and Power Fx formula review. Covers scaffolding a PCF control, binding it to a
  form control, building and deploying it through a wrapper solution or direct push, and keeping
  the manifest version in sync with the wrapper-solution version. Also covers single and batch
  JavaScript/HTML/CSS/XML/image web resource sync and publish, OnLoad/OnSave/OnChange form
  handler registration, and Xrm.WebApi client code. Trigger this whenever the user mentions PCF,
  pcfproj, ControlManifest, `pac pcf`, web resources, form scripts, ribbon JavaScript rules,
  Xrm/formContext, or wants a Power Fx / canvas formula debugged — even if no helper is named.
---

# PCF and Web Resources

This skill owns the client-side and field-rendering surfaces of a model-driven app: PCF code components, authored web resources (JavaScript, HTML, CSS, XML, images), client form scripts, and Power Fx formula review. Prefer the lightest surface that satisfies the requirement — a named form-script handler or a small web resource before a PCF control, and a PCF control before a heavy HTML web resource. Keep everything source-controlled and deploy through targeted helpers, not whole-solution import.

## When to use this

- Scaffold, implement, version, or deploy a PCF field or dataset control.
- Bind a deployed PCF control to a specific form control.
- Add or update an OnLoad / OnSave / OnChange form script or a ribbon `CustomRule` JavaScript function.
- Sync and publish one web resource, or a batch of changed web resources.
- Review or debug a Power Fx formula for delegation risk, missing `IfError`, or maintainability.

For tables, columns, form metadata, or RibbonDiffXml structure, use `dataverse-schema`. For plug-ins, custom APIs, or shared server logic, use `plugins-server-extensions`. For a full pro-code SPA, use `code-apps`.

## Helpers

Helpers live in the plugin's `scripts/` directory at the plugin root, not inside this skill folder. Resolve the plugin root and invoke them:

- Claude Code: `python "$CLAUDE_PLUGIN_ROOT/scripts/scaffold_pcf_control.py" --help`
- Codex: `python "$CODEX_PLUGIN_ROOT/scripts/scaffold_pcf_control.py" --help` (also exposed as `$PLUGIN_ROOT`)
- Standalone / unsure: the `scripts/` folder sits beside this skill bundle; invoke by its path within the install.

| Helper | Use it to |
| --- | --- |
| `scaffold_pcf_control.py` | Create a new control (`--template field` or `--template dataset`) in the inferred or explicit PCF area, keeping the namespace aligned with the publisher prefix. |
| `version_pcf_solution.py` | Bump both version surfaces together — the 3-part `version` in `ControlManifest.Input.xml` and the 4-part version in the wrapper `Solutions\src\Other\Solution.xml`. |
| `deploy_pcf.py` | In `auto` mode: install dependencies, build, and either package-import the wrapper solution or fall back to direct `pac pcf push`. |
| `bind_pcf_control.py` | Attach a deployed control to an existing form control through a headless `systemform.formxml` update when the binding is deterministic. |
| `sync_webresource.py` | Headlessly upload/update and publish a single JS/HTML/CSS/XML/image web resource. |
| `sync_webresources_batch.py` | Sync/publish several changed web resources in one pass — stop if the batch sweeps in unrelated files. |
| `debug_power_fx.py` | Heuristic Power Fx review: function inventory, delegation-risk checks, missing-`IfError` on writes, maintainability warnings, rewrite hints, and test cases. |

## Workflow

1. **Pick the surface.** Form-scoped behavior → named form-script handler. Reusable input/visualization or dataset rendering → PCF. Focused static UI → small HTML/CSS web resource. Never introduce a Business Rule; never add unsupported DOM coupling to the page.
2. **PCF — scaffold and implement.** Use `scaffold_pcf_control.py`; design for empty, loading, error, and disabled states; preserve accessibility and keyboard behavior; do not introduce a second frontend toolchain if the repo already standardizes one.
3. **PCF — version before deploy.** Run `version_pcf_solution.py` so the manifest and wrapper-solution versions move together. Mismatched versions are the most common cause of a control that imports but does not update.
4. **PCF — build, then deploy.** `deploy_pcf.py` in `auto` mode after a local build. If the repo has a wrapper `Solutions` project, treat it as the deployable package path: `Debug` artifacts come from `Solutions\bin\Debug`, `Release` (often managed + unmanaged) from `Solutions\bin\Release` — prefer the managed artifact unless the user asks for unmanaged.
5. **PCF — bind.** When the form control target is known, run `bind_pcf_control.py`; otherwise report the remaining maker step.
6. **Web resources.** Edit the authored source, then `sync_webresource.py` (one file) or `sync_webresources_batch.py` (several). For ribbon visibility/enablement, prefer a JavaScript `CustomRule` in a web resource over an XML `ValueRule`, and deploy the web resource only when the command already exists.
7. **Form scripts.** Use `executionContext.getFormContext()` for new code; register only named exported functions with the expected signature; prefer `Xrm.WebApi` (`retrieveRecord`, `retrieveMultipleRecords`, `createRecord`, `updateRecord`, `execute`) selecting only the logical-name fields you need.
8. **Power Fx.** Use `debug_power_fx.py` as a reviewer, not a compiler. Never claim a formula is delegation-safe unless the underlying connector and data source are known.

## Safety and decision rules

- Before any live mutation — web resource publish, PCF push/import, form metadata update — run the **mandatory live-mutation preflight from the `powerplatform-core` orchestrator** and stop if any required field is missing.
- Keep manifest and wrapper-solution versions in sync on every PCF deploy. Do not ship one without the other unless the repo clearly uses a different convention.
- Do not import a PCF wrapper ZIP from `bin`, `Release`, `Downloads`, or an old temp folder unless it was built in the current session or explicitly selected. If multiple package candidates exist, stop and ask.
- Never silently escalate a targeted web-resource or form change into a whole-solution import. If the change exceeds the targeted helper surface (entity-level command bar, new button/command, new display rule), say so and ask before broadening the blast radius.
- After a command-bar or ribbon-JS change, verify behavior on the real grid (hard refresh, clear command-bar cache, test the show/hide matrix) and read back the metadata — do not trust import output alone.
- Do not hard-code environment URLs or tenant-specific values into web resources or controls.
- Report what was built, versioned, deployed, and verified, and which publish/import/bind steps still need environment access.

## References

- `references/pcf-controls.md` — PCF design, scaffolding, wrapper-solution packaging, dual-surface versioning, and validation.
- `references/client-customization.md` — form scripts, client APIs, ribbon JavaScript rules, and HTML/CSS/JS/TS web resources.
- `references/power-fx.md` — formula debugging, delegation review, and rewrite guidance.
