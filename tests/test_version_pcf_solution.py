from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
