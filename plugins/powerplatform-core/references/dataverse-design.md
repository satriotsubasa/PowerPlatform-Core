# Dataverse Design

Use this reference when the task is about turning business requirements into Dataverse table, field, lookup, alternate-key, and query designs before live execution starts.

## Goal

- Turn structured business requirements into a reviewable Dataverse design.
- Keep the output close to the helper specs already used by this skill.
- Prefer explicit design review before creating metadata in a live environment.

## Preferred Helper

- `scripts/design_dataverse_schema.py`

Use it when you need:

- suggested table and column names
- suggested alternate keys
- suggested relationship definitions
- starter FetchXML and OData examples
- helper-ready specs for `create_table.py`, `create_field.py`, and `create_lookup.py`

## Expected Input Shape

Prefer a structured design spec:

```json
{
  "publisherPrefix": "contoso",
  "solutionUniqueName": "ContosoCore",
  "tables": [
    {
      "displayName": "Notification Definition",
      "pluralDisplayName": "Notification Definitions",
      "ownershipType": "UserOwned",
      "fields": [
        {
          "displayName": "Code",
          "type": "string",
          "required": true,
          "maxLength": 100,
          "alternateKey": true
        }
      ],
      "lookups": [
        {
          "targetTable": "contoso_notificationtemplate",
          "displayName": "Notification Template"
        }
      ],
      "accessPatterns": [
        {
          "name": "Active by code",
          "select": ["contoso_code", "contoso_name"],
          "filter": [
            { "field": "statecode", "operator": "eq", "value": 0 }
          ]
        }
      ]
    }
  ]
}
```

## Output Expectations

The design helper should return:

- resolved logical names and schema names
- helper-ready metadata specs
- alternate-key candidates
- query examples
- warnings when the spec is underspecified or ambiguous

## Operating Rules

- Prefer explicit publisher prefixes over guessing.
- Keep names stable and reviewable before live creation.
- Treat this as a design layer first, not a deployment shortcut.
- After design approval, move into `create_table.py`, `create_field.py`, `create_lookup.py`, and related form or view helpers.
