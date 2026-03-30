from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import design_dataverse_query  # type: ignore


class DesignDataverseQueryTests(unittest.TestCase):
    def test_build_query_design_uses_entity_set_name_and_generates_flow_parameters(self) -> None:
        payload = design_dataverse_query.build_query_design(
            {
                "tableLogicalName": "account",
                "entitySetName": "accounts",
                "select": ["name", "accountnumber"],
                "filters": [
                    {"field": "name", "operator": "contains", "value": "Contoso"},
                    {"field": "statecode", "operator": "eq", "value": 0},
                ],
                "orderBy": [{"field": "name", "direction": "asc"}],
                "top": 5,
            }
        )

        self.assertEqual(payload["entitySetName"], "accounts")
        self.assertIn("/api/data/v9.2/accounts?", payload["odata"])
        self.assertIn("$top=5", payload["odata"])
        self.assertEqual(payload["powerAutomate"]["tableName"], "account")
        self.assertEqual(payload["powerAutomate"]["topCount"], 5)
        self.assertIn("contains(name,'Contoso')", payload["powerAutomate"]["filterRows"])
        self.assertIn("operator=\"like\"", payload["fetchXml"])

    def test_build_query_design_warns_when_entity_set_name_is_missing(self) -> None:
        payload = design_dataverse_query.build_query_design(
            {
                "tableLogicalName": "ec_notificationdefinition",
                "select": ["ec_name"],
            }
        )

        self.assertTrue(any("Entity set name was not provided" in warning for warning in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
