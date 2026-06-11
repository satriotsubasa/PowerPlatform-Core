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
import create_security_role  # type: ignore
import inspect_security_role  # type: ignore


class SecurityRoleRequirementSpecTests(unittest.TestCase):
    def test_expand_requirement_spec_includes_security_role_steps(self) -> None:
        requirement = {
            "securityRoles": {
                "inspections": [{"mode": "inspect", "name": "Contoso App User"}],
                "creations": [{"name": "Contoso App User"}],
                "updates": [{"name": "Contoso App User"}],
            }
        }

        steps = apply_requirement_spec.expand_requirement_spec(requirement)

        self.assertEqual(
            [step["type"] for step in steps],
            [
                "inspect-security-role",
                "create-security-role",
                "update-security-role",
            ],
        )


class SecurityRoleScriptTests(unittest.TestCase):
    def test_create_security_role_injects_selected_solution(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured["command"] = command
            captured["cwd"] = cwd
            spec_path = Path(command[command.index("--spec-file") + 1])
            captured["spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            create_security_role,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
            },
        ), mock.patch.object(create_security_role, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "create_security_role.py",
                    "--spec",
                    '{"name":"Contoso App User"}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = create_security_role.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["command"][:4], ["securityrole", "--mode", "create", "--spec-file"])
        self.assertEqual(captured["spec"], {"name": "Contoso App User", "solutionUniqueName": "ContosoApp"})

    def test_inspect_security_role_keeps_solution_scope_explicit(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured["command"] = command
            spec_path = Path(command[command.index("--spec-file") + 1])
            captured["spec"] = json.loads(spec_path.read_text(encoding="utf-8"))
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            inspect_security_role,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
                "solution_unique_name": "ContosoApp",
            },
        ), mock.patch.object(inspect_security_role, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "inspect_security_role.py",
                    "--spec",
                    '{"mode":"list","includePrivileges":false}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = inspect_security_role.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["command"][:4], ["securityrole", "--mode", "list", "--spec-file"])
        self.assertEqual(captured["spec"], {"mode": "list", "includePrivileges": False})


if __name__ == "__main__":
    unittest.main()
