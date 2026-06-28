from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import inspect_flow_runs  # type: ignore


def runs_args(**overrides: object) -> argparse.Namespace:
    base = dict(
        workflow_id=None,
        workflow_unique_id=None,
        unique_name=None,
        name=None,
        solution_unique_name=None,
        max_runs=20,
        status=None,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class InspectFlowRunsTests(unittest.TestCase):
    def test_spec_includes_selector_and_max_runs_and_drops_nones(self) -> None:
        spec = inspect_flow_runs.build_runs_spec(runs_args(name="My Flow", max_runs=50), {"solution_unique_name": None})
        self.assertEqual(spec["name"], "My Flow")
        self.assertEqual(spec["maxRuns"], 50)
        self.assertNotIn("workflowId", spec)
        self.assertNotIn("status", spec)

    def test_spec_filters_status_and_uses_connection_solution(self) -> None:
        spec = inspect_flow_runs.build_runs_spec(
            runs_args(workflow_id="abc", status="Failed"),
            {"solution_unique_name": "my_solution"},
        )
        self.assertEqual(spec["workflowId"], "abc")
        self.assertEqual(spec["status"], "Failed")
        self.assertEqual(spec["solutionUniqueName"], "my_solution")

    def test_explicit_solution_overrides_connection(self) -> None:
        spec = inspect_flow_runs.build_runs_spec(
            runs_args(name="F", solution_unique_name="explicit"),
            {"solution_unique_name": "from_conn"},
        )
        self.assertEqual(spec["solutionUniqueName"], "explicit")


if __name__ == "__main__":
    unittest.main()
