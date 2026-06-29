from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import admin_inspect  # type: ignore


class AdminInspectTests(unittest.TestCase):
    def test_environments_builds_pac_admin_list(self) -> None:
        self.assertEqual(admin_inspect.build_admin_command("environments"), ["pac", "admin", "list"])

    def test_tenant_settings_builds_list_tenant_settings(self) -> None:
        self.assertEqual(
            admin_inspect.build_admin_command("tenant-settings"),
            ["pac", "admin", "list-tenant-settings"],
        )

    def test_dlp_policies_is_read_only_list(self) -> None:
        self.assertEqual(
            admin_inspect.build_admin_command("dlp-policies"),
            ["pac", "admin", "dlp-policy", "list"],
        )

    def test_groups_builds_list_groups(self) -> None:
        self.assertEqual(admin_inspect.build_admin_command("groups"), ["pac", "admin", "list-groups"])

    def test_unknown_mode_raises(self) -> None:
        with self.assertRaises(SystemExit):
            admin_inspect.build_admin_command("delete-tenant")


if __name__ == "__main__":
    unittest.main()
