from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import apply_requirement_spec  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "discover_context"


class ApplyRequirementSpecTests(unittest.TestCase):
    def test_expand_requirement_spec_includes_remaining_gap_sections(self) -> None:
        requirement = {
            "flows": {
                "connectorReviews": [{"name": "Notify flow", "clientData": {"properties": {"definition": {"actions": {}}}}}],
            },
            "queryDesigns": [{"tableLogicalName": "account", "select": ["name"]}],
            "documentGenerationPlans": [{"path": "Word Templates", "templateName": "sample.docx"}],
            "solutionPatchPlans": [{"mainSolutionUniqueName": "MainSolution", "selectedSolutionUniqueName": "MainSolution_Patch_001", "selectedIsPatch": True}],
        }

        steps = apply_requirement_spec.expand_requirement_spec(requirement)
        self.assertEqual(
            [step["type"] for step in steps],
            [
                "review-flow-connectors",
                "design-dataverse-query",
                "plan-document-generation",
                "plan-solution-patch-merge",
            ],
        )

    def test_expand_requirement_spec_includes_plugin_step_state_sections(self) -> None:
        requirement = {
            "plugins": {
                "stepInspections": [{"pluginId": "11111111-1111-1111-1111-111111111111", "pluginType": "Assembly"}],
                "stepStateEnsures": [
                    {
                        "pluginId": "11111111-1111-1111-1111-111111111111",
                        "pluginType": "Assembly",
                        "steps": [{"name": "Account Create", "desiredState": "Enabled"}],
                    }
                ],
            }
        }

        steps = apply_requirement_spec.expand_requirement_spec(requirement)
        self.assertEqual(
            [step["type"] for step in steps],
            [
                "inspect-plugin-steps",
                "ensure-plugin-step-state",
            ],
        )

    def test_flow_connector_review_only_requires_live_when_no_local_definition(self) -> None:
        self.assertFalse(
            apply_requirement_spec.step_requires_live_connection(
                {"type": "review-flow-connectors", "spec": {"clientData": {"properties": {"definition": {"actions": {}}}}}}
            )
        )
        self.assertTrue(
            apply_requirement_spec.step_requires_live_connection(
                {"type": "review-flow-connectors", "spec": {"name": "My Flow"}}
            )
        )

    def test_resolve_local_solution_info_returns_none_for_ambiguous_authoritative_solutions(self) -> None:
        repo = FIXTURES_ROOT / "multiple_primary_solutions_repo"
        discovery = {
            "artifacts": {
                "unpacked_solutions": [
                    {"solution_folder_relative_path": "Dataverse/Alpha", "solution_role": "dataverse-reference"},
                    {"solution_folder_relative_path": "Dataverse/Beta", "solution_role": "dataverse-reference"},
                ]
            }
        }

        self.assertIsNone(apply_requirement_spec.resolve_local_solution_info(repo, discovery))

    def test_should_ensure_dataverse_reference_for_supporting_only_solution_source(self) -> None:
        discovery = {
            "artifacts": {
                "solution_projects": [
                    {"relative_path": "Contoso.Controls.PCF/Solutions/Controls.cdsproj", "solution_role": "pcf-packaging"}
                ],
                "unpacked_solutions": [
                    {
                        "solution_folder_relative_path": "Contoso.Controls.PCF/Solutions/Controls",
                        "solution_role": "pcf-packaging",
                    }
                ],
            }
        }
        connection = {"solution_unique_name": "MainApp", "environment_url": "https://example.crm.dynamics.com"}

        self.assertTrue(
            apply_requirement_spec.should_ensure_dataverse_reference(
                discovery,
                live_required=True,
                use_auth_dialog=True,
                connection=connection,
            )
        )


if __name__ == "__main__":
    unittest.main()
