from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import discover_context  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "discover_context.py"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "discover_context"


def normalize_path(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\\", "/")


class DiscoverContextTests(unittest.TestCase):
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

    def test_infer_solution_role_accepts_posix_style_dataverse_paths(self) -> None:
        role = discover_context.infer_solution_role(
            "Dataverse/SampleSolution",
            {"dataverse": ["Dataverse"], "pcf": [], "reference": []},
        )
        self.assertEqual(role, "dataverse-reference")

    def test_prefer_paths_under_accepts_posix_style_relative_paths(self) -> None:
        plugin_path = "Contoso.Sample.Plugins/Contoso.Sample.Plugins.csproj"
        selected = discover_context.prefer_paths_under([plugin_path], ["Contoso.Sample.Plugins"])
        self.assertEqual(selected, plugin_path)

    def test_prefer_plugin_project_leaves_ambiguous_non_tool_candidates_unset(self) -> None:
        selected = discover_context.prefer_plugin_project(
            [
                "Zeta.App.Plugins/Zeta.App.Plugins.csproj",
                "Fabrikam.App.Plugins/Fabrikam.App.Plugins.csproj",
            ],
            [],
            ["Tools"],
        )
        self.assertIsNone(selected)

    def test_cli_detects_layered_hybrid_fixture(self) -> None:
        payload = self.run_discovery("layered_hybrid_repo")
        inferred = payload["inferred"]

        self.assertEqual(inferred["repo_archetype"], "layered-dotnet-dataverse")
        self.assertEqual(inferred["solution_source_model"], "hybrid-code-and-solution-source")
        self.assertEqual(normalize_path(inferred["solution_folder"]), "Dataverse/SampleSolution")
        self.assertEqual(
            normalize_path(inferred["plugin_project"]),
            "Contoso.Sample.Plugins/Contoso.Sample.Plugins.csproj",
        )

    def test_cli_prefers_namespace_matching_data_area_in_ambiguous_repo(self) -> None:
        payload = self.run_discovery("ambiguous_non_house_style_repo")
        inferred = payload["inferred"]

        self.assertEqual(normalize_path(inferred["data_area"]), "Zeta.App.Data")
        self.assertEqual(
            normalize_path(inferred["plugin_project"]),
            "Zeta.App.Plugins/Zeta.App.Plugins.csproj",
        )

    def test_cli_leaves_tool_only_plugin_repo_unset(self) -> None:
        payload = self.run_discovery("tool_only_repo")
        inferred = payload["inferred"]

        self.assertIsNone(inferred["plugin_project"])
        self.assertEqual(normalize_path(inferred["tools_area"]), "Tools")

    def test_cli_reports_sparse_repo_without_guessing(self) -> None:
        payload = self.run_discovery("no_structure_repo")

        self.assertIsNone(payload["inferred"]["repo_archetype"])
        self.assertIn(
            "No Power Platform solution, plug-in, PCF, pipeline, or deployment artifacts were detected in the scan path.",
            payload["warnings"],
        )
        self.assertIn(
            "What is the target solution unique name for this task?",
            payload["recommended_questions"],
        )

    def test_cli_ignores_fixture_noise_inside_tests_directories(self) -> None:
        payload = self.run_discovery("repo_with_test_fixture_noise")

        self.assertEqual(payload["candidates"]["solution_unique_names"], ["MainSolution"])
        self.assertEqual(payload["candidates"]["publisher_prefixes"], ["main"])
        self.assertNotIn("NoiseSolution", payload["candidates"]["local_solution_unique_names"])

    def test_cli_marks_supporting_only_solution_sources_as_non_primary(self) -> None:
        payload = self.run_discovery("supporting_solution_only_repo")

        self.assertEqual(payload["candidates"]["solution_unique_names"], [])
        self.assertIn("ContosoControls", payload["candidates"]["supporting_solution_unique_names"])
        self.assertIn(
            "What is the target solution unique name for this task?",
            payload["recommended_questions"],
        )


if __name__ == "__main__":
    unittest.main()
