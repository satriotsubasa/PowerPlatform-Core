from __future__ import annotations

import io
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
import deploy_solution  # type: ignore


class DeploySolutionSafetyTests(unittest.TestCase):
    def test_infer_deployment_change_scope_detects_targeted_component_requirement(self) -> None:
        requirement = {
            "mainForms": [{"tableLogicalName": "contoso_requestline", "formName": "Information"}],
            "webResources": [{"name": "contoso_/RequestLine.js", "path": "WebResources/JScript/RequestLine.js"}],
            "deployment": {},
        }
        steps = apply_requirement_spec.expand_requirement_spec(requirement)

        scope = apply_requirement_spec.infer_deployment_change_scope(steps)

        self.assertEqual(scope, "targeted-component")

    def test_run_deploy_solution_helper_passes_inferred_change_scope(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_command(command: list[str], *, cwd: Path | None = None, check: bool = True) -> SimpleNamespace:
            captured["command"] = command
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(apply_requirement_spec, "run_command", side_effect=fake_run_command):
            apply_requirement_spec.run_deploy_solution_helper(
                {"changeScope": "targeted-component"},
                repo=Path.cwd(),
                connection={"environment_url": "https://contoso.crm.dynamics.com"},
            )

        self.assertIn("--change-scope", captured["command"])
        scope_index = captured["command"].index("--change-scope") + 1
        self.assertEqual(captured["command"][scope_index], "targeted-component")

    def test_deploy_solution_blocks_targeted_component_import_without_explicit_override(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            [
                "deploy_solution.py",
                "--repo-root",
                str(Path.cwd()),
                "--change-scope",
                "targeted-component",
            ],
        ):
            with self.assertRaises(RuntimeError):
                with redirect_stdout(io.StringIO()):
                    deploy_solution.main()

    def test_deploy_solution_allows_targeted_component_import_with_explicit_override(self) -> None:
        executed: list[list[str]] = []

        def fake_run_command(
            args: list[str],
            *,
            cwd: Path | None = None,
            check: bool = True,
            retries: int | None = None,
            wait_seconds: int | None = None,
        ) -> SimpleNamespace:
            executed.append(args)
            return SimpleNamespace(stdout="")

        with mock.patch.object(deploy_solution, "infer_unpacked_solution_folder", return_value=Path.cwd() / "Dataverse" / "Main"), \
             mock.patch.object(deploy_solution, "resolve_environment_url", return_value="https://contoso.crm.dynamics.com"), \
             mock.patch.object(deploy_solution, "run_command", side_effect=fake_run_command), \
             mock.patch.object(deploy_solution, "run_command_with_dataverse_lock_retry", side_effect=fake_run_command), \
             mock.patch.object(deploy_solution, "write_json_output"):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "deploy_solution.py",
                    "--repo-root",
                    str(Path.cwd()),
                    "--change-scope",
                    "targeted-component",
                    "--allow-broad-import",
                ],
            ):
                exit_code = deploy_solution.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(executed[0][:3], ["pac", "solution", "pack"])
        self.assertEqual(executed[1][:3], ["pac", "solution", "import"])


if __name__ == "__main__":
    unittest.main()
