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
import patch_form_ribbon  # type: ignore
import patch_form_xml  # type: ignore


class FormXmlPatchRequirementSpecTests(unittest.TestCase):
    def test_expand_requirement_spec_includes_form_xml_patch_sections(self) -> None:
        requirement = {
            "formXmlPatches": [
                {
                    "entityLogicalName": "account",
                    "formName": "Information",
                    "operations": [
                        {
                            "type": "replace-element",
                            "targetXPath": ".//header/cell[1]",
                            "xml": '<cell id="replacement" />',
                        }
                    ],
                }
            ],
            "formRibbonPatches": [
                {
                    "entityLogicalName": "account",
                    "formName": "Information",
                    "operations": [
                        {
                            "type": "append-child",
                            "targetXPath": ".",
                            "xml": "<CustomActions />",
                        }
                    ],
                }
            ],
        }

        steps = apply_requirement_spec.expand_requirement_spec(requirement)

        self.assertEqual(
            [step["type"] for step in steps],
            [
                "patch-form-xml",
                "patch-form-ribbon",
            ],
        )
        self.assertEqual(
            apply_requirement_spec.infer_deployment_change_scope(steps),
            "targeted-component",
        )


class FormXmlPatchScriptTests(unittest.TestCase):
    def test_patch_form_xml_uses_metadata_patch_form_xml_mode(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured["command"] = command
            captured["cwd"] = cwd
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            patch_form_xml,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
            },
        ), mock.patch.object(patch_form_xml, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "patch_form_xml.py",
                    "--spec",
                    '{"entityLogicalName":"account","formName":"Information","operations":[{"type":"replace-element","targetXPath":".//header/cell[1]","xml":"<cell id=\\"replacement\\" />"}]}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = patch_form_xml.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["command"][:3], ["metadata", "patch-form-xml", "--spec"])
        self.assertIn("--environment-url", captured["command"])
        self.assertIn("--username", captured["command"])

    def test_patch_form_ribbon_uses_metadata_patch_form_ribbon_mode(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            captured["command"] = command
            captured["cwd"] = cwd
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            patch_form_ribbon,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
            },
        ), mock.patch.object(patch_form_ribbon, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "patch_form_ribbon.py",
                    "--spec",
                    '{"entityLogicalName":"account","formName":"Information","operations":[{"type":"append-child","targetXPath":".","xml":"<CustomActions />"}]}',
                    "--repo-root",
                    str(Path.cwd()),
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = patch_form_ribbon.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["command"][:3], ["metadata", "patch-form-ribbon", "--spec"])
        self.assertIn("--environment-url", captured["command"])
        self.assertIn("--username", captured["command"])


if __name__ == "__main__":
    unittest.main()
