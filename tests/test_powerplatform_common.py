from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import powerplatform_common  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "discover_context"


class ResolveExecutableTests(unittest.TestCase):
    def test_windows_fallback_returns_original_command_when_no_candidate_exists(self) -> None:
        with mock.patch.object(powerplatform_common.shutil, "which", return_value=None) as which_mock:
            with mock.patch.object(powerplatform_common.os, "name", "nt"):
                resolved = powerplatform_common.resolve_executable("pac")

        self.assertEqual(resolved, "pac")
        self.assertEqual(
            [call.args[0] for call in which_mock.call_args_list],
            ["pac", "pac.exe", "pac.cmd", "pac.bat"],
        )

    def test_direct_resolution_stops_before_windows_suffix_fallback(self) -> None:
        with mock.patch.object(powerplatform_common.shutil, "which", return_value=r"C:\Tools\pac.exe") as which_mock:
            with mock.patch.object(powerplatform_common.os, "name", "nt"):
                resolved = powerplatform_common.resolve_executable("pac")

        self.assertEqual(resolved, r"C:\Tools\pac.exe")
        self.assertEqual(which_mock.call_count, 1)


class EnvironmentUrlWarningTests(unittest.TestCase):
    def test_normalize_environment_url_removes_trailing_slash_and_lowercases_host(self) -> None:
        self.assertEqual(
            powerplatform_common.normalize_environment_url("HTTPS://Contoso.CRM.Dynamics.com/"),
            "https://contoso.crm.dynamics.com",
        )

    def test_build_pac_environment_mismatch_warning_returns_message_for_different_target(self) -> None:
        warning = powerplatform_common.build_pac_environment_mismatch_warning(
            requested_environment_url="https://target.crm.dynamics.com",
            pac_environment_url="https://other.crm.dynamics.com",
        )

        self.assertIn("active PAC profile targets", warning)
        self.assertIn("target.crm.dynamics.com", warning)
        self.assertIn("other.crm.dynamics.com", warning)

    def test_build_pac_environment_mismatch_warning_ignores_matching_urls(self) -> None:
        warning = powerplatform_common.build_pac_environment_mismatch_warning(
            requested_environment_url="https://target.crm.dynamics.com/",
            pac_environment_url="https://target.crm.dynamics.com",
        )

        self.assertEqual(warning, "")


class ActivePacProfileTests(unittest.TestCase):
    def test_active_pac_profile_returns_empty_values_when_pac_is_unavailable(self) -> None:
        with mock.patch.object(powerplatform_common, "run_command", side_effect=FileNotFoundError()):
            profile = powerplatform_common.active_pac_profile()

        self.assertEqual(
            profile,
            {
                "user": None,
                "tenant_id": None,
                "environment_url": None,
            },
        )


class SolutionSourceResolutionTests(unittest.TestCase):
    def test_infer_unpacked_solution_folder_rejects_multiple_authoritative_solutions(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "More than one authoritative unpacked solution"):
            powerplatform_common.infer_unpacked_solution_folder(
                FIXTURES_ROOT / "multiple_primary_solutions_repo"
            )

    def test_has_local_solution_source_ignores_supporting_only_solution_artifacts(self) -> None:
        self.assertFalse(
            powerplatform_common.has_local_solution_source(
                FIXTURES_ROOT / "supporting_solution_only_repo"
            )
        )


if __name__ == "__main__":
    unittest.main()
