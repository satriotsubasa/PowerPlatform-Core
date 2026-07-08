#!/usr/bin/env python3
"""Read Dataverse business data: retrieve one row by key, or list rows for a query.

Read-only. The `retrieve` mode reads a single record by primary key (`--id`) or
alternate key (`--key`); the `list` mode runs a FetchXML query (passed directly with
`--fetchxml`, or built from a `--spec` via the offline query designer) with bounded
paging and total-count reporting. Because reads do not mutate, they do not require the
orchestrator live-mutation preflight.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from design_dataverse_query import build_query_design
from powerplatform_common import (
    append_tool_connection_args,
    read_json_argument,
    resolve_live_connection,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read Dataverse business data: retrieve a single row by id/alternate key, or list rows for a FetchXML/spec query.",
    )
    parser.add_argument("--mode", choices=["retrieve", "list"], default="retrieve")
    parser.add_argument("--table", help="Dataverse table logical name (required for retrieve).")
    parser.add_argument("--id", help="Primary-key GUID for retrieve.")
    parser.add_argument("--key", help="JSON object or path with alternate-key values for retrieve.")
    parser.add_argument("--columns", help="Comma-separated column logical names to return on retrieve. Default: all columns.")
    parser.add_argument("--all-columns", action="store_true", help="Return every column on retrieve (the default when --columns is omitted).")
    parser.add_argument("--fetchxml", help="FetchXML string or path for list mode.")
    parser.add_argument("--spec", help="Query spec (JSON object or path) for list mode; converted to FetchXML with the offline query designer.")
    parser.add_argument("--max-rows", type=int, default=100, help="Maximum rows to return for list mode (default 100). The response still reports whether more rows exist.")
    parser.add_argument("--page-size", type=int, help="Page size for list paging (capped at the Dataverse 5000 page limit).")
    parser.add_argument("--exact-total", action="store_true", help="Also fetch the unfiltered table total via RetrieveTotalRecordCount (a snapshot up to ~24h stale that ignores the query filter).")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org/environment URL for the auth dialog.")
    parser.add_argument("--username", help="Username for interactive OAuth connection. Defaults from active PAC auth profile.")
    parser.add_argument("--tenant-id", help="Tenant ID for MSAL authentication. Defaults from active PAC auth profile when available.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before the read (optional for reads).")
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
    args = parser.parse_args()

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

    command = build_retrieve_command(args, connection) if args.mode == "retrieve" else build_list_command(args, connection)

    completed = run_dataverse_tool(command)
    print(completed.stdout.strip())
    return 0


def shared_connection_args(args: argparse.Namespace, connection: dict) -> list[str]:
    return append_tool_connection_args(
        [],
        connection,
        auth_flow=args.auth_flow,
        app_id=args.app_id,
        certificate_path=args.certificate_path,
        force_prompt=args.force_prompt,
        verbose=args.verbose,
    )


def build_retrieve_command(args: argparse.Namespace, connection: dict) -> list[str]:
    if not args.table:
        raise SystemExit("ERROR: --table is required for --mode retrieve.")
    if not args.id and not args.key:
        raise SystemExit("ERROR: retrieve requires --id or --key.")

    command = ["row", "--mode", "retrieve", "--table", args.table]
    if args.id:
        command.extend(["--id", args.id])
    if args.key:
        key = read_json_argument(args.key)
        if not isinstance(key, dict):
            raise SystemExit("ERROR: --key must resolve to a JSON object.")
        command.extend(["--key", json.dumps(key)])
    if args.all_columns:
        command.append("--all-columns")
    elif args.columns:
        command.extend(["--columns", args.columns])
    command.extend(shared_connection_args(args, connection))
    return command


def build_list_command(args: argparse.Namespace, connection: dict) -> list[str]:
    fetch_xml = resolve_fetchxml(args)
    command = ["query", "--fetchxml", fetch_xml, "--max-rows", str(args.max_rows)]
    if args.page_size:
        command.extend(["--page-size", str(args.page_size)])
    if args.exact_total:
        command.append("--exact-total")
    command.extend(shared_connection_args(args, connection))
    return command


def resolve_fetchxml(args: argparse.Namespace) -> str:
    if args.fetchxml:
        candidate = Path(args.fetchxml)
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
        return args.fetchxml
    if args.spec:
        spec = read_json_argument(args.spec)
        if not isinstance(spec, dict):
            raise SystemExit("ERROR: --spec must resolve to a JSON object.")
        return build_query_design(spec)["fetchXml"]
    raise SystemExit("ERROR: list mode requires --fetchxml or --spec.")


if __name__ == "__main__":
    raise SystemExit(main())
