"""Deterministic AP controls: three-way match, duplicates, bank changes, approval, and WHT."""

from __future__ import annotations

from datetime import date
import re
import sqlite3

CONTOSO_TAX_ID = "0105560000001"
VAT_RATE = 0.07
PRICE_TOLERANCE_PCT = 2
TOTAL_TOLERANCE_PCT = 1
TOTAL_TOLERANCE_THB = 1000
APPROVAL_MATRIX = (
    (50_000, "AP Officer"),
    (200_000, "AP Manager"),
    (1_000_000, "Finance Controller"),
    (float("inf"), "CFO"),
)


def _round2(value: float) -> float:
    return round(value + 1e-10, 2)


def _thb(value: float) -> str:
    return f"THB {value:,.2f}"


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _days_between(left: str, right: str) -> int:
    return abs((date.fromisoformat(left) - date.fromisoformat(right)).days)


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _summarize(invoice: dict, vendor: dict | None, checks: list[dict], lines: list[dict] | None = None) -> dict:
    outcome = (
        "REJECTED" if any(item["status"] == "REJECT" for item in checks)
        else "ON HOLD" if any(item["status"] == "HOLD" for item in checks)
        else "APPROVED"
    )
    total = invoice.get("total") or 0
    approver = next(name for maximum, name in APPROVAL_MATRIX if total <= maximum)
    rate = vendor["wht_rate_pct"] if vendor else None
    wht = _round2((invoice.get("subtotal") or 0) * rate / 100) if rate is not None else None
    return {
        "invoice_number": invoice.get("invoice_number"),
        "vendor": (
            {"id": vendor["vendor_id"], "name": vendor["vendor_name"], "category": vendor["category"]}
            if vendor else None
        ),
        "outcome": outcome,
        "approver": f"{approver} (Section 7, total {_thb(total)})",
        "withholding_tax": (
            {"rate_pct": rate, "amount": wht, "net_payable": _round2(total - wht)} if wht is not None else None
        ),
        "checks": checks,
        "lines": lines or [],
    }


def verify_invoice(conn: sqlite3.Connection, invoice: dict) -> dict:
    """Apply the workshop policy to one normalized invoice and return checks plus outcome."""
    checks: list[dict] = []

    def add(check_id: str, section: str, status: str, detail: str) -> None:
        checks.append({"id": check_id, "section": section, "status": status, "detail": detail})

    missing = [
        key for key in ("invoice_number", "invoice_date", "vendor_tax_id", "total", "vat")
        if invoice.get(key) is None
    ]
    add(
        "required_fields", "2", "REJECT" if missing else "PASS",
        f"Missing: {', '.join(missing)}" if missing else "All mandatory tax-invoice fields present",
    )
    if invoice.get("buyer_tax_id") and invoice["buyer_tax_id"] != CONTOSO_TAX_ID:
        add("buyer_entity", "2", "REJECT",
            f"Billed to tax ID {invoice['buyer_tax_id']}, not Contoso ({CONTOSO_TAX_ID})")

    vendor = _one(conn, "SELECT * FROM vendors WHERE tax_id = ?", (invoice.get("vendor_tax_id") or "",))
    if not vendor:
        vendor = _one(
            conn, "SELECT * FROM vendors WHERE lower(vendor_name) = lower(?)", (invoice.get("vendor_name") or "",)
        )
    if not vendor:
        add("vendor_known", "3.5", "HOLD",
            f"Vendor tax ID {invoice.get('vendor_tax_id')} not in vendor master")
        return _summarize(invoice, None, checks)
    add("vendor_known", "3.5", "PASS", f"{vendor['vendor_name']} ({vendor['vendor_id']})")
    add("vendor_status", "6", "HOLD" if vendor["status"] == "BLOCKED" else "PASS",
        f"Vendor status {vendor['status']}")

    if invoice.get("bank_account") and _digits(invoice["bank_account"]) != _digits(vendor["bank_account"]):
        add(
            "bank_account", "6", "HOLD",
            f"Invoice asks payment to {invoice.get('bank_name') or '?'} {invoice['bank_account']}, "
            f"vendor master has {vendor['bank_name']} {vendor['bank_account']}. "
            f"Call back on {vendor['phone']} (vendor master), not the invoice.",
        )
    else:
        add("bank_account", "6", "PASS",
            "Matches vendor master" if invoice.get("bank_account") else "No bank details on invoice")

    same_number = _rows(
        conn,
        "SELECT invoice_number, status, invoice_date FROM invoices "
        "WHERE vendor_id = ? AND invoice_number = ? AND status <> 'REJECTED'",
        (vendor["vendor_id"], invoice.get("invoice_number") or ""),
    )
    same_amount = _rows(
        conn,
        "SELECT invoice_number, status, invoice_date FROM invoices "
        "WHERE vendor_id = ? AND abs(total_amount - ?) < 0.01 AND status <> 'REJECTED'",
        (vendor["vendor_id"], invoice.get("total") or 0),
    )
    same_amount = [
        row for row in same_amount
        if _days_between(row["invoice_date"], invoice["invoice_date"]) <= 30
    ] if invoice.get("invoice_date") else []
    if same_number:
        add("duplicate", "5", "REJECT", f"Invoice number already exists with status {same_number[0]['status']}")
    elif same_amount:
        add("duplicate", "5", "HOLD",
            f"Suspected duplicate: {same_amount[0]['invoice_number']} has the same amount within 30 days")
    else:
        add("duplicate", "5", "PASS", "No duplicate found")

    po = _one(conn, "SELECT * FROM purchase_orders WHERE po_number = ?", (invoice.get("po_number") or "",))
    if not po:
        add("po_exists", "3", "HOLD", f"PO {invoice.get('po_number') or '(missing)'} not found")
        return _summarize(invoice, vendor, checks)
    if po["vendor_id"] != vendor["vendor_id"]:
        add("po_vendor", "3.5", "HOLD",
            f"PO {po['po_number']} belongs to vendor {po['vendor_id']}, not {vendor['vendor_id']}")

    po_lines = _rows(
        conn,
        """SELECT l.line_no, l.item_code, l.description, l.quantity AS ordered, l.unit_price,
                  COALESCE((SELECT SUM(g.quantity_received) FROM grn_lines g
                            WHERE g.po_number = l.po_number AND g.line_no = l.line_no), 0) AS received
             FROM po_lines l WHERE l.po_number = ? ORDER BY l.line_no""",
        (po["po_number"],),
    )
    expected_subtotal = 0.0
    line_results = []
    for line in invoice.get("lines") or []:
        po_line = next(
            (item for item in po_lines if line.get("item_code") and item["item_code"] == line["item_code"]),
            None,
        )
        if po_line is None:
            po_line = next((item for item in po_lines if item["line_no"] == line.get("line_no")), None)
        if po_line is None:
            add("line_match", "3", "HOLD",
                f"Invoice line {line.get('line_no')} ({line.get('item_code') or line.get('description')}) not on PO")
            continue
        price_variance = _round2(((line["unit_price"] - po_line["unit_price"]) / po_line["unit_price"]) * 100)
        price_ok = abs(price_variance) <= PRICE_TOLERANCE_PCT
        quantity_ok = line["quantity"] <= po_line["received"]
        expected_subtotal += min(line["quantity"], po_line["received"]) * po_line["unit_price"]
        line_results.append({
            "line": po_line["line_no"], "item": po_line["item_code"],
            "inv_qty": line["quantity"], "received": po_line["received"],
            "inv_price": line["unit_price"], "po_price": po_line["unit_price"],
            "price_var_pct": price_variance,
        })
        if not price_ok:
            sign = "+" if price_variance > 0 else ""
            add("unit_price", "3.2", "HOLD",
                f"{po_line['item_code']}: invoiced {_thb(line['unit_price'])} vs PO {_thb(po_line['unit_price'])} "
                f"({sign}{price_variance}%, limit {PRICE_TOLERANCE_PCT}%)")
        if not quantity_ok:
            add("quantity", "3.1", "HOLD",
                f"{po_line['item_code']}: invoiced {line['quantity']} but only {po_line['received']} received")

    if not any(item["id"] in {"unit_price", "quantity", "line_match"} for item in checks):
        add("line_match", "3.1-3.2", "PASS",
            f"{len(line_results)} line(s) match PO price and received quantity")

    expected_subtotal = _round2(expected_subtotal)
    diff = _round2((invoice.get("subtotal") or 0) - expected_subtotal)
    allowed = min(expected_subtotal * TOTAL_TOLERANCE_PCT / 100, TOTAL_TOLERANCE_THB)
    add(
        "subtotal", "3.3", "PASS" if abs(diff) <= allowed else "HOLD",
        f"Invoice subtotal {_thb(invoice.get('subtotal') or 0)} vs expected {_thb(expected_subtotal)} "
        f"(diff {_thb(diff)}, allowed {_thb(allowed)})",
    )
    expected_vat = _round2((invoice.get("subtotal") or 0) * VAT_RATE)
    add(
        "vat", "3.4", "PASS" if abs((invoice.get("vat") or 0) - expected_vat) <= 1 else "HOLD",
        f"VAT {_thb(invoice.get('vat') or 0)} vs 7% = {_thb(expected_vat)}",
    )
    return _summarize(invoice, vendor, checks, line_results)
