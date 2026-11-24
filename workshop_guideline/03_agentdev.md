# Lab 3: Build "Contoso AP Verify" with GitHub Copilot

**Goal:** use GitHub Copilot Plan mode and Agent mode to turn the requirements meeting into a working, Python-only Streamlit app.

**Time:** 45 to 60 minutes

**Before you start:** finish Labs 1 and 2. Run the Python examples and tests first.

## Lab 3.1: Read the requirements

Open `data/meeting_transcript.txt`. It records the Finance team's decisions:

- Upload + OCR, editable fields, three-way match checks, Ask the Policy, Ask the Data, Web check, one routed chat
- Out-of-scope actions, including paying invoices
- Four acceptance scenarios with expected outcomes

The app must be Python-only. Do not generate a JavaScript frontend, Node.js server, or `package.json`.

## Lab 3.2: Plan mode

1. Open Copilot Chat and switch to **Plan** mode.
2. Choose a strong reasoning model.
3. Paste this prompt:

```
Read data/meeting_transcript.txt first. It contains the requirements and acceptance scenarios. Build the "Contoso AP Verify" application as a local, Python-only Streamlit app.

Do not use JavaScript, Node.js, Vite, Express, or package.json. Keep API keys on the local server side in .env. Keep chat history in Streamlit session state only.

Use the existing Python interfaces and do not invent new Foundry SDK patterns:
- Invoice OCR: python_examples/workshop_api.py:extract_invoice
- Policy Vector Search: python_examples/workshop_api.py:ask_policy
- AP database Text2SQL: python_examples/workshop_api.py:ask_data. Show its SQL in an expander.
- Web IQ: python_examples/workshop_api.py:ask_web. Show source URLs.
- Routing: python_examples/workshop_api.py:route_chat
- Deterministic decisions: python_examples/verify.py:verify_invoice
- Database: sqlite3 with data/ap_database.sql
- Shared model configuration: python_examples/common.py

Create app.py and any small Python-only helpers needed. UI requirements:
- Left column: invoice upload, extracted editable header and line fields, Verify button, outcome and checks table.
- Right column: one chat with a Policy/Data/Web badge per response and a five-turn in-memory history.
- Upload accepts PDF, PNG and JPG. Save uploads to a temporary file before calling extract_invoice, then remove the temporary file.
- For the offline workshop demo, use data/invoices/ground_truth.json when the user selects the offline option.
- The rules engine is the only source of APPROVED / ON HOLD / REJECTED. The model must never change the outcome.
- A human AP Officer always makes the final decision. Never post, approve or pay an invoice.

Add a simple requirements entry if Streamlit is needed. Add clear errors when configuration is missing. Do not commit .env or API keys.
```

4. Answer Copilot's questions using the transcript. Suggested choices:

| Likely question | Suggested answer |
|---|---|
| UI framework? | Streamlit, all Python |
| App state? | `st.session_state`, keep the last 5 turns |
| Chat routing? | Use `route_chat`, then call the matching Python function |
| Where do decisions come from? | Always `verify_invoice`; the LLM only explains |
| Show SQL? | Yes, in a collapsible expander |

![Plan mode](../images/plan1.png)

5. Review the plan. Confirm it only creates Python files and a Streamlit app. Check that the rules engine decides the outcome and the model only explains it. Select **Start implementation**.

![Start implementation](../images/plan2.png)

![Implementing](../images/implement1.png)

## Lab 3.3: Run and test the app

From the repository root, with the virtual environment active:

```bash
streamlit run app.py
```

### Test A: upload invoices

Upload each file from `data/invoices/` and compare the results:

| File | Expected outcome | Key check |
|---|---|---|
| `INV-SOS-2026-0415.pdf` | APPROVED, route to AP Manager | All checks PASS |
| `INV-TTS-2026-118.pdf` | ON HOLD | Unit price +8.7% vs PO, limit 2% |
| `INV-BEL-7781_scan.png` | ON HOLD | Invoiced 120 pallets, only 100 received |
| `INV-CMP-2026-0057.pdf` | ON HOLD | Bank account differs; call back on vendor-master phone |

### Test B: chat and routing badges

```
Q1) What is the allowed unit price variance for a three-way match?
Q2) Which invoices are on hold right now, and why?
Q3.1) How much have we paid Rama Property Management in 2026?
Q3.2) And how much withholding tax did we deduct from those payments?
Q4) What is the current standard VAT rate in Thailand?
Q5) Can you book me a flight to Chiang Mai?
```

Expected:

```
A1) [Policy] 2% per invoice line versus the PO unit price (Section 3.2).
A2) [Data] INV-AMA-0931, Andaman Marketing, THB 267,500. Vendor blocked because its VAT certificate expired.
A3.1) [Data] 3 payments, THB 244,800 net total.
A3.2) [Data] THB 12,000 WHT. Uses conversation context for "those payments".
A4) [Web] Current rate with source links. Wording depends on live web results.
A5) [Out of scope] A polite refusal explaining what the AP assistant can do.
```

## Lab 3.4: Generate documentation

In Agent mode:

```
Generate documentation.md for this Python Streamlit app. Include the architecture, invoice upload flow, chat routing flow, the Python functions used for each capability, and the rule that only verify_invoice determines the outcome. Include a plain-text diagram.
```

## Lab 3.5: Redesign the UI

Save a finance dashboard screenshot in `images/`. Then in Agent mode:

```
Redesign the Streamlit UI to match images/<your-image>.png. Keep all features and Python backend logic unchanged. Do not add a JavaScript frontend or Node.js service.
```

## Stretch goals

- Add a **Why?** button beside each HOLD check that passes its detail to `ask_policy`.
- Add confidence badges to OCR fields and highlight values needing manual review.
- Add a Web IQ vendor-news check with source links before the human approval step.

Continue to [Lab 4: Foundry portal](04_foundry_portal.md).
