from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import debug_power_fx  # type: ignore


def _has_in_operator_finding(formula: str) -> bool:
    findings = debug_power_fx.find_delegation_risks(formula, debug_power_fx.extract_functions(formula))
    return any(finding["code"] == "delegation-in-operator" for finding in findings)


class DebugPowerFxDelegationInOperatorTests(unittest.TestCase):
    def test_real_in_operator_is_detected(self) -> None:
        self.assertTrue(_has_in_operator_finding('"a" in Accounts'))
        self.assertTrue(_has_in_operator_finding("Filter(Accounts, Status exactin SelectedStatuses)"))

    def test_in_inside_string_literal_does_not_false_positive(self) -> None:
        self.assertFalse(_has_in_operator_finding('Notify("Saved in progress")'))
        self.assertFalse(_has_in_operator_finding('Set(message, "logged in successfully")'))

    def test_in_inside_quoted_column_name_does_not_false_positive(self) -> None:
        # A display-name identifier such as 'Check in date' must not trigger.
        self.assertFalse(_has_in_operator_finding("ThisItem.'Check in date'"))

    def test_in_as_substring_of_identifier_does_not_false_positive(self) -> None:
        self.assertFalse(_has_in_operator_finding("Set(invoiceTotal, 100)"))


if __name__ == "__main__":
    unittest.main()
