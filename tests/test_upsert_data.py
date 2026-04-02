from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import upsert_data  # type: ignore


class UpsertDataTests(unittest.TestCase):
    def test_upsert_data_coerces_profile_configured_choice_columns(self) -> None:
        captured: dict[str, object] = {}

        def fake_run_dataverse_tool(command: list[str]) -> SimpleNamespace:
            captured["command"] = command
            return SimpleNamespace(stdout='{"success": true}')

        with mock.patch.object(
            upsert_data,
            "load_deployment_defaults",
            return_value={
                "dataWrites": {
                    "typedColumns": {
                        "account": {
                            "statuscode": "choice",
                        }
                    }
                }
            },
        ), mock.patch.object(
            upsert_data,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": "tenant-id",
            },
        ), mock.patch.object(upsert_data, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "upsert_data.py",
                    "--repo-root",
                    str(Path.cwd()),
                    "--table",
                    "account",
                    "--data",
                    '{"statuscode":1,"name":"Acme"}',
                    "--environment-url",
                    "https://contoso.crm.dynamics.com",
                ],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = upsert_data.main()

        self.assertEqual(exit_code, 0)
        data_index = captured["command"].index("--data") + 1
        payload = json.loads(captured["command"][data_index])
        self.assertEqual(payload["statuscode"], {"type": "choice", "value": 1})
        self.assertEqual(payload["name"], "Acme")


if __name__ == "__main__":
    unittest.main()
