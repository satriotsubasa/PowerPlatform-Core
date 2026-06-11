#!/usr/bin/env python3
"""Design a custom connector or integration wrapper plan from structured input or OpenAPI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from powerplatform_common import read_json_argument, repo_root, write_json_output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Design a custom connector or integration wrapper plan from structured input or OpenAPI.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the connector or integration requirement.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve relative OpenAPI paths.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args()

    spec = read_json_argument(args.spec)
    if not isinstance(spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    source, normalized = load_connector_source(spec, repo)
    plan = build_connector_plan(source, normalized)
    write_json_output(plan, args.output)
    return 0


def load_connector_source(spec: dict[str, Any], repo: Path) -> tuple[str, dict[str, Any]]:
    openapi_path = spec.get("openApiPath")
    if isinstance(openapi_path, str) and openapi_path.strip():
        path = Path(openapi_path)
        resolved = path.resolve() if path.is_absolute() else (repo / path).resolve()
        text = resolved.read_text(encoding="utf-8")
        if resolved.suffix.lower() == ".json" or text.lstrip().startswith("{"):
            document = json.loads(text)
        else:
            try:
                import yaml  # type: ignore
            except Exception as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "YAML OpenAPI parsing requires PyYAML. Provide JSON OpenAPI, or install PyYAML first."
                ) from exc
            document = yaml.safe_load(text)
        if not isinstance(document, dict):
            raise RuntimeError("OpenAPI input must resolve to a JSON object.")
        return "openapi", document
    return "structured", spec


def build_connector_plan(source: str, normalized: dict[str, Any]) -> dict[str, Any]:
    if source == "openapi":
        return build_openapi_plan(normalized)
    return build_structured_plan(normalized)


def build_openapi_plan(document: dict[str, Any]) -> dict[str, Any]:
    info = document.get("info") if isinstance(document.get("info"), dict) else {}
    servers = document.get("servers") if isinstance(document.get("servers"), list) else []
    paths = document.get("paths") if isinstance(document.get("paths"), dict) else {}
    security_schemes = (
        document.get("components", {}).get("securitySchemes")
        if isinstance(document.get("components"), dict)
        else {}
    )
    security_schemes = security_schemes if isinstance(security_schemes, dict) else {}

    operations = []
    has_binary = False
    for raw_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(operation, dict):
                continue
            operation_id = str(operation.get("operationId") or f"{method}_{raw_path}")
            request_body = operation.get("requestBody") if isinstance(operation.get("requestBody"), dict) else {}
            request_json = json.dumps(request_body)
            if "multipart/form-data" in request_json or "application/octet-stream" in request_json:
                has_binary = True
            operations.append(
                {
                    "method": method.upper(),
                    "path": raw_path,
                    "operationId": operation_id,
                    "summary": operation.get("summary"),
                }
            )

    auth_types = sorted(
        {
            str((scheme or {}).get("type") or "unknown")
            for scheme in security_schemes.values()
            if isinstance(scheme, dict)
        }
    )
    needs_facade = has_binary or not auth_types or any(auth_type in {"oauth1", "unknown"} for auth_type in auth_types)
    recommendation = (
        "Use a direct custom connector first."
        if not needs_facade
        else "Use an Azure Function or similar facade first, then expose a custom connector over the stable facade surface."
    )

    return {
        "success": True,
        "mode": "design-custom-connector",
        "source": "openapi",
        "connectorName": info.get("title") or "Custom Connector",
        "version": info.get("version"),
        "baseUrl": servers[0].get("url") if servers and isinstance(servers[0], dict) else None,
        "operationCount": len(operations),
        "operations": operations,
        "authTypes": auth_types,
        "needsFacade": needs_facade,
        "recommendedPattern": recommendation,
        "environmentVariables": suggest_environment_variables(base_url=servers[0].get("url") if servers and isinstance(servers[0], dict) else None),
        "connectionReferences": ["Create one connection reference per connector instance inside the target solution."],
        "warnings": build_connector_warnings(needs_facade=needs_facade, has_binary=has_binary, auth_types=auth_types),
    }


def build_structured_plan(spec: dict[str, Any]) -> dict[str, Any]:
    connector_name = str(spec.get("connectorName") or spec.get("name") or "Custom Connector")
    auth_type = str(spec.get("authType") or "apiKey")
    operations = spec.get("operations")
    if not isinstance(operations, list) or not operations:
        raise RuntimeError("Structured connector specs must include a non-empty 'operations' array.")

    normalized_operations = []
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            raise RuntimeError(f"Operation {index} must be a JSON object.")
        normalized_operations.append(
            {
                "name": operation.get("name") or operation.get("operationId") or f"operation-{index}",
                "method": str(operation.get("method") or "GET").upper(),
                "path": operation.get("path"),
                "summary": operation.get("summary"),
                "responseType": operation.get("responseType"),
            }
        )

    facade_reason = []
    if str(spec.get("protocol") or "rest").lower() != "rest":
        facade_reason.append("The integration is not REST-shaped.")
    if spec.get("needsFanOut"):
        facade_reason.append("The integration needs orchestration or fan-out logic before exposure.")
    if spec.get("needsTransformation"):
        facade_reason.append("The integration needs payload transformation before exposure.")

    needs_facade = bool(facade_reason)

    return {
        "success": True,
        "mode": "design-custom-connector",
        "source": "structured",
        "connectorName": connector_name,
        "baseUrl": spec.get("baseUrl"),
        "authTypes": [auth_type],
        "operations": normalized_operations,
        "needsFacade": needs_facade,
        "recommendedPattern": (
            "Use a direct custom connector."
            if not needs_facade
            else "Use an Azure Function or API facade before the custom connector."
        ),
        "facadeRationale": facade_reason,
        "environmentVariables": suggest_environment_variables(base_url=spec.get("baseUrl")),
        "connectionReferences": ["Add the custom connector and its connection reference to the selected working solution."],
        "warnings": build_connector_warnings(needs_facade=needs_facade, has_binary=bool(spec.get("binaryPayloads")), auth_types=[auth_type]),
    }


def suggest_environment_variables(*, base_url: Any) -> list[str]:
    variables = ["Base URL", "Audience or resource identifier when OAuth is used", "Default timeout or retry profile when the integration is brittle"]
    if isinstance(base_url, str) and base_url.strip():
        variables.insert(0, f"Base URL currently appears to be {base_url.strip()}")
    return variables


def build_connector_warnings(*, needs_facade: bool, has_binary: bool, auth_types: list[str]) -> list[str]:
    warnings = []
    if needs_facade:
        warnings.append("A facade is recommended before exposing this integration as a custom connector.")
    if has_binary:
        warnings.append("Binary or multipart payloads usually need extra testing in custom connectors.")
    if not auth_types:
        warnings.append("No auth scheme was detected, so connection setup still needs explicit design.")
    return warnings


if __name__ == "__main__":
    raise SystemExit(main())
