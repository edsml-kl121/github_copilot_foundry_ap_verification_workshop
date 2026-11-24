"""Offline tests for the Python rules and Text2SQL safety guardrail."""

from __future__ import annotations

import json
import sqlite3
import unittest

from python_examples.common import DATA, GROUND_TRUTH
from python_examples.text2sql import assert_read_only
from python_examples.verify import verify_invoice


class PythonWorkshopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(":memory:")
        cls.conn.row_factory = sqlite3.Row
        cls.conn.executescript((DATA / "ap_database.sql").read_text(encoding="utf-8"))
        cls.invoices = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_sample_outcomes_match_the_workshop_scenarios(self):
        expected = {
            "INV-SOS-2026-0415.pdf": "APPROVED",
            "INV-TTS-2026-118.pdf": "ON HOLD",
            "INV-BEL-7781.pdf": "ON HOLD",
            "INV-CMP-2026-0057.pdf": "ON HOLD",
        }
        for name, outcome in expected.items():
            with self.subTest(invoice=name):
                result = verify_invoice(self.conn, self.invoices[name])
                self.assertEqual(result["outcome"], outcome)

    def test_duplicate_invoice_is_rejected(self):
        invoice = dict(self.invoices["INV-SOS-2026-0415.pdf"])
        invoice["invoice_number"] = "INV-SOS-2026-0388"
        result = verify_invoice(self.conn, invoice)
        self.assertEqual(result["outcome"], "REJECTED")
        self.assertTrue(any(check["id"] == "duplicate" and check["status"] == "REJECT"
                            for check in result["checks"]))

    def test_sql_guardrail_accepts_select_and_blocks_writes(self):
        self.assertEqual(assert_read_only("SELECT 1;"), "SELECT 1")
        for sql in ("DELETE FROM invoices", "SELECT 1; DROP TABLE invoices", "PRAGMA table_info(invoices)"):
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                assert_read_only(sql)


if __name__ == "__main__":
    unittest.main()
