# Microsoft Foundry AP Verification Workshop: Python quick reference

The full labs are in [`workshop_guideline/`](workshop_guideline/). All backend/AI examples and deterministic rules use Python. Sample documents and descriptive data are Thai. Lab 3 adds a React/Vite frontend using Node.js, with a Python/FastAPI backend.

## 1. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.template .env
python python_examples/00_check_setup.py
```

Set these values in `.env`:

| Variable | Value |
|---|---|
| `FOUNDRY_ENDPOINT` | AOAI endpoint, `https://<resource>.openai.azure.com/` |
| `FOUNDRY_API_KEY` | Foundry resource API key |
| `FOUNDRY_PROJECT_ENDPOINT` | Project endpoint for portal and optional agent code |
| `FOUNDRY_DEPLOYMENT_CHAT` | Chat deployment name, default `gpt-4.1-mini` |
| `FOUNDRY_DEPLOYMENT_VISION` | Vision-capable deployment name, default `gpt-4.1` |
| `WEBIQ_API_KEY` | Key from [webiq.microsoft.ai/profiles](https://webiq.microsoft.ai/profiles) |

## 2. Run the Python examples

| Command | Capability |
|---|---|
| `python python_examples/01_basic_chat.py` | Multi-turn Responses API chat |
| `python python_examples/02_ocr_invoice.py` | Document Intelligence Layout OCR + chat mapping to invoice JSON |
| `python python_examples/02_ocr_invoice.py --vision` | Vision model OCR on the noisy sample |
| `python python_examples/03_vector_search.py` | Vector Search / File Search over the policy PDF |
| `python python_examples/04_text2sql.py` | Text2SQL with a read-only SQL guardrail |
| `python python_examples/05_web_iq.py` | Web IQ search with grounded citations |
| `python python_examples/06_ap_verification_pipeline.py` | Full OCR, rules, policy, Web IQ and memo pipeline |
| `python python_examples/06_ap_verification_pipeline.py --offline` | Ground-truth OCR and Python rules, no cloud calls |
| `python -m unittest discover -s python_examples -p 'test_*.py'` | Offline tests |

Pass your own input:

```bash
python python_examples/02_ocr_invoice.py data/invoices/INV-CMP-2026-0057.pdf
python python_examples/03_vector_search.py "ต้องเก็บใบแจ้งหนี้ไว้นานเท่าไร?"
python python_examples/04_text2sql.py "ปี 2026 จ่ายเงินให้ผู้ขายรายใดมากที่สุด?"
python python_examples/05_web_iq.py "อัตราภาษีหัก ณ ที่จ่ายค่าโฆษณาของไทยในปัจจุบัน"
python python_examples/06_ap_verification_pipeline.py data/invoices/INV-BEL-7781_scan.png --vision
```

## 3. Authentication notes

- Python examples use the API key in `.env` with the Azure OpenAI v1 endpoint at `<FOUNDRY_ENDPOINT>openai/v1/`.
- Document Intelligence uses that resource key on `https://<resource>.cognitiveservices.azure.com/`.
- The Foundry portal Code tab uses Microsoft Entra ID. Run `az login` and ensure your account has the **Azure AI User** role.
- Web IQ uses its separate key in the `x-apikey` header.

## 4. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Missing `FOUNDRY_ENDPOINT` | `.env` is missing or still has placeholders. |
| `401 Unauthorized` | Wrong API key or a key from a different resource than the endpoint. |
| `404 DeploymentNotFound` | Deployment name in `.env` does not match Foundry. |
| Document Intelligence `404` | Set `FOUNDRY_DOCINTEL_ENDPOINT=https://<resource>.cognitiveservices.azure.com/`. |
| First vector search is slow | Initial PDF ingestion may take 10 to 30 seconds; set `AP_POLICY_VECTOR_STORE_ID` to reuse the store. |
| Web IQ `401` / `403` | Wrong Web IQ key or inactive profile. |
| `429 Too Many Requests` | Shared quota; wait a minute and retry. |
| Want fresh Thai sample data | `pip install -r scripts/requirements.txt && python scripts/generate_sample_data.py` overwrites generated files in `data/`; bundled Sarabun fonts support Thai shaping. |
| Policy answers still use old English document | Create a fresh vector store for the Thai PDF and update `AP_POLICY_VECTOR_STORE_ID`. |

## 5. App lab

Node.js 22 LTS or later is needed only for the frontend. After Copilot creates the app in Lab 3:

```bash
# Terminal 1, repository root, with .venv active
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
# Terminal 2
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

The browser calls relative `/api/*` URLs through Vite's proxy. Credentials and all AI calls stay in Python. In Codespaces, forward only frontend port 5173 as private.
