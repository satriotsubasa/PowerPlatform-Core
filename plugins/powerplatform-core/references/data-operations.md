# Data Operations

Use this reference for Dataverse business data row creation, update, upsert, and configuration data sync work.

Default safety rule:

- create, update, and upsert are in scope when the user asks
- separate solution customization from configuration rows; a solution import is not the default way to sync environment-specific config data
- do not delete business data unless the user explicitly asks for deletion and separately approves it
- require a dry-run, diff, or workflow-level plan before applying config data to TST/TEST

## Supported Paths

Prefer these paths:

1. Dataverse SDK for .NET when the repo already has server-side or integration code using the SDK
2. Dataverse Web API when a direct HTTP or scriptable path is simpler
3. existing repo tooling if the project already has a proven data-sync or seed-data mechanism

Reusable helper:

- use `scripts/upsert_data.py` when the current task is a row-level create, update, or upsert operation that fits the shared helper payload model

## Before Writing Data

Confirm or infer:

- target environment
- target table logical name and entity set name
- whether the operation is create-only, update-only, or create-or-update
- the matching key: record ID, alternate key, or another agreed lookup strategy
- exact column values to set
- duplicate handling expectations
- lookup behavior and ownership expectations where relevant

If the task is ambiguous, ask only for the missing high-risk parts.

When the task is integration-style, migration-style, or likely to be rerun, also confirm:

- whether the chosen key is truly stable and immutable
- whether the source system needs to be recorded alongside the source ID
- whether target-only rows should be left alone, deactivated, flagged, or removed by a separate approved path
- whether the run needs a plan or dry-run phase before live apply

## Create

For create operations:

- use SDK `Create` or Web API `POST`
- prefer letting Dataverse assign the primary key
- use lookup binding correctly
- keep payloads minimal and explicit

If the task requires linking related rows in one pass, use supported related-row creation patterns rather than multiple manual steps.

## Update

For update operations:

- use SDK `Update` or Web API `PATCH`
- send only the columns being changed
- when using the Web API for update-only behavior, use `If-Match: *` so the request does not silently become an upsert
- prefer primary key or alternate key targeting over broad searches

## Upsert

Use upsert when the user wants create-or-update behavior or when the target row might already exist.

- prefer alternate keys for repeatable integrations
- prefer immutable keys over user-editable business fields
- in the SDK, use `UpsertRequest`
- in the Web API, use `PATCH` against a keyed URL
- if you must prevent creation during a keyed update path, use `If-Match: *`

When the source identifier comes from another system, do not rely on a bare reused ID by itself unless it is globally unique in the tenant. Prefer a source-system-qualified key such as `source_system + source_id`.

## Lookup And Choice Handling

- resolve lookups using supported references, not display-name guessing
- use logical names and valid choice values
- if the repo already contains early-bound classes, enums, or constants, reuse them
- prefer reference tables or global choices over repeated free text when the same controlled value set will be reused across imports, automation, and reporting

## Dry-Run And Apply Planning

For config data sync, imports, migrations, bulk corrections, or other rerunnable write sets, prefer a plan phase before live apply.

A useful dry-run or plan should surface:

- rows that would be created
- rows that would be updated
- rows that would be skipped
- validation failures
- target-only rows that already exist in Dataverse but are missing from the current source extract

That last category matters because it drives whether a deactivation, deletion, or explicit no-op policy is needed.

Important current capability boundary:

- the shared helper `scripts/upsert_data.py` performs live row writes and optional post-write verification
- it does not currently expose a generic dry-run or plan mode
- when a dry-run is required, keep that phase in the workflow or repo-specific tooling layer instead of implying that the shared helper already supports it
- do not upsert config data to TST/TEST until the dry-run/diff names created, updated, skipped, and invalid rows

## Provenance

When importing or syncing data from another source:

- preserve enough provenance to identify where the record came from
- keep source-system-qualified keys when multiple upstream systems may reuse the same external ID
- report whether the operation created, updated, or upserted the target row
- avoid overwriting provenance columns casually if they are part of reconciliation or audit logic

## Validation

Before finishing:

- confirm the target table and keying strategy
- validate the smallest possible payload
- capture whether the action created or updated the row when that matters
- state whether the flow was plan-only or applied live
- report the environment, table, key, and columns that changed
- state clearly if no write was executed because a required key or environment value was missing

## Reporting

When data writes are performed, report:

- what table was targeted
- whether the action created, updated, or upserted data
- what key or alternate key was used
- which columns changed
- what safety checks were applied
