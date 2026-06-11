from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AuthBrokerConfigurationTests(unittest.TestCase):
    def test_dataverse_ops_uses_broker_package_instead_of_desktop_only(self) -> None:
        project_text = (
            REPO_ROOT
            / "tools"
            / "CodexPowerPlatform.DataverseOps"
            / "CodexPowerPlatform.DataverseOps.csproj"
        ).read_text(encoding="utf-8")

        self.assertIn('PackageReference Include="Microsoft.Identity.Client.Broker"', project_text)

    def test_program_prefers_broker_interactive_auth_over_embedded_webview(self) -> None:
        program_text = (
            REPO_ROOT
            / "tools"
            / "CodexPowerPlatform.DataverseOps"
            / "Program.cs"
        ).read_text(encoding="utf-8")

        self.assertIn(".WithBroker(", program_text)
        self.assertNotIn(".WithUseEmbeddedWebView(true)", program_text)

    def test_program_parents_broker_auth_to_the_dialog_window(self) -> None:
        program_text = (
            REPO_ROOT
            / "tools"
            / "CodexPowerPlatform.DataverseOps"
            / "Program.cs"
        ).read_text(encoding="utf-8")

        self.assertIn('"parent-window-handle"', program_text)
        self.assertIn(".WithParentActivityOrWindow(", program_text)

    def test_auth_dialog_passes_parent_window_handle_to_child_processes(self) -> None:
        main_window_text = (
            REPO_ROOT
            / "tools"
            / "CodexPowerPlatform.AuthDialog"
            / "MainWindow.xaml.cs"
        ).read_text(encoding="utf-8")
        whoami_runner_text = (
            REPO_ROOT
            / "tools"
            / "CodexPowerPlatform.AuthDialog"
            / "WhoAmIProcessRunner.cs"
        ).read_text(encoding="utf-8")
        solution_runner_text = (
            REPO_ROOT
            / "tools"
            / "CodexPowerPlatform.AuthDialog"
            / "SolutionListProcessRunner.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("WindowInteropHelper", main_window_text)
        self.assertIn("parentWindowHandle", whoami_runner_text)
        self.assertIn("--parent-window-handle", whoami_runner_text)
        self.assertIn("parentWindowHandle", solution_runner_text)
        self.assertIn("--parent-window-handle", solution_runner_text)


if __name__ == "__main__":
    unittest.main()
