from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import register_plugin_package_headless as registrar  # type: ignore


class RegisterPluginPackageHeadlessTests(unittest.TestCase):
    def test_missing_nuspec_fields_do_not_set_none_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "Plugin.csproj"
            project_path.write_text("<Project />", encoding="utf-8")
            package_path = Path(temp_dir) / "Plugin.1.0.0.nupkg"
            package_path.write_text("placeholder", encoding="utf-8")

            captured: dict[str, object] = {}

            def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> object:
                spec_index = command.index("--spec") + 1
                captured["spec"] = json.loads(command[spec_index])
                return type("Result", (), {"stdout": "{}"})()

            with mock.patch.object(registrar, "repo_root", return_value=Path(temp_dir)), \
                 mock.patch.object(registrar, "infer_plugin_project", return_value=project_path), \
                 mock.patch.object(registrar, "infer_plugin_package_file", return_value=package_path), \
                 mock.patch.object(
                     registrar,
                     "read_nuget_metadata",
                     return_value={"id": None, "version": None, "title": None, "description": None},
                 ), \
                 mock.patch.object(
                     registrar,
                     "resolve_live_connection",
                     return_value={
                         "environment_url": "https://contoso.crm.dynamics.com",
                         "username": "user@contoso.com",
                         "tenant_id": None,
                     },
                 ), \
                 mock.patch.object(registrar, "apply_selected_solution_to_spec", side_effect=lambda spec, _conn: spec), \
                 mock.patch.object(registrar, "apply_plugin_step_state_defaults_to_registration_spec", side_effect=lambda spec, _contract: spec), \
                 mock.patch.object(registrar, "load_plugin_step_state_contract", return_value={}), \
                 mock.patch.object(registrar, "run_dataverse_tool", side_effect=fake_run_dataverse_tool), \
                 mock.patch.object(
                     sys,
                     "argv",
                     ["register_plugin_package_headless.py", "--spec", "{}", "--skip-pack"],
                 ):
                exit_code = registrar.main()

        self.assertEqual(exit_code, 0)
        spec = captured["spec"]
        # A missing nuspec field must never be defaulted to None.
        self.assertNotIn("uniqueName", spec)
        self.assertNotIn("name", spec)
        self.assertNotIn("version", spec)
        for key, value in spec.items():
            self.assertIsNotNone(value, msg=f"spec['{key}'] should not be None")

    def test_present_nuspec_fields_populate_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "Plugin.csproj"
            project_path.write_text("<Project />", encoding="utf-8")
            package_path = Path(temp_dir) / "Plugin.1.0.0.nupkg"
            package_path.write_text("placeholder", encoding="utf-8")

            captured: dict[str, object] = {}

            def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> object:
                spec_index = command.index("--spec") + 1
                captured["spec"] = json.loads(command[spec_index])
                return type("Result", (), {"stdout": "{}"})()

            with mock.patch.object(registrar, "repo_root", return_value=Path(temp_dir)), \
                 mock.patch.object(registrar, "infer_plugin_project", return_value=project_path), \
                 mock.patch.object(registrar, "infer_plugin_package_file", return_value=package_path), \
                 mock.patch.object(
                     registrar,
                     "read_nuget_metadata",
                     return_value={"id": "Contoso.Plugins", "version": "1.0.0", "title": "Contoso Plugins", "description": "Desc"},
                 ), \
                 mock.patch.object(
                     registrar,
                     "resolve_live_connection",
                     return_value={
                         "environment_url": "https://contoso.crm.dynamics.com",
                         "username": "user@contoso.com",
                         "tenant_id": None,
                     },
                 ), \
                 mock.patch.object(registrar, "apply_selected_solution_to_spec", side_effect=lambda spec, _conn: spec), \
                 mock.patch.object(registrar, "apply_plugin_step_state_defaults_to_registration_spec", side_effect=lambda spec, _contract: spec), \
                 mock.patch.object(registrar, "load_plugin_step_state_contract", return_value={}), \
                 mock.patch.object(registrar, "run_dataverse_tool", side_effect=fake_run_dataverse_tool), \
                 mock.patch.object(
                     sys,
                     "argv",
                     ["register_plugin_package_headless.py", "--spec", "{}", "--skip-pack"],
                 ):
                exit_code = registrar.main()

        self.assertEqual(exit_code, 0)
        spec = captured["spec"]
        self.assertEqual(spec["uniqueName"], "Contoso.Plugins")
        self.assertEqual(spec["name"], "Contoso Plugins")
        self.assertEqual(spec["version"], "1.0.0")
        self.assertEqual(spec["description"], "Desc")


if __name__ == "__main__":
    unittest.main()
