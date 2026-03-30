from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "discover_context.py"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "discover_context"
SCENARIOS_PATH = REPO_ROOT / "tests" / "acceptance_scenarios.json"


def normalize_path(value: object) -> object:
    if not isinstance(value, str):
        return value
    return value.replace("\\", "/")


class SkillAcceptanceScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scenarios = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))

    def run_discovery(self, fixture_name: str) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--path", str(FIXTURES_ROOT / fixture_name)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return json.loads(completed.stdout)

    def test_acceptance_scenarios(self) -> None:
        for scenario in self.scenarios:
            with self.subTest(name=scenario["name"]):
                payload = self.run_discovery(scenario["fixture"])
                inferred = payload["inferred"]
                questions = payload["recommended_questions"]
                warnings = payload["warnings"]

                for key, expected in scenario.get("expected_inferred", {}).items():
                    actual = normalize_path(inferred.get(key))
                    self.assertEqual(actual, normalize_path(expected), key)

                for question in scenario.get("required_questions", []):
                    self.assertIn(question, questions)
                for question in scenario.get("forbidden_questions", []):
                    self.assertNotIn(question, questions)

                for warning in scenario.get("required_warnings", []):
                    self.assertIn(warning, warnings)
                for warning in scenario.get("forbidden_warnings", []):
                    self.assertNotIn(warning, warnings)


if __name__ == "__main__":
    unittest.main()
