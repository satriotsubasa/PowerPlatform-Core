---
name: data-operations
description: >
  Use whenever the user wants to read or write Dataverse business or configuration data — create,
  update, or upsert rows, seed or sync reference/config data, or design a query — rather than
  change table metadata. Trigger on phrases like "create a record/row", "update this record",
  "upsert by alternate key", "seed config data", "import/sync these rows", "set a field value on
  a row", or "design an OData / FetchXML query" and "build the List rows filter for a flow", even
  when the user never names a helper script. Prefer this skill for keyed create/update/upsert via
  SDK or Web API and for query design across OData, FetchXML, and Power Automate "List rows".
---

# Data Operations

This skill owns Dataverse row create/update/upsert and query design. It is the data branch of the `powerplatform-core` orchestrator — start there to discover repo context and confirm the target environment and solution. Keep data work separate from schema work: a solution import is not the way to sync environment-specific config data, and creating/changing tables or columns belongs in the `dataverse-schema` skill.

Default safety posture: create, update, and upsert are in scope when the user asks for them. Do not delete business data unless the user explicitly requests deletion and separately approves it.

## When to use this

- Create a single row, or create-or-update by primary key or alternate key.
- Update only the columns that changed on a known record.
- Seed or sync reference/configuration data into an environment.
- Design a query and get the OData path, FetchXML, and Power Automate "List rows" parameters for a structured spec.

For table/column/lookup/form/view/ribbon/icon changes, use the `dataverse-schema` skill instead.

## Helpers

The Python helpers live in the plugin's **`scripts/`** directory at the plugin root, not inside this skill folder. Resolve the plugin root and invoke a helper like this (use `$CODEX_PLUGIN_ROOT`, also exposed as `$PLUGIN_ROOT`, when running under Codex; if installed standalone, the `scripts/` folder sits beside this bundle):

- **Claude Code:** `python "$CLAUDE_PLUGIN_ROOT/scripts/upsert_data.py" --table contoso_account --data ./row.json --key ./key.json --auth-dialog --verify`
- **Codex:** `python "$CODEX_PLUGIN_ROOT/scripts/upsert_data.py" --table contoso_account --data ./row.json --key ./key.json --auth-dialog --verify`

- `design_dataverse_query.py` — offline query designer. Takes `--spec` (a JSON object or path describing `tableLogicalName`, `entitySetName`, `select`, `filters`, `orderBy`, `top`, `expand`) plus optional `--repo-root` / `--output`. Emits a Web API OData path, FetchXML, Power Automate "List rows" parameters, and warnings about missing filters, row limits, select lists, or entity-set names. No live call.
- `upsert_data.py` — live row write. Key flags: `--table` (logical name, required), `--data` (JSON object or path, required), `--mode {create,update,upsert}` (default `upsert`), `--id` (primary-key GUID for update/upsert), `--key` (JSON object or path with alternate-key values), `--verify` (retrieve the changed columns after the write), plus the shared auth flags (`--environment-url`/`--target-url`, `--username`, `--tenant-id`, `--auth-dialog`, `--auto-validate`, `--auth-flow {auto,devicecode,interactive}`, `--force-prompt`, `--verbose`) and `--repo-root` (resolves project-profile deployment defaults, including typed row-write coercion).

If the repo already has a proven seed-data or data-sync mechanism, or server-side SDK code, prefer that repo-owned path over reconstructing one. The Web API is the simpler direct/scriptable path when no SDK code exists.

## Workflow

1. **Confirm targeting before writing.** Resolve the target environment, the table logical name (and entity set name when querying), whether the operation is create-only, update-only, or create-or-update, the matching key (record ID, alternate key, or agreed lookup), the exact columns to set, and duplicate-handling expectations. If ambiguous, ask only for the missing high-risk parts.
2. **Choose the mode deliberately.** Use `create` to let Dataverse assign the key; `update` to send only changed columns by primary or alternate key; `upsert` for create-or-update when the row might already exist. For Web API update-only behavior, `If-Match: *` prevents a silent upsert.
3. **Key choice for rerunnable work.** For integration/migration/rerunnable writes, prefer alternate keys over user-editable business fields, and prefer immutable keys. When the source identifier comes from another system, do not rely on a bare reused ID unless it is globally unique in the tenant — prefer a source-system-qualified key (`source_system + source_id`).
4. **Resolve lookups and choices safely.** Bind lookups using supported references, not display-name guessing; use logical names and valid choice values; reuse early-bound classes, enums, or constants when the repo already has them; prefer reference tables or global choices over repeated free text for controlled value sets.
5. **Plan before bulk/config apply.** For config-data sync, imports, migrations, or bulk corrections, run a dry-run/diff/plan phase first that names rows to be created, updated, skipped, invalid, and any target-only rows present in Dataverse but missing from the source extract (that last category drives whether deactivation, deletion, or an explicit no-op policy is needed). Do not apply config data to TST/TEST until that plan exists.
6. **Apply and verify.** Validate the smallest possible payload, use `--verify` when confirming the write matters, and capture whether the action created or updated the row.
7. **Preserve provenance.** When syncing from another source, keep enough provenance to identify origin, retain source-system-qualified keys when multiple upstreams may reuse an external ID, and avoid casually overwriting provenance columns used for reconciliation or audit.

## Key safety and decision rules

- **Run the live-mutation preflight defined in the `powerplatform-core` orchestrator before any live row write.** Stop if any required field is missing.
- Prefer the auth dialog (`--auth-dialog`) so the user confirms the target URL and selects the working solution; warn when the requested target does not match the active PAC profile. Treat `DEV` as the working environment and `TEST` as validation. Do not touch production.
- **Capability boundary:** `upsert_data.py` performs live row writes and optional post-write verification — it does **not** have a generic dry-run/plan mode. When a dry-run is required, keep that phase in the workflow or repo-specific tooling layer; do not imply the shared helper already supports it.
- Do not delete business data unless the user explicitly asked for deletion and separately approved it. Prefer safe create, keyed update, or upsert over any delete path.
- Separate solution customization from configuration rows. A solution import is not the default way to sync environment-specific config data.
- If no write executed because a required key or environment value was missing, say so explicitly. When a write is performed, report the table targeted, whether it created/updated/upserted, the key or alternate key used, which columns changed, and what safety checks were applied.

## Query design notes

- Prefer the simplest query that matches the requirement: use logical names (not display names), select only needed columns, set row limits and pagination intentionally, and guard against nulls and empty arrays.
- Use OData (`$select`, then `$filter` only for necessary predicates, `$expand` sparingly) for straightforward server-side filtering. Dataverse Web API does not support every OData option; if the query needs complex joins, aggregates, or view definitions, prefer FetchXML.
- If the entity set name is unknown, provide it explicitly in the helper input rather than guessing a pluralized logical name.
- For Power Automate expressions, prefer clear guards (`coalesce`, `if`, `empty`) over nested fragile expressions. Validate `in` filters against the specific connector action, falling back to FetchXML if rejected.

## References

Read the shared references at the plugin's `references/` directory for depth:

- `references/data-operations.md` — create/update/upsert paths, keying and provenance, dry-run/apply planning, and validation/reporting.
- `references/queries-and-xml.md` — OData and FetchXML guidance, view `FetchXml`/`LayoutXml`, and direct solution XML rules.
