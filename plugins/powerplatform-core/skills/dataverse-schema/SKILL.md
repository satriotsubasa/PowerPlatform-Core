---
name: dataverse-schema
description: >
  Use for Dataverse table METADATA - tables, columns, lookups/relationships, choices/option
  sets, alternate keys, main forms, public/lookup views, the form-level ribbon (RibbonDiffXml),
  form event handlers and script libraries, and table icons - plus up-front schema and
  query-shape design before metadata exists. Trigger on "create a table", "add a column/field",
  "add a lookup", "add a choice", "set an alternate key", "update the main form", "add a view /
  change view columns", "add a button to the form ribbon", "set the table icon", or "design a
  Dataverse schema", even when no helper is named. Prefer this over hand-edited
  customizations.xml. Not for row/record DATA, seeding config rows, or query authoring - use
  data-operations.
---

# Dataverse Schema

This skill owns Dataverse schema work: turning a requirement into tables, columns, lookups, alternate keys, forms, views, the form-level ribbon, and table icons, and applying those changes through the shared SDK metadata helpers. It is the metadata branch of the `powerplatform-core` orchestrator — start there to discover repo context (`scripts/discover_context.py`), confirm the target solution and publisher prefix, and pick the lightest surface. Keep every change solution-scoped: add or update only the scoped components in the target unmanaged solution or selected patch; that does not mean defaulting to a whole-solution import.

Prefer supported, source-controlled metadata APIs and the helpers below over hand-edited `customizations.xml`. Edit raw form/ribbon/view XML only when the task explicitly requires it or when the unpacked solution already stores that artifact as XML.

## When to use this

- Create or modify tables, columns, lookups/relationships, choices, or alternate keys.
- Update a main form's layout, add fields/sections/subgrids, or register form libraries and event handlers.
- Change a public, lookup, or personal view's columns, sorting, or filter (FetchXml and/or LayoutXml).
- Patch a form-level command bar (RibbonDiffXml) on one named form.
- Set or change a custom table's icon from image web resources.
- Design a schema or query shape for review before creating anything live.

For row create/update/upsert and standalone query authoring (OData/FetchXML/"List rows"), use the `data-operations` skill instead. For entity-level command bars, new buttons/commands, or new display rules, that exceeds the form-ribbon helper — see the workflow note below.

## Helpers

The Python helpers live in the plugin's **`scripts/`** directory at the plugin root, not inside this skill folder. Resolve the plugin root and invoke a helper like this (use `$CODEX_PLUGIN_ROOT`, also exposed as `$PLUGIN_ROOT`, when running under Codex; if installed standalone, the `scripts/` folder sits beside this bundle):

- **Claude Code:** `python "$CLAUDE_PLUGIN_ROOT/scripts/create_table.py" --spec ./table.json --auth-dialog`
- **Codex:** `python "$CODEX_PLUGIN_ROOT/scripts/create_table.py" --spec ./table.json --auth-dialog`

Design helpers (offline planning — take `--spec` plus optional `--repo-root` / `--output`, no live write):

- `design_dataverse_schema.py` — turn a structured requirement into resolved logical/schema names, alternate-key candidates, relationship definitions, starter FetchXML/OData, and helper-ready specs for `create_table.py`, `create_field.py`, and `create_lookup.py`.

Live metadata helpers (each takes `--spec` — a JSON object or a path to a JSON file — plus shared auth flags: `--environment-url`/`--target-url`, `--username`, `--tenant-id`, `--auth-dialog`, `--auto-validate`, `--auth-flow {auto,devicecode,interactive}`, `--force-prompt`, `--verbose`):

- `create_table.py` — create a table (primary name, ownership, notes/activities/audit).
- `create_field.py` — create a column (string, memo, integer, decimal, money, boolean, datetime, choice, multiselect, etc.).
- `create_lookup.py` — create a lookup relationship between two tables.
- `update_main_form.py` — update a named main form's layout (tabs, sections, field placement, subgrids).
- `update_form_events.py` — register form script libraries and event handler bindings on a form.
- `patch_form_xml.py` — targeted `systemform.formxml` patch operations (replace header/body fragments, insert XML, set element attributes) on a named form; also accepts `--repo-root`.
- `patch_form_ribbon.py` — targeted form-level `RibbonDiffXml` patch operations on a named form; also accepts `--repo-root`.
- `update_view.py` — update a named view's `FetchXml` and/or `LayoutXml` (columns, widths, sort, filter).
- `set_table_icon.py` — set a custom table's icon metadata from existing image web resources.

## Workflow

1. **Discover and confirm context first.** Run the orchestrator's discovery, then confirm publisher prefix, target solution unique name, environment URL, and ownership model before creating anything. Prefer stable schema names; do not rename existing schema names casually — forms, views, flows, and code depend on them.
2. **Design before live creation.** For non-trivial schema, run `design_dataverse_schema.py` to produce reviewable names, alternate keys, relationships, and query examples. Treat it as a design layer, not a deployment shortcut. If the task is "create a field" with no detail, ask for the data type and whether it belongs on forms, views, or automation filters.
3. **Order of operations.** Create the table, then its columns, then lookups/relationships. Add or move fields on the form, then reflect them in the relevant views, quick find, and any client script or server-side validation. For an end-to-end lookup addition, update the relationship, the form placement, and impacted view columns together.
4. **Alternate keys.** If a column will be an integration/import key, design it to be immutable over the record lifetime; if the candidate value can change, define a key-rotation or mapping approach before treating it as the rerun key.
5. **Forms.** Keep form diffs minimal. Use `update_main_form.py` for layout, `update_form_events.py` for library/handler registration, and `patch_form_xml.py` for targeted XML fragment patches. Target the smallest XPath and fragment that satisfies the requirement.
6. **Views.** When the change is XML-based, adjust `FetchXml` (records and sort) and `LayoutXml` (visible columns) together when the request changes both data and presentation. Ensure any referenced image web resources or JavaScript functions are part of the same solution change.
7. **Ribbon (form-level only).** Use `patch_form_ribbon.py` for targeted form-level command changes. For subgrid command visibility/enablement, prefer static command definitions plus JavaScript `CustomRule` in a web resource; avoid XML `ValueRule` for selected-row field or status logic unless that exact rule shape is already proven on the target live grid.
8. **Icons.** Use `set_table_icon.py` with existing image web resources. Do not invent image files — if the user does not provide assets, ask for them; confirm whether both classic and unified interface entries need updates.
9. **Finish cohesively.** Treat "create a table/field/lookup" as incomplete until you also check whether the component is in the target solution, whether the app/sitemap needs it exposed, whether forms and views should include the new field, and whether automation or scripts depend on the new logical name. Do not treat app-module exposure as implied just because a component exists in solution metadata.

## Key safety and decision rules

- **Run the live-mutation preflight defined in the `powerplatform-core` orchestrator before any live metadata write** (create, update, patch, icon, or import). Stop if any required field is missing.
- Prefer the auth dialog (`--auth-dialog`) so the user confirms the target URL and selects the working solution before execution; warn when the requested target does not match the active PAC profile. Treat `DEV` as the working environment and `TEST` as validation. Do not touch production.
- Do not introduce Dataverse Business Rules. Use client script for form-scoped behavior and plug-ins or custom APIs for shared server-side behavior.
- Do not silently escalate from a targeted helper to a whole-solution import. If a ribbon or metadata change exceeds the targeted helper surface — entity-level command bars, new buttons, new commands, or new display rules — stop and explain that this needs the fresh export/overlay/import recovery path (fresh selected solution or patch export, overlay only `Entities/<entity>/RibbonDiff.xml` and related web resources, bump version, import, targeted publish, read-back) and ask before accepting the broader blast radius.
- Ask before delete, import, or publish. Do not rename established schema artifacts without a migration reason.
- Edit unpacked XML only when required; preserve encoding and formatting, keep diffs minimal, update related files together, and call out any publish step still required for the change to take effect. Verify logical names and XML well-formedness before finishing.
- Report what changed, what was inferred, what was executed, what was verified, and which publish/import steps were intentionally not performed.

## References

Read the shared references at the plugin's `references/` directory for depth:

- `references/dataverse-design.md` — requirement-to-schema design, alternate keys, and query-shape planning before metadata execution.
- `references/dataverse-metadata.md` — tables, columns, relationships, forms, views, icons, and app/sitemap exposure.
- `references/queries-and-xml.md` — FetchXml/LayoutXml, view XML, form/ribbon XML, and direct solution XML editing rules.
