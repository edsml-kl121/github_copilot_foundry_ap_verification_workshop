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
INSERT INTO vendors VALUES ('V001', 'Siam Office Supplies Co., Ltd.', '0105551234567', 'GOODS', 0, 'Kasikornbank', '123-4-56789-0', 30, 'ACTIVE', '+66 2 111 2001', '45 Rama IV Road, Pathum Wan, Bangkok 10330');
INSERT INTO vendors VALUES ('V002', 'Bangkok Express Logistics Co., Ltd.', '0105559876543', 'TRANSPORT', 1, 'Bangkok Bank', '234-5-67890-1', 30, 'ACTIVE', '+66 2 222 3002', '199 Bang Na-Trat Road, Bang Na, Bangkok 10260');
INSERT INTO vendors VALUES ('V003', 'Thai Tech Solutions Co., Ltd.', '0105562223334', 'SERVICES', 3, 'Siam Commercial Bank', '345-6-78901-2', 45, 'ACTIVE', '+66 2 333 4003', '12 Silom Road, Bang Rak, Bangkok 10500');
INSERT INTO vendors VALUES ('V004', 'Chiang Mai Paper Products Co., Ltd.', '0505553334445', 'GOODS', 0, 'Krungthai Bank', '456-7-89012-3', 30, 'ACTIVE', '+66 53 444 5004', '77 Huay Kaew Road, Mueang, Chiang Mai 50200');
INSERT INTO vendors VALUES ('V005', 'Andaman Marketing Agency Co., Ltd.', '0835554445556', 'ADVERTISING', 2, 'Kasikornbank', '567-8-90123-4', 30, 'BLOCKED', '+66 76 555 6005', '9 Patong Beach Road, Kathu, Phuket 83150');
INSERT INTO vendors VALUES ('V006', 'Rama Property Management Co., Ltd.', '0105547778889', 'RENTAL', 5, 'Bangkok Bank', '678-9-01234-5', 15, 'ACTIVE', '+66 2 666 7006', '1 Rama IX Road, Huai Khwang, Bangkok 10310');

-- purchase orders
INSERT INTO purchase_orders VALUES ('PO-2026-0010', 'V006', '2026-01-05', 'Facilities', 'Somsak P.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0010', 1, 'RENT-HQ', 'Office rent HQ floor 12 (per month)', 12, 80000.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0087', 'V001', '2026-09-01', 'Administration', 'Nok S.', 'THB', 'CLOSED');
INSERT INTO po_lines VALUES ('PO-2026-0087', 1, 'PAP-A4-80', 'A4 copy paper 80gsm (box of 5 reams)', 60, 650.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0092', 'V002', '2026-09-10', 'Warehouse', 'Anan K.', 'THB', 'CLOSED');
INSERT INTO po_lines VALUES ('PO-2026-0092', 1, 'LOG-BKK-RYG', 'Pallet delivery Bangkok - Rayong (per pallet)', 80, 450.0);
INSERT INTO po_lines VALUES ('PO-2026-0092', 2, 'LOG-FUEL', 'Fuel surcharge (per trip)', 4, 1200.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0095', 'V003', '2026-09-15', 'IT', 'Ploy T.', 'THB', 'CLOSED');
INSERT INTO po_lines VALUES ('PO-2026-0095', 1, 'SVC-SEC-ASSESS', 'Network security assessment', 1, 120000.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0098', 'V005', '2026-09-20', 'Marketing', 'Mint R.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0098', 1, 'MKT-SOCIAL-Q4', 'Social media campaign Q4 2026', 1, 250000.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0101', 'V001', '2026-10-20', 'Administration', 'Nok S.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0101', 1, 'PAP-A4-80', 'A4 copy paper 80gsm (box of 5 reams)', 50, 650.0);
INSERT INTO po_lines VALUES ('PO-2026-0101', 2, 'TON-HP26A', 'Toner cartridge HP 26A', 10, 2800.0);
INSERT INTO po_lines VALUES ('PO-2026-0101', 3, 'MRK-WB-12', 'Whiteboard markers (box of 12)', 20, 180.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0102', 'V003', '2026-10-05', 'IT', 'Ploy T.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0102', 1, 'SVC-LAPTOP-IMG', 'Laptop setup and imaging service (per device)', 40, 1150.0);
INSERT INTO po_lines VALUES ('PO-2026-0102', 2, 'SVC-M365-MIG', 'Microsoft 365 mailbox migration (per mailbox)', 40, 900.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0103', 'V002', '2026-10-12', 'Warehouse', 'Anan K.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0103', 1, 'LOG-BKK-RYG', 'Pallet delivery Bangkok - Rayong (per pallet)', 120, 450.0);
INSERT INTO po_lines VALUES ('PO-2026-0103', 2, 'LOG-FUEL', 'Fuel surcharge (per trip)', 6, 1200.0);
INSERT INTO purchase_orders VALUES ('PO-2026-0104', 'V004', '2026-10-15', 'Administration', 'Nok S.', 'THB', 'OPEN');
INSERT INTO po_lines VALUES ('PO-2026-0104', 1, 'PAP-RCY-A4', 'Recycled A4 copy paper (per ream)', 200, 115.0);
INSERT INTO po_lines VALUES ('PO-2026-0104', 2, 'CUP-8OZ-50', 'Paper cups 8oz (pack of 50)', 40, 95.0);

-- goods receipts
INSERT INTO goods_receipts VALUES ('GRN-2026-0150', 'PO-2026-0010', '2026-08-01', 'Somsak P.');
INSERT INTO grn_lines VALUES ('GRN-2026-0150', 'PO-2026-0010', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0168', 'PO-2026-0010', '2026-09-01', 'Somsak P.');
INSERT INTO grn_lines VALUES ('GRN-2026-0168', 'PO-2026-0010', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0170', 'PO-2026-0087', '2026-09-05', 'Nok S.');
INSERT INTO grn_lines VALUES ('GRN-2026-0170', 'PO-2026-0087', 1, 60);
INSERT INTO goods_receipts VALUES ('GRN-2026-0176', 'PO-2026-0092', '2026-09-18', 'Anan K.');
INSERT INTO grn_lines VALUES ('GRN-2026-0176', 'PO-2026-0092', 1, 80);
INSERT INTO grn_lines VALUES ('GRN-2026-0176', 'PO-2026-0092', 2, 4);
INSERT INTO goods_receipts VALUES ('GRN-2026-0181', 'PO-2026-0095', '2026-09-29', 'Ploy T.');
INSERT INTO grn_lines VALUES ('GRN-2026-0181', 'PO-2026-0095', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0186', 'PO-2026-0010', '2026-10-01', 'Somsak P.');
INSERT INTO grn_lines VALUES ('GRN-2026-0186', 'PO-2026-0010', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0192', 'PO-2026-0098', '2026-10-30', 'Mint R.');
INSERT INTO grn_lines VALUES ('GRN-2026-0192', 'PO-2026-0098', 1, 1);
INSERT INTO goods_receipts VALUES ('GRN-2026-0201', 'PO-2026-0101', '2026-10-27', 'Nok S.');
INSERT INTO grn_lines VALUES ('GRN-2026-0201', 'PO-2026-0101', 1, 50);
INSERT INTO grn_lines VALUES ('GRN-2026-0201', 'PO-2026-0101', 2, 10);
INSERT INTO grn_lines VALUES ('GRN-2026-0201', 'PO-2026-0101', 3, 20);
INSERT INTO goods_receipts VALUES ('GRN-2026-0203', 'PO-2026-0102', '2026-10-30', 'Ploy T.');
INSERT INTO grn_lines VALUES ('GRN-2026-0203', 'PO-2026-0102', 1, 40);
INSERT INTO grn_lines VALUES ('GRN-2026-0203', 'PO-2026-0102', 2, 40);
INSERT INTO goods_receipts VALUES ('GRN-2026-0205', 'PO-2026-0103', '2026-10-31', 'Anan K.');
INSERT INTO grn_lines VALUES ('GRN-2026-0205', 'PO-2026-0103', 1, 100);
INSERT INTO grn_lines VALUES ('GRN-2026-0205', 'PO-2026-0103', 2, 5);
INSERT INTO goods_receipts VALUES ('GRN-2026-0207', 'PO-2026-0104', '2026-11-03', 'Nok S.');
INSERT INTO grn_lines VALUES ('GRN-2026-0207', 'PO-2026-0104', 1, 200);
INSERT INTO grn_lines VALUES ('GRN-2026-0207', 'PO-2026-0104', 2, 40);
INSERT INTO goods_receipts VALUES ('GRN-2026-0212', 'PO-2026-0010', '2026-11-01', 'Somsak P.');
INSERT INTO grn_lines VALUES ('GRN-2026-0212', 'PO-2026-0010', 1, 1);

-- invoice history
INSERT INTO invoices VALUES (1, 'INV-RPM-2026-08', 'V006', 'PO-2026-0010', '2026-08-01', '2026-08-16', 80000.0, 5600.0, 85600.0, 'THB', 'PAID', 'Kanya W. (AP Manager)', 'Monthly rent August');
INSERT INTO invoices VALUES (2, 'INV-RPM-2026-09', 'V006', 'PO-2026-0010', '2026-09-01', '2026-09-16', 80000.0, 5600.0, 85600.0, 'THB', 'PAID', 'Kanya W. (AP Manager)', 'Monthly rent September');
INSERT INTO invoices VALUES (3, 'INV-SOS-2026-0388', 'V001', 'PO-2026-0087', '2026-09-06', '2026-10-06', 39000.0, 2730.0, 41730.0, 'THB', 'PAID', 'Malee C. (AP Officer)', NULL);
INSERT INTO invoices VALUES (4, 'INV-BEL-7702', 'V002', 'PO-2026-0092', '2026-09-20', '2026-10-20', 40800.0, 2856.0, 43656.0, 'THB', 'PAID', 'Malee C. (AP Officer)', NULL);
INSERT INTO invoices VALUES (5, 'INV-RPM-2026-10', 'V006', 'PO-2026-0010', '2026-10-01', '2026-10-16', 80000.0, 5600.0, 85600.0, 'THB', 'PAID', 'Kanya W. (AP Manager)', 'Monthly rent October');
INSERT INTO invoices VALUES (6, 'INV-TTS-2026-102', 'V003', 'PO-2026-0095', '2026-09-30', '2026-11-14', 120000.0, 8400.0, 128400.0, 'THB', 'APPROVED', 'Kanya W. (AP Manager)', 'Approved; payment run missed');
INSERT INTO invoices VALUES (7, 'INV-AMA-0931', 'V005', 'PO-2026-0098', '2026-10-31', '2026-11-30', 250000.0, 17500.0, 267500.0, 'THB', 'ON_HOLD', NULL, 'Vendor blocked: VAT registration certificate (Por Por 20) expired; awaiting updated document');
INSERT INTO invoices VALUES (8, 'INV-RPM-2026-11', 'V006', 'PO-2026-0010', '2026-11-01', '2026-11-16', 80000.0, 5600.0, 85600.0, 'THB', 'PENDING', NULL, 'Monthly rent November; awaiting AP Manager approval');
INSERT INTO invoices VALUES (9, 'INV-SOS-2026-0388', 'V001', 'PO-2026-0087', '2026-09-06', '2026-10-06', 39000.0, 2730.0, 41730.0, 'THB', 'REJECTED', 'Malee C. (AP Officer)', 'Duplicate resubmission received 2026-11-10; original already paid on 2026-10-06');

-- payments
INSERT INTO payments VALUES (1, 1, '2026-08-15', 85600.0, 4000.0, 81600.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (2, 2, '2026-09-15', 85600.0, 4000.0, 81600.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (3, 3, '2026-10-06', 41730.0, 0.0, 41730.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (4, 4, '2026-10-20', 43656.0, 408.0, 43248.0, 'BANK_TRANSFER');
INSERT INTO payments VALUES (5, 5, '2026-10-15', 85600.0, 4000.0, 81600.0, 'BANK_TRANSFER');
