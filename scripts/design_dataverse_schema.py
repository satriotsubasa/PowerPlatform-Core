#!/usr/bin/env python3
"""Design Dataverse tables, relationships, and query examples from a structured requirement."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from powerplatform_common import discover_repo_context, infer_publisher_prefix, read_json_argument, repo_root, write_json_output

SUPPORTED_FIELD_TYPES = {
    "string",
    "memo",
    "integer",
    "decimal",
    "money",
    "boolean",
    "datetime",
    "choice",
    "multiselectchoice",
}
DEFAULT_STRING_LENGTH = 100
NATURAL_KEY_HINTS = ("code", "number", "identifier", "externalid", "external_id", "reference")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Design Dataverse schema and query examples from a structured requirement spec.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the schema requirement.")
    parser.add_argument("--repo-root", default=".", help="Repository root used for publisher-prefix inference.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    discovery = discover_repo_context(repo)
    prefix = resolve_publisher_prefix(repo, spec)
    solution_unique_name = spec.get("solutionUniqueName") or discovery.get("inferred", {}).get("solution_unique_name")

    raw_tables = spec.get("tables") or spec.get("entities")
    if not isinstance(raw_tables, list) or not raw_tables:
        raise RuntimeError("Schema design specs must include a non-empty 'tables' array.")

    tables = [build_table_design(item, prefix=prefix, solution_unique_name=solution_unique_name) for item in raw_tables]
    warnings = sorted({warning for table in tables for warning in table["warnings"]})

    payload = {
        "success": True,
        "mode": "design-dataverse-schema",
        "publisherPrefix": prefix,
        "solutionUniqueName": solution_unique_name,
        "tableCount": len(tables),
        "tables": tables,
        "warnings": warnings,
    }
    write_json_output(payload, args.output)
    return 0


def resolve_publisher_prefix(repo: Path, spec: dict[str, Any]) -> str:
    explicit = spec.get("publisherPrefix")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()
    try:
        return infer_publisher_prefix(repo)
    except Exception:
        inferred = discover_repo_context(repo).get("inferred", {}).get("publisher_prefix")
        if isinstance(inferred, str) and inferred.strip():
            return inferred.strip().lower()
    raise RuntimeError("Could not infer a publisher prefix. Provide 'publisherPrefix' in the design spec.")


def build_table_design(raw: Any, *, prefix: str, solution_unique_name: str | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("Each schema-design table item must be a JSON object.")

    display_name = require_text(raw, "displayName")
    plural_display_name = text_value(raw, "pluralDisplayName") or pluralize(display_name)
    table_stub = slug_name(raw.get("logicalName") or display_name)
    table_logical_name = normalize_with_prefix(prefix, table_stub)
    table_schema_name = raw.get("schemaName") or schema_name(prefix, display_name)
    ownership_type = text_value(raw, "ownershipType") or "UserOwned"

    primary_name_input = raw.get("primaryName")
    primary_name = build_primary_name(primary_name_input, prefix=prefix)

    fields = []
    relationships = []
    field_specs = []
    lookup_specs = []
    warnings: list[str] = []
    alternate_keys: list[dict[str, Any]] = []

    for item in require_list(raw, "fields"):
        field_design = build_field_design(item, prefix=prefix, table_logical_name=table_logical_name, solution_unique_name=solution_unique_name)
        fields.append(field_design["field"])
        field_specs.append(field_design["helperSpec"])
        warnings.extend(field_design["warnings"])
        if field_design["alternateKeyCandidate"]:
            alternate_keys.append(field_design["alternateKeyCandidate"])

    for item in require_list(raw, "lookups") + require_list(raw, "relationships"):
        lookup_design = build_lookup_design(item, prefix=prefix, referencing_entity=table_logical_name, solution_unique_name=solution_unique_name)
        relationships.append(lookup_design["relationship"])
        lookup_specs.append(lookup_design["helperSpec"])
        warnings.extend(lookup_design["warnings"])

    access_patterns = require_list(raw, "accessPatterns") or [{"name": "Default list"}]
    query_examples = [build_query_example(pattern, table_logical_name=table_logical_name, primary_name=primary_name, fields=fields) for pattern in access_patterns]

    suggested_alternate_keys = dedupe_alternate_keys(
        explicit_keys=require_list(raw, "alternateKeys"),
        inferred_keys=alternate_keys,
    )

    return {
        "displayName": display_name,
        "pluralDisplayName": plural_display_name,
        "logicalName": table_logical_name,
        "schemaName": table_schema_name,
        "ownershipType": ownership_type,
        "primaryName": primary_name,
        "fields": fields,
        "relationships": relationships,
        "alternateKeys": suggested_alternate_keys,
        "queryExamples": query_examples,
        "helperSpecs": {
            "createTable": {
                "schemaName": table_schema_name,
                "logicalName": table_logical_name,
                "displayName": display_name,
                "pluralDisplayName": plural_display_name,
                "description": text_value(raw, "description"),
                "solutionUniqueName": solution_unique_name,
                "ownershipType": ownership_type,
                "hasActivities": bool(raw.get("hasActivities")),
                "hasNotes": raw.get("hasNotes", True),
                "hasFeedback": bool(raw.get("hasFeedback")),
                "enableAudit": raw.get("enableAudit"),
                "primaryName": {
                    "schemaName": primary_name["schemaName"],
                    "logicalName": primary_name["logicalName"],
                    "displayName": primary_name["displayName"],
                    "requiredLevel": primary_name.get("requiredLevel"),
                    "maxLength": primary_name.get("maxLength"),
                    "description": primary_name.get("description"),
                },
            },
            "createFields": field_specs,
            "createLookups": lookup_specs,
        },
        "warnings": sorted(set(warnings)),
    }


def build_primary_name(raw: Any, *, prefix: str) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    display_name = text_value(source, "displayName") or "Name"
    logical_stub = slug_name(source.get("logicalName") or display_name)
    schema_source = source.get("schemaName") or display_name
    return {
        "displayName": display_name,
        "logicalName": logical_stub,
        "schemaName": schema_name(prefix, schema_source),
        "requiredLevel": text_value(source, "requiredLevel") or "ApplicationRequired",
        "maxLength": int(source.get("maxLength") or 200),
        "description": text_value(source, "description"),
    }


def build_field_design(raw: Any, *, prefix: str, table_logical_name: str, solution_unique_name: str | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("Each field item must be a JSON object.")

    display_name = require_text(raw, "displayName")
    field_type = normalize_field_type(require_text(raw, "type"))
    logical_stub = slug_name(raw.get("logicalName") or display_name)
    logical_name = normalize_with_prefix(prefix, logical_stub)
    schema = raw.get("schemaName") or schema_name(prefix, display_name)
    warnings: list[str] = []

    helper_spec: dict[str, Any] = {
        "tableLogicalName": table_logical_name,
        "type": map_helper_field_type(field_type),
        "schemaName": schema,
        "logicalName": logical_name,
        "displayName": display_name,
        "description": text_value(raw, "description"),
        "requiredLevel": text_value(raw, "requiredLevel") or ("ApplicationRequired" if raw.get("required") else None),
        "enableAudit": raw.get("enableAudit"),
        "isSecured": raw.get("isSecured"),
        "solutionUniqueName": solution_unique_name,
    }

    if field_type in {"string", "memo"}:
        helper_spec["maxLength"] = int(raw.get("maxLength") or (2000 if field_type == "memo" else DEFAULT_STRING_LENGTH))
        if field_type == "memo":
            helper_spec["type"] = "Memo"
    elif field_type == "integer":
        helper_spec["minValueInt"] = raw.get("minValueInt")
        helper_spec["maxValueInt"] = raw.get("maxValueInt")
    elif field_type in {"decimal", "money"}:
        helper_spec["precision"] = raw.get("precision")
        helper_spec["minValueDecimal"] = raw.get("minValueDecimal")
        helper_spec["maxValueDecimal"] = raw.get("maxValueDecimal")
    elif field_type == "datetime":
        helper_spec["dateTimeFormat"] = text_value(raw, "dateTimeFormat") or "DateOnly"
        helper_spec["dateTimeBehavior"] = text_value(raw, "dateTimeBehavior") or "UserLocal"
    elif field_type == "boolean":
        helper_spec["trueLabel"] = text_value(raw, "trueLabel") or "Yes"
        helper_spec["falseLabel"] = text_value(raw, "falseLabel") or "No"
        if "defaultBooleanValue" in raw:
            helper_spec["defaultBooleanValue"] = bool(raw.get("defaultBooleanValue"))
    elif field_type in {"choice", "multiselectchoice"}:
        options = require_list(raw, "options")
        if not options:
            warnings.append(f"{display_name}: choice fields should declare at least one option.")
        helper_spec["options"] = [
            {
                "label": require_text(option, "label"),
                "value": option.get("value"),
            }
            for option in options
        ]
        helper_spec["optionValueSeed"] = raw.get("optionValueSeed")
        if field_type == "multiselectchoice":
            helper_spec["type"] = "MultiSelectPicklist"

    alternate_key_candidate = None
    if raw.get("alternateKey") or raw.get("unique") or is_natural_key_candidate(logical_stub):
        alternate_key_candidate = {
            "name": text_value(raw, "alternateKeyName") or f"{schema}Key",
            "fields": [logical_name],
            "rationale": "Explicitly marked unique or inferred as a likely business identifier.",
        }

    return {
        "field": {
            "displayName": display_name,
            "logicalName": logical_name,
            "schemaName": schema,
            "type": field_type,
            "requiredLevel": helper_spec.get("requiredLevel"),
            "alternateKeyCandidate": alternate_key_candidate,
        },
        "helperSpec": helper_spec,
        "alternateKeyCandidate": alternate_key_candidate,
        "warnings": warnings,
    }


def build_lookup_design(raw: Any, *, prefix: str, referencing_entity: str, solution_unique_name: str | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("Each lookup item must be a JSON object.")

    target = require_text(raw, "targetTable", fallback_keys=("referencedEntity", "target"))
    display_name = text_value(raw, "displayName") or prettify(target)
    logical_stub = slug_name(raw.get("logicalName") or f"{slug_name(target)}id")
    logical_name = normalize_with_prefix(prefix, logical_stub)
    schema = raw.get("schemaName") or schema_name(prefix, logical_stub)
    relationship_schema = raw.get("relationshipSchemaName") or f"{schema_name(prefix, prettify(referencing_entity))}_{schema_name(prefix, prettify(target))}"

    helper_spec = {
        "referencingEntity": referencing_entity,
        "referencedEntity": target,
        "referencedAttribute": text_value(raw, "referencedAttribute"),
        "relationshipSchemaName": relationship_schema,
        "lookupSchemaName": schema,
        "lookupLogicalName": logical_name,
        "displayName": display_name,
        "description": text_value(raw, "description"),
        "requiredLevel": text_value(raw, "requiredLevel") or ("ApplicationRequired" if raw.get("required") else None),
        "solutionUniqueName": solution_unique_name,
        "associatedMenuBehavior": text_value(raw, "associatedMenuBehavior"),
        "associatedMenuGroup": text_value(raw, "associatedMenuGroup"),
        "associatedMenuLabel": text_value(raw, "associatedMenuLabel"),
        "associatedMenuOrder": raw.get("associatedMenuOrder"),
        "cascade": raw.get("cascade"),
    }

    return {
        "relationship": {
            "displayName": display_name,
            "referencingEntity": referencing_entity,
            "referencedEntity": target,
            "lookupLogicalName": logical_name,
            "lookupSchemaName": schema,
            "relationshipSchemaName": relationship_schema,
        },
        "helperSpec": helper_spec,
        "warnings": [],
    }


def build_query_example(pattern: dict[str, Any], *, table_logical_name: str, primary_name: dict[str, Any], fields: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(pattern, dict):
        raise RuntimeError("Each accessPatterns item must be a JSON object.")

    name = text_value(pattern, "name") or "Query"
    select = pattern.get("select")
    if not isinstance(select, list) or not select:
        select = [primary_name["logicalName"], *(field["logicalName"] for field in fields[:2])]

    order_by = pattern.get("orderBy")
    if not isinstance(order_by, list) or not order_by:
        order_by = [{"field": primary_name["logicalName"], "direction": "asc"}]

    filters = pattern.get("filter")
    if not isinstance(filters, list):
        filters = []

    fetch_parts = [f"<fetch><entity name=\"{table_logical_name}\">"]
    for column in select:
        fetch_parts.append(f"<attribute name=\"{column}\" />")
    if filters:
        fetch_parts.append("<filter type=\"and\">")
        for condition in filters:
            if not isinstance(condition, dict):
                continue
            field = text_value(condition, "field")
            if not field:
                continue
            operator = text_value(condition, "operator") or "eq"
            value = condition.get("value")
            if value is None:
                fetch_parts.append(f"<condition attribute=\"{field}\" operator=\"{operator}\" />")
            else:
                fetch_parts.append(f"<condition attribute=\"{field}\" operator=\"{operator}\" value=\"{value}\" />")
        fetch_parts.append("</filter>")
    for sort in order_by:
        if not isinstance(sort, dict):
            continue
        field = text_value(sort, "field")
        if not field:
            continue
        descending = str(sort.get("direction", "asc")).strip().lower() == "desc"
        fetch_parts.append(f"<order attribute=\"{field}\" descending=\"{str(descending).lower()}\" />")
    fetch_parts.append("</entity></fetch>")

    odata_parts = []
    if select:
        odata_parts.append("$select=" + ",".join(str(column) for column in select))
    if filters:
        rendered_filters = []
        for condition in filters:
            if not isinstance(condition, dict):
                continue
            field = text_value(condition, "field")
            if not field:
                continue
            operator = map_odata_operator(text_value(condition, "operator") or "eq")
            value = format_odata_value(condition.get("value"))
            rendered_filters.append(f"{field} {operator} {value}")
        if rendered_filters:
            odata_parts.append("$filter=" + " and ".join(rendered_filters))
    if order_by:
        rendered_order = []
        for sort in order_by:
            if not isinstance(sort, dict):
                continue
            field = text_value(sort, "field")
            if not field:
                continue
            direction = str(sort.get("direction", "asc")).strip().lower()
            rendered_order.append(f"{field} {direction}")
        if rendered_order:
            odata_parts.append("$orderby=" + ",".join(rendered_order))
    top_value = pattern.get("top")
    if top_value is not None:
        odata_parts.append(f"$top={int(top_value)}")

    return {
        "name": name,
        "fetchXml": "".join(fetch_parts),
        "odata": f"/api/data/v9.2/{table_logical_name}s?" + "&".join(odata_parts) if odata_parts else f"/api/data/v9.2/{table_logical_name}s",
    }


def normalize_field_type(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "").replace("_", "")
    if normalized == "wholenumber":
        normalized = "integer"
    if normalized not in SUPPORTED_FIELD_TYPES:
        raise RuntimeError(f"Unsupported field type '{value}'. Supported types: {', '.join(sorted(SUPPORTED_FIELD_TYPES))}.")
    return normalized


def map_helper_field_type(field_type: str) -> str:
    mapping = {
        "string": "String",
        "memo": "Memo",
        "integer": "Integer",
        "decimal": "Decimal",
        "money": "Money",
        "boolean": "Boolean",
        "datetime": "DateTime",
        "choice": "Picklist",
        "multiselectchoice": "MultiSelectPicklist",
    }
    return mapping[field_type]


def slug_name(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()
    return text or "item"


def normalize_with_prefix(prefix: str, value: str) -> str:
    normalized = slug_name(value)
    if normalized.startswith(prefix.lower() + "_"):
        return normalized
    return f"{prefix.lower()}_{normalized}"


def schema_name(prefix: str, value: Any) -> str:
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", str(value)) if token]
    if tokens and tokens[0].lower() == prefix.lower():
        tokens = tokens[1:]
    return prefix.lower() + "".join(token[:1].upper() + token[1:] for token in tokens)


def pluralize(value: str) -> str:
    return value if value.endswith("s") else value + "s"


def prettify(value: str) -> str:
    return re.sub(r"[_-]+", " ", value).strip().title()


def text_value(source: dict[str, Any], key: str, fallback_keys: tuple[str, ...] = ()) -> str | None:
    keys = (key, *fallback_keys)
    for candidate in keys:
        value = source.get(candidate)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def require_text(source: dict[str, Any], key: str, fallback_keys: tuple[str, ...] = ()) -> str:
    value = text_value(source, key, fallback_keys)
    if value:
        return value
    raise RuntimeError(f"Expected a non-empty string for '{key}'.")


def require_list(source: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = source.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError(f"Expected '{key}' to be a JSON array when present.")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Item {index} in '{key}' must be a JSON object.")
    return value


def is_natural_key_candidate(logical_stub: str) -> bool:
    return any(hint in logical_stub for hint in NATURAL_KEY_HINTS)


def dedupe_alternate_keys(*, explicit_keys: list[dict[str, Any]], inferred_keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    combined = explicit_keys + inferred_keys
    results = []
    for key in combined:
        fields = tuple(sorted(str(item) for item in key.get("fields", [])))
        name = str(key.get("name") or "")
        signature = (name, fields)
        if not name or not fields or signature in seen:
            continue
        seen.add(signature)
        results.append({"name": name, "fields": list(fields), "rationale": key.get("rationale")})
    return results


def map_odata_operator(operator: str) -> str:
    return {
        "eq": "eq",
        "ne": "ne",
        "gt": "gt",
        "ge": "ge",
        "lt": "lt",
        "le": "le",
    }.get(operator.lower(), operator)


def format_odata_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


if __name__ == "__main__":
    raise SystemExit(main())
