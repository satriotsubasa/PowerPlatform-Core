from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import plan_solution_patch_merge  # type: ignore


class PlanSolutionPatchMergeTests(unittest.TestCase):
    def test_continue_current_patch_recommends_patch_target_and_version_bump(self) -> None:
        payload = plan_solution_patch_merge.build_patch_plan(
            {
                "mainSolutionUniqueName": "ContosoOperatingSystem",
                "selectedSolutionUniqueName": "ContosoOperatingSystem_Patch_88524e5b",
                "selectedIsPatch": True,
                "selectedVersion": "1.1.1.0",
                "parentSolutionUniqueName": "ContosoOperatingSystem",
            }
        )

        self.assertEqual(payload["intent"], "continue-current-patch")
        self.assertEqual(payload["targetRecommendation"], "ContosoOperatingSystem_Patch_88524e5b")
        self.assertEqual(payload["recommendedNextVersion"], "1.1.1.1")

    def test_mismatched_parent_solution_emits_warning(self) -> None:
        payload = plan_solution_patch_merge.build_patch_plan(
            {
                "mainSolutionUniqueName": "MainSolution",
                "selectedSolutionUniqueName": "MainSolution_Patch_001",
                "selectedIsPatch": True,
                "selectedVersion": "2.0.0.0",
                "parentSolutionUniqueName": "DifferentParent",
                "intent": "continue-current-patch",
            }
        )

        self.assertTrue(any("parent does not match" in warning for warning in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
