#!/usr/bin/env python3
"""Create or update multiple Dataverse web resources from local files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from powerplatform_common import (
    apply_selected_solution_to_spec,
    read_json_argument,
    repo_root,
    resolve_live_connection,
    run_dataverse_tool,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or update multiple Dataverse web resources through the shared SDK helper.",
    )
    parser.add_argument("--spec", required=True, help="JSON object or path to a JSON file describing the batch sync.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve relative file paths inside the batch spec.")
    parser.add_argument("--environment-url", help="Target Dataverse environment URL.")
    parser.add_argument("--target-url", help="Target org URL or Power Apps environment or solution URL for the auth dialog.")
    parser.add_argument("--username", help="Username for Dataverse authentication.")
    parser.add_argument("--tenant-id", help="Tenant ID for Dataverse authentication.")
    parser.add_argument("--auth-dialog", action="store_true", help="Launch the reusable auth dialog before syncing web resources.")
    parser.add_argument("--auto-validate", action="store_true", help="Start the auth dialog validation automatically when the dialog opens.")
    parser.add_argument(
        "--auth-flow",
        choices=["auto", "devicecode", "interactive"],
        default="auto",
        help="Authentication flow for the shared Dataverse SDK tool when the auth dialog is not used.",
    )
    parser.add_argument("--force-prompt", action="store_true", help="Force an interactive auth prompt instead of using a cached MSAL token.")
    parser.add_argument("--verbose", action="store_true", help="Print Dataverse SDK auth diagnostics to stderr.")
    args = parser.parse_args()

    batch_spec = read_json_argument(args.spec)
    if not isinstance(batch_spec, dict):
        print("ERROR: --spec must resolve to a JSON object.", file=sys.stderr)
        return 2

    items = batch_spec.get("items")
    if not isinstance(items, list) or not items:
        print("ERROR: Batch spec must contain a non-empty 'items' array.", file=sys.stderr)
        return 2

    repo = repo_root(Path(args.repo_root))
    connection = resolve_live_connection(
        environment_url=args.environment_url,
        username=args.username,
        tenant_id=args.tenant_id,
        auth_dialog=args.auth_dialog,
        target_url=args.target_url,
        auto_validate=args.auto_validate,
    )
    publish_after_all = bool(batch_spec.get("publishAfterAll"))
    continue_on_error = bool(batch_spec.get("continueOnError"))
    default_publish = bool(batch_spec.get("publish"))

    results = []
    changed_and_requested_publish: list[str] = []
    success = True
    error_message = None

    for index, raw_item in enumerate(items, start=1):
        if not isinstance(raw_item, dict):
            print(f"ERROR: items[{index}] must be a JSON object.", file=sys.stderr)
            return 2

        item = apply_selected_solution_to_spec(dict(raw_item), connection)
        if "filePath" in item and isinstance(item["filePath"], str):
            candidate = Path(item["filePath"])
            if not candidate.is_absolute():
                item["filePath"] = str((repo / candidate).resolve())

        per_item_publish = bool(item.get("publish", default_publish))
        if publish_after_all:
            item["publish"] = False

        command = [
            "webresource",
            "--mode",
            "sync-file",
            "--spec",
            json.dumps(item),
            "--environment-url",
            connection["environment_url"],
            "--username",
            connection["username"],
            "--auth-flow",
            args.auth_flow,
        ]
        if connection["tenant_id"]:
            command.extend(["--tenant-id", connection["tenant_id"]])
        if args.force_prompt:
            command.append("--force-prompt")
        if args.verbose:
            command.append("--verbose")

        try:
            completed = run_dataverse_tool(command, cwd=repo)
            payload = json.loads(completed.stdout)
            results.append(
                {
                    "index": index,
                    "success": True,
                    "name": item.get("name"),
                    "result": payload,
                }
            )
            if per_item_publish and payload.get("changed") and isinstance(item.get("name"), str):
                changed_and_requested_publish.append(item["name"])
        except Exception as exc:
            success = False
            error_message = str(exc)
            results.append(
                {
                    "index": index,
                    "success": False,
                    "name": item.get("name"),
                    "error": str(exc),
                }
            )
            if not continue_on_error:
                break

    publish_result = None
    if publish_after_all and changed_and_requested_publish:
        command = [
            "webresource",
            "--mode",
            "publish-many",
            "--spec",
            json.dumps({"names": changed_and_requested_publish}),
            "--environment-url",
            connection["environment_url"],
            "--username",
            connection["username"],
            "--auth-flow",
            args.auth_flow,
        ]
        if connection["tenant_id"]:
            command.extend(["--tenant-id", connection["tenant_id"]])
        if args.force_prompt:
            command.append("--force-prompt")
        if args.verbose:
            command.append("--verbose")
        completed = run_dataverse_tool(command, cwd=repo)
        publish_result = json.loads(completed.stdout)

    payload = {
        "success": success,
        "mode": "sync-webresources-batch",
        "publishAfterAll": publish_after_all,
        "publishedNames": changed_and_requested_publish if publish_after_all else [],
        "publishResult": publish_result,
        "results": results,
    }
    if error_message:
        payload["error"] = error_message

    print(json.dumps(payload, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
