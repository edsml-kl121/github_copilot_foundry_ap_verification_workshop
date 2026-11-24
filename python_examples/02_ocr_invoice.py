"""Extract invoice fields with Document Intelligence or a vision model."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import time
import urllib.request
from pathlib import Path

try:
    from .common import INVOICE_DIR, client_for, config, json_response
except ImportError:
    from common import INVOICE_DIR, client_for, config, json_response

API_VERSION = "2024-11-30"
NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_NUMBER = {"type": ["number", "null"]}
INVOICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "invoice_number", "invoice_date", "due_date", "po_number", "vendor_name", "vendor_tax_id",
        "buyer_tax_id", "bank_name", "bank_account", "currency", "subtotal", "vat", "total", "lines",
    ],
    "properties": {
        "invoice_number": NULLABLE_STRING,
        "invoice_date": NULLABLE_STRING,
        "due_date": NULLABLE_STRING,
        "po_number": NULLABLE_STRING,
        "vendor_name": NULLABLE_STRING,
        "vendor_tax_id": NULLABLE_STRING,
        "buyer_tax_id": NULLABLE_STRING,
        "bank_name": NULLABLE_STRING,
        "bank_account": NULLABLE_STRING,
        "currency": NULLABLE_STRING,
        "subtotal": NULLABLE_NUMBER,
        "vat": NULLABLE_NUMBER,
        "total": NULLABLE_NUMBER,
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["line_no", "item_code", "description", "quantity", "unit_price", "amount"],
                "properties": {
                    "line_no": {"type": "integer"},
                    "item_code": NULLABLE_STRING,
                    "description": NULLABLE_STRING,
                    "quantity": NULLABLE_NUMBER,
                    "unit_price": NULLABLE_NUMBER,
                    "amount": NULLABLE_NUMBER,
                },
            },
        },
    },
}


def _request(url: str, *, headers: dict[str, str], data: bytes | None = None, method: str = "GET"):
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.status, response.headers, response.read()


def _value(field: dict | None):
    if not field:
        return None
    currency = field.get("valueCurrency")
    if currency:
        return currency.get("amount")
    for key in ("valueString", "valueDate", "valueNumber", "valueInteger", "content"):
        if field.get(key) is not None:
            return field[key]
    return None


def _extract_bank_details(content: str) -> tuple[str | None, str | None]:
    bank = re.search(
        r"(?:remit to:?|please remit to:?|โอนเงินไปยัง\s*:?)\s*([^,\n]+),\s*"
        r"(?:account no\.?|เลขที่บัญชี)\s*:?\s*([\d-]+)",
        content,
        re.I,
    )
    return (bank.group(1).strip(), bank.group(2)) if bank else (None, None)


def extract_with_document_intelligence(file_path: Path, cfg: dict[str, str]) -> dict:
    url = (
        f"{cfg['docintel_endpoint']}documentintelligence/documentModels/prebuilt-invoice:analyze"
        f"?api-version={API_VERSION}"
    )
    payload = json.dumps({"base64Source": base64.b64encode(file_path.read_bytes()).decode()}).encode()
    status, headers, body = _request(
        url,
        headers={"Ocp-Apim-Subscription-Key": cfg["api_key"], "content-type": "application/json"},
        data=payload,
        method="POST",
    )
    if status != 202:
        raise RuntimeError(f"Document Intelligence analyze returned HTTP {status}: {body.decode(errors='replace')}")
    operation_url = headers.get("operation-location")
    if not operation_url:
        raise RuntimeError("Document Intelligence response did not include operation-location.")
    poll_headers = {"Ocp-Apim-Subscription-Key": cfg["api_key"]}
    for _ in range(60):
        time.sleep(1)
        _, _, poll_body = _request(operation_url, headers=poll_headers)
        result = json.loads(poll_body)
        if result.get("status") == "succeeded":
            analysis = result["analyzeResult"]
            fields = analysis.get("documents", [{}])[0].get("fields", {})
            bank_name, bank_account = _extract_bank_details(analysis.get("content", ""))
            items = fields.get("Items", {}).get("valueArray", [])
            lines = []
            for index, item in enumerate(items, start=1):
                obj = item.get("valueObject", {})
                lines.append({
                    "line_no": index,
                    "item_code": _value(obj.get("ProductCode")),
                    "description": _value(obj.get("Description")),
                    "quantity": _value(obj.get("Quantity")),
                    "unit_price": _value(obj.get("UnitPrice")),
                    "amount": _value(obj.get("Amount")),
                })
            tax_id = lambda name: re.sub(r"\D", "", str(_value(fields.get(name)) or "")) or None
            currency = fields.get("InvoiceTotal", {}).get("valueCurrency", {})
            return {
                "invoice_number": _value(fields.get("InvoiceId")),
                "invoice_date": _value(fields.get("InvoiceDate")),
                "due_date": _value(fields.get("DueDate")),
                "po_number": _value(fields.get("PurchaseOrder")),
                "vendor_name": _value(fields.get("VendorName")),
                "vendor_tax_id": tax_id("VendorTaxId"),
                "buyer_tax_id": tax_id("CustomerTaxId"),
                "bank_name": bank_name,
                "bank_account": bank_account,
                "currency": currency.get("currencyCode", "THB"),
                "subtotal": _value(fields.get("SubTotal")),
                "vat": _value(fields.get("TotalTax")),
                "total": _value(fields.get("InvoiceTotal")),
                "lines": lines,
            }
        if result.get("status") == "failed":
            raise RuntimeError(f"Document Intelligence failed: {result.get('error')}")
    raise TimeoutError("Document Intelligence timed out after 60 seconds.")


def extract_with_vision(file_path: Path, cfg: dict[str, str]) -> dict:
    mime = mimetypes.guess_type(file_path)[0] or "image/png"
    data_url = f"data:{mime};base64,{base64.b64encode(file_path.read_bytes()).decode()}"
    extracted = json_response(
        client_for(cfg),
        model=cfg["vision_deployment"],
        name="invoice",
        schema=INVOICE_SCHEMA,
        instructions=(
            "You are an OCR engine for supplier tax invoices. Transcribe values exactly as printed. "
            "Preserve Thai names and descriptions without translation. "
            "Use null for anything not visible. Numbers must be plain numbers without commas. Dates as YYYY-MM-DD."
        ),
        input_data=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Extract all invoice header fields and every line item."},
                {"type": "input_image", "image_url": data_url, "detail": "high"},
            ],
        }],
    )
    for key in ("vendor_tax_id", "buyer_tax_id"):
        value = extracted.get(key)
        extracted[key] = re.sub(r"\D", "", value) if value else None
    return extracted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", type=Path)
    parser.add_argument("--vision", action="store_true", help="Use the vision model instead of Document Intelligence.")
    args = parser.parse_args()
    path = args.file or INVOICE_DIR / ("INV-BEL-7781_scan.png" if args.vision else "INV-TTS-2026-118.pdf")
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    cfg = config()
    extracted = extract_with_vision(path, cfg) if args.vision else extract_with_document_intelligence(path, cfg)
    print(json.dumps(extracted, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
