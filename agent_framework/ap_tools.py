"""Function tools for the AP verification agents (Lab 5).

Every tool is a plain Python function with type hints. Agent Framework turns the
signature and docstring into a tool schema the model can call.

Run this file directly to test the tools offline (no Azure calls):

    python agent_framework/ap_tools.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INVOICE_DIR = DATA / "invoices"
POLICY_PDF = DATA / "Contoso_AP_Invoice_Policy.pdf"
sys.path.insert(0, str(ROOT / "python_examples"))
sys.path.insert(0, str(ROOT))
from python_examples.verify import verify_invoice
from python_examples.text2sql import assert_read_only


@lru_cache(maxsize=1)
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript((DATA / "ap_database.sql").read_text(encoding="utf-8"))
    conn.row_factory = sqlite3.Row
    return conn


@lru_cache(maxsize=1)
def _ground_truth() -> dict:
    return json.loads((INVOICE_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def read_invoice(
    file_name: Annotated[str, Field(description="Invoice file name in data/invoices, e.g. INV-TTS-2026-118.pdf")],
) -> str:
    """Return the OCR result (invoice fields and lines as JSON) for an invoice file.

    The lab uses the pre-extracted OCR output from Lab 2 so it runs fast and repeatably.
    """
    invoice = _ground_truth().get(Path(file_name).name)
    if invoice is None:
        return json.dumps({"error": f"Unknown file {file_name}", "available": list(_ground_truth())})
    return json.dumps({k: v for k, v in invoice.items() if not k.startswith("_")})


def run_three_way_match(
    file_name: Annotated[str, Field(description="Invoice file name in data/invoices")],
) -> str:
    """Run Contoso's deterministic AP rules (PO vs goods receipt vs invoice, bank, duplicates, VAT).

    Returns the outcome (APPROVED / ON HOLD / REJECTED), approver, withholding tax and every check.
    This is the ONLY source of truth for the outcome.
    """
    invoice = read_invoice(file_name)
    if '"error"' in invoice[:10]:
        return invoice
    try:
        result = verify_invoice(_db(), json.loads(invoice))
    except Exception as exc:
        return json.dumps({"error": f"AP rules failed: {exc}"})
    return json.dumps(result)


def query_ap_database(
    sql: Annotated[str, Field(description="One read-only SQLite SELECT statement")],
) -> str:
    """Run a read-only SQL query on the AP database and return up to 50 rows as JSON.

    Tables: vendors, purchase_orders, po_lines, goods_receipts, grn_lines, invoices, payments.
    """
    try:
        statement = assert_read_only(sql)
        rows = _db().execute(statement).fetchmany(50)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    except sqlite3.Error as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps([dict(r) for r in rows], default=str)


def get_database_schema() -> str:
    """Return the CREATE TABLE statements of the AP database."""
    rows = _db().execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall()
    return "\n".join(r[0] for r in rows)


@lru_cache(maxsize=1)
def read_policy() -> str:
    """Return the full text of the Contoso AP Invoice Policy (with section numbers)."""
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(str(POLICY_PDF)).pages)


def web_search(
    query: Annotated[str, Field(description="Web search query, e.g. 'Thailand withholding tax rate transport services'")],
) -> str:
    """Search the live web with Microsoft Web IQ. Returns titles, URLs and relevant passages."""
    api_key = os.getenv("WEBIQ_API_KEY", "")
    if not api_key or api_key.startswith("replace-with"):
        return json.dumps({"error": "WEBIQ_API_KEY not set; web search unavailable."})
    request = urllib.request.Request(
        "https://api.microsoft.ai/v3/search/web",
        data=json.dumps({"query": query, "maxResults": 5, "contentFormat": "passage", "maxLength": 1500}).encode(),
        headers={"x-apikey": api_key, "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())
    except Exception as exc:  # noqa: BLE001 - surface any network error to the agent
        return json.dumps({"error": f"Web IQ request failed: {exc}"})
    return json.dumps(
        [{"title": r.get("title"), "url": r.get("url"), "content": r.get("content")} for r in body.get("webResults", [])]
    )


if __name__ == "__main__":
    print("read_invoice:", read_invoice("INV-TTS-2026-118.pdf")[:120], "...")
    for name in sorted(_ground_truth()):
        result = json.loads(run_three_way_match(name))
        holds = [c["detail"] for c in result.get("checks", []) if c["status"] != "PASS"]
        print(f"{name:28} {result.get('outcome', result.get('error')):9} {holds[:1]}")
    print("query_ap_database:", query_ap_database("SELECT invoice_number, status FROM invoices WHERE status='ON_HOLD'"))
    print("blocked write:", query_ap_database("DELETE FROM invoices"))
    print("read_policy:", read_policy()[:80].replace("\n", " "), "...")
    print("web_search:", web_search("Thailand VAT rate")[:120])
