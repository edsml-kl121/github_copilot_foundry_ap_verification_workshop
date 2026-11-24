# GitHub Copilot + Microsoft Foundry Workshop: AP Invoice Verification

Build an assistant that checks supplier invoices before Contoso (Thailand) pays them. The workshop is **Python-only** and demonstrates OCR, Vector Search, Text2SQL and Web IQ.

**Why AP verification?** No finance experience is needed. A three-way match compares what the company ordered (Purchase Order), received (Goods Receipt) and was billed (Invoice). A deterministic Python rules engine decides whether an invoice is APPROVED, ON HOLD or REJECTED. The model explains the result, and a human makes the final decision.

## Labs

| Lab | Topic | Time |
|---|---|---|
| [1. Setup](workshop_guideline/01_setup_lab.md) | Python environment, Foundry models, keys and smoke checks | 30 to 40 min |
| [2. Capabilities](workshop_guideline/02_capabilities_lab.md) | Python examples for OCR, Vector Search, Text2SQL, Web IQ and the pipeline | 45 to 60 min |
| [3. Build the app with Copilot](workshop_guideline/03_agentdev.md) | Build a local Python Streamlit app from the requirements transcript | 45 to 60 min |
| [4. Foundry portal](workshop_guideline/04_foundry_portal.md) | No-code agent with File Search and Web IQ MCP | 30 to 40 min |
| [5. Agent Framework](workshop_guideline/05_agent_framework.md) | Python multi-agent workflow using the same rules | 30 to 45 min |

Quick reference: [Foundry_tutorial.md](Foundry_tutorial.md).

## Architecture

```
Invoice PDF / scan
        |
        v
OCR: Document Intelligence or vision model
        |
        v
Python rules: PO + receipt + invoice + bank + duplicates
        |                     -> APPROVED / ON HOLD / REJECTED
        +----------+----------+
                   |
       +-----------+------------------+
       v                 v            v
 Vector Search       Text2SQL       Web IQ
 (policy PDF)       (AP database)  (live facts)
       +-----------------+------------+
                         v
               model writes a memo
                         |
                         v
                 human makes decision
```

## Repository layout

```
├── .env.template                  # copy to .env (Lab 1)
├── requirements.txt               # Python dependencies for all labs
├── data/
│   ├── meeting_transcript.txt     # requirements for the Copilot app build
│   ├── Contoso_AP_Invoice_Policy.pdf
│   ├── ap_database.sql            # vendors, POs, receipts, invoices, payments
│   └── invoices/                  # sample invoices and OCR ground truth
├── python_examples/
│   ├── 00_check_setup.py
│   ├── 01_basic_chat.py
│   ├── 02_ocr_invoice.py
│   ├── 03_vector_search.py
│   ├── 04_text2sql.py
│   ├── 05_web_iq.py
│   ├── 06_ap_verification_pipeline.py
│   └── verify.py                  # deterministic AP rules
├── agent_framework/               # multi-agent extension of the same Python tools
├── scripts/generate_sample_data.py
└── workshop_guideline/
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.template .env              # fill in Foundry and Web IQ values
python python_examples/00_check_setup.py
python -m unittest discover -s python_examples -p 'test_*.py'
python python_examples/06_ap_verification_pipeline.py --offline
```

All company names, people, tax IDs and bank accounts in `data/` are fictitious.
