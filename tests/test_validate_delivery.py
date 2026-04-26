from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_delivery  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "discover_context"


class ValidateDeliveryTests(unittest.TestCase):
    def test_build_live_mutation_preflight_reports_required_gate_fields(self) -> None:
        payload = validate_delivery.build_live_mutation_preflight(
            repo=REPO_ROOT,
            spec={
                "environmentUrl": "https://contoso-dev.crm.dynamics.com",
                "activePacProfile": "contoso-dev",
                "targetSolutionUniqueName": "ContosoCore_Patch_001",
                "mutationType": "ribbon",
                "components": [
                    {
                        "type": "systemform",
                        "name": "account:Information",
                    }
                ],
                "deliveryPrimitive": "patch-form-ribbon",
                "blastRadius": "targeted",
                "rollbackPlan": "Restore the previous RibbonDiffXml from source control.",
                "fallbackPath": "Stop and ask before solution import.",
            },
        )

        self.assertTrue(payload["success"])
        self.assertEqual(payload["mode"], "live-mutation-preflight")
        self.assertEqual(payload["environmentUrl"], "https://contoso-dev.crm.dynamics.com")
        self.assertEqual(payload["activePacProfile"], "contoso-dev")
        self.assertEqual(payload["targetSolutionUniqueName"], "ContosoCore_Patch_001")
        self.assertEqual(payload["mutationType"], "ribbon")
        self.assertEqual(payload["deliveryPrimitive"], "patch-form-ribbon")
        self.assertEqual(payload["blastRadius"], "targeted")
        self.assertFalse(payload["requiresConfirmation"])
        self.assertEqual(payload["componentCount"], 1)
        self.assertEqual(payload["components"][0]["type"], "systemform")

    def test_build_live_mutation_preflight_requires_confirmation_for_solution_import(self) -> None:
        payload = validate_delivery.build_live_mutation_preflight(
            repo=REPO_ROOT,
            spec={
                "environmentUrl": "https://contoso-dev.crm.dynamics.com",
                "targetSolutionUniqueName": "ContosoCore",
                "mutationType": "solution-import",
                "components": [{"type": "webresource", "name": "contoso_/Account.js"}],
                "deliveryPrimitive": "deploy-solution",
                "blastRadius": "whole-solution",
                "rollbackPlan": "Restore from exported backup package.",
                "fallbackPath": "Use targeted sync if possible.",
            },
        )

        self.assertTrue(payload["requiresConfirmation"])
        self.assertIn("whole-solution", payload["confirmationReason"])

    def test_build_artifact_metadata_blocks_stale_release_zip_without_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            artifact = repo / "Solutions" / "bin" / "Release" / "ContosoCore.zip"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"stale package")

            with self.assertRaises(RuntimeError):
                validate_delivery.build_artifact_metadata(
                    repo=repo,
                    artifact_path=artifact,
                    generated_this_session=False,
                    explicit_user_selection=False,
                )

    def test_build_artifact_metadata_allows_explicitly_selected_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            artifact = repo / "Solutions" / "bin" / "Release" / "ContosoCore.zip"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"selected package")

            metadata = validate_delivery.build_artifact_metadata(
                repo=repo,
                artifact_path=artifact,
                generated_this_session=False,
                explicit_user_selection=True,
            )

        self.assertEqual(metadata["path"], str(artifact))
        self.assertFalse(metadata["generatedThisSession"])
        self.assertTrue(metadata["explicitUserSelection"])
        self.assertEqual(metadata["staleRisk"], "allowed-explicit-selection")

    def test_run_solution_pack_check_warns_when_only_supporting_solution_source_exists(self) -> None:
        result = validate_delivery.run_solution_pack_check(
            FIXTURES_ROOT / "supporting_solution_only_repo",
            solution_folder=None,
            zipfile=None,
            checker_output=None,
            run_solution_check=False,
            environment_url=None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "warning")

    def test_main_reports_discovery_summary_from_inferred_context(self) -> None:
        discovery = {
            "inferred": {
                "repo_archetype": "solution-centric-dataverse",
                "solution_source_model": "unpacked-solution-source",
            }
        }

        with mock.patch.object(validate_delivery, "discover_repo_context", return_value=discovery), \
             mock.patch.object(validate_delivery, "repo_root", return_value=REPO_ROOT), \
             mock.patch.object(validate_delivery, "write_json_output") as write_json_output:
            with mock.patch.object(
                sys,
                "argv",
                [
                    "validate_delivery.py",
                    "--repo-root",
                    str(REPO_ROOT),
                    "--skip-plugin-build",
                    "--skip-pcf-build",
                    "--skip-word-templates",
                    "--skip-solution-pack",
                ],
            ):
                exit_code = validate_delivery.main()

        self.assertEqual(exit_code, 0)
        payload = write_json_output.call_args.args[0]
        self.assertEqual(payload["discovery"]["repoArchetype"], "solution-centric-dataverse")
        self.assertEqual(payload["discovery"]["solutionSourceModel"], "unpacked-solution-source")


if __name__ == "__main__":
    unittest.main()
