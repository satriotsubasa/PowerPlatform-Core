from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import create_environment_variable_definition as creator  # type: ignore


def _run(argv: list[str], connection: dict) -> dict:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
        captured["command"] = command
        spec_path = Path(command[command.index("--spec-file") + 1])
        captured["spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
        captured["spec_path"] = spec_path
        return SimpleNamespace(stdout="{}")

    with mock.patch.object(creator, "resolve_live_connection", return_value=connection), mock.patch.object(
        creator, "run_dataverse_tool", side_effect=fake_run
    ):
        with mock.patch.object(sys, "argv", argv):
            captured["exit_code"] = creator.main()
    return captured


class CreateEnvVarDefinitionTests(unittest.TestCase):
    def test_builds_create_definition_command_with_serialized_spec_and_auth(self) -> None:
        captured = _run(
            [
                "create_environment_variable_definition.py",
                "--spec",
                '{"schemaName":"contoso_ApiUrl","displayName":"API URL","type":"string"}',
            ],
            {"environment_url": "https://contoso.crm.dynamics.com", "username": "user@contoso.com", "tenant_id": None},
        )

        self.assertEqual(captured["exit_code"], 0)
        command = captured["command"]
        self.assertEqual(command[:4], ["envvar", "--mode", "create-definition", "--spec-file"])
        # The spec is serialized to the temp file intact.
        self.assertEqual(
            captured["spec"], {"schemaName": "contoso_ApiUrl", "displayName": "API URL", "type": "string"}
        )
        # Auth wiring is passed through.
        self.assertIn("--environment-url", command)
        self.assertIn("https://contoso.crm.dynamics.com", command)
        self.assertIn("--username", command)
        self.assertIn("user@contoso.com", command)
        self.assertIn("--auth-flow", command)
        # tenant_id is None here, so --tenant-id must be omitted.
        self.assertNotIn("--tenant-id", command)
        # The temp spec file is cleaned up in the finally block.
        self.assertFalse(captured["spec_path"].exists())

    def test_includes_tenant_id_when_present(self) -> None:
        captured = _run(
            [
                "create_environment_variable_definition.py",
                "--spec",
                '{"schemaName":"contoso_ApiUrl","displayName":"API URL","type":"secret"}',
            ],
            {"environment_url": "https://contoso.crm.dynamics.com", "username": "user@contoso.com", "tenant_id": "tid-123"},
        )

        command = captured["command"]
        self.assertIn("--tenant-id", command)
        self.assertIn("tid-123", command)

    def test_rejects_non_object_spec(self) -> None:
        with mock.patch.object(sys, "argv", ["create_environment_variable_definition.py", "--spec", "[]"]):
            self.assertEqual(creator.main(), 2)


if __name__ == "__main__":
    unittest.main()
