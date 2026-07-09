from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import design_dataverse_schema as dds  # type: ignore


class AutoNumberDesignTests(unittest.TestCase):
    def _design(self, raw: dict) -> dict:
        return dds.build_field_design(
            raw,
            prefix="tenure",
            table_logical_name="tenure_matter",
            solution_unique_name="TenureOperatingSystem",
        )

    def test_autonumber_type_maps_to_string_and_emits_format(self) -> None:
        helper = self._design({"displayName": "Tenure Code", "type": "autonumber", "autoNumberFormat": "T-{SEQNUM:5}"})["helperSpec"]
        self.assertEqual(helper["type"], "String")
        self.assertEqual(helper["autoNumberFormat"], "T-{SEQNUM:5}")

    def test_autonumber_requires_a_format(self) -> None:
        with self.assertRaises(RuntimeError):
            self._design({"displayName": "Code", "type": "autonumber"})

    def test_plain_string_field_passes_through_autonumber_format(self) -> None:
        helper = self._design({"displayName": "Ref", "type": "string", "autoNumberFormat": "R-{SEQNUM:4}"})["helperSpec"]
        self.assertEqual(helper["type"], "String")
        self.assertEqual(helper["autoNumberFormat"], "R-{SEQNUM:4}")

    def test_memo_rejects_autonumber_format(self) -> None:
        with self.assertRaises(RuntimeError):
            self._design({"displayName": "Notes", "type": "memo", "autoNumberFormat": "X-{SEQNUM:4}"})

    def test_string_without_format_has_no_autonumber_key(self) -> None:
        helper = self._design({"displayName": "Name", "type": "string"})["helperSpec"]
        self.assertNotIn("autoNumberFormat", helper)


if __name__ == "__main__":
    unittest.main()
