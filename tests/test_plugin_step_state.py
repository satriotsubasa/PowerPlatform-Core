from __future__ import annotations

import importlib
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

import powerplatform_common  # type: ignore


class PluginStepStateProfileTests(unittest.TestCase):
    def test_build_plugin_step_state_contract_from_profile_infers_enabled_and_disabled_targets(self) -> None:
        raw_profile = {
            "criticalPluginSteps": [
                "Account Create",
                {
                    "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
                    "messageName": "Update",
                    "primaryEntityLogicalName": "account",
                    "stage": "PreOperation",
                },
            ],
            "intentionallyDisabledPluginSteps": [
                {
                    "name": "Account Archive",
                    "mode": "Synchronous",
                }
            ],
        }

        contract = powerplatform_common.build_plugin_step_state_contract_from_profile(raw_profile)

        self.assertEqual(
            contract,
            [
                {"name": "Account Create", "desiredState": "Enabled"},
                {
                    "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
                    "messageName": "Update",
                    "primaryEntityLogicalName": "account",
                    "stage": "PreOperation",
                    "desiredState": "Enabled",
                },
                {
                    "name": "Account Archive",
                    "mode": "Synchronous",
                    "desiredState": "Disabled",
                },
            ],
        )

    def test_apply_plugin_step_state_defaults_to_registration_spec_sets_missing_states(self) -> None:
        spec = {
            "steps": [
                {"name": "Account Create", "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin", "messageName": "Create"},
                {
                    "name": "Account Archive",
                    "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
                    "messageName": "Update",
                    "desiredState": "Disabled",
                },
                {
                    "name": "Contact Update",
                    "pluginTypeName": "Contoso.Sample.Plugins.ContactPlugin",
                    "messageName": "Update",
                },
            ]
        }
        contract = [
            {"name": "Account Create", "desiredState": "Enabled"},
            {"name": "Account Archive", "desiredState": "Disabled"},
        ]

        enriched = powerplatform_common.apply_plugin_step_state_defaults_to_registration_spec(spec, contract)

        self.assertEqual(
            enriched["steps"],
            [
                {
                    "name": "Account Create",
                    "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
                    "messageName": "Create",
                    "desiredState": "Enabled",
                },
                {
                    "name": "Account Archive",
                    "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
                    "messageName": "Update",
                    "desiredState": "Disabled",
                },
                {
                    "name": "Contact Update",
                    "pluginTypeName": "Contoso.Sample.Plugins.ContactPlugin",
                    "messageName": "Update",
                    "desiredState": "Enabled",
                },
            ],
        )


class PluginStepStateScriptTests(unittest.TestCase):
    def test_inspect_plugin_steps_injects_selected_solution_and_uses_plugin_tool(self) -> None:
        inspect_plugin_steps = importlib.import_module("inspect_plugin_steps")
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured["command"] = command
            spec_path = Path(command[command.index("--spec-file") + 1])
            captured["spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            inspect_plugin_steps,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
            },
        ), mock.patch.object(inspect_plugin_steps, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "inspect_plugin_steps.py",
                    "--spec",
                    '{"pluginId":"11111111-1111-1111-1111-111111111111","pluginType":"Assembly"}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = inspect_plugin_steps.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["command"][:4], ["plugin", "--mode", "list-steps", "--spec-file"])
        self.assertEqual(
            captured["spec"],
            {
                "pluginId": "11111111-1111-1111-1111-111111111111",
                "pluginType": "Assembly",
                "solutionUniqueName": "ContosoApp",
            },
        )

    def test_ensure_plugin_step_state_injects_selected_solution_and_uses_plugin_tool(self) -> None:
        ensure_plugin_step_state = importlib.import_module("ensure_plugin_step_state")
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured["command"] = command
            spec_path = Path(command[command.index("--spec-file") + 1])
            captured["spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            ensure_plugin_step_state,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
            },
        ), mock.patch.object(ensure_plugin_step_state, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "ensure_plugin_step_state.py",
                    "--spec",
                    '{"pluginId":"11111111-1111-1111-1111-111111111111","pluginType":"Assembly","steps":[{"name":"Account Create","desiredState":"Enabled"}]}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = ensure_plugin_step_state.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["command"][:4], ["plugin", "--mode", "ensure-step-state", "--spec-file"])
        self.assertEqual(
            captured["spec"],
            {
                "pluginId": "11111111-1111-1111-1111-111111111111",
                "pluginType": "Assembly",
                "steps": [{"name": "Account Create", "desiredState": "Enabled"}],
                "solutionUniqueName": "ContosoApp",
            },
        )

    def test_push_plugin_verification_fails_when_existing_step_becomes_disabled(self) -> None:
        import push_plugin  # type: ignore

        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            project_path = repo / "Contoso.Sample.Plugins.csproj"
            plugin_file = repo / "bin" / "Debug" / "net462" / "Contoso.Sample.Plugins.dll"
            plugin_file.parent.mkdir(parents=True, exist_ok=True)
            project_path.write_text("<Project />", encoding="utf-8")
            plugin_file.write_bytes(b"placeholder")

            pre_push = {
                "success": True,
                "steps": [
                    {
                        "sdkMessageProcessingStepId": "22222222-2222-2222-2222-222222222222",
                        "name": "Account Create",
                        "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
                        "messageName": "Create",
                        "primaryEntityLogicalName": "account",
                        "stage": 20,
                        "mode": 0,
                        "stateCode": 0,
                        "stateLabel": "Enabled",
                    }
                ],
            }
            post_push = {
                "success": True,
                "steps": [
                    {
                        "sdkMessageProcessingStepId": "22222222-2222-2222-2222-222222222222",
                        "name": "Account Create",
                        "pluginTypeName": "Contoso.Sample.Plugins.AccountPlugin",
                        "messageName": "Create",
                        "primaryEntityLogicalName": "account",
                        "stage": 20,
                        "mode": 0,
                        "stateCode": 1,
                        "stateLabel": "Disabled",
                    }
                ],
            }

            with mock.patch.object(push_plugin, "inspect_plugin_steps_payload", side_effect=[pre_push, post_push]), mock.patch.object(
                push_plugin,
                "resolve_live_connection",
                return_value={
                    "environment_url": "https://contoso.crm.dynamics.com",
                    "username": "user@contoso.com",
                    "tenant_id": "tenant-id",
                    "solution_unique_name": "ContosoApp",
                },
            ), mock.patch.object(push_plugin, "run_command", return_value=SimpleNamespace(stdout="", stderr="", returncode=0)):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "push_plugin.py",
                        "--repo-root",
                        str(repo),
                        "--project",
                        str(project_path),
                        "--plugin-id",
                        "11111111-1111-1111-1111-111111111111",
                        "--plugin-file",
                        str(plugin_file),
                        "--environment-url",
                        "https://contoso.crm.dynamics.com",
                        "--verify-step-state",
                    ],
                ):
                    with self.assertRaises(RuntimeError) as raised:
                        with redirect_stdout(io.StringIO()):
                            push_plugin.main()

            self.assertIn("Account Create", str(raised.exception))
            self.assertIn("Disabled", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
