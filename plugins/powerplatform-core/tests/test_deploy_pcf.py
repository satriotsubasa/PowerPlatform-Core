from __future__ import annotations

import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import deploy_pcf  # type: ignore


class DeployPcfTests(unittest.TestCase):
    def test_checker_only_solution_package_does_not_require_live_connection(self) -> None:
        args = Namespace(
            repo_root=".",
            project=None,
            publisher_prefix=None,
            solution_name=None,
            environment_url="https://example.crm.dynamics.com",
            target_url=None,
            username=None,
            tenant_id=None,
            auth_dialog=False,
            auto_validate=False,
            skip_install=True,
            skip_build=True,
            skip_solution_build=True,
            production=False,
            incremental=False,
            mode="solution-package",
            configuration="Release",
            artifact_file="artifact.zip",
            allow_version_mismatch=True,
            run_check=True,
            checker_output=None,
            skip_import=True,
            publish_changes=False,
            activate_plugins=False,
            force_overwrite=False,
            skip_dependency_check=False,
            import_as_holding=False,
            stage_and_upgrade=False,
            convert_to_managed=False,
            lock_retries=20,
            lock_wait_seconds=30,
            verbosity=None,
            output=None,
        )

        with mock.patch.object(deploy_pcf, "repo_root", return_value=Path(".")), \
             mock.patch.object(
                 deploy_pcf,
                 "resolve_pcf_context",
                 return_value={
                     "package_root": ".",
                     "pcf_project_file": "control.pcfproj",
                     "solution_project": "Solutions\\Wrapper.cdsproj",
                     "solution_context": {},
                     "manifests": [],
                 },
             ), \
             mock.patch.object(deploy_pcf, "find_pcf_solution_artifact", return_value=Path("artifact.zip")), \
             mock.patch.object(deploy_pcf, "evaluate_version_alignment", return_value={"aligned": True, "manifest_versions": [], "solution_version": None}), \
             mock.patch.object(deploy_pcf, "execute_solution_package", return_value={"success": True}) as execute_solution_package, \
             mock.patch.object(deploy_pcf, "resolve_live_connection") as resolve_live_connection, \
             mock.patch.object(deploy_pcf, "write_json_output"):
            with mock.patch.object(sys, "argv", ["deploy_pcf.py", "--mode", "solution-package", "--run-check", "--skip-import", "--environment-url", "https://example.crm.dynamics.com", "--artifact-file", "artifact.zip", "--skip-install", "--skip-build", "--skip-solution-build", "--allow-version-mismatch"]):
                exit_code = deploy_pcf.main()

        self.assertEqual(exit_code, 0)
        resolve_live_connection.assert_not_called()
        self.assertIsNone(execute_solution_package.call_args.kwargs["connection"])

    def test_execute_solution_package_uses_explicit_environment_for_checker_without_connection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            artifact_path = repo / "artifact.zip"
            artifact_path.write_text("placeholder", encoding="utf-8")

            args = Namespace(
                skip_install=True,
                skip_build=True,
                skip_solution_build=True,
                configuration="Release",
                artifact_file=str(artifact_path),
                run_check=True,
                checker_output=None,
                environment_url="https://example.crm.dynamics.com",
                skip_import=True,
                publish_changes=False,
                activate_plugins=False,
                force_overwrite=False,
                skip_dependency_check=False,
                import_as_holding=False,
                stage_and_upgrade=False,
                convert_to_managed=False,
                lock_retries=20,
                lock_wait_seconds=30,
                production=False,
            )

            commands: list[list[str]] = []

            def capture_run_command(command: list[str], *, cwd: Path | None = None) -> mock.Mock:
                commands.append(command)
                return mock.Mock(stdout="", returncode=0)

            with mock.patch.object(deploy_pcf, "run_command", side_effect=capture_run_command):
                result = deploy_pcf.execute_solution_package(
                    args,
                    repo=repo,
                    package_root=repo,
                    pcf_context={
                        "pcf_project_file": "control.pcfproj",
                        "solution_project": "Solutions\\Wrapper.cdsproj",
                        "solution_context": {},
                    },
                    connection=None,
                    version_alignment={"aligned": True},
                )

        self.assertTrue(result["success"])
        self.assertIn(
            "--environment",
            commands[0],
        )
        self.assertIn(
            "https://example.crm.dynamics.com",
            commands[0],
        )


if __name__ == "__main__":
    unittest.main()
