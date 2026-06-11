from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import version_pcf_solution  # type: ignore

MANIFEST_XML = """<?xml version="1.0" encoding="utf-8"?>
<manifest>
  <control namespace="Contoso.Sample" constructor="SampleControl" version="1.2.3" />
</manifest>
"""

SOLUTION_XML = """<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml>
  <SolutionManifest>
    <Version>1.2.3.4</Version>
  </SolutionManifest>
</ImportExportXml>
"""


class VersionPcfSolutionTests(unittest.TestCase):
    def test_calculate_new_versions_increments_patch_and_resets_revision(self) -> None:
        solution_version, manifest_version = version_pcf_solution.calculate_new_versions(
            current_version="1.2.3.4",
            explicit_version=None,
            increment="patch",
        )

        self.assertEqual(solution_version, "1.2.4.0")
        self.assertEqual(manifest_version, "1.2.4")

    def test_calculate_new_versions_accepts_three_part_explicit_version(self) -> None:
        solution_version, manifest_version = version_pcf_solution.calculate_new_versions(
            current_version="1.2.3.4",
            explicit_version="2.0.1",
            increment=None,
        )

        self.assertEqual(solution_version, "2.0.1.0")
        self.assertEqual(manifest_version, "2.0.1")

    def test_update_manifest_and_solution_files_together(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "ControlManifest.Input.xml"
            solution_path = root / "Solution.xml"
            manifest_path.write_text(MANIFEST_XML, encoding="utf-8")
            solution_path.write_text(SOLUTION_XML, encoding="utf-8")

            version_pcf_solution.update_manifest_version(manifest_path, "1.2.4")
            version_pcf_solution.update_solution_version(solution_path, "1.2.4.0")

            self.assertIn('version="1.2.4"', manifest_path.read_text(encoding="utf-8"))
            self.assertIn("<Version>1.2.4.0</Version>", solution_path.read_text(encoding="utf-8"))

    def test_main_errors_and_does_not_rewrite_when_no_version_or_increment(self) -> None:
        pcf_context = {
            "package_root": "pkg",
            "pcf_project_file": "control.pcfproj",
            "manifests": [{"manifest_path": "ControlManifest.Input.xml", "version": "1.2.3"}],
            "solution_context": {"version": "1.2.3.4"},
            "solution_xml": "Solution.xml",
        }

        with mock.patch.object(version_pcf_solution, "repo_root", return_value=Path(".")), \
             mock.patch.object(version_pcf_solution, "resolve_pcf_context", return_value=pcf_context), \
             mock.patch.object(version_pcf_solution, "update_manifest_version") as update_manifest, \
             mock.patch.object(version_pcf_solution, "update_solution_version") as update_solution, \
             mock.patch.object(version_pcf_solution, "write_json_output") as write_json_output, \
             mock.patch.object(sys, "argv", ["version_pcf_solution.py"]):
            with self.assertRaises(SystemExit) as raised:
                version_pcf_solution.main()

        self.assertNotEqual(raised.exception.code, 0)
        update_manifest.assert_not_called()
        update_solution.assert_not_called()
        write_json_output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
