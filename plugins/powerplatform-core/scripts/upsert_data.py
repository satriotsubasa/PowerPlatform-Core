#!/usr/bin/env python3
"""Create, update, or upsert Dataverse rows with the shared SDK tool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from powerplatform_common import (
    append_tool_connection_args,
    coerce_dataverse_row_data,
    load_deployment_defaults,
    read_json_argument,
    repo_root,
    resolve_live_connection,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create, update, or upsert Dataverse business data through the shared Dataverse SDK helper.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve project-profile deployment defaults.")
    parser.add_argument("--mode", choices=["create", "update", "upsert"], default="upsert")
    parser.add_argument("--table", required=True, help="Dataverse table logical name.")
    parser.add_argument("--data", required=True, help="JSON object or path to a JSON file with the columns to write.")
    parser.add_argument("--id", help="Primary key GUID for update or upsert.")
    parser.add_argument("--key", help="JSON object or path to a JSON file with alternate key values.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for interactive OAuth connection. Defaults from active PAC auth profile.")
    parser.add_argument("--tenant-id", help="Tenant ID for MSAL authentication. Defaults from active PAC auth profile when available.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before the write.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive", "clientsecret", "certificate"],
        default="auto",
        help="Authentication flow. Interactive: auto/devicecode/interactive. Unattended service principal: clientsecret (secret in DATAVERSE_CLIENT_SECRET env var) or certificate (with --certificate-path).",
    )
    parser.add_argument("--app-id", help="Application (client) ID for service-principal auth (--auth-flow clientsecret/certificate).")
    parser.add_argument("--certificate-path", help="Certificate (.pfx) path for --auth-flow certificate (password in DATAVERSE_CERTIFICATE_PASSWORD env var).")
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    parser.add_argument("--verify", action="store_true", help="Retrieve the changed columns after the write.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read the current row and print a per-column diff of the would-be write without mutating anything. "
        "Requires --id or --key for update/upsert; create mode reports every column as new.",
    )
    args = parser.parse_args()

    data = read_json_argument(args.data)
    if not isinstance(data, dict):
        print("ERROR: --data must resolve to a JSON object.", file=sys.stderr)
        return 2
    repo = repo_root(Path(args.repo_root))
    deployment_defaults = load_deployment_defaults(repo)
    data = coerce_dataverse_row_data(args.table, data, deployment_defaults)

    key_text = None
    if args.key:
        key = read_json_argument(args.key)
        if not isinstance(key, dict):
            print("ERROR: --key must resolve to a JSON object.", file=sys.stderr)
            return 2
        key_text = json.dumps(key)

    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
        auth_flow=args.auth_flow,
        app_id=args.app_id,
        certificate_path=args.certificate_path,
    )

    if args.dry_run:
        plan = compute_dry_run_plan(args, data, key_text, connection)
        print(json.dumps(plan, indent=2, default=str))
        return 0

    command = [
        "row",
        "--mode",
        args.mode,
        "--table",
        args.table,
        "--data",
        json.dumps(data),
    ]
    if args.id:
        command.extend(["--id", args.id])
    if key_text:
        command.extend(["--key", key_text])
    if args.verify:
        command.append("--verify")
    append_tool_connection_args(
        command,
        connection,
        auth_flow=args.auth_flow,
        app_id=args.app_id,
        certificate_path=args.certificate_path,
        force_prompt=args.force_prompt,
        verbose=args.verbose,
    )

    completed = run_dataverse_tool(command)
    print(completed.stdout.strip())
    return 0


_MISSING = object()


def compute_dry_run_plan(args: argparse.Namespace, data: dict, key_text: str | None, connection: dict) -> dict:
    """Build a no-mutation preview of a keyed write by diffing against the current live row."""
    keyed = bool(args.id or key_text)
    if args.mode != "create" and not keyed:
        return {
            "dryRun": True,
            "mode": args.mode,
            "table": args.table,
            "diffable": False,
            "note": "Provide --id or --key to diff an update/upsert against the current row.",
            "proposed": data,
        }

    row_found = False
    current_columns: dict | None = None
    if keyed and args.mode != "create":
        payload = retrieve_current_row(args, data, key_text, connection)
        row_found = bool(payload.get("found"))
        row = payload.get("row") if isinstance(payload, dict) else None
        if isinstance(row, dict) and isinstance(row.get("columns"), dict):
            current_columns = row["columns"]

    return build_dry_run_plan(
        mode=args.mode,
        table=args.table,
        record_id=args.id,
        key_text=key_text,
        proposed_data=data,
        current_columns=current_columns,
        row_found=row_found,
    )


def retrieve_current_row(args: argparse.Namespace, data: dict, key_text: str | None, connection: dict) -> dict:
    command = ["row", "--mode", "retrieve", "--table", args.table]
    if args.id:
        command.extend(["--id", args.id])
    if key_text:
        command.extend(["--key", key_text])
    columns = ",".join(data.keys())
    if columns:
        command.extend(["--columns", columns])
    append_tool_connection_args(
        command,
        connection,
        auth_flow=args.auth_flow,
        app_id=args.app_id,
        certificate_path=args.certificate_path,
        force_prompt=args.force_prompt,
        verbose=args.verbose,
    )
    completed = run_dataverse_tool(command)
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("Dry-run retrieve did not return a JSON object from the Dataverse tool.")
    return payload


def build_dry_run_plan(
    *,
    mode: str,
    table: str,
    record_id: str | None,
    key_text: str | None,
    proposed_data: dict,
    current_columns: dict | None,
    row_found: bool,
) -> dict:
    changes: list[dict] = []
    unchanged: list[dict] = []
    for column, proposed in proposed_data.items():
        if not row_found:
            changes.append({"column": column, "changeType": "create", "current": None, "proposed": proposed})
            continue
        current = current_columns.get(column, _MISSING) if isinstance(current_columns, dict) else _MISSING
        if current is _MISSING:
            changes.append({"column": column, "changeType": "add", "current": None, "proposed": proposed})
        elif values_equal_for_diff(proposed, current):
            unchanged.append({"column": column, "value": proposed})
        else:
            changes.append({"column": column, "changeType": "update", "current": current, "proposed": proposed})

    return {
        "dryRun": True,
        "mode": mode,
        "table": table,
        "id": record_id,
        "key": json.loads(key_text) if key_text else None,
        "diffable": True,
        "rowExists": row_found,
        "effectiveOperation": resolve_effective_operation(mode, row_found),
        "changeCount": len(changes),
        "unchangedCount": len(unchanged),
        "changes": changes,
        "unchanged": unchanged,
        "note": dry_run_note(mode, row_found),
    }


def resolve_effective_operation(mode: str, row_found: bool) -> str:
    if not row_found:
        return "create"
    if mode == "create":
        return "conflict"
    return "update"


def dry_run_note(mode: str, row_found: bool) -> str | None:
    if mode == "update" and not row_found:
        return "No matching row exists, so a live update would fail. Use upsert to create-or-update."
    if mode == "create" and row_found:
        return "A row already exists for this key, so a live create with the same identity would conflict."
    return None


def normalize_for_diff(value: object) -> object:
    """Reduce proposed typed values and current simplified values to a comparable form."""
    if isinstance(value, dict):
        vtype = value.get("type")
        if isinstance(vtype, str):
            typed = vtype.strip().lower()
            if typed == "lookup":
                return ("lookup", str(value.get("entity", "")).lower(), str(value.get("id", "")).lower())
            if typed in ("money", "choice"):
                return value.get("value")
            if typed in ("datetime", "guid"):
                raw = value.get("value")
                return str(raw).lower() if raw is not None else None
        if "logicalName" in value and "id" in value:
            return ("lookup", str(value.get("logicalName", "")).lower(), str(value.get("id", "")).lower())
    return value


def values_equal_for_diff(proposed: object, current: object) -> bool:
    normalized_proposed = normalize_for_diff(proposed)
    normalized_current = normalize_for_diff(current)
    # A two-option bool must not compare equal to its numeric twin (True == 1 in Python),
    # so a genuine type flip still shows up as a change.
    if isinstance(normalized_proposed, bool) != isinstance(normalized_current, bool):
        return False
    if normalized_proposed == normalized_current:
        return True
    scalar_types = (int, float, str)
    if isinstance(normalized_proposed, scalar_types) and isinstance(normalized_current, scalar_types):
        return str(normalized_proposed) == str(normalized_current)
    return False


if __name__ == "__main__":
    raise SystemExit(main())
