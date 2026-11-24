"""Regenerate every synthetic file in data/ from one source of truth.

Outputs:
  data/ap_database.sql                     ERP-style AP database (SQLite dialect) for Text2SQL
  data/Contoso_AP_Invoice_Policy.pdf       AP policy for Vector Search (File Search)
  data/invoices/*.pdf                      Incoming vendor invoices for OCR
  data/invoices/INV-BEL-7781_scan.png      "Scanned" invoice image for vision OCR
  data/invoices/ground_truth.json          Expected OCR output per file (to score OCR, or skip OCR offline)

Usage:
  pip install reportlab pillow
  python scripts/generate_sample_data.py

All companies, people, tax IDs and bank accounts are fictitious.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INVOICES = DATA / "invoices"

VAT_RATE = 0.07

BUYER = {
    "name": "Contoso (Thailand) Co., Ltd.",
    "tax_id": "0105560000001",
    "address": "88 Sukhumvit Road, Khlong Toei, Bangkok 10110",
}

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------
VENDORS = [
    # id, name, tax_id, category, wht_rate(%), bank, account, terms, status, phone, address
    ("V001", "Siam Office Supplies Co., Ltd.", "0105551234567", "GOODS", 0, "Kasikornbank", "123-4-56789-0", 30, "ACTIVE", "+66 2 111 2001", "45 Rama IV Road, Pathum Wan, Bangkok 10330"),
    ("V002", "Bangkok Express Logistics Co., Ltd.", "0105559876543", "TRANSPORT", 1, "Bangkok Bank", "234-5-67890-1", 30, "ACTIVE", "+66 2 222 3002", "199 Bang Na-Trat Road, Bang Na, Bangkok 10260"),
    ("V003", "Thai Tech Solutions Co., Ltd.", "0105562223334", "SERVICES", 3, "Siam Commercial Bank", "345-6-78901-2", 45, "ACTIVE", "+66 2 333 4003", "12 Silom Road, Bang Rak, Bangkok 10500"),
    ("V004", "Chiang Mai Paper Products Co., Ltd.", "0505553334445", "GOODS", 0, "Krungthai Bank", "456-7-89012-3", 30, "ACTIVE", "+66 53 444 5004", "77 Huay Kaew Road, Mueang, Chiang Mai 50200"),
    ("V005", "Andaman Marketing Agency Co., Ltd.", "0835554445556", "ADVERTISING", 2, "Kasikornbank", "567-8-90123-4", 30, "BLOCKED", "+66 76 555 6005", "9 Patong Beach Road, Kathu, Phuket 83150"),
    ("V006", "Rama Property Management Co., Ltd.", "0105547778889", "RENTAL", 5, "Bangkok Bank", "678-9-01234-5", 15, "ACTIVE", "+66 2 666 7006", "1 Rama IX Road, Huai Khwang, Bangkok 10310"),
]
VENDOR_BY_ID = {v[0]: v for v in VENDORS}

# po_number, vendor_id, po_date, department, requester, status, lines[(item_code, desc, qty, unit_price)]
PURCHASE_ORDERS = [
    ("PO-2026-0010", "V006", "2026-01-05", "Facilities", "Somsak P.", "OPEN",
     [("RENT-HQ", "Office rent HQ floor 12 (per month)", 12, 80000.00)]),
    ("PO-2026-0087", "V001", "2026-09-01", "Administration", "Nok S.", "CLOSED",
     [("PAP-A4-80", "A4 copy paper 80gsm (box of 5 reams)", 60, 650.00)]),
    ("PO-2026-0092", "V002", "2026-09-10", "Warehouse", "Anan K.", "CLOSED",
     [("LOG-BKK-RYG", "Pallet delivery Bangkok - Rayong (per pallet)", 80, 450.00),
      ("LOG-FUEL", "Fuel surcharge (per trip)", 4, 1200.00)]),
    ("PO-2026-0095", "V003", "2026-09-15", "IT", "Ploy T.", "CLOSED",
     [("SVC-SEC-ASSESS", "Network security assessment", 1, 120000.00)]),
    ("PO-2026-0098", "V005", "2026-09-20", "Marketing", "Mint R.", "OPEN",
     [("MKT-SOCIAL-Q4", "Social media campaign Q4 2026", 1, 250000.00)]),
    ("PO-2026-0101", "V001", "2026-10-20", "Administration", "Nok S.", "OPEN",
     [("PAP-A4-80", "A4 copy paper 80gsm (box of 5 reams)", 50, 650.00),
      ("TON-HP26A", "Toner cartridge HP 26A", 10, 2800.00),
      ("MRK-WB-12", "Whiteboard markers (box of 12)", 20, 180.00)]),
    ("PO-2026-0102", "V003", "2026-10-05", "IT", "Ploy T.", "OPEN",
     [("SVC-LAPTOP-IMG", "Laptop setup and imaging service (per device)", 40, 1150.00),
      ("SVC-M365-MIG", "Microsoft 365 mailbox migration (per mailbox)", 40, 900.00)]),
    ("PO-2026-0103", "V002", "2026-10-12", "Warehouse", "Anan K.", "OPEN",
     [("LOG-BKK-RYG", "Pallet delivery Bangkok - Rayong (per pallet)", 120, 450.00),
      ("LOG-FUEL", "Fuel surcharge (per trip)", 6, 1200.00)]),
    ("PO-2026-0104", "V004", "2026-10-15", "Administration", "Nok S.", "OPEN",
     [("PAP-RCY-A4", "Recycled A4 copy paper (per ream)", 200, 115.00),
      ("CUP-8OZ-50", "Paper cups 8oz (pack of 50)", 40, 95.00)]),
]
PO_BY_NUMBER = {p[0]: p for p in PURCHASE_ORDERS}

# grn_number, po_number, receipt_date, received_by, {line_no: qty_received}
GOODS_RECEIPTS = [
    ("GRN-2026-0150", "PO-2026-0010", "2026-08-01", "Somsak P.", {1: 1}),
    ("GRN-2026-0168", "PO-2026-0010", "2026-09-01", "Somsak P.", {1: 1}),
    ("GRN-2026-0170", "PO-2026-0087", "2026-09-05", "Nok S.", {1: 60}),
    ("GRN-2026-0176", "PO-2026-0092", "2026-09-18", "Anan K.", {1: 80, 2: 4}),
    ("GRN-2026-0181", "PO-2026-0095", "2026-09-29", "Ploy T.", {1: 1}),
    ("GRN-2026-0186", "PO-2026-0010", "2026-10-01", "Somsak P.", {1: 1}),
    ("GRN-2026-0192", "PO-2026-0098", "2026-10-30", "Mint R.", {1: 1}),
    ("GRN-2026-0201", "PO-2026-0101", "2026-10-27", "Nok S.", {1: 50, 2: 10, 3: 20}),
    ("GRN-2026-0203", "PO-2026-0102", "2026-10-30", "Ploy T.", {1: 40, 2: 40}),
    ("GRN-2026-0205", "PO-2026-0103", "2026-10-31", "Anan K.", {1: 100, 2: 5}),
    ("GRN-2026-0207", "PO-2026-0104", "2026-11-03", "Nok S.", {1: 200, 2: 40}),
    ("GRN-2026-0212", "PO-2026-0010", "2026-11-01", "Somsak P.", {1: 1}),
]

# Invoices already in the AP system (history). The 4 new PDFs in data/invoices are NOT here:
# they are the incoming invoices the workshop app must verify.
# invoice_id, invoice_number, vendor_id, po_number, invoice_date, due_date, subtotal,
# currency, status, approved_by, notes
INVOICE_HISTORY = [
    (1, "INV-RPM-2026-08", "V006", "PO-2026-0010", "2026-08-01", "2026-08-16", 80000.00, "THB", "PAID", "Kanya W. (AP Manager)", "Monthly rent August"),
    (2, "INV-RPM-2026-09", "V006", "PO-2026-0010", "2026-09-01", "2026-09-16", 80000.00, "THB", "PAID", "Kanya W. (AP Manager)", "Monthly rent September"),
    (3, "INV-SOS-2026-0388", "V001", "PO-2026-0087", "2026-09-06", "2026-10-06", 39000.00, "THB", "PAID", "Malee C. (AP Officer)", None),
    (4, "INV-BEL-7702", "V002", "PO-2026-0092", "2026-09-20", "2026-10-20", 40800.00, "THB", "PAID", "Malee C. (AP Officer)", None),
    (5, "INV-RPM-2026-10", "V006", "PO-2026-0010", "2026-10-01", "2026-10-16", 80000.00, "THB", "PAID", "Kanya W. (AP Manager)", "Monthly rent October"),
    (6, "INV-TTS-2026-102", "V003", "PO-2026-0095", "2026-09-30", "2026-11-14", 120000.00, "THB", "APPROVED", "Kanya W. (AP Manager)", "Approved; payment run missed"),
    (7, "INV-AMA-0931", "V005", "PO-2026-0098", "2026-10-31", "2026-11-30", 250000.00, "THB", "ON_HOLD", None, "Vendor blocked: VAT registration certificate (Por Por 20) expired; awaiting updated document"),
    (8, "INV-RPM-2026-11", "V006", "PO-2026-0010", "2026-11-01", "2026-11-16", 80000.00, "THB", "PENDING", None, "Monthly rent November; awaiting AP Manager approval"),
    (9, "INV-SOS-2026-0388", "V001", "PO-2026-0087", "2026-09-06", "2026-10-06", 39000.00, "THB", "REJECTED", "Malee C. (AP Officer)", "Duplicate resubmission received 2026-11-10; original already paid on 2026-10-06"),
]

# payment_id, invoice_id, payment_date, method
PAYMENTS = [
    (1, 1, "2026-08-15", "BANK_TRANSFER"),
    (2, 2, "2026-09-15", "BANK_TRANSFER"),
    (3, 3, "2026-10-06", "BANK_TRANSFER"),
    (4, 4, "2026-10-20", "BANK_TRANSFER"),
    (5, 5, "2026-10-15", "BANK_TRANSFER"),
]

# ---------------------------------------------------------------------------
# Incoming invoices (the OCR inputs). Each one tests a different policy rule.
# ---------------------------------------------------------------------------
NEW_INVOICES = [
    {
        "file": "INV-SOS-2026-0415.pdf",
        "scenario": "Clean 3-way match -> APPROVE (route to AP Manager, > THB 50,000)",
        "invoice_number": "INV-SOS-2026-0415",
        "vendor_id": "V001",
        "po_number": "PO-2026-0101",
        "invoice_date": "2026-10-28",
        "due_date": "2026-11-27",
        "lines": [(1, 50, 650.00), (2, 10, 2800.00), (3, 20, 180.00)],
        "bank": None,
    },
    {
        "file": "INV-TTS-2026-118.pdf",
        "scenario": "Unit price 1,250 vs PO 1,150 (+8.7%) -> HOLD (price variance > 2%)",
        "invoice_number": "INV-TTS-2026-118",
        "vendor_id": "V003",
        "po_number": "PO-2026-0102",
        "invoice_date": "2026-11-02",
        "due_date": "2026-12-17",
        "lines": [(1, 40, 1250.00), (2, 40, 900.00)],
        "bank": None,
    },
    {
        "file": "INV-BEL-7781.pdf",
        "scenario": "Billed 120 pallets / 6 trips but only 100 / 5 received -> HOLD (qty > GRN)",
        "invoice_number": "INV-BEL-7781",
        "vendor_id": "V002",
        "po_number": "PO-2026-0103",
        "invoice_date": "2026-11-05",
        "due_date": "2026-12-05",
        "lines": [(1, 120, 450.00), (2, 6, 1200.00)],
        "bank": None,
    },
    {
        "file": "INV-CMP-2026-0057.pdf",
        "scenario": "Amounts match but bank account differs from vendor master -> HOLD (bank change verification)",
        "invoice_number": "INV-CMP-2026-0057",
        "vendor_id": "V004",
        "po_number": "PO-2026-0104",
        "invoice_date": "2026-11-06",
        "due_date": "2026-12-06",
        "lines": [(1, 200, 115.00), (2, 40, 95.00)],
        "bank": ("Siam Commercial Bank", "999-1-23456-7"),
    },
]


def money(x: float) -> str:
    return f"{x:,.2f}"


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


def sql_str(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# SQL database
# ---------------------------------------------------------------------------
SCHEMA = """-- Contoso (Thailand) AP database. Synthetic data for the workshop.
-- Loaded into Python's in-memory sqlite3 database. Regenerate with scripts/generate_sample_data.py.

CREATE TABLE vendors (
  vendor_id          TEXT PRIMARY KEY,
  vendor_name        TEXT NOT NULL,
  tax_id             TEXT NOT NULL UNIQUE,      -- 13-digit Thai tax ID
  category           TEXT NOT NULL,             -- GOODS | SERVICES | TRANSPORT | ADVERTISING | RENTAL
  wht_rate_pct       REAL NOT NULL,             -- withholding tax % applied to pre-VAT amount
  bank_name          TEXT NOT NULL,
  bank_account       TEXT NOT NULL,             -- approved remittance account (vendor master)
  payment_terms_days INTEGER NOT NULL,
  status             TEXT NOT NULL,             -- ACTIVE | BLOCKED
  phone              TEXT NOT NULL,             -- callback number for bank-change verification
  address            TEXT NOT NULL
);

CREATE TABLE purchase_orders (
  po_number   TEXT PRIMARY KEY,
  vendor_id   TEXT NOT NULL REFERENCES vendors(vendor_id),
  po_date     TEXT NOT NULL,                    -- ISO date
  department  TEXT NOT NULL,
  requester   TEXT NOT NULL,
  currency    TEXT NOT NULL DEFAULT 'THB',
  status      TEXT NOT NULL                     -- OPEN | CLOSED
);

CREATE TABLE po_lines (
  po_number   TEXT NOT NULL REFERENCES purchase_orders(po_number),
  line_no     INTEGER NOT NULL,
  item_code   TEXT NOT NULL,
  description TEXT NOT NULL,
  quantity    REAL NOT NULL,
  unit_price  REAL NOT NULL,                    -- excl. VAT
  PRIMARY KEY (po_number, line_no)
);

CREATE TABLE goods_receipts (
  grn_number    TEXT PRIMARY KEY,
  po_number     TEXT NOT NULL REFERENCES purchase_orders(po_number),
  receipt_date  TEXT NOT NULL,
  received_by   TEXT NOT NULL
);

CREATE TABLE grn_lines (
  grn_number        TEXT NOT NULL REFERENCES goods_receipts(grn_number),
  po_number         TEXT NOT NULL,
  line_no           INTEGER NOT NULL,           -- matches po_lines.line_no
  quantity_received REAL NOT NULL,
  PRIMARY KEY (grn_number, line_no)
);

CREATE TABLE invoices (
  invoice_id      INTEGER PRIMARY KEY,
  invoice_number  TEXT NOT NULL,                -- vendor's invoice number (not unique: duplicates are possible)
  vendor_id       TEXT NOT NULL REFERENCES vendors(vendor_id),
  po_number       TEXT REFERENCES purchase_orders(po_number),
  invoice_date    TEXT NOT NULL,
  due_date        TEXT NOT NULL,
  subtotal        REAL NOT NULL,                -- excl. VAT
  vat_amount      REAL NOT NULL,
  total_amount    REAL NOT NULL,                -- incl. VAT
  currency        TEXT NOT NULL DEFAULT 'THB',
  status          TEXT NOT NULL,                -- PENDING | APPROVED | ON_HOLD | REJECTED | PAID
  approved_by     TEXT,
  notes           TEXT
);

CREATE TABLE payments (
  payment_id    INTEGER PRIMARY KEY,
  invoice_id    INTEGER NOT NULL REFERENCES invoices(invoice_id),
  payment_date  TEXT NOT NULL,
  gross_amount  REAL NOT NULL,                  -- invoice total incl. VAT
  wht_amount    REAL NOT NULL,                  -- withholding tax deducted
  net_paid      REAL NOT NULL,                  -- gross_amount - wht_amount
  method        TEXT NOT NULL
);
"""


def build_sql() -> str:
    out = [SCHEMA]

    out.append("\n-- vendors")
    for v in VENDORS:
        out.append(f"INSERT INTO vendors VALUES ({', '.join(sql_str(x) for x in v)});")

    out.append("\n-- purchase orders")
    for po, vid, d, dept, req, status, lines in PURCHASE_ORDERS:
        out.append(
            f"INSERT INTO purchase_orders VALUES ({sql_str(po)}, {sql_str(vid)}, {sql_str(d)}, "
            f"{sql_str(dept)}, {sql_str(req)}, 'THB', {sql_str(status)});"
        )
        for i, (code, desc, qty, price) in enumerate(lines, start=1):
            out.append(
                f"INSERT INTO po_lines VALUES ({sql_str(po)}, {i}, {sql_str(code)}, {sql_str(desc)}, {qty}, {price});"
            )

    out.append("\n-- goods receipts")
    for grn, po, d, by, lines in GOODS_RECEIPTS:
        out.append(f"INSERT INTO goods_receipts VALUES ({sql_str(grn)}, {sql_str(po)}, {sql_str(d)}, {sql_str(by)});")
        for line_no, qty in lines.items():
            out.append(f"INSERT INTO grn_lines VALUES ({sql_str(grn)}, {sql_str(po)}, {line_no}, {qty});")

    out.append("\n-- invoice history")
    inv_by_id = {}
    for inv in INVOICE_HISTORY:
        iid, num, vid, po, d, due, sub, cur, status, appr, notes = inv
        vat = r2(sub * VAT_RATE)
        total = r2(sub + vat)
        inv_by_id[iid] = (vid, sub, total)
        out.append(
            "INSERT INTO invoices VALUES ("
            + ", ".join(sql_str(x) for x in (iid, num, vid, po, d, due, sub, vat, total, cur, status, appr, notes))
            + ");"
        )

    out.append("\n-- payments")
    for pid, iid, d, method in PAYMENTS:
        vid, sub, total = inv_by_id[iid]
        wht = r2(sub * VENDOR_BY_ID[vid][4] / 100)
        out.append(
            f"INSERT INTO payments VALUES ({pid}, {iid}, {sql_str(d)}, {total}, {wht}, {r2(total - wht)}, {sql_str(method)});"
        )
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Invoice rendering
# ---------------------------------------------------------------------------
def invoice_model(spec: dict) -> dict:
    vendor = VENDOR_BY_ID[spec["vendor_id"]]
    po_lines = PO_BY_NUMBER[spec["po_number"]][6]
    lines = []
    for line_no, qty, price in spec["lines"]:
        code, desc, _, _ = po_lines[line_no - 1]
        lines.append({"code": code, "desc": desc, "qty": qty, "price": price, "amount": r2(qty * price)})
    subtotal = r2(sum(l["amount"] for l in lines))
    vat = r2(subtotal * VAT_RATE)
    bank = spec["bank"] or (vendor[5], vendor[6])
    return {
        **spec,
        "vendor_name": vendor[1],
        "vendor_tax_id": vendor[2],
        "vendor_address": vendor[10],
        "vendor_phone": vendor[9],
        "lines": lines,
        "subtotal": subtotal,
        "vat": vat,
        "total": r2(subtotal + vat),
        "bank_name": bank[0],
        "bank_account": bank[1],
    }


def render_invoice_pdf(inv: dict, path: Path) -> None:
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, leading=12)
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=20, alignment=2)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm)

    header = Table(
        [[
            Paragraph(f"<b>{inv['vendor_name']}</b><br/>{inv['vendor_address']}<br/>"
                      f"Tax ID: {inv['vendor_tax_id']} (Head Office)<br/>Tel: {inv['vendor_phone']}", small),
            Paragraph("TAX INVOICE", title),
        ]],
        colWidths=[105 * mm, 69 * mm],
    )
    meta = Table(
        [[
            Paragraph(f"<b>Bill To</b><br/>{BUYER['name']}<br/>{BUYER['address']}<br/>Tax ID: {BUYER['tax_id']}", small),
            Paragraph(f"<b>Invoice No:</b> {inv['invoice_number']}<br/><b>Invoice Date:</b> {inv['invoice_date']}<br/>"
                      f"<b>Due Date:</b> {inv['due_date']}<br/><b>Customer PO:</b> {inv['po_number']}", small),
        ]],
        colWidths=[105 * mm, 69 * mm],
    )
    rows = [["#", "Item Code", "Description", "Qty", "Unit Price", "Amount (THB)"]]
    for i, l in enumerate(inv["lines"], start=1):
        rows.append([str(i), l["code"], Paragraph(l["desc"], small), f"{l['qty']:g}", money(l["price"]), money(l["amount"])])
    rows += [
        ["", "", "", "", "Subtotal", money(inv["subtotal"])],
        ["", "", "", "", "VAT 7%", money(inv["vat"])],
        ["", "", "", "", "Total", money(inv["total"])],
    ]
    items = Table(rows, colWidths=[8 * mm, 28 * mm, 70 * mm, 14 * mm, 24 * mm, 30 * mm])
    n = len(inv["lines"])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, n), 0.4, colors.grey),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (4, n + 3), (-1, n + 3), "Helvetica-Bold"),
        ("LINEABOVE", (4, n + 1), (-1, n + 1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    pay = Paragraph(
        f"<b>Payment Instructions</b><br/>Please remit to: {inv['bank_name']}, Account No. {inv['bank_account']}, "
        f"Account Name: {inv['vendor_name']}<br/>Payment terms: due by {inv['due_date']}. "
        "Withholding tax certificate (50 Tawi) to be sent to accounting@vendor.example.",
        small,
    )
    doc.build([header, Spacer(1, 8 * mm), meta, Spacer(1, 8 * mm), items, Spacer(1, 10 * mm), pay,
               Spacer(1, 18 * mm), Paragraph("Authorized Signature ____________________", small)])


def _font(size: int):
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def render_invoice_png(inv: dict, path: Path) -> None:
    """A slightly skewed, noisy 'phone scan' so vision OCR has something realistic to read."""
    w, h = 1240, 1754
    img = Image.new("RGB", (w, h), (250, 249, 244))
    d = ImageDraw.Draw(img)
    f_b, f_m, f_s = _font(46), _font(26), _font(22)
    y = 80
    d.text((80, y), inv["vendor_name"], font=f_m, fill="black")
    d.text((820, y), "TAX INVOICE", font=f_b, fill=(31, 78, 121))
    for line in (inv["vendor_address"], f"Tax ID: {inv['vendor_tax_id']}", f"Tel: {inv['vendor_phone']}"):
        y += 34
        d.text((80, y), line, font=f_s, fill="black")
    y += 80
    d.text((80, y), "Bill To:", font=f_m, fill="black")
    d.text((760, y), f"Invoice No: {inv['invoice_number']}", font=f_s, fill="black")
    for left, right in (
        (BUYER["name"], f"Invoice Date: {inv['invoice_date']}"),
        (BUYER["address"], f"Due Date: {inv['due_date']}"),
        (f"Tax ID: {BUYER['tax_id']}", f"Customer PO: {inv['po_number']}"),
    ):
        y += 34
        d.text((80, y), left, font=f_s, fill="black")
        d.text((760, y), right, font=f_s, fill="black")
    y += 80
    cols = [80, 130, 330, 800, 900, 1060]
    d.rectangle([70, y - 8, 1170, y + 34], fill=(31, 78, 121))
    for x, t in zip(cols, ["#", "Item Code", "Description", "Qty", "Unit Price", "Amount"]):
        d.text((x, y), t, font=f_s, fill="white")
    for i, l in enumerate(inv["lines"], start=1):
        y += 50
        for x, t in zip(cols, [str(i), l["code"], l["desc"][:36], f"{l['qty']:g}", money(l["price"]), money(l["amount"])]):
            d.text((x, y), t, font=f_s, fill="black")
    y += 70
    for label, val in (("Subtotal", inv["subtotal"]), ("VAT 7%", inv["vat"]), ("Total", inv["total"])):
        d.text((870, y), label, font=f_m, fill="black")
        d.text((1030, y), money(val), font=f_m, fill="black")
        y += 42
    y += 60
    d.text((80, y), "Payment Instructions", font=f_m, fill="black")
    y += 38
    d.text((80, y), f"Remit to: {inv['bank_name']}, Account No. {inv['bank_account']}", font=f_s, fill="black")
    y += 120
    d.text((80, y), "Authorized Signature ____________________", font=f_s, fill="black")

    rng = random.Random(42)
    px = img.load()
    for _ in range(9000):
        x, yy = rng.randrange(w), rng.randrange(h)
        g = rng.randint(150, 220)
        px[x, yy] = (g, g, g)
    img = img.rotate(1.2, resample=Image.BICUBIC, expand=False, fillcolor=(235, 233, 226)).filter(ImageFilter.GaussianBlur(0.6))
    img.save(path, optimize=True)


# ---------------------------------------------------------------------------
# AP policy PDF (Vector Search knowledge)
# ---------------------------------------------------------------------------
POLICY = [
    ("1. Purpose and Scope",
     ["This policy defines how the Accounts Payable (AP) team of Contoso (Thailand) Co., Ltd. verifies supplier "
      "invoices before payment. It applies to all purchase-order (PO) backed invoices in Thai Baht (THB) and in "
      "foreign currency. Non-PO invoices (for example utilities) follow Appendix A and are out of scope for the "
      "automated verification assistant.",
      "Policy owner: Finance Controller. Effective date: 1 July 2026. Version 3.2."]),
    ("2. Required Invoice Fields",
     ["An invoice is only valid for processing if it is a full Tax Invoice under the Thai Revenue Code (Section 86/4) "
      "and shows: (a) the words 'Tax Invoice'; (b) supplier name, address and 13-digit tax ID; (c) buyer name, address "
      "and tax ID (Contoso tax ID 0105560000001); (d) invoice number and invoice date; (e) description, quantity and "
      "value of goods or services; (f) VAT shown separately from the price.",
      "Invoices missing any required field are REJECTED and returned to the supplier with the reason. A Contoso PO "
      "number must be quoted on every PO-backed invoice; if missing, the AP Officer may look it up but must record "
      "the lookup in the invoice notes."]),
    ("3. Three-Way Match",
     ["Every PO-backed invoice must pass a three-way match between the Purchase Order (PO), the Goods Receipt Note "
      "(GRN, or service acceptance for services) and the Invoice. Matching is done line by line using the PO line "
      "number or item code.",
      "3.1 Quantity: the invoiced quantity for each line must NOT exceed the cumulative quantity received on GRNs for "
      "that PO line. There is zero tolerance on quantity. Partial invoicing (invoiced quantity lower than received) "
      "is allowed.",
      "3.2 Unit price: the invoiced unit price (excluding VAT) may differ from the PO unit price by at most 2% per "
      "line. Any line above 2% is a price variance exception.",
      "3.3 Invoice total: the invoice subtotal (excluding VAT) may differ from the expected subtotal (matched "
      "quantity x PO unit price) by at most 1% or THB 1,000, whichever is lower.",
      "3.4 VAT: VAT must equal 7% of the subtotal, with a rounding tolerance of THB 1.00.",
      "3.5 Vendor: the supplier tax ID on the invoice must match the vendor on the PO in the vendor master."]),
    ("4. Verification Outcomes",
     ["APPROVED: all checks pass. The invoice is routed for approval according to Section 7.",
      "ON HOLD: one or more exceptions that may be resolved, for example price variance, quantity exceeding receipt, "
      "bank detail change, blocked vendor or missing GRN. The AP Officer must contact the requester or supplier and "
      "resolve the exception within 3 business days. Held invoices are revisited every 7 days until resolved.",
      "REJECTED: the invoice cannot be paid in its current form, for example a duplicate invoice, an invalid tax "
      "invoice, or an invoice addressed to another legal entity. The supplier must issue a credit note or a "
      "corrected invoice.",
      "The verification assistant only RECOMMENDS an outcome. A human AP Officer always makes the final decision and "
      "records it in the AP system."]),
    ("5. Duplicate Invoice Detection",
     ["Before approval, AP must check for duplicates. An invoice is treated as a suspected duplicate if either: "
      "(a) the same vendor and the same invoice number already exist in any status other than REJECTED; or "
      "(b) the same vendor, the same total amount and an invoice date within 30 days of an existing invoice.",
      "Confirmed duplicates are REJECTED. Never pay an invoice twice; if a duplicate payment is discovered, "
      "notify the AP Manager the same day and request a refund from the supplier."]),
    ("6. Vendor Master and Bank Detail Changes",
     ["Payments are only made to the bank account recorded in the vendor master. If the bank account printed on an "
      "invoice differs from the vendor master, the invoice must be put ON HOLD and must not be paid. This is a common "
      "invoice-fraud pattern (business email compromise).",
      "To verify a bank change: (1) call the supplier using the phone number already stored in the vendor master, "
      "never a number printed on the invoice or in an email; (2) obtain a signed bank change letter on company "
      "letterhead plus a bank book or bank confirmation; (3) the Vendor Master team updates the record with "
      "two-person approval; (4) a cooling-off period of 5 business days applies before the first payment to the "
      "new account.",
      "Invoices from vendors with status BLOCKED must be put ON HOLD until the Vendor Master team unblocks the vendor."]),
    ("7. Approval Matrix",
     ["Approval is based on the invoice total including VAT:",
      "- Up to THB 50,000: AP Officer.",
      "- THB 50,000.01 to THB 200,000: AP Manager.",
      "- THB 200,000.01 to THB 1,000,000: Finance Controller.",
      "- Above THB 1,000,000: Chief Financial Officer (CFO).",
      "The person who verifies an invoice cannot be the same person who approves it (segregation of duties)."]),
    ("8. Withholding Tax (WHT) and VAT",
     ["Contoso deducts withholding tax at payment, calculated on the amount before VAT, based on the vendor category "
      "in the vendor master: services 3%, transport 1%, advertising 2%, rental 5%, goods 0%.",
      "Net payment = invoice total including VAT minus WHT. A withholding tax certificate (Form 50 Tawi) must be "
      "issued to the supplier for every payment with WHT, and WHT must be filed with the Revenue Department "
      "(Form Por Ngor Dor 53) by the 7th of the following month (15th if filed online).",
      "Standard VAT is 7%. If the Revenue Department announces a change to VAT or WHT rates, the Tax team will update "
      "this policy; AP staff should verify current rates on the Revenue Department website when in doubt."]),
    ("9. Payment Terms",
     ["Default payment term is 30 days from invoice date unless the vendor master specifies otherwise. Payment runs "
      "are executed every Tuesday and Friday. Approved invoices due before the next payment run are included in the "
      "current run. Overdue approved invoices must be escalated to the AP Manager.",
      "Early payment discounts (for example 2/10 net 30) should be captured whenever the invoice is approved within "
      "the discount window."]),
    ("10. Foreign Currency Invoices",
     ["Foreign currency invoices are converted to THB for approval-matrix purposes using the Bank of Thailand "
      "reference rate (average selling rate) on the invoice date. The rate and source must be recorded in the invoice "
      "notes."]),
    ("11. Record Retention",
     ["Invoices, GRNs, POs and payment evidence must be retained for at least 5 years from the end of the accounting "
      "period, in line with Thai tax and accounting requirements."]),
    ("Appendix A. Quick Reference for AP Officers",
     ["Price tolerance: 2% per line. Total tolerance: 1% or THB 1,000 (lower). Quantity tolerance: zero.",
      "Bank details differ from vendor master: ON HOLD, callback using vendor-master phone number, 5 business-day "
      "cooling-off.",
      "Duplicate (same vendor + invoice number): REJECT.",
      "Questions about this policy: ap-policy@contoso.example. Questions about vendor master data: "
      "vendor-master@contoso.example."]),
]


def render_policy_pdf(path: Path) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=15, spaceAfter=6)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            title="Contoso AP Invoice Verification Policy")
    flow = [
        Paragraph("Contoso (Thailand) Co., Ltd.", styles["Heading2"]),
        Paragraph("Accounts Payable Invoice Verification Policy", styles["Title"]),
        Paragraph("Version 3.2, effective 1 July 2026. Owner: Finance Controller. Internal use only.", body),
        Spacer(1, 6 * mm),
    ]
    for i, (heading, paras) in enumerate(POLICY):
        if i in (4, 8):
            flow.append(PageBreak())
        flow.append(Paragraph(heading, styles["Heading2"]))
        flow += [Paragraph(p, body) for p in paras]
    doc.build(flow)


def ground_truth(inv: dict) -> dict:
    """What a perfect OCR run should return (same shape as Python invoice extraction)."""
    return {
        "invoice_number": inv["invoice_number"],
        "invoice_date": inv["invoice_date"],
        "due_date": inv["due_date"],
        "po_number": inv["po_number"],
        "vendor_name": inv["vendor_name"],
        "vendor_tax_id": inv["vendor_tax_id"],
        "buyer_tax_id": BUYER["tax_id"],
        "bank_name": inv["bank_name"],
        "bank_account": inv["bank_account"],
        "currency": "THB",
        "subtotal": inv["subtotal"],
        "vat": inv["vat"],
        "total": inv["total"],
        "lines": [
            {"line_no": i, "item_code": l["code"], "description": l["desc"], "quantity": l["qty"],
             "unit_price": l["price"], "amount": l["amount"]}
            for i, l in enumerate(inv["lines"], start=1)
        ],
        "_scenario": inv["scenario"],
    }


def main() -> None:
    INVOICES.mkdir(parents=True, exist_ok=True)
    (DATA / "ap_database.sql").write_text(build_sql(), encoding="utf-8")
    render_policy_pdf(DATA / "Contoso_AP_Invoice_Policy.pdf")
    truth = {}
    for spec in NEW_INVOICES:
        inv = invoice_model(spec)
        render_invoice_pdf(inv, INVOICES / spec["file"])
        truth[spec["file"]] = ground_truth(inv)
        if spec["invoice_number"] == "INV-BEL-7781":
            render_invoice_png(inv, INVOICES / "INV-BEL-7781_scan.png")
            truth["INV-BEL-7781_scan.png"] = truth[spec["file"]]
        print(f"  {spec['file']:<26} total {money(inv['total']):>12}  {spec['scenario']}")
    (INVOICES / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
    print("Done. Files written to", DATA)


if __name__ == "__main__":
    main()
