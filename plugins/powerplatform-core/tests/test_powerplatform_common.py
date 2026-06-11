from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import powerplatform_common  # type: ignore


class DeploymentDefaultsTests(unittest.TestCase):
    def test_load_deployment_defaults_returns_empty_when_profile_has_no_section(self) -> None:
        with mock.patch.object(
            powerplatform_common,
            "discover_repo_context",
            return_value={"artifacts": {"project_profile": {"raw": {"mainSolutionUniqueName": "ContosoCore"}}}},
        ):
            defaults = powerplatform_common.load_deployment_defaults(Path.cwd())

        self.assertEqual(defaults, {})

    def test_coerce_dataverse_row_data_applies_configured_choice_columns(self) -> None:
        deployment_defaults = {
            "dataWrites": {
                "typedColumns": {
                    "account": {
                        "statuscode": "choice",
                    }
                }
            }
        }

        coerced = powerplatform_common.coerce_dataverse_row_data(
            "account",
            {"statuscode": 1, "name": "Acme"},
            deployment_defaults,
        )

        self.assertEqual(
            coerced,
            {
                "statuscode": {"type": "choice", "value": 1},
                "name": "Acme",
            },
        )


class CommandTimeoutTests(unittest.TestCase):
    def test_run_command_wraps_timeout_expired(self) -> None:
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["pac"], timeout=45)):
            with self.assertRaises(RuntimeError) as raised:
                powerplatform_common.run_command(["pac", "solution", "import"], timeout_seconds=45)

        self.assertIn("45", str(raised.exception))

    def test_run_command_with_dataverse_lock_retry_honors_runtime_budget(self) -> None:
        completed = SimpleNamespace(returncode=1, stdout="Cannot start another [Import]", stderr="")

        with mock.patch.object(powerplatform_common, "run_command", return_value=completed), mock.patch.object(
            powerplatform_common.time,
            "monotonic",
            side_effect=[0.0, 0.0, 31.0, 31.0, 62.0, 62.0],
        ), mock.patch.object(powerplatform_common.time, "sleep") as sleep_mock:
            with self.assertRaises(RuntimeError) as raised:
                powerplatform_common.run_command_with_dataverse_lock_retry(
                    ["pac", "solution", "import"],
                    retries=20,
                    wait_seconds=30,
                    max_runtime_seconds=45,
                )

        self.assertIn("runtime budget", str(raised.exception))
        self.assertEqual(sleep_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
