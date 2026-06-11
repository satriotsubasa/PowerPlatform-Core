from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import power_automate_common  # type: ignore
import powerplatform_common  # type: ignore
import update_flow  # type: ignore


def make_client_data(*, acquirer_actions: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "properties": {
            "definition": {
                "triggers": {
                    "manual": {
                        "type": "Request",
                        "kind": "Http",
                    }
                },
                "actions": {
                    "Determine_document_type": {
                        "type": "Switch",
                        "expression": "@triggerBody()?['documentType']",
                        "cases": {
                            "Case A": {
                                "actions": acquirer_actions
                                if acquirer_actions is not None
                                else {
                                    "List_rows_contoso_contacts": {"type": "OpenApiConnection"},
                                    "List_rows_contoso_authorisedcontacts": {"type": "OpenApiConnection"},
                                }
                            }
                        },
                        "default": {"actions": {}},
                    }
                },
            }
        }
    }


class FlowSemanticGuardTests(unittest.TestCase):
    def test_compare_flow_semantics_detects_non_empty_case_becoming_empty(self) -> None:
        baseline = make_client_data()
        proposed = make_client_data(acquirer_actions={})

        findings = power_automate_common.compare_flow_semantics(
            baseline,
            proposed,
            flow_guard=None,
            comparison_label="source-preflight",
        )

        self.assertTrue(findings)
        self.assertEqual(findings[0]["code"], "switch-case-became-empty")

    def test_compare_flow_semantics_enforces_required_switch_case_actions(self) -> None:
        proposed = make_client_data(
            acquirer_actions={
                "List_rows_contoso_contacts": {"type": "OpenApiConnection"},
            }
        )
        flow_guard = {
            "requiredSwitchCases": [
                {
                    "switchName": "Determine_document_type",
                    "caseName": "Case A",
                    "requiredActionNames": [
                        "List_rows_contoso_contacts",
                        "List_rows_contoso_authorisedcontacts",
                    ],
                }
            ]
        }

        findings = power_automate_common.compare_flow_semantics(
            None,
            proposed,
            flow_guard=flow_guard,
            comparison_label="source-preflight",
        )

        self.assertEqual(findings[0]["code"], "required-switch-case-actions-missing")
        self.assertEqual(findings[0]["missingActionNames"], ["List_rows_contoso_authorisedcontacts"])

    def test_load_flow_guard_contract_uses_project_profile_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / ".git").mkdir()
            (repo / ".codex").mkdir()
            guard_path = repo / ".codex" / "contoso.flow-guards.json"
            guard_path.write_text(
                json.dumps(
                    {
                        "flows": [
                            {
                                "match": {"displayName": "Contoso Flow"},
                                "requiredSwitchCases": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (repo / ".codex" / "power-platform.project-profile.json").write_text(
                json.dumps({"flowGuardSpecPath": ".codex/contoso.flow-guards.json"}),
                encoding="utf-8",
            )

            contract = powerplatform_common.load_flow_guard_contract(repo)

        self.assertEqual(contract.get("path"), str(guard_path.resolve()))
        self.assertEqual(contract.get("raw", {}).get("flows", [])[0]["match"]["displayName"], "Contoso Flow")


class UpdateFlowGuardTests(unittest.TestCase):
    def test_update_flow_blocks_semantic_regression_before_deploy(self) -> None:
        dataverse_commands: list[list[str]] = []

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            dataverse_commands.append(command)
            if command[:3] == ["flow", "--mode", "inspect"]:
                return SimpleNamespace(
                    stdout=json.dumps(
                        {
                            "success": True,
                            "flow": {
                                "workflowId": "11111111-1111-1111-1111-111111111111",
                                "name": "Contoso Flow",
                                "clientData": json.dumps(make_client_data()),
                            },
                        }
                    )
                )

            if command[:3] == ["flow", "--mode", "update"]:
                raise AssertionError("Update should not run when semantic drift is detected.")

            raise AssertionError(f"Unexpected Dataverse command: {command}")

        with mock.patch.object(
            update_flow,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
            },
        ), mock.patch.object(update_flow, "run_dataverse_tool", side_effect=fake_run_dataverse_tool), mock.patch.object(
            update_flow, "load_flow_guard_contract", return_value={"raw": {}}
        ):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "update_flow.py",
                    "--spec",
                    json.dumps(
                        {
                            "name": "Contoso Flow",
                            "clientData": make_client_data(acquirer_actions={}),
                        }
                    ),
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with self.assertRaises(RuntimeError):
                    with redirect_stdout(io.StringIO()):
                        update_flow.main()

        self.assertEqual(dataverse_commands[0][:3], ["flow", "--mode", "inspect"])

    def test_update_flow_allows_explicit_semantic_drift_override(self) -> None:
        dataverse_commands: list[list[str]] = []
        inspect_call_count = 0

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            nonlocal inspect_call_count
            dataverse_commands.append(command)
            if command[:3] == ["flow", "--mode", "inspect"]:
                inspect_call_count += 1
                return SimpleNamespace(
                    stdout=json.dumps(
                        {
                            "success": True,
                            "flow": {
                                "workflowId": "11111111-1111-1111-1111-111111111111",
                                "name": "Contoso Flow",
                                "clientData": json.dumps(
                                    make_client_data()
                                    if inspect_call_count == 1
                                    else make_client_data(acquirer_actions={})
                                ),
                            },
                        }
                    )
                )

            if command[:3] == ["flow", "--mode", "update"]:
                return SimpleNamespace(stdout='{"success": true}')

            raise AssertionError(f"Unexpected Dataverse command: {command}")

        with mock.patch.object(
            update_flow,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
            },
        ), mock.patch.object(update_flow, "run_dataverse_tool", side_effect=fake_run_dataverse_tool), mock.patch.object(
            update_flow, "load_flow_guard_contract", return_value={"raw": {}}
        ):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "update_flow.py",
                    "--spec",
                    json.dumps(
                        {
                            "name": "Contoso Flow",
                            "clientData": make_client_data(acquirer_actions={}),
                        }
                    ),
                    "--repo-root",
                    str(Path.cwd()),
                    "--allow-semantic-drift",
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = update_flow.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            [command[:3] for command in dataverse_commands],
            [
                ["flow", "--mode", "inspect"],
                ["flow", "--mode", "update"],
                ["flow", "--mode", "inspect"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
