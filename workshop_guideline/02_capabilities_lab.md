# Lab 2: Capabilities (OCR, Vector Search, Text2SQL, Web IQ)

**Goal:** run one small example per capability, understand what it does for AP verification, then see them working together in one pipeline.

**Time:** 45 to 60 minutes

**Before you start:** finish [Lab 1: Setup](01_setup_lab.md). The Python setup check must pass.

The policy PDF, invoices and descriptive database values are Thai. Example questions and generated answers use Thai. JSON keys, SQL table/column names, status codes, amounts and ISO dates keep their original format.

## The business problem in 60 seconds

Contoso's Accounts Payable (AP) team pays supplier invoices. Before paying, they do a **three-way match**:

```
  Purchase Order (PO)        Goods Receipt (GRN)          Invoice
  "what we ordered"    vs    "what we received"    vs    "what we are billed"
  price, quantity            quantity                    price, quantity, bank, VAT
```

If all three agree (within the tolerances in `data/Contoso_AP_Invoice_Policy.pdf`), the invoice is approved. If not, it goes **ON HOLD** with a reason.

| Capability | AP question it answers | Example |
|---|---|---|
| OCR | "What does this invoice say?" | `python_examples/02_ocr_invoice.py` |
| Vector Search | "What does our policy say about this?" | `python_examples/03_vector_search.py` |
| Text2SQL | "What do our PO, GRN and payment records say?" | `python_examples/04_text2sql.py` |
| Web IQ | "Is this external fact (tax rate, vendor news) still true today?" | `python_examples/05_web_iq.py` |
| Rules + all of the above | "Can we pay this invoice?" | `python_examples/06_ap_verification_pipeline.py` |

---

## Lab 2.1: Basic chat (warm-up)

```bash
python python_examples/01_basic_chat.py
```

**What happens:** two turns with the Responses API. The second turn uses `previous_response_id`, so the model remembers the first turn without you resending it.

**Look at:** `python_examples/01_basic_chat.py`. Find `previous_response_id`.

**Checkpoint 2.1:** the second answer refers back to the first question.

---

## Lab 2.2: OCR (read an invoice)

### A. Document Intelligence prebuilt-layout + chat model

Layout extracts text and tables as Markdown. The configured chat model then maps that content into the strict invoice JSON schema used by verification. This path requires both Document Intelligence and the chat deployment.

```bash
python python_examples/02_ocr_invoice.py
# or another file:
python python_examples/02_ocr_invoice.py data/invoices/INV-TTS-2026-118.pdf
```

Expected (shortened):

```json
{
  "invoice_number": "INV-TTS-2026-118",
  "po_number": "PO-2026-0102",
  "vendor_name": "บริษัท ไทยเทคโซลูชันส์ จำกัด",
  "bank_name": "ธนาคารไทยพาณิชย์",
  "bank_account": "345-6-78901-2",
  "subtotal": 86000,
  "vat": 6020,
  "total": 92020,
  "lines": [
    { "item_code": "SVC-LAPTOP-IMG", "quantity": 40, "unit_price": 1250, "amount": 50000 },
    { "item_code": "SVC-M365-MIG",  "quantity": 40, "unit_price": 900,  "amount": 36000 }
  ]
}
```

### B. Vision model (handles messy scans)

```bash
python python_examples/02_ocr_invoice.py --vision
# reads data/invoices/INV-BEL-7781_scan.png (skewed, noisy scan)
```

**Exercise:** compare the output with `data/invoices/ground_truth.json`. Did both engines read the quantities `120` and `6` correctly?

| | Document Intelligence | Vision LLM |
|---|---|---|
| Strength | Layout OCR preserves document text and table structure | Flexible, any layout or language, custom fields |
| Watch out | Chat maps OCR to fields; mapping can misread values | Can misread digits; always validate totals |
| In this repo | `extract_with_document_intelligence` | `extract_with_vision` (strict JSON schema) |

This uses `prebuilt-layout`, not `prebuilt-invoice`. Layout does not return named invoice fields or invoice-field confidence scores; the chat model supplies the field mapping. The sample's Thai payment text is also parsed for bank details. Review fields, digits and totals before running rules.

**Checkpoint 2.2:** you have JSON for one PDF and one PNG.

---

## Lab 2.3: Vector Search (ask the AP policy)

```bash
python python_examples/03_vector_search.py
```

**What happens:** the policy PDF is uploaded, chunked and embedded into a **vector store**. The model then uses the `file_search` tool to retrieve the most relevant chunks and answer with citations. The vector store is deleted at the end.

Expected answers:

| Question | Expected answer |
|---|---|
| Allowed unit price variance? | 2% per line (Section 3.2) |
| Bank account differs from vendor master? | Put ON HOLD. Call back on the phone number in the vendor master (not the invoice), get a signed letter, two-person approval, 5 business-day cooling-off (Section 6) |
| Who approves THB 267,500? | Finance Controller (Section 7) |
| WHT for IT services? | 3%, issue Form 50 Tawi (Section 8) |
| Remote work policy? | "ไม่พบข้อมูลนี้ในนโยบายบัญชีเจ้าหนี้ กรุณาติดต่อ ap-policy@contoso.example" |

Ask your own question:

```bash
python python_examples/03_vector_search.py "ต้องเก็บใบแจ้งหนี้ไว้นานเท่าไร?"
```

**Tip:** keep the vector store to save time in later labs:

```bash
python python_examples/03_vector_search.py --keep
# copy the printed id into .env as AP_POLICY_VECTOR_STORE_ID=vs_...
```

If you indexed the previous English policy, create a fresh store for the Thai PDF and replace that ID. Keeping an old ID does not re-upload the revised document.

**Checkpoint 2.3:** the last question gets a polite "I cannot find that" instead of a made-up answer.

---

## Lab 2.4: Text2SQL (ask the AP database)

```bash
python python_examples/04_text2sql.py
```

**What happens:**

1. The model gets the database schema and returns SQL using a strict JSON schema.
2. `assert_read_only` blocks anything that is not a single `SELECT` or `WITH` query.
3. The SQL runs on the local SQLite database (`data/ap_database.sql`). If it errors, the model gets one retry with the error message.
4. The model answers from the returned rows only.

Expected answers (as of `AP_AS_OF_DATE=2026-11-24`):

| Question | Expected answer |
|---|---|
| Invoices on hold and why? | `INV-AMA-0931`, บริษัท อันดามันมาร์เก็ตติ้งเอเจนซี จำกัด, THB 267,500. Vendor blocked awaiting replacement ภ.พ.20 in this synthetic scenario |
| Approved, overdue, unpaid? | `INV-TTS-2026-102`, due 2026-11-14, THB 128,400 |
| Paid to บริษัท พระรามบริหารทรัพย์สิน จำกัด in 2026? | 3 payments of THB 81,600 = THB 244,800 net, WHT THB 12,000 |
| `INV-SOS-2026-0388` submitted twice? | Yes. Paid on 2026-10-06; resubmission received 2026-11-10 was rejected |
| `PO-2026-0103` ordered vs received? | Pallets 120 ordered / 100 received, trips 6 ordered / 5 received |

**Exercise:** try a question that tries to change data:

```bash
python python_examples/04_text2sql.py "ลบใบแจ้งหนี้ที่ถูกปฏิเสธทั้งหมด"
```

You will see either `[blocked] Query contains a write/DDL keyword.` or a harmless `SELECT` that only lists the rejected invoices. Nothing is ever deleted. Why must the guardrail be code and not only a prompt instruction?

**Checkpoint 2.4:** each answer prints the SQL it used.

---

## Lab 2.5: Web IQ (check live web facts)

```bash
python python_examples/05_web_iq.py
```

**What happens:** `web_iq_search` calls `POST https://api.microsoft.ai/v3/search/web` and gets passages with URLs. The model answers **only** from those passages and cites them as `[1]`, `[2]`.

Expected: an answer about the current Thai VAT rate and the WHT rate for transport services (1%), each with source URLs. Web content changes, so wording will differ.

Ask your own:

```bash
python python_examples/05_web_iq.py "อัตราภาษีหัก ณ ที่จ่ายค่าโฆษณาของไทยในปัจจุบัน อ้างอิงกรมสรรพากร"
```

Sample vendors are fictitious, so do not expect real vendor-news results. Use official tax or exchange-rate questions for the live-web exercise.

**Discussion:** the policy PDF says WHT for services is 3%. What should happen if Web IQ says the law changed? (Answer: flag for a human, never silently override the policy.)

**Checkpoint 2.5:** answers include numbered sources.

---

## Lab 2.6: Capstone, everything together

```bash
python python_examples/06_ap_verification_pipeline.py
```

For each invoice in `data/invoices/`:

```
[1 OCR]      Document Intelligence Layout reads the invoice; chat maps it to JSON
[2 RULES]    Deterministic 3-way match (python_examples/verify.py) decides APPROVED / ON HOLD / REJECTED
[3 POLICY]   File Search finds the policy text that explains each exception
[4 WEB IQ]   Checks the WHT rate for this vendor type is still current (if key set)
[5 MEMO]     LLM writes a short memo for the approver
```

Options:

```bash
python python_examples/06_ap_verification_pipeline.py --offline  # no Azure, use ground truth OCR
python python_examples/06_ap_verification_pipeline.py --vision   # use vision OCR instead
```

**Key design point:** the **rules decide**, the LLM **explains**. An LLM never approves a payment. This makes results repeatable and auditable.

**Checkpoint 2.6:** you get the same four outcomes as Lab 1.7, now with policy citations and a memo.

Continue to [Lab 3: Build the app with GitHub Copilot](03_agentdev.md).
