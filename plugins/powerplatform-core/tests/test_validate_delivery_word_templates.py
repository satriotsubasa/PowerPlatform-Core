from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_delivery as vd  # type: ignore


class WordTemplateAutoSkipTests(unittest.TestCase):
    def test_absent_area_warns_and_passes_without_running_the_check(self) -> None:
        with mock.patch.object(vd, "discover_repo_context", return_value={"inferred": {}}), mock.patch.object(
            vd, "run_command"
        ) as run_command:
            result = vd.run_word_template_check(Path("."), None)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "warning")
        run_command.assert_not_called()

    def test_discovered_area_still_runs_the_check(self) -> None:
        completed = SimpleNamespace(stdout='{"templates": []}')
        with mock.patch.object(
            vd, "discover_repo_context", return_value={"inferred": {"word_templates_area": "Word Templates"}}
        ), mock.patch.object(vd, "run_command", return_value=completed) as run_command:
            result = vd.run_word_template_check(Path("."), None)

        self.assertTrue(result["success"])
        run_command.assert_called_once()

    def test_explicit_path_forces_the_check_even_when_undiscovered(self) -> None:
        completed = SimpleNamespace(stdout='{"templates": []}')
        with mock.patch.object(vd, "discover_repo_context", return_value={"inferred": {}}), mock.patch.object(
            vd, "run_command", return_value=completed
        ) as run_command:
            result = vd.run_word_template_check(Path("."), "Some/Explicit/Templates")

        self.assertTrue(result["success"])
        run_command.assert_called_once()


if __name__ == "__main__":
    unittest.main()
