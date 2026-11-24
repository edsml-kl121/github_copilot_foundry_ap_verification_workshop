-- Contoso (Thailand) AP database. Synthetic data for the workshop.
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


-- vendors
INSERT INTO vendors VALUES ('V001', 'บริษัท สยามเครื่องใช้สำนักงาน จำกัด', '0105551234567', 'GOODS', 0, 'ธนาคารกสิกรไทย', '123-4-56789-0', 30, 'ACTIVE', '+66 2 111 2001', '45 ถนนพระราม 4 เขตปทุมวัน กรุงเทพมหานคร 10330');
INSERT INTO vendors VALUES ('V002', 'บริษัท บางกอกเอ็กซ์เพรสโลจิสติกส์ จำกัด', '0105559876543', 'TRANSPORT', 1, 'ธนาคารกรุงเทพ', '234-5-67890-1', 30, 'ACTIVE', '+66 2 222 3002', '199 ถนนบางนา-ตราด เขตบางนา กรุงเทพมหานคร 10260');
INSERT INTO vendors VALUES ('V003', 'บริษัท ไทยเทคโซลูชันส์ จำกัด', '0105562223334', 'SERVICES', 3, 'ธนาคารไทยพาณิชย์', '345-6-78901-2', 45, 'ACTIVE', '+66 2 333 4003', '12 ถนนสีลม เขตบางรัก กรุงเทพมหานคร 10500');
INSERT INTO vendors VALUES ('V004', 'บริษัท เชียงใหม่ผลิตภัณฑ์กระดาษ จำกัด', '0505553334445', 'GOODS', 0, 'ธนาคารกรุงไทย', '456-7-89012-3', 30, 'ACTIVE', '+66 53 444 5004', '77 ถนนห้วยแก้ว อำเภอเมืองเชียงใหม่ จังหวัดเชียงใหม่ 50200');
INSERT INTO vendors VALUES ('V005', 'บริษัท อันดามันมาร์เก็ตติ้งเอเจนซี จำกัด', '0835554445556', 'ADVERTISING', 2, 'ธนาคารกสิกรไทย', '567-8-90123-4', 30, 'BLOCKED', '+66 76 555 6005', '9 ถนนหาดป่าตอง อำเภอกะทู้ จังหวัดภูเก็ต 83150');
INSERT INTO vendors VALUES ('V006', 'บริษัท พระรามบริหารทรัพย์สิน จำกัด', '0105547778889', 'RENTAL', 5, 'ธนาคารกรุงเทพ', '678-9-01234-5', 15, 'ACTIVE', '+66 2 666 7006', '1 ถนนพระราม 9 เขตห้วยขวาง กรุงเทพมหานคร 10310');

-- purchase orders
INSERT INTO purchase_orders VALUES ('PO-2026-0010', 'V006', '2026-01-05', 'อาคารสถานที่', 'สมศักดิ์ พ.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0010', 1, 'RENT-HQ', 'ค่าเช่าสำนักงานใหญ่ ชั้น 12 (ต่อเดือน)', 12, 80000.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0087', 'V001', '2026-09-01', 'ธุรการ', 'นก ส.', 'THB', 'CLOSED');
INSERT INTO po_lines VALUES ('PO-2026-0087', 1, 'PAP-A4-80', 'กระดาษถ่ายเอกสาร A4 80 แกรม (กล่องละ 5 รีม)', 60, 650.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0092', 'V002', '2026-09-10', 'คลังสินค้า', 'อนันต์ ก.', 'THB', 'CLOSED');
INSERT INTO po_lines VALUES ('PO-2026-0092', 1, 'LOG-BKK-RYG', 'ค่าขนส่งพาเลต กรุงเทพฯ - ระยอง (ต่อพาเลต)', 80, 450.0);
INSERT INTO po_lines VALUES ('PO-2026-0092', 2, 'LOG-FUEL', 'ค่าธรรมเนียมน้ำมัน (ต่อเที่ยว)', 4, 1200.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0095', 'V003', '2026-09-15', 'เทคโนโลยีสารสนเทศ', 'พลอย ท.', 'THB', 'CLOSED');
INSERT INTO po_lines VALUES ('PO-2026-0095', 1, 'SVC-SEC-ASSESS', 'บริการประเมินความปลอดภัยเครือข่าย', 1, 120000.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0098', 'V005', '2026-09-20', 'การตลาด', 'มิ้นท์ ร.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0098', 1, 'MKT-SOCIAL-Q4', 'แคมเปญสื่อสังคมออนไลน์ ไตรมาส 4 ปี 2026', 1, 250000.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0101', 'V001', '2026-10-20', 'ธุรการ', 'นก ส.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0101', 1, 'PAP-A4-80', 'กระดาษถ่ายเอกสาร A4 80 แกรม (กล่องละ 5 รีม)', 50, 650.0);
INSERT INTO po_lines VALUES ('PO-2026-0101', 2, 'TON-HP26A', 'ตลับหมึกเครื่องพิมพ์ HP 26A', 10, 2800.0);
INSERT INTO po_lines VALUES ('PO-2026-0101', 3, 'MRK-WB-12', 'ปากกาไวท์บอร์ด (กล่องละ 12 ด้าม)', 20, 180.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0102', 'V003', '2026-10-05', 'เทคโนโลยีสารสนเทศ', 'พลอย ท.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0102', 1, 'SVC-LAPTOP-IMG', 'บริการติดตั้งระบบโน้ตบุ๊ก (ต่อเครื่อง)', 40, 1150.0);
INSERT INTO po_lines VALUES ('PO-2026-0102', 2, 'SVC-M365-MIG', 'บริการย้ายกล่องจดหมาย Microsoft 365 (ต่อกล่อง)', 40, 900.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0103', 'V002', '2026-10-12', 'คลังสินค้า', 'อนันต์ ก.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0103', 1, 'LOG-BKK-RYG', 'ค่าขนส่งพาเลต กรุงเทพฯ - ระยอง (ต่อพาเลต)', 120, 450.0);
INSERT INTO po_lines VALUES ('PO-2026-0103', 2, 'LOG-FUEL', 'ค่าธรรมเนียมน้ำมัน (ต่อเที่ยว)', 6, 1200.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0104', 'V004', '2026-10-15', 'ธุรการ', 'นก ส.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0104', 1, 'PAP-RCY-A4', 'กระดาษถ่ายเอกสาร A4 รีไซเคิล (ต่อรีม)', 200, 115.0);
INSERT INTO po_lines VALUES ('PO-2026-0104', 2, 'CUP-8OZ-50', 'แก้วกระดาษ 8 ออนซ์ (แพ็กละ 50 ใบ)', 40, 95.0);

-- goods receipts
INSERT INTO goods_receipts VALUES ('GRN-2026-0150', 'PO-2026-0010', '2026-08-01', 'สมศักดิ์ พ.');
INSERT INTO grn_lines VALUES ('GRN-2026-0150', 'PO-2026-0010', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0168', 'PO-2026-0010', '2026-09-01', 'สมศักดิ์ พ.');
INSERT INTO grn_lines VALUES ('GRN-2026-0168', 'PO-2026-0010', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0170', 'PO-2026-0087', '2026-09-05', 'นก ส.');
INSERT INTO grn_lines VALUES ('GRN-2026-0170', 'PO-2026-0087', 1, 60);
INSERT INTO goods_receipts VALUES ('GRN-2026-0176', 'PO-2026-0092', '2026-09-18', 'อนันต์ ก.');
INSERT INTO grn_lines VALUES ('GRN-2026-0176', 'PO-2026-0092', 1, 80);
INSERT INTO grn_lines VALUES ('GRN-2026-0176', 'PO-2026-0092', 2, 4);
INSERT INTO goods_receipts VALUES ('GRN-2026-0181', 'PO-2026-0095', '2026-09-29', 'พลอย ท.');
INSERT INTO grn_lines VALUES ('GRN-2026-0181', 'PO-2026-0095', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0186', 'PO-2026-0010', '2026-10-01', 'สมศักดิ์ พ.');
INSERT INTO grn_lines VALUES ('GRN-2026-0186', 'PO-2026-0010', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0192', 'PO-2026-0098', '2026-10-30', 'มิ้นท์ ร.');
INSERT INTO grn_lines VALUES ('GRN-2026-0192', 'PO-2026-0098', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0201', 'PO-2026-0101', '2026-10-27', 'นก ส.');
INSERT INTO grn_lines VALUES ('GRN-2026-0201', 'PO-2026-0101', 1, 50);
INSERT INTO grn_lines VALUES ('GRN-2026-0201', 'PO-2026-0101', 2, 10);
INSERT INTO grn_lines VALUES ('GRN-2026-0201', 'PO-2026-0101', 3, 20);
INSERT INTO goods_receipts VALUES ('GRN-2026-0203', 'PO-2026-0102', '2026-10-30', 'พลอย ท.');
INSERT INTO grn_lines VALUES ('GRN-2026-0203', 'PO-2026-0102', 1, 40);
INSERT INTO grn_lines VALUES ('GRN-2026-0203', 'PO-2026-0102', 2, 40);
INSERT INTO goods_receipts VALUES ('GRN-2026-0205', 'PO-2026-0103', '2026-10-31', 'อนันต์ ก.');
INSERT INTO grn_lines VALUES ('GRN-2026-0205', 'PO-2026-0103', 1, 100);
INSERT INTO grn_lines VALUES ('GRN-2026-0205', 'PO-2026-0103', 2, 5);
INSERT INTO goods_receipts VALUES ('GRN-2026-0207', 'PO-2026-0104', '2026-11-03', 'นก ส.');
INSERT INTO grn_lines VALUES ('GRN-2026-0207', 'PO-2026-0104', 1, 200);
INSERT INTO grn_lines VALUES ('GRN-2026-0207', 'PO-2026-0104', 2, 40);
INSERT INTO goods_receipts VALUES ('GRN-2026-0212', 'PO-2026-0010', '2026-11-01', 'สมศักดิ์ พ.');
INSERT INTO grn_lines VALUES ('GRN-2026-0212', 'PO-2026-0010', 1, 1);

-- invoice history
INSERT INTO invoices VALUES (1, 'INV-RPM-2026-08', 'V006', 'PO-2026-0010', '2026-08-01', '2026-08-16', 80000.0, 5600.0, 85600.0, 'THB', 'PAID', 'กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)', 'ค่าเช่าประจำเดือนสิงหาคม');
INSERT INTO invoices VALUES (2, 'INV-RPM-2026-09', 'V006', 'PO-2026-0010', '2026-09-01', '2026-09-16', 80000.0, 5600.0, 85600.0, 'THB', 'PAID', 'กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)', 'ค่าเช่าประจำเดือนกันยายน');
INSERT INTO invoices VALUES (3, 'INV-SOS-2026-0388', 'V001', 'PO-2026-0087', '2026-09-06', '2026-10-06', 39000.0, 2730.0, 41730.0, 'THB', 'PAID', 'มาลี ช. (เจ้าหน้าที่บัญชีเจ้าหนี้)', NULL);
INSERT INTO invoices VALUES (4, 'INV-BEL-7702', 'V002', 'PO-2026-0092', '2026-09-20', '2026-10-20', 40800.0, 2856.0, 43656.0, 'THB', 'PAID', 'มาลี ช. (เจ้าหน้าที่บัญชีเจ้าหนี้)', NULL);
INSERT INTO invoices VALUES (5, 'INV-RPM-2026-10', 'V006', 'PO-2026-0010', '2026-10-01', '2026-10-16', 80000.0, 5600.0, 85600.0, 'THB', 'PAID', 'กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)', 'ค่าเช่าประจำเดือนตุลาคม');
INSERT INTO invoices VALUES (6, 'INV-TTS-2026-102', 'V003', 'PO-2026-0095', '2026-09-30', '2026-11-14', 120000.0, 8400.0, 128400.0, 'THB', 'APPROVED', 'กัญญา ว. (ผู้จัดการบัญชีเจ้าหนี้)', 'อนุมัติแล้ว แต่ยังไม่เข้ารอบจ่ายเงิน');
INSERT INTO invoices VALUES (7, 'INV-AMA-0931', 'V005', 'PO-2026-0098', '2026-10-31', '2026-11-30', 250000.0, 17500.0, 267500.0, 'THB', 'ON_HOLD', NULL, 'ระงับผู้ขาย: เอกสาร ภ.พ.20 ในชุดข้อมูลสมมติหมดอายุ รอเอกสารฉบับใหม่');
INSERT INTO invoices VALUES (8, 'INV-RPM-2026-11', 'V006', 'PO-2026-0010', '2026-11-01', '2026-11-16', 80000.0, 5600.0, 85600.0, 'THB', 'PENDING', NULL, 'ค่าเช่าประจำเดือนพฤศจิกายน รอผู้จัดการบัญชีเจ้าหนี้อนุมัติ');
INSERT INTO invoices VALUES (9, 'INV-SOS-2026-0388', 'V001', 'PO-2026-0087', '2026-09-06', '2026-10-06', 39000.0, 2730.0, 41730.0, 'THB', 'REJECTED', 'มาลี ช. (เจ้าหน้าที่บัญชีเจ้าหนี้)', 'ได้รับใบแจ้งหนี้ซ้ำเมื่อ 2026-11-10 ฉบับเดิมจ่ายแล้วเมื่อ 2026-10-06');

-- payments
INSERT INTO payments VALUES (1, 1, '2026-08-15', 85600.0, 4000.0, 81600.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (2, 2, '2026-09-15', 85600.0, 4000.0, 81600.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (3, 3, '2026-10-06', 41730.0, 0.0, 41730.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (4, 4, '2026-10-20', 43656.0, 408.0, 43248.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (5, 5, '2026-10-15', 85600.0, 4000.0, 81600.0, 'BANK_TRANSFER');
