from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import powerplatform_common as ppc  # type: ignore


class PreflightTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ppc.preflight_token_path()
        self._backup = self.path.read_text(encoding="utf-8") if self.path.exists() else None

    def tearDown(self) -> None:
        if self._backup is None:
            if self.path.exists():
                self.path.unlink()
        else:
            self.path.write_text(self._backup, encoding="utf-8")

    def test_write_then_enforce_passes(self) -> None:
        payload = ppc.write_preflight_token({"environmentUrl": "https://org.crm.dynamics.com"})
        # Should not raise, and the recorded token round-trips.
        ppc.enforce_preflight(provided_token=payload["token"])
        self.assertEqual(ppc.load_preflight_token()["token"], payload["token"])

    def test_no_token_raises(self) -> None:
        if self.path.exists():
            self.path.unlink()
        with self.assertRaises(SystemExit):
            ppc.enforce_preflight()

    def test_no_preflight_bypass_passes(self) -> None:
        if self.path.exists():
            self.path.unlink()
        ppc.enforce_preflight(allow_no_preflight=True)  # bypass, no raise

    def test_expired_token_is_ignored(self) -> None:
        self.path.write_text(
            json.dumps({"token": "t", "specHash": "h", "expiresAt": "2000-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        self.assertIsNone(ppc.load_preflight_token())
        with self.assertRaises(SystemExit):
            ppc.enforce_preflight()

    def test_mismatched_provided_token_raises(self) -> None:
        ppc.write_preflight_token({"a": 1})
        with self.assertRaises(SystemExit):
            ppc.enforce_preflight(provided_token="not-the-token")


if __name__ == "__main__":
    unittest.main()
