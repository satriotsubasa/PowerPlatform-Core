from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import design_dataverse_schema as dds  # type: ignore


class ComputedColumnRedirectTests(unittest.TestCase):
    def _design(self, raw: dict) -> dict:
        return dds.build_field_design(
            raw, prefix="tenure", table_logical_name="tenure_matter", solution_unique_name="TenureOperatingSystem"
        )

    def test_type_formula_redirects(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "make.powerapps.com"):
            self._design({"displayName": "Total", "type": "formula"})

    def test_type_calculated_redirects(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "solution import"):
            self._design({"displayName": "Total", "type": "calculated"})

    def test_type_rollup_redirects(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "solution import"):
            self._design({"displayName": "Count", "type": "rollup"})

    def test_computed_subobject_redirects(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "maker portal"):
            self._design({"displayName": "Line Total", "type": "decimal", "computed": {"kind": "calculated"}})

    def test_bare_formula_definition_redirects(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "headlessly"):
            self._design({"displayName": "Total", "type": "decimal", "formulaDefinition": "<Activity/>"})

    def test_plain_decimal_still_works(self) -> None:
        helper = self._design({"displayName": "Amount", "type": "decimal"})["helperSpec"]
        self.assertEqual(helper["type"], "Decimal")


if __name__ == "__main__":
    unittest.main()
