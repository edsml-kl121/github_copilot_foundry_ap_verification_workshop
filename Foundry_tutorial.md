# Microsoft Foundry AP Verification Workshop: Python quick reference

The full labs are in [`workshop_guideline/`](workshop_guideline/). Every local code example and the deterministic rules engine use Python.

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
| `python python_examples/02_ocr_invoice.py` | Document Intelligence invoice OCR |
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
python python_examples/03_vector_search.py "How long must invoices be retained?"
python python_examples/04_text2sql.py "Which vendor have we paid the most in 2026?"
python python_examples/05_web_iq.py "Current Thai withholding tax rate for advertising services"
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
| Want fresh sample data | `python3 -m pip install reportlab pillow && python3 scripts/generate_sample_data.py` |
