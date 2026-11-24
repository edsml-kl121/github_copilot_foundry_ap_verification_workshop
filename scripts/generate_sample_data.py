"""Regenerate every synthetic file in data/ from one source of truth.

Outputs:
  data/ap_database.sql                     ERP-style AP database (SQLite dialect) for Text2SQL
  data/Contoso_AP_Invoice_Policy.pdf       AP policy for Vector Search (File Search)
  data/invoices/*.pdf                      Incoming vendor invoices for OCR
  data/invoices/INV-BEL-7781_scan.png      "Scanned" invoice image for vision OCR
  data/invoices/ground_truth.json          Expected OCR output per file (to score OCR, or skip OCR offline)

Usage:
  pip install -r scripts/requirements.txt
  python scripts/generate_sample_data.py

All companies, people, tax IDs and bank accounts are fictitious.
Sarabun fonts: https://github.com/google/fonts/tree/main/ofl/sarabun
Redistributed under the SIL Open Font License in scripts/fonts/OFL.txt.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
FONTS = Path(__file__).resolve().parent / "fonts"

VAT_RATE = 0.07

BUYER = {
    "name": "บริษัท คอนโทโซ (ประเทศไทย) จำกัด",
    "tax_id": "0105560000001",
    "address": "88 ถนนสุขุมวิท เขตคลองเตย กรุงเทพมหานคร 10110",
}

# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------
VENDORS = [
    # id, name, tax_id, category, wht_rate(%), bank, account, terms, status, phone, address
    ("V001", "บริษัท สยามเครื่องใช้สำนักงาน จำกัด", "0105551234567", "GOODS", 0, "ธนาคารกสิกรไทย", "123-4-56789-0", 30, "ACTIVE", "+66 2 111 2001", "45 ถนนพระราม 4 เขตปทุมวัน กรุงเทพมหานคร 10330"),
    ("V002", "บริษัท บางกอกเอ็กซ์เพรสโลจิสติกส์ จำกัด", "0105559876543", "TRANSPORT", 1, "ธนาคารกรุงเทพ", "234-5-67890-1", 30, "ACTIVE", "+66 2 222 3002", "199 ถนนบางนา-ตราด เขตบางนา กรุงเทพมหานคร 10260"),
    ("V003", "บริษัท ไทยเทคโซลูชันส์ จำกัด", "0105562223334", "SERVICES", 3, "ธนาคารไทยพาณิชย์", "345-6-78901-2", 45, "ACTIVE", "+66 2 333 4003", "12 ถนนสีลม เขตบางรัก กรุงเทพมหานคร 10500"),
    ("V004", "บริษัท เชียงใหม่ผลิตภัณฑ์กระดาษ จำกัด", "0505553334445", "GOODS", 0, "ธนาคารกรุงไทย", "456-7-89012-3", 30, "ACTIVE", "+66 53 444 5004", "77 ถนนห้วยแก้ว อำเภอเมืองเชียงใหม่ จังหวัดเชียงใหม่ 50200"),
    ("V005", "บริษัท อันดามันมาร์เก็ตติ้งเอเจนซี จำกัด", "0835554445556", "ADVERTISING", 2, "ธนาคารกสิกรไทย", "567-8-90123-4", 30, "BLOCKED", "+66 76 555 6005", "9 ถนนหาดป่าตอง อำเภอกะทู้ จังหวัดภูเก็ต 83150"),
    ("V006", "บริษัท พระรามบริหารทรัพย์สิน จำกัด", "0105547778889", "RENTAL", 5, "ธนาคารกรุงเทพ", "678-9-01234-5", 15, "ACTIVE", "+66 2 666 7006", "1 ถนนพระราม 9 เขตห้วยขวาง กรุงเทพมหานคร 10310"),
]
VENDOR_BY_ID = {v[0]: v for v in VENDORS}

# po_number, vendor_id, po_date, department, requester, status, lines[(item_code, desc, qty, unit_price)]
PURCHASE_ORDERS = [
    ("PO-2026-0010", "V006", "2026-01-05", "อาคารสถานที่", "สมศักดิ์ พ.", "OPEN",
     [("RENT-HQ", "ค่าเช่าสำนักงานใหญ่ ชั้น 12 (ต่อเดือน)", 12, 80000.00)]),
    ("PO-2026-0087", "V001", "2026-09-01", "ธุรการ", "นก ส.", "CLOSED",
     [("PAP-A4-80", "กระดาษถ่ายเอกสาร A4 80 แกรม (กล่องละ 5 รีม)", 60, 650.00)]),
    ("PO-2026-0092", "V002", "2026-09-10", "คลังสินค้า", "อนันต์ ก.", "CLOSED",
     [("LOG-BKK-RYG", "ค่าขนส่งพาเลต กรุงเทพฯ - ระยอง (ต่อพาเลต)", 80, 450.00),
      ("LOG-FUEL", "ค่าธรรมเนียมน้ำมัน (ต่อเที่ยว)", 4, 1200.00)]),
    ("PO-2026-0095", "V003", "2026-09-15", "เทคโนโลยีสารสนเทศ", "พลอย ท.", "CLOSED",
     [("SVC-SEC-ASSESS", "บริการประเมินความปลอดภัยเครือข่าย", 1, 120000.00)]),
    ("PO-2026-0098", "V005", "2026-09-20", "การตลาด", "มิ้นท์ ร.", "OPEN",
     [("MKT-SOCIAL-Q4", "แคมเปญสื่อสังคมออนไลน์ ไตรมาส 4 ปี 2026", 1, 250000.00)]),
    ("PO-2026-0101", "V001", "2026-10-20", "ธุรการ", "นก ส.", "OPEN",
     [("PAP-A4-80", "กระดาษถ่ายเอกสาร A4 80 แกรม (กล่องละ 5 รีม)", 50, 650.00),
      ("TON-HP26A", "ตลับหมึกเครื่องพิมพ์ HP 26A", 10, 2800.00),
      ("MRK-WB-12", "ปากกาไวท์บอร์ด (กล่องละ 12 ด้าม)", 20, 180.00)]),
    ("PO-2026-0102", "V003", "2026-10-05", "เทคโนโลยีสารสนเทศ", "พลอย ท.", "OPEN",
     [("SVC-LAPTOP-IMG", "บริการติดตั้งระบบโน้ตบุ๊ก (ต่อเครื่อง)", 40, 1150.00),
      ("SVC-M365-MIG", "บริการย้ายกล่องจดหมาย Microsoft 365 (ต่อกล่อง)", 40, 900.00)]),
    ("PO-2026-0103", "V002", "2026-10-12", "คลังสินค้า", "อนันต์ ก.", "OPEN",
     [("LOG-BKK-RYG", "ค่าขนส่งพาเลต กรุงเทพฯ - ระยอง (ต่อพาเลต)", 120, 450.00),
      ("LOG-FUEL", "ค่าธรรมเนียมน้ำมัน (ต่อเที่ยว)", 6, 1200.00)]),
    ("PO-2026-0104", "V004", "2026-10-15", "ธุรการ", "นก ส.", "OPEN",
     [("PAP-RCY-A4", "กระดาษถ่ายเอกสาร A4 รีไซเคิล (ต่อรีม)", 200, 115.00),
      ("CUP-8OZ-50", "แก้วกระดาษ 8 ออนซ์ (แพ็กละ 50 ใบ)", 40, 95.00)]),
]
PO_BY_NUMBER = {p[0]: p for p in PURCHASE_ORDERS}

# grn_number, po_number, receipt_date, received_by, {line_no: qty_received}
GOODS_RECEIPTS = [
    ("GRN-2026-0150", "PO-2026-0010", "2026-08-01", "สมศักดิ์ พ.", {1: 1}),
    ("GRN-2026-0168", "PO-2026-0010", "2026-09-01", "สมศักดิ์ พ.", {1: 1}),
    ("GRN-2026-0170", "PO-2026-0087", "2026-09-05", "นก ส.", {1: 60}),
    ("GRN-2026-0176", "PO-2026-0092", "2026-09-18", "อนันต์ ก.", {1: 80, 2: 4}),
    ("GRN-2026-0181", "PO-2026-0095", "2026-09-29", "พลอย ท.", {1: 1}),
    ("GRN-2026-0186", "PO-2026-0010", "2026-10-01", "สมศักดิ์ พ.", {1: 1}),
    ("GRN-2026-0192", "PO-2026-0098", "2026-10-30", "มิ้นท์ ร.", {1: 1}),
    ("GRN-2026-0201", "PO-2026-0101", "2026-10-27", "นก ส.", {1: 50, 2: 10, 3: 20}),
    ("GRN-2026-0203", "PO-2026-0102", "2026-10-30", "พลอย ท.", {1: 40, 2: 40}),
    ("GRN-2026-0205", "PO-2026-0103", "2026-10-31", "อนันต์ ก.", {1: 100, 2: 5}),
    ("GRN-2026-0207", "PO-2026-0104", "2026-11-03", "นก ส.", {1: 200, 2: 40}),
    ("GRN-2026-0212", "PO-2026-0010", "2026-11-01", "สมศักดิ์ พ.", {1: 1}),
]

# Invoices already in the AP system (history). The 4 new PDFs in data/invoices are NOT here:
# they are the incoming invoices the workshop app must verify.
# invoice_id, invoice_number, vendor_id, po_number, invoice_date, due_date, subtotal,
# currency, status, approved_by, notes
INVOICE_HISTORY = [
    (1, "INV-RPM-2026-08", "V006", "PO-2026-0010", "2026-08-01", "2026-08-16", 80000.00, "THB", "PAID", "กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)", "ค่าเช่าประจำเดือนสิงหาคม"),
    (2, "INV-RPM-2026-09", "V006", "PO-2026-0010", "2026-09-01", "2026-09-16", 80000.00, "THB", "PAID", "กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)", "ค่าเช่าประจำเดือนกันยายน"),
    (3, "INV-SOS-2026-0388", "V001", "PO-2026-0087", "2026-09-06", "2026-10-06", 39000.00, "THB", "PAID", "มาลี ช. (เจ้าหน้าที่บัญชีเจ้าหนี้)", None),
    (4, "INV-BEL-7702", "V002", "PO-2026-0092", "2026-09-20", "2026-10-20", 40800.00, "THB", "PAID", "มาลี ช. (เจ้าหน้าที่บัญชีเจ้าหนี้)", None),
    (5, "INV-RPM-2026-10", "V006", "PO-2026-0010", "2026-10-01", "2026-10-16", 80000.00, "THB", "PAID", "กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)", "ค่าเช่าประจำเดือนตุลาคม"),
    (6, "INV-TTS-2026-102", "V003", "PO-2026-0095", "2026-09-30", "2026-11-14", 120000.00, "THB", "APPROVED", "กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)", "อนุมัติแล้ว แต่ยังไม่เข้ารอบจ่ายเงิน"),
    (7, "INV-AMA-0931", "V005", "PO-2026-0098", "2026-10-31", "2026-11-30", 250000.00, "THB", "ON_HOLD", None, "ระงับผู้ขาย: เอกสาร ภ.พ.20 ในชุดข้อมูลสมมติหมดอายุ รอเอกสารฉบับใหม่"),
    (8, "INV-RPM-2026-11", "V006", "PO-2026-0010", "2026-11-01", "2026-11-16", 80000.00, "THB", "PENDING", None, "ค่าเช่าประจำเดือนพฤศจิกายน รอผู้จัดการบัญชีเจ้าหนี้อนุมัติ"),
    (9, "INV-SOS-2026-0388", "V001", "PO-2026-0087", "2026-09-06", "2026-10-06", 39000.00, "THB", "REJECTED", "มาลี ช. (เจ้าหน้าที่บัญชีเจ้าหนี้)", "ได้รับใบแจ้งหนี้ซ้ำเมื่อ 2026-11-10 ฉบับเดิมจ่ายแล้วเมื่อ 2026-10-06"),
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
        "scenario": "เอกสารทั้งสามตรงกัน -> APPROVED (ส่งผู้จัดการบัญชีเจ้าหนี้ ยอดเกิน 50,000 บาท)",
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
        "scenario": "ราคาต่อหน่วย 1,250 เทียบกับ PO 1,150 (+8.7%) -> ON HOLD (ต่างเกิน 2%)",
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
        "scenario": "เรียกเก็บ 120 พาเลต / 6 เที่ยว แต่รับจริง 100 / 5 -> ON HOLD (จำนวนเกิน GRN)",
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
        "scenario": "ยอดเงินตรงกัน แต่บัญชีธนาคารต่างจากทะเบียนผู้ขาย -> ON HOLD (ต้องยืนยันการเปลี่ยนบัญชี)",
        "invoice_number": "INV-CMP-2026-0057",
        "vendor_id": "V004",
        "po_number": "PO-2026-0104",
        "invoice_date": "2026-11-06",
        "due_date": "2026-12-06",
        "lines": [(1, 200, 115.00), (2, 40, 95.00)],
        "bank": ("ธนาคารไทยพาณิชย์", "999-1-23456-7"),
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
def thai_styles():
    for name, filename in (("Sarabun", "Sarabun-Regular.ttf"), ("Sarabun-Bold", "Sarabun-Bold.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(FONTS / filename)))
    pdfmetrics.registerFontFamily("Sarabun", normal="Sarabun", bold="Sarabun-Bold",
                                  italic="Sarabun", boldItalic="Sarabun-Bold")
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        if not isinstance(style, ParagraphStyle):
            continue
        style.fontName = "Sarabun-Bold" if style.fontName.endswith("Bold") else "Sarabun"
        style.shaping = 1
        style.wordWrap = "CJK"
        style.leading = max(style.leading, style.fontSize * 1.6)
    return styles


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
    styles = thai_styles()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=9, leading=15)
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=20, alignment=2)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm)

    header = Table(
        [[
            Paragraph(f"<b>{inv['vendor_name']}</b><br/>{inv['vendor_address']}<br/>"
                      f"เลขประจำตัวผู้เสียภาษี: {inv['vendor_tax_id']} (สำนักงานใหญ่)<br/>โทร: {inv['vendor_phone']}", small),
            Paragraph("ใบกำกับภาษี", title),
        ]],
        colWidths=[105 * mm, 69 * mm],
    )
    meta = Table(
        [[
            Paragraph(f"<b>ผู้ซื้อ</b><br/>{BUYER['name']}<br/>{BUYER['address']}<br/>เลขประจำตัวผู้เสียภาษี: {BUYER['tax_id']}", small),
            Paragraph(f"<b>เลขที่ใบแจ้งหนี้:</b> {inv['invoice_number']}<br/><b>วันที่ (ค.ศ.):</b> {inv['invoice_date']}<br/>"
                      f"<b>ครบกำหนด:</b> {inv['due_date']}<br/><b>เลขที่ใบสั่งซื้อ:</b> {inv['po_number']}", small),
        ]],
        colWidths=[105 * mm, 69 * mm],
    )
    rows = [["ที่", "รหัสสินค้า", "รายละเอียด", "จำนวน", "ราคาต่อหน่วย", "จำนวนเงิน (บาท)"]]
    for i, l in enumerate(inv["lines"], start=1):
        rows.append([str(i), l["code"], Paragraph(l["desc"], small), f"{l['qty']:g}", money(l["price"]), money(l["amount"])])
    rows += [
        ["", "", "", "", "ยอดก่อนภาษี", money(inv["subtotal"])],
        ["", "", "", "", "ภาษีมูลค่าเพิ่ม 7%", money(inv["vat"])],
        ["", "", "", "", "ยอดรวม", money(inv["total"])],
    ]
    header_style = ParagraphStyle("table_header", parent=small, textColor=colors.white)
    number_style = ParagraphStyle("table_number", parent=small, alignment=2)
    rows = [
        [Paragraph(cell, header_style if row_no == 0 else number_style if column >= 3 else small)
         if isinstance(cell, str) else cell for column, cell in enumerate(row)]
        for row_no, row in enumerate(rows)
    ]
    items = Table(rows, colWidths=[11 * mm, 33 * mm, 62 * mm, 14 * mm, 24 * mm, 30 * mm])
    n = len(inv["lines"])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, n), 0.4, colors.grey),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Sarabun"),
        ("LINEABOVE", (4, n + 1), (-1, n + 1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    pay = Paragraph(
        f"<b>รายละเอียดการชำระเงิน</b><br/>โอนเงินไปยัง: {inv['bank_name']}, เลขที่บัญชี {inv['bank_account']}, "
        f"ชื่อบัญชี: {inv['vendor_name']}<br/>กำหนดชำระภายในวันที่ {inv['due_date']} (ค.ศ.) "
        "กรุณาส่งหนังสือรับรองการหักภาษี ณ ที่จ่าย (50 ทวิ) ไปที่ accounting@vendor.example",
        small,
    )
    doc.build([header, Spacer(1, 8 * mm), meta, Spacer(1, 8 * mm), items, Spacer(1, 10 * mm), pay,
               Spacer(1, 18 * mm), Paragraph("ลงชื่อผู้มีอำนาจ ____________________", small),
               Spacer(1, 6 * mm), Paragraph("เอกสารและข้อมูลสมมติสำหรับการฝึกอบรมเท่านั้น ไม่ใช่เอกสารภาษีจริง", small)])


def render_invoice_png(inv: dict, path: Path) -> None:
    """A slightly skewed, noisy 'phone scan' so vision OCR has something realistic to read."""
    # Rasterize the PDF so Thai glyph shaping and line wrapping stay identical.
    with pdfium.PdfDocument(str(path.with_name(inv["file"]))) as pdf:
        page = pdf[0]
        bitmap = page.render(scale=2.1)
        img = bitmap.to_pil().convert("RGB")
        bitmap.close()
        page.close()
    w, h = img.size

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
    ("1. วัตถุประสงค์และขอบเขต",
     ["นโยบายนี้กำหนดวิธีตรวจสอบใบแจ้งหนี้ของผู้ขายก่อนชำระเงิน สำหรับทีมบัญชีเจ้าหนี้ (AP) "
      "ของบริษัท คอนโทโซ (ประเทศไทย) จำกัด ใช้กับใบแจ้งหนี้ที่อ้างอิงใบสั่งซื้อ (PO) ทั้งเงินบาท (THB) "
      "และสกุลเงินต่างประเทศ ใบแจ้งหนี้ที่ไม่มี PO เช่น ค่าสาธารณูปโภค อยู่นอกขอบเขตผู้ช่วยตรวจสอบอัตโนมัติ",
      "เจ้าของนโยบาย: ผู้ควบคุมการเงิน (Finance Controller) มีผลตั้งแต่ 1 กรกฎาคม 2569 ฉบับที่ 3.2"]),
    ("2. ข้อมูลที่จำเป็นในใบแจ้งหนี้",
     ["ใบแจ้งหนี้ต้องเป็นใบกำกับภาษีแบบเต็มรูปตามประมวลรัษฎากร มาตรา 86/4 และระบุ "
      "(ก) คำว่า 'ใบกำกับภาษี' (ข) ชื่อ ที่อยู่ และเลขประจำตัวผู้เสียภาษี 13 หลักของผู้ขาย "
      "(ค) ชื่อ ที่อยู่ และเลขประจำตัวผู้เสียภาษีของผู้ซื้อ (คอนโทโซ: 0105560000001) "
      "(ง) เลขที่และวันที่ใบแจ้งหนี้ (จ) รายละเอียด จำนวน และมูลค่าสินค้าหรือบริการ "
      "(ฉ) ภาษีมูลค่าเพิ่มแยกจากราคาสินค้าหรือบริการ",
      "หากขาดข้อมูลจำเป็น ให้ปฏิเสธ (REJECTED) และคืนเอกสารพร้อมเหตุผล "
      "ใบแจ้งหนี้ที่มี PO ต้องระบุเลขที่ PO หากไม่ระบุ เจ้าหน้าที่ AP อาจค้นหาได้ "
      "แต่ต้องบันทึกการค้นหาไว้ในหมายเหตุ"]),
    ("3. การตรวจสอบเอกสารสามทาง (Three-Way Match)",
     ["เปรียบเทียบใบสั่งซื้อ (PO) ใบรับสินค้า (GRN หรือใบตรวจรับบริการ) และใบแจ้งหนี้ "
      "ทีละรายการ โดยใช้เลขลำดับรายการใน PO หรือรหัสสินค้า",
      "3.1 จำนวน: จำนวนที่เรียกเก็บแต่ละรายการต้องไม่เกินจำนวนรับสะสมตาม GRN ของรายการ PO นั้น "
      "ไม่อนุญาตให้จำนวนเกินแม้แต่น้อย แต่อนุญาตให้เรียกเก็บบางส่วนต่ำกว่าจำนวนที่รับแล้ว",
      "3.2 ราคาต่อหน่วย: ราคาก่อน VAT ในใบแจ้งหนี้ต่างจากราคาใน PO ได้ไม่เกิน 2% ต่อรายการ "
      "หากเกิน 2% ถือเป็นข้อยกเว้นด้านราคา",
      "3.3 ยอดรวมก่อนภาษี: ต่างจากยอดที่คาดหมาย (จำนวนที่ตรวจสอบ x ราคาต่อหน่วยใน PO) "
      "ได้ไม่เกิน 1% หรือ 1,000 บาท โดยใช้ค่าที่ต่ำกว่า",
      "3.4 ภาษีมูลค่าเพิ่ม: VAT ต้องเท่ากับ 7% ของยอดก่อนภาษี ยอมรับการปัดเศษต่างได้ไม่เกิน 1.00 บาท",
      "3.5 ผู้ขาย: เลขประจำตัวผู้เสียภาษีในใบแจ้งหนี้ต้องตรงกับผู้ขายใน PO และทะเบียนผู้ขาย"]),
    ("4. ผลการตรวจสอบ",
     ["APPROVED (ผ่านการตรวจสอบ): ผ่านทุกข้อ ส่งให้ผู้มีอำนาจอนุมัติตามข้อ 7",
      "ON HOLD (พักรายการ): มีข้อยกเว้นที่แก้ไขได้ เช่น ราคาต่าง จำนวนเกินรับ เปลี่ยนบัญชีธนาคาร "
      "ผู้ขายถูกระงับ หรือไม่มี GRN เจ้าหน้าที่ AP ต้องประสานผู้ขอซื้อหรือผู้ขายให้แก้ไขภายใน 3 วันทำการ "
      "และทบทวนรายการที่พักไว้ทุก 7 วันจนกว่าจะเสร็จ",
      "REJECTED (ปฏิเสธ): ไม่สามารถจ่ายตามเอกสารปัจจุบัน เช่น ใบแจ้งหนี้ซ้ำ ใบกำกับภาษีไม่ถูกต้อง "
      "หรือออกให้คนละนิติบุคคล ผู้ขายต้องออกใบลดหนี้หรือใบแจ้งหนี้ฉบับแก้ไข",
      "ผู้ช่วยตรวจสอบให้เพียงคำแนะนำ เจ้าหน้าที่ AP ที่เป็นมนุษย์ตัดสินใจขั้นสุดท้ายและบันทึกในระบบเสมอ"]),
    ("5. การตรวจจับใบแจ้งหนี้ซ้ำ",
     ["ก่อนอนุมัติ ต้องตรวจรายการซ้ำ โดยสงสัยว่าเป็นรายการซ้ำเมื่อ "
      "(ก) ผู้ขายและเลขที่ใบแจ้งหนี้ตรงกับรายการเดิมที่มีสถานะอื่นนอกจาก REJECTED หรือ "
      "(ข) ผู้ขายและยอดรวมตรงกัน และวันที่ใบแจ้งหนี้ห่างจากรายการเดิมไม่เกิน 30 วัน",
      "หากยืนยันว่าซ้ำ ให้ REJECTED ห้ามจ่ายซ้ำ หากพบการจ่ายซ้ำ "
      "แจ้งผู้จัดการบัญชีเจ้าหนี้ภายในวันเดียวกันและขอคืนเงินจากผู้ขาย"]),
    ("6. ทะเบียนผู้ขายและการเปลี่ยนบัญชีธนาคาร",
     ["จ่ายเงินเฉพาะบัญชีที่อนุมัติในทะเบียนผู้ขาย หากบัญชีในใบแจ้งหนี้ต่างจากทะเบียน "
      "ต้อง ON HOLD และห้ามจ่าย เพราะอาจเป็นการฉ้อโกงผ่านอีเมลธุรกิจ",
      "วิธียืนยันการเปลี่ยนบัญชี: (1) โทรกลับด้วยเบอร์ที่มีอยู่ในทะเบียนผู้ขาย "
      "ห้ามใช้เบอร์จากใบแจ้งหนี้หรืออีเมล (2) ขอหนังสือเปลี่ยนบัญชีบนหัวจดหมายบริษัทพร้อมลายเซ็น "
      "และสำเนาสมุดบัญชีหรือหนังสือยืนยันธนาคาร (3) ทีมทะเบียนผู้ขายแก้ไขข้อมูลโดยผู้อนุมัติสองคน "
      "(4) รอ 5 วันทำการก่อนจ่ายเข้าบัญชีใหม่ครั้งแรก",
      "ใบแจ้งหนี้ของผู้ขายสถานะ BLOCKED ต้อง ON HOLD จนกว่าทีมทะเบียนผู้ขายจะปลดระงับ"]),
    ("7. ตารางอำนาจอนุมัติ",
     ["พิจารณาจากยอดใบแจ้งหนี้รวม VAT:",
      "ไม่เกิน 50,000 บาท: เจ้าหน้าที่บัญชีเจ้าหนี้ (AP Officer)",
      "50,000.01 ถึง 200,000 บาท: ผู้จัดการบัญชีเจ้าหนี้ (AP Manager)",
      "200,000.01 ถึง 1,000,000 บาท: ผู้ควบคุมการเงิน (Finance Controller)",
      "เกิน 1,000,000 บาท: ผู้อำนวยการฝ่ายการเงิน (CFO)",
      "ผู้ตรวจสอบและผู้อนุมัติต้องเป็นคนละคน เพื่อแบ่งแยกหน้าที่"]),
    ("8. ภาษีหัก ณ ที่จ่าย (WHT) และภาษีมูลค่าเพิ่ม (VAT)",
     ["คอนโทโซหักภาษี ณ ที่จ่ายตอนชำระเงิน โดยคำนวณจากยอดก่อน VAT "
      "ตามประเภทผู้ขายในทะเบียน: บริการ 3%, ขนส่ง 1%, โฆษณา 2%, ค่าเช่า 5%, สินค้า 0%",
      "ยอดจ่ายสุทธิ = ยอดใบแจ้งหนี้รวม VAT ลบ WHT ต้องออกหนังสือรับรองการหักภาษี ณ ที่จ่าย "
      "(50 ทวิ) ให้ผู้ขายทุกครั้งที่มีการหัก และยื่น ภ.ง.ด.53 ต่อกรมสรรพากร "
      "ภายในวันที่ 7 ของเดือนถัดไป (วันที่ 15 หากยื่นออนไลน์ ตามสมมติฐานของแบบฝึกหัด)",
      "VAT ตามนโยบายสมมติเท่ากับ 7% หากกรมสรรพากรประกาศเปลี่ยนอัตรา VAT หรือ WHT "
      "ทีมภาษีต้องปรับนโยบาย เจ้าหน้าที่ AP ควรตรวจอัตราปัจจุบันจากเว็บไซต์กรมสรรพากรเมื่อไม่แน่ใจ"]),
    ("9. เงื่อนไขการชำระเงิน",
     ["กำหนดชำระปกติคือ 30 วันนับจากวันที่ใบแจ้งหนี้ เว้นแต่ทะเบียนผู้ขายกำหนดต่างออกไป "
      "จ่ายเงินทุกวันอังคารและวันศุกร์ รายการอนุมัติแล้วที่ครบกำหนดก่อนรอบจ่ายถัดไปให้เข้ารอบปัจจุบัน "
      "รายการอนุมัติแล้วแต่เลยกำหนดต้องแจ้งผู้จัดการบัญชีเจ้าหนี้",
      "ควรใช้ส่วนลดจ่ายก่อนกำหนด เช่น 2/10 net 30 เมื่ออนุมัติทันช่วงส่วนลด"]),
    ("10. ใบแจ้งหนี้สกุลเงินต่างประเทศ",
     ["แปลงเป็นเงินบาทเพื่อเลือกผู้มีอำนาจอนุมัติ โดยใช้อัตราอ้างอิงธนาคารแห่งประเทศไทย "
      "(อัตราขายเฉลี่ย) ณ วันที่ใบแจ้งหนี้ และบันทึกอัตรากับแหล่งอ้างอิงในหมายเหตุ"]),
    ("11. การเก็บรักษาเอกสาร",
     ["เก็บใบแจ้งหนี้ GRN PO และหลักฐานจ่ายเงินอย่างน้อย 5 ปีนับจากสิ้นรอบบัญชี "
      "ตามสมมติฐานด้านภาษีและบัญชีของแบบฝึกหัด"]),
    ("ภาคผนวก ก. สรุปสำหรับเจ้าหน้าที่บัญชีเจ้าหนี้",
     ["ราคาต่างได้ 2% ต่อรายการ ยอดก่อนภาษีต่างได้ 1% หรือ 1,000 บาท ใช้ค่าที่ต่ำกว่า จำนวนเกินรับไม่ได้",
      "บัญชีธนาคารต่างจากทะเบียน: ON HOLD โทรกลับด้วยเบอร์ในทะเบียน และรอ 5 วันทำการก่อนจ่ายบัญชีใหม่",
      "ใบแจ้งหนี้ซ้ำ (ผู้ขายเดียวกัน + เลขที่เดียวกัน): REJECTED",
      "สอบถามนโยบาย: ap-policy@contoso.example สอบถามทะเบียนผู้ขาย: vendor-master@contoso.example"]),
]


def render_policy_pdf(path: Path) -> None:
    styles = thai_styles()
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, leading=18, spaceAfter=8)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                            title="นโยบายตรวจสอบใบแจ้งหนี้บัญชีเจ้าหนี้ คอนโทโซ")
    flow = [
        Paragraph(BUYER["name"], styles["Heading2"]),
        Paragraph("นโยบายตรวจสอบใบแจ้งหนี้บัญชีเจ้าหนี้", styles["Title"]),
        Paragraph("ฉบับที่ 3.2 มีผลตั้งแต่ 1 กรกฎาคม 2569 เจ้าของ: ผู้ควบคุมการเงิน ใช้ภายในเท่านั้น", body),
        Paragraph("เอกสารสมมติสำหรับการฝึกอบรม ไม่ใช่คำแนะนำด้านภาษีหรือกฎหมาย "
                  "อัตราและกำหนดยื่นเป็นสมมติฐานของแบบฝึกหัด ต้องตรวจสอบกับหน่วยงานทางการก่อนใช้งานจริง "
                  "วันที่ในฐานข้อมูลและใบแจ้งหนี้ใช้ปี ค.ศ. 2026 ซึ่งตรงกับ พ.ศ. 2569", body),
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
    (INVOICES / "ground_truth.json").write_text(json.dumps(truth, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Done. Files written to", DATA)


if __name__ == "__main__":
    main()
