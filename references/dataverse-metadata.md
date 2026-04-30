# Dataverse Metadata

Use this reference for table, column, relationship, form, view, icon, app-module, and sitemap work.

## Table Design

Before creating or modifying a table, confirm:

- display name and plural name
- schema or logical name
- ownership model
- primary name column
- whether activities, notes, queues, or auditing are required
- which app or sitemap area should expose the table

Prefer stable schema names. Do not rename existing schema names casually because downstream scripts, forms, views, flows, and code often depend on them.

## Column Design

Before creating a column, confirm:

- display name
- schema or logical name
- data type and format
- required level
- max length, precision, or option set behavior where applicable
- searchable or auditing expectations
- whether field security is needed

If a column will be used as a stable integration or import key, design it to be immutable over the record lifetime. If the candidate value can change, define an explicit key-rotation or mapping approach before treating it as the rerun key.

If the task is "create a field" without more detail, ask for the data type and whether it belongs on forms, views, or automation filters.

## Lookup Fields And Relationships

For a lookup from table A to table B, confirm:

- relationship schema name
- referencing table and referenced table
- relationship behavior and cascade needs
- whether the lookup should appear on the main form
- whether default views or lookup filters should change

Update the relationship, the field placement on the form, and any impacted view columns together when the task implies an end-to-end lookup addition.

## Forms

For main form updates, identify:

- exact form name
- target tab and section
- field order
- required controls or subgrids
- any script libraries and handler bindings

Keep form diffs minimal. If a field is added for business use, consider whether it also belongs in quick find, default views, advanced find, client script, or server-side validation logic.

When the change is more complex than moving or adding fields:

- use `scripts/patch_form_xml.py` for targeted `systemform.formxml` patch operations such as replacing header or body fragments, inserting specific XML fragments, or setting element attributes on a named form
- use `scripts/patch_form_ribbon.py` for targeted `RibbonDiffXml` patch operations on a named form when the requirement is really command-bar or ribbon metadata and should not broaden into a whole-solution import
- for subgrid command visibility or enablement, prefer static command definitions plus JavaScript `CustomRule` in a web resource; avoid XML `ValueRule` for selected-row field or status logic unless proven on the target live grid
- keep the patch spec narrow and reviewable; target the smallest XPath and fragment that satisfies the requirement
- if the needed change still exceeds these helper surfaces, stop and explain the limitation instead of escalating silently to a broad solution import

## Views

For view updates, confirm:

- exact view name
- public view, lookup view, or personal view
- column list and widths
- default sorting
- filter criteria
- whether related-table columns are needed

When the change is XML-based, adjust both `FetchXml` and `LayoutXml` if the request changes both data selection and visible columns.

Prefer source-controlled or headless metadata changes when the repo or toolchain already supports them reliably. Use XML or SDK edits when the task explicitly calls for a named view XML change or when the unpacked solution already stores the view as XML.

## Icons

For custom table icon changes, use supported table icon customization with image web resources. Confirm:

- target custom table
- icon assets and sizes
- whether both classic and unified interface entries need updates

Do not invent image files. If the user does not provide assets, ask for them.

## Model-Driven Apps And Sitemap Exposure

Use metadata or app-configuration surfaces when the change is about:

- exposing a table, dashboard, view, page, or group inside a model-driven app
- changing navigation labels, areas, groups, or subareas
- deciding whether a table should appear in the app at all

Before changing app exposure, confirm:

- exact app or apps affected
- whether the request is about one app only or every app that includes the table
- whether the sitemap or app navigation should change
- whether default views, forms, or dashboards also need to be visible

Do not treat app-module exposure as implied just because a table or view exists in solution metadata already.

## End-To-End Metadata Tasks

For common requests such as "create a table", "create a field", "create a lookup", "update main form", or "update view", treat the task as incomplete until you also check:

- whether the component is in the target solution
- whether the app needs the component exposed
- whether sitemap or navigation changes are part of the request
- whether forms and views should include the new field
- whether automation or scripts depend on the new logical name

Prefer cohesive changes over isolated metadata edits that leave the app half-configured.
