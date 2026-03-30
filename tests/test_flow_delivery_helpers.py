from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import apply_requirement_spec  # type: ignore
import get_flow_trigger_url  # type: ignore
import set_environment_variable_value  # type: ignore


class FlowDeliveryRequirementSpecTests(unittest.TestCase):
    def test_expand_requirement_spec_includes_flow_trigger_and_envvar_steps(self) -> None:
        requirement = {
            "flows": {
                "triggerUrls": [{"name": "Contoso HTTP Flow"}],
            },
            "environmentVariables": {
                "valueSets": [{"schemaName": "contoso_CallbackUrl", "value": "https://example.test"}],
            },
        }

        steps = apply_requirement_spec.expand_requirement_spec(requirement)

        self.assertEqual(
            [step["type"] for step in steps],
            [
                "get-flow-trigger-url",
                "set-environment-variable-value",
            ],
        )


class FlowDeliveryScriptTests(unittest.TestCase):
    def test_get_flow_trigger_url_injects_selected_solution_and_uses_auth_payload_whoami(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured.setdefault("dataverse_commands", []).append(command)
            if command[0] == "flow":
                spec_path = Path(command[command.index("--spec-file") + 1])
                captured["inspect_spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
                flow_payload = {
                    "success": True,
                    "flow": {
                        "workflowId": "11111111-1111-1111-1111-111111111111",
                        "name": "Contoso HTTP Flow",
                        "definitionSummary": {
                            "triggerNames": ["manual"],
                        },
                        "clientData": json.dumps(
                            {
                                "properties": {
                                    "definition": {
                                        "triggers": {
                                            "manual": {
                                                "type": "Request",
                                                "kind": "Http",
                                            }
                                        }
                                    }
                                }
                            }
                        ),
                    },
                }
                return SimpleNamespace(stdout=json.dumps(flow_payload))

            raise AssertionError(f"Unexpected Dataverse command: {command}")

        def fake_run_command(command: list[str], *, cwd: Path | None = None, check: bool = True) -> SimpleNamespace:
            captured["powershell_command"] = command
            spec_path = Path(command[command.index("-SpecFile") + 1])
            captured["powershell_spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
            return SimpleNamespace(stdout='{"success": true, "callbackUrl": "https://example.test"}')

        with mock.patch.object(
            get_flow_trigger_url,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
                "auth_payload": {
                    "whoAmI": {
                        "organizationId": "22222222-2222-2222-2222-222222222222",
                    }
                },
            },
        ), mock.patch.object(get_flow_trigger_url, "run_dataverse_tool", side_effect=fake_run_dataverse_tool), mock.patch.object(
            get_flow_trigger_url, "run_command", side_effect=fake_run_command
        ):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "get_flow_trigger_url.py",
                    "--spec",
                    '{"name":"Contoso HTTP Flow"}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = get_flow_trigger_url.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            captured["inspect_spec"],
            {
                "name": "Contoso HTTP Flow",
                "solutionUniqueName": "ContosoApp",
                "includeClientData": True,
            },
        )
        self.assertEqual(
            captured["powershell_spec"],
            {
                "environmentUrl": "https://contoso.crm.dynamics.com",
                "organizationId": "22222222-2222-2222-2222-222222222222",
                "triggerName": "manual",
                "workflowId": "11111111-1111-1111-1111-111111111111",
                "workflowName": "Contoso HTTP Flow",
            },
        )

    def test_set_environment_variable_value_uses_envvar_tool(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured["command"] = command
            spec_path = Path(command[command.index("--spec-file") + 1])
            captured["spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            set_environment_variable_value,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
            },
        ), mock.patch.object(set_environment_variable_value, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "set_environment_variable_value.py",
                    "--spec",
                    '{"schemaName":"contoso_CallbackUrl","value":"https://example.test"}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = set_environment_variable_value.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["command"][:4], ["envvar", "--mode", "set-value", "--spec-file"])
        self.assertEqual(
            captured["spec"],
            {
                "schemaName": "contoso_CallbackUrl",
                "value": "https://example.test",
            },
        )


if __name__ == "__main__":
    unittest.main()
