#!/usr/bin/env python3
"""Design Dataverse OData, FetchXML, and flow-friendly query parameters."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from powerplatform_common import read_json_argument, repo_root, write_json_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Design Dataverse OData, FetchXML, and flow-friendly query parameters.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the query design.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve relative spec paths.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo_root(Path(args.repo_root))
    payload = build_query_design(spec)
    write_json_output(payload, args.output)
    return 0


def build_query_design(spec: dict[str, Any]) -> dict[str, Any]:
    table_logical_name = require_text(spec, "tableLogicalName")
    entity_set_name = optional_text(spec, "entitySetName")
    select = require_string_list(spec.get("select"))
    if not select:
        primary_name = optional_text(spec, "primaryName", fallback_keys=("primaryField",))
        if primary_name:
            select = [primary_name]
    filters = require_object_list(spec.get("filters"))
    order_by = require_object_list(spec.get("orderBy"))
    if not order_by and select:
        order_by = [{"field": select[0], "direction": "asc"}]
    top = spec.get("top")
    expand = require_string_list(spec.get("expand"))

    fetch_xml = build_fetchxml(table_logical_name, select, filters, order_by, top)
    odata_parts: list[str] = []
    if select:
        odata_parts.append("$select=" + ",".join(select))
    if filters:
        odata_parts.append("$filter=" + " and ".join(render_odata_filter(item) for item in filters))
    if order_by:
        odata_parts.append("$orderby=" + ",".join(render_odata_order(item) for item in order_by))
    if top is not None:
        odata_parts.append(f"$top={int(top)}")
    if expand:
        odata_parts.append("$expand=" + ",".join(expand))
    entity_set_segment = entity_set_name or table_logical_name

    return {
        "success": True,
        "mode": "design-dataverse-query",
        "tableLogicalName": table_logical_name,
        "entitySetName": entity_set_name,
        "odata": f"/api/data/v9.2/{entity_set_segment}?" + "&".join(odata_parts) if odata_parts else f"/api/data/v9.2/{entity_set_segment}",
        "fetchXml": fetch_xml,
        "powerAutomate": {
            "action": "List rows",
            "tableName": table_logical_name,
            "selectColumns": ",".join(select) if select else None,
            "filterRows": " and ".join(render_odata_filter(item) for item in filters) if filters else None,
            "orderBy": ",".join(render_odata_order(item) for item in order_by) if order_by else None,
            "topCount": int(top) if top is not None else None,
            "fetchXml": fetch_xml,
        },
        "warnings": build_query_warnings(filters, top, select, entity_set_name, filters),
    }


def build_fetchxml(table_logical_name: str, select: list[str], filters: list[dict[str, Any]], order_by: list[dict[str, Any]], top: Any) -> str:
    parts = ["<fetch"]
    if top is not None:
        parts.append(f" count=\"{int(top)}\"")
    parts.append(f"><entity name=\"{table_logical_name}\">")
    for column in select:
        parts.append(f"<attribute name=\"{column}\" />")
    if filters:
        parts.append("<filter type=\"and\">")
        for item in filters:
            field = require_text(item, "field")
            operator = normalize_operator(str(item.get("operator") or "eq"))
            value = item.get("value")
            if operator in {"null", "not-null"} or value is None:
                parts.append(f"<condition attribute=\"{field}\" operator=\"{operator}\" />")
            elif operator == "in":
                parts.append(f"<condition attribute=\"{field}\" operator=\"in\">")
                for child_value in ensure_list(value):
                    parts.append(f"<value>{child_value}</value>")
                parts.append("</condition>")
            elif operator in {"contains", "startswith", "endswith"}:
                parts.append(f"<condition attribute=\"{field}\" operator=\"like\" value=\"{render_fetch_like_value(operator, value)}\" />")
            else:
                parts.append(f"<condition attribute=\"{field}\" operator=\"{operator}\" value=\"{value}\" />")
        parts.append("</filter>")
    for item in order_by:
        field = require_text(item, "field")
        descending = str(item.get("direction") or "asc").strip().lower() == "desc"
        parts.append(f"<order attribute=\"{field}\" descending=\"{str(descending).lower()}\" />")
    parts.append("</entity></fetch>")
    return "".join(parts)


def render_odata_filter(item: dict[str, Any]) -> str:
    field = require_text(item, "field")
    operator = normalize_operator(str(item.get("operator") or "eq"))
    value = item.get("value")
    if operator == "null" or value is None:
        return f"{field} eq null"
    if operator == "not-null":
        return f"{field} ne null"
    if isinstance(value, bool):
        rendered = str(value).lower()
    elif isinstance(value, (int, float)):
        rendered = str(value)
    elif isinstance(value, list):
        rendered = "(" + ",".join(render_odata_literal(item) for item in value) + ")"
    else:
        rendered = "'" + str(value).replace("'", "''") + "'"
    if operator in {"contains", "startswith", "endswith"}:
        return f"{operator}({field},{rendered})"
    if operator == "in":
        return f"{field} in {rendered}"
    return f"{field} {operator} {rendered}"


def render_odata_order(item: dict[str, Any]) -> str:
    field = require_text(item, "field")
    direction = str(item.get("direction") or "asc").strip().lower()
    return f"{field} {direction}"


def build_query_warnings(
    filters: list[dict[str, Any]],
    top: Any,
    select: list[str],
    entity_set_name: str | None,
    filter_items: list[dict[str, Any]],
) -> list[str]:
    warnings = []
    if not entity_set_name:
        warnings.append("Entity set name was not provided, so the OData path uses the table logical name as a fallback. Prefer supplying entitySetName for Web API accuracy.")
    if not filters:
        warnings.append("The query has no explicit filter, so it may read more rows than intended.")
    if top is None:
        warnings.append("The query has no explicit top limit, so list actions may return large result sets.")
    if not select:
        warnings.append("The query has no explicit select list, so connector defaults may return wider payloads than necessary.")
    if any(normalize_operator(str(item.get("operator") or "eq")) == "in" for item in filter_items):
        warnings.append("The query uses an 'in' filter. Validate OData support for the specific Dataverse action, or prefer FetchXML if the connector rejects it.")
    return warnings


def render_odata_literal(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def render_fetch_like_value(operator: str, value: Any) -> str:
    text = str(value)
    if operator == "startswith":
        return f"{text}%"
    if operator == "endswith":
        return f"%{text}"
    return f"%{text}%"


def normalize_operator(value: str) -> str:
    mapping = {
        "equals": "eq",
        "equal": "eq",
        "not-equal": "ne",
        "not_equal": "ne",
        "contains": "contains",
        "startswith": "startswith",
        "endswith": "endswith",
        "null": "null",
        "isnull": "null",
        "not-null": "not-null",
        "notnull": "not-null",
    }
    return mapping.get(value.strip().lower(), value.strip().lower())


def ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return [value]


def require_text(source: dict[str, Any], key: str, fallback_keys: tuple[str, ...] = ()) -> str:
    for candidate in (key, *fallback_keys):
        value = source.get(candidate)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise RuntimeError(f"Expected a non-empty string for '{key}'.")


def optional_text(source: dict[str, Any], key: str, fallback_keys: tuple[str, ...] = ()) -> str | None:
    for candidate in (key, *fallback_keys):
        value = source.get(candidate)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def require_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError("Expected a JSON array of strings.")
    output = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RuntimeError("Expected a JSON array of non-empty strings.")
        output.append(item.strip())
    return output


def require_object_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError("Expected a JSON array of objects.")
    for item in value:
        if not isinstance(item, dict):
            raise RuntimeError("Expected a JSON array of objects.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
