from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import review_flow_connectors  # type: ignore


class ReviewFlowConnectorsTests(unittest.TestCase):
    def test_connector_review_reports_dataverse_sharepoint_and_outlook_findings(self) -> None:
        client_data = {
            "properties": {
                "definition": {
                    "actions": {
                        "List_notifications": {
                            "type": "OpenApiConnection",
                            "inputs": {
                                "host": {
                                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                                    "operationId": "ListRows",
                                },
                                "parameters": {"entityName": "ec_notificationlog"},
                            },
                        },
                        "Read_docs": {
                            "type": "OpenApiConnection",
                            "inputs": {
                                "host": {
                                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline",
                                    "operationId": "GetItems",
                                },
                                "parameters": {"dataset": "Documents"},
                            },
                        },
                        "Send_mail": {
                            "type": "OpenApiConnection",
                            "inputs": {
                                "host": {
                                    "apiId": "/providers/Microsoft.PowerApps/apis/shared_office365",
                                    "operationId": "SendEmailV2",
                                },
                                "parameters": {},
                            },
                        },
                    }
                }
            }
        }

        payload = review_flow_connectors.review_connectors(client_data)
        codes = {finding["code"] for finding in payload["findings"]}

        self.assertIn("dataverse", payload["connectors"])
        self.assertIn("sharepoint", payload["connectors"])
        self.assertIn("outlook", payload["connectors"])
        self.assertIn("dataverse-list-no-select", codes)
        self.assertIn("sharepoint-list-no-filter", codes)
        self.assertIn("outlook-send-no-recipient", codes)


if __name__ == "__main__":
    unittest.main()
