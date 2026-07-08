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


class DryRunPlanTests(unittest.TestCase):
    def test_row_not_found_reports_every_column_as_create(self) -> None:
        plan = upsert_data.build_dry_run_plan(
            mode="upsert",
            table="contoso_account",
            record_id=None,
            key_text=json.dumps({"contoso_code": "A-1"}),
            proposed_data={"name": "Acme", "creditlimit": 5000},
            current_columns=None,
            row_found=False,
        )
        self.assertTrue(plan["dryRun"])
        self.assertFalse(plan["rowExists"])
        self.assertEqual(plan["effectiveOperation"], "create")
        self.assertEqual(plan["changeCount"], 2)
        self.assertEqual(plan["unchangedCount"], 0)
        self.assertEqual({c["changeType"] for c in plan["changes"]}, {"create"})

    def test_existing_row_splits_update_add_and_unchanged(self) -> None:
        plan = upsert_data.build_dry_run_plan(
            mode="update",
            table="contoso_account",
            record_id="11111111-1111-1111-1111-111111111111",
            key_text=None,
            proposed_data={"name": "New Name", "creditlimit": 5000, "description": "brand new"},
            current_columns={"name": "Old Name", "creditlimit": 5000},
            row_found=True,
        )
        self.assertEqual(plan["effectiveOperation"], "update")
        by_column = {c["column"]: c for c in plan["changes"]}
        self.assertEqual(by_column["name"]["changeType"], "update")
        self.assertEqual(by_column["name"]["current"], "Old Name")
        self.assertEqual(by_column["description"]["changeType"], "add")
        self.assertEqual([u["column"] for u in plan["unchanged"]], ["creditlimit"])

    def test_update_on_missing_row_warns_it_would_fail(self) -> None:
        plan = upsert_data.build_dry_run_plan(
            mode="update",
            table="contoso_account",
            record_id="11111111-1111-1111-1111-111111111111",
            key_text=None,
            proposed_data={"name": "X"},
            current_columns=None,
            row_found=False,
        )
        self.assertIn("would fail", plan["note"])


class DiffNormalizationTests(unittest.TestCase):
    def test_typed_lookup_matches_current_simplified_lookup(self) -> None:
        proposed = {"type": "lookup", "entity": "contoso_parent", "id": "AAAA1111-1111-1111-1111-111111111111"}
        current = {"logicalName": "contoso_parent", "id": "aaaa1111-1111-1111-1111-111111111111", "name": "Parent"}
        self.assertTrue(upsert_data.values_equal_for_diff(proposed, current))

    def test_typed_money_matches_current_number(self) -> None:
        self.assertTrue(upsert_data.values_equal_for_diff({"type": "money", "value": 5000}, 5000))

    def test_typed_choice_change_is_detected(self) -> None:
        self.assertFalse(upsert_data.values_equal_for_diff({"type": "choice", "value": 1}, 2))

    def test_numeric_string_and_number_are_equal(self) -> None:
        self.assertTrue(upsert_data.values_equal_for_diff("5000", 5000))

    def test_bool_is_not_loosely_equal_to_int(self) -> None:
        self.assertFalse(upsert_data.values_equal_for_diff(True, 1))


class DryRunMainPathTests(unittest.TestCase):
    def test_dry_run_only_retrieves_and_prints_a_plan(self) -> None:
        commands: list[list[str]] = []

        def fake_run_dataverse_tool(command: list[str], *, cwd: Path | None = None) -> SimpleNamespace:
            commands.append(command)
            self.assertEqual(command[:3], ["row", "--mode", "retrieve"])
            return SimpleNamespace(
                stdout=json.dumps(
                    {
                        "success": True,
                        "mode": "retrieve",
                        "table": "contoso_account",
                        "found": True,
                        "row": {"id": "g", "columns": {"name": "Old Name"}},
                    }
                )
            )

        with mock.patch.object(upsert_data, "load_deployment_defaults", return_value={}), mock.patch.object(
            upsert_data, "coerce_dataverse_row_data", side_effect=lambda _t, d, _dd: d
        ), mock.patch.object(
            upsert_data,
            "resolve_live_connection",
            return_value={
                "environment_url": "https://contoso.crm.dynamics.com",
                "username": "user@contoso.com",
                "tenant_id": None,
            },
        ), mock.patch.object(upsert_data, "run_dataverse_tool", side_effect=fake_run_dataverse_tool):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "upsert_data.py",
                    "--table",
                    "contoso_account",
                    "--data",
                    json.dumps({"name": "New Name"}),
                    "--id",
                    "11111111-1111-1111-1111-111111111111",
                    "--dry-run",
                ],
            ):
                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    exit_code = upsert_data.main()

        self.assertEqual(exit_code, 0)
        # Only the read happened; no create/update/upsert write command was issued.
        self.assertEqual(len(commands), 1)
        plan = json.loads(buffer.getvalue())
        self.assertTrue(plan["dryRun"])
        self.assertEqual(plan["changes"][0]["column"], "name")
        self.assertEqual(plan["changes"][0]["changeType"], "update")


if __name__ == "__main__":
    unittest.main()
