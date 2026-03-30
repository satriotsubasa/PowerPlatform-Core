# Queries And XML

Use this reference for Power Automate Dataverse queries, Web API OData, FetchXML, view XML, and direct solution XML edits.

## Primary Helper

- `scripts/design_dataverse_query.py`

## Power Automate And Dataverse Queries

Prefer the simplest query that matches the requirement.

- use logical names, not display names
- select only needed columns
- use row limits and pagination intentionally
- guard against nulls and empty arrays
- keep expressions readable

For Power Automate expressions, prefer clear guards such as `coalesce`, `if`, and `empty` instead of nested fragile expressions.

The query-design helper can turn a structured spec into:

- Web API OData path
- FetchXML
- Power Automate `List rows` parameters
- warnings about missing filters, row limits, or entity set names

## OData Guidance

Use OData filters for straightforward server-side filtering. Keep them narrow and readable.

For Dataverse Web API work:

- prefer `$select`
- add `$filter` only for necessary predicates
- use `$expand` sparingly

Dataverse Web API does not support every OData option. If the query becomes complex or needs joins that are awkward in OData, prefer FetchXML.
If the entity set name is unknown, prefer providing it explicitly in the helper input instead of guessing a pluralized logical name.

## FetchXML Guidance

Use FetchXML when you need:

- complex joins
- view definitions
- aggregate-style query structures supported by Dataverse
- query reuse in model-driven app views

Keep aliases, filters, and linked entities explicit. When changing an existing view, preserve the original intent and touch the smallest necessary part of the query.

## View XML

For named view updates, remember that:

- `FetchXml` controls which records and sort order are returned
- `LayoutXml` controls which columns render and how they appear

If the request changes both data and presentation, update both.

For icon-enhanced columns, view layout XML can reference image web resources and JavaScript functions. Make sure the linked resources are part of the same solution change.

## Solution XML And Customization XML

Edit unpacked XML only when the task explicitly needs it or when the repo already treats XML as the source of truth.

Common XML surfaces include:

- `Other/Solution.xml`
- `customizations.xml`
- form XML
- ribbon or command XML
- view `FetchXml` and `LayoutXml`

Rules for direct XML edits:

- preserve encoding and existing formatting
- keep diffs minimal
- avoid broad reorder-only changes
- update related files together when references change

Prefer a CLI or maker-designer action when it produces the same result with less risk.

## Validation

Before finishing:

- check logical names carefully
- check XML well-formedness
- ensure any referenced web resources or fields exist
- call out any publish step still required for the XML change to take effect
