from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import delete_data  # type: ignore
import read_data  # type: ignore

FAKE_CONNECTION = {
    "environment_url": "https://org.crm.dynamics.com",
    "username": "user@example.com",
    "tenant_id": "tenant-1",
}


def read_args(**overrides: object) -> argparse.Namespace:
    base = dict(
        mode="retrieve",
        table=None,
        id=None,
        key=None,
        columns=None,
        all_columns=False,
        fetchxml=None,
        spec=None,
        max_rows=100,
        page_size=None,
        exact_total=False,
        auth_flow="auto",
        app_id=None,
        certificate_path=None,
        force_prompt=False,
        verbose=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class ReadDataTests(unittest.TestCase):
    def test_retrieve_by_id_builds_row_retrieve_command(self) -> None:
        args = read_args(
            mode="retrieve",
            table="dhx_invoice",
            id="11111111-1111-1111-1111-111111111111",
            columns="dhx_name,statecode",
        )
        command = read_data.build_retrieve_command(args, FAKE_CONNECTION)
        self.assertEqual(command[:5], ["row", "--mode", "retrieve", "--table", "dhx_invoice"])
        self.assertIn("--id", command)
        self.assertIn("--columns", command)
        self.assertIn("dhx_name,statecode", command)
        self.assertIn("--environment-url", command)
        self.assertIn("https://org.crm.dynamics.com", command)

    def test_retrieve_requires_table(self) -> None:
        with self.assertRaises(SystemExit):
            read_data.build_retrieve_command(read_args(mode="retrieve", id="x"), FAKE_CONNECTION)

    def test_retrieve_requires_id_or_key(self) -> None:
        with self.assertRaises(SystemExit):
            read_data.build_retrieve_command(read_args(mode="retrieve", table="dhx_invoice"), FAKE_CONNECTION)

    def test_list_from_spec_builds_query_command_with_fetchxml(self) -> None:
        spec = {"tableLogicalName": "account", "select": ["name"], "top": 5}
        args = read_args(mode="list", spec=json.dumps(spec), max_rows=250, exact_total=True)
        command = read_data.build_list_command(args, FAKE_CONNECTION)
        self.assertEqual(command[0], "query")
        self.assertIn("--fetchxml", command)
        fetch_xml = command[command.index("--fetchxml") + 1]
        self.assertIn('<entity name="account"', fetch_xml)
        self.assertIn("--max-rows", command)
        self.assertIn("250", command)
        self.assertIn("--exact-total", command)

    def test_list_requires_fetchxml_or_spec(self) -> None:
        with self.assertRaises(SystemExit):
            read_data.resolve_fetchxml(read_args(mode="list"))

    def test_list_accepts_raw_fetchxml(self) -> None:
        raw = '<fetch><entity name="contact"><attribute name="fullname" /></entity></fetch>'
        self.assertEqual(read_data.resolve_fetchxml(read_args(mode="list", fetchxml=raw)), raw)

    def test_service_principal_uses_app_id_and_no_username(self) -> None:
        args = read_args(
            mode="retrieve",
            table="dhx_invoice",
            id="11111111-1111-1111-1111-111111111111",
            auth_flow="clientsecret",
            app_id="app-guid",
        )
        command = read_data.build_retrieve_command(args, FAKE_CONNECTION)
        self.assertIn("--auth-flow", command)
        self.assertIn("clientsecret", command)
        self.assertIn("--app-id", command)
        self.assertIn("app-guid", command)
        self.assertNotIn("--username", command)


class DeleteDataTests(unittest.TestCase):
    def test_delete_by_id_builds_row_delete_command(self) -> None:
        args = read_args(table="dhx_invoice", id="22222222-2222-2222-2222-222222222222")
        command = delete_data.build_delete_command(args, FAKE_CONNECTION)
        self.assertEqual(command[:5], ["row", "--mode", "delete", "--table", "dhx_invoice"])
        self.assertIn("--id", command)
        self.assertIn("--environment-url", command)

    def test_delete_by_alternate_key_serializes_key_json(self) -> None:
        args = read_args(table="dhx_invoice", key=json.dumps({"dhx_number": "INV-1"}))
        command = delete_data.build_delete_command(args, FAKE_CONNECTION)
        self.assertIn("--key", command)
        self.assertIn(json.dumps({"dhx_number": "INV-1"}), command)

    def test_delete_requires_id_or_key(self) -> None:
        with self.assertRaises(SystemExit):
            delete_data.build_delete_command(read_args(table="dhx_invoice"), FAKE_CONNECTION)

    def test_delete_service_principal_uses_app_id(self) -> None:
        args = read_args(table="dhx_invoice", id="22222222-2222-2222-2222-222222222222", auth_flow="certificate", app_id="app-guid", certificate_path="/tmp/c.pfx")
        command = delete_data.build_delete_command(args, FAKE_CONNECTION)
        self.assertIn("--app-id", command)
        self.assertIn("--certificate-path", command)
        self.assertIn("/tmp/c.pfx", command)
        self.assertNotIn("--username", command)


if __name__ == "__main__":
    unittest.main()
