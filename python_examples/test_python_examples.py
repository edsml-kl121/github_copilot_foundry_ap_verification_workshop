"""Offline tests for the Python rules and Text2SQL safety guardrail."""

from __future__ import annotations

import json
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pypdf import PdfReader

from python_examples.common import DATA, GROUND_TRUTH
from python_examples.text2sql import assert_read_only
from python_examples.verify import verify_invoice
from python_examples import workshop_api


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

    def test_thai_invoices_remain_consistent_with_database_and_ocr(self):
        ocr = workshop_api._load("02_ocr_invoice.py", "ap_ocr_test")
        for filename, invoice in self.invoices.items():
            with self.subTest(invoice=filename):
                vendor = self.conn.execute(
                    "SELECT vendor_name FROM vendors WHERE tax_id=?", (invoice["vendor_tax_id"],)
                ).fetchone()
                self.assertEqual(vendor["vendor_name"], invoice["vendor_name"])
                if not filename.endswith(".pdf"):
                    continue
                reader = PdfReader(DATA / "invoices" / filename)
                self.assertEqual(len(reader.pages), 1)
                text = reader.pages[0].extract_text()
                self.assertIn(invoice["vendor_name"], text)
                self.assertIn("ใบกำกับภาษี", text)
                self.assertIn(invoice["invoice_number"], text)
                self.assertEqual(
                    ocr._extract_bank_details(text), (invoice["bank_name"], invoice["bank_account"])
                )
                for line in invoice["lines"]:
                    self.assertIn(line["item_code"], text)
                    description = self.conn.execute(
                        "SELECT description FROM po_lines WHERE po_number=? AND item_code=?",
                        (invoice["po_number"], line["item_code"]),
                    ).fetchone()["description"]
                    self.assertEqual(line["description"], description)
                    self.assertIn("".join(description.split()), "".join(text.split()))

    def test_ocr_bank_parser_preserves_english_and_handles_thai(self):
        ocr = workshop_api._load("02_ocr_invoice.py", "ap_ocr_test")
        for text, expected in (
            ("Please remit to: Bangkok Bank, Account No. 234-5-67890-1",
             ("Bangkok Bank", "234-5-67890-1")),
            ("โอนเงินไปยัง: ธนาคารกรุงเทพ,\nเลขที่บัญชี 234-5-67890-1",
             ("ธนาคารกรุงเทพ", "234-5-67890-1")),
            ("ไม่มีรายละเอียดบัญชี", (None, None)),
        ):
            with self.subTest(text=text):
                self.assertEqual(ocr._extract_bank_details(text), expected)

    def test_layout_ocr_maps_markdown_to_existing_invoice_schema(self):
        ocr = workshop_api._load("02_ocr_invoice.py", "ap_ocr_layout_test")
        invoice = {
            key: value for key, value in self.invoices["INV-TTS-2026-118.pdf"].items()
            if key != "_scenario"
        }
        invoice["vendor_tax_id"] = "0-1234-56789-01-2"
        content = (
            "# Invoice INV-TTS-2026-118\n\n"
            "| Item | Quantity | Unit price | Amount |\n"
            "| --- | --- | --- | --- |\n"
            "| SVC-LAPTOP-IMG | 40 | 1250 | 50000 |\n"
        )
        create = unittest.mock.Mock(return_value=SimpleNamespace(output_text=json.dumps(invoice)))
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        cfg = {
            "docintel_endpoint": "https://example.cognitiveservices.azure.com/",
            "api_key": "test-key",
            "chat_deployment": "test-chat",
        }
        replies = [
            (202, {"operation-location": "https://example.test/operation"}, b""),
            (200, {}, b'{"status": "running"}'),
            (200, {}, json.dumps({
                "status": "succeeded", "analyzeResult": {"content": content},
            }).encode()),
        ]
        with patch.object(ocr, "_request", side_effect=replies) as request, \
                patch.object(ocr.time, "sleep"), \
                patch.object(ocr, "client_for", return_value=client):
            result = ocr.extract_with_document_intelligence(
                DATA / "invoices" / "INV-TTS-2026-118.pdf", cfg,
            )
        analyze = request.call_args_list[0]
        self.assertIn("/prebuilt-layout:analyze?", analyze.args[0])
        self.assertIn("outputContentFormat=markdown", analyze.args[0])
        self.assertEqual(analyze.kwargs["method"], "POST")
        self.assertIn("base64Source", json.loads(analyze.kwargs["data"]))
        self.assertEqual(request.call_args_list[1].args[0], "https://example.test/operation")
        payload = create.call_args.kwargs
        self.assertEqual(payload["model"], "test-chat")
        self.assertIn(content, payload["input"][0]["content"])
        self.assertEqual(payload["text"]["format"]["schema"], ocr.INVOICE_SCHEMA)
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(result["vendor_tax_id"], "0123456789012")
        self.assertEqual(result["lines"], invoice["lines"])
        self.assertEqual(set(result), set(ocr.INVOICE_SCHEMA["required"]))

    def test_layout_ocr_surfaces_failed_and_empty_analysis(self):
        ocr = workshop_api._load("02_ocr_invoice.py", "ap_ocr_layout_errors_test")
        cfg = {"docintel_endpoint": "https://example.test/", "api_key": "test-key"}
        for response, error, message in (
            ({"status": "failed", "error": {"message": "Unreadable file"}},
             RuntimeError, "Unreadable file"),
            ({"status": "succeeded", "analyzeResult": {"content": " \n"}},
             ValueError, "no invoice text"),
        ):
            with self.subTest(response=response), \
                    patch.object(ocr, "_request", side_effect=[
                        (202, {"operation-location": "https://example.test/operation"}, b""),
                        (200, {}, json.dumps(response).encode()),
                    ]), patch.object(ocr.time, "sleep"), \
                    patch.object(ocr, "client_for") as client, \
                    self.assertRaisesRegex(error, message):
                ocr.extract_with_document_intelligence(
                    DATA / "invoices" / "INV-TTS-2026-118.pdf", cfg,
                )
            client.assert_not_called()

    def test_vision_ocr_still_uses_image_and_vision_deployment(self):
        ocr = workshop_api._load("02_ocr_invoice.py", "ap_ocr_vision_test")
        invoice = self.invoices["INV-TTS-2026-118.pdf"]
        create = unittest.mock.Mock(return_value=SimpleNamespace(output_text=json.dumps(invoice)))
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        with patch.object(ocr, "client_for", return_value=client), \
                patch.object(ocr, "_request") as request:
            result = ocr.extract_with_vision(
                DATA / "invoices" / "INV-BEL-7781_scan.png", {"vision_deployment": "test-vision"},
            )
        request.assert_not_called()
        payload = create.call_args.kwargs
        self.assertEqual(payload["model"], "test-vision")
        image = payload["input"][0]["content"][1]
        self.assertEqual(image["type"], "input_image")
        self.assertTrue(image["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(result, invoice)

    def test_chat_router_serializes_thai_context_for_responses_api(self):
        create = unittest.mock.Mock(return_value=SimpleNamespace(output_text="data"))
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        history = [{"role": "user", "content": str(index)} for index in range(12)]
        question = "ปี 2026 จ่ายเงินให้ผู้ขายรายใดมากที่สุด?"
        with patch.object(workshop_api, "config", return_value={"chat_deployment": "test"}), \
                patch.object(workshop_api, "client_for", return_value=client):
            self.assertEqual(workshop_api.route_chat(question, history), "data")
        payload = json.loads(create.call_args.kwargs["input"])
        self.assertEqual(payload["question"], question)
        self.assertEqual(payload["recent_conversation"], history[-10:])


if __name__ == "__main__":
    unittest.main()
