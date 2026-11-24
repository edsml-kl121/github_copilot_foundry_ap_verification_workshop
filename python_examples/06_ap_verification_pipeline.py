"""Run OCR, deterministic checks, policy search, Web IQ and an AP memo."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

try:
    from .common import GROUND_TRUTH, INVOICE_DIR, client_for, config
    from .verify import verify_invoice
except ImportError:
    from common import GROUND_TRUTH, INVOICE_DIR, client_for, config
    from verify import verify_invoice


def _load_module(filename: str, module_name: str):
    examples = Path(__file__).resolve().parent
    sys.path.insert(0, str(examples))
    spec = importlib.util.spec_from_file_location(module_name, examples / filename)
    if not spec or not spec.loader:
        raise ImportError(f"Cannot load Python example module {filename}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript((INVOICE_DIR.parent / "ap_database.sql").read_text(encoding="utf-8"))
    return conn


def _print_checks(result: dict) -> None:
    for check in result["checks"]:
        print(f"  {check['status']:6} {check['id']:18} Section {check['section']:5} {check['detail']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--offline", action="store_true", help="Use ground-truth OCR; skip all Foundry calls.")
    parser.add_argument("--vision", action="store_true", help="Use the vision model for OCR.")
    args = parser.parse_args()
    targets = args.files or sorted(INVOICE_DIR.glob("*.pdf"))
    truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    db = _database()
    policy_module = None
    web_module = None
    vector_store_id = None
    vector_store_created = False
    policy_file_id = None
    cfg = client = None

    if not args.offline:
        cfg = config()
        client = client_for(cfg)
        policy_module = _load_module("03_vector_search.py", "ap_policy_search")
        web_module = _load_module("05_web_iq.py", "ap_web_iq")
        vector_store_id, vector_store_created, policy_file_id = policy_module.ensure_policy_vector_store(client)

    web_cache: dict[str, tuple[str, list[dict]]] = {}
    try:
        for path in targets:
            path = path if path.is_absolute() else (Path.cwd() / path).resolve()
            name = path.name
            print(f"\n{'=' * 76}\n{name}\n{'=' * 76}")
            if args.offline:
                if name not in truth:
                    raise ValueError(f"No ground truth for {name}; run without --offline.")
                invoice = truth[name]
                print("[1 OCR]      skipped (--offline): using ground_truth.json")
            else:
                ocr_module = _load_module("02_ocr_invoice.py", "ap_ocr")
                use_vision = args.vision or path.suffix.lower() != ".pdf"
                invoice = (
                    ocr_module.extract_with_vision(path, cfg)
                    if use_vision
                    else ocr_module.extract_with_document_intelligence(path, cfg)
                )
                print(f"[1 OCR]      {invoice.get('invoice_number')} | {invoice.get('vendor_name')} | "
                      f"PO {invoice.get('po_number')} | total {invoice.get('total')}")

            result = verify_invoice(db, invoice)
            print(f"[2 RULES]    outcome: {result['outcome']} | approver: {result['approver']}")
            _print_checks(result)
            wht = result.get("withholding_tax")
            if wht:
                print(f"             WHT {wht['rate_pct']}% = {wht['amount']} | net payable {wht['net_payable']}")
            if args.offline:
                continue

            exceptions = [item for item in result["checks"] if item["status"] != "PASS"]
            if exceptions:
                policy_question = (
                    "An invoice has these exceptions: "
                    + "; ".join(f"{item['detail']} (Section {item['section']})" for item in exceptions)
                    + ". What must the AP Officer do for each, according to the policy?"
                )
            else:
                policy_question = (
                    f"An invoice passed the three-way match with total {invoice.get('total')} THB. "
                    "Who approves it and what are the next steps?"
                )
            guidance = policy_module.ask_policy(client, vector_store_id, policy_question, cfg["chat_deployment"])
            print(f"[3 POLICY]   {guidance}")

            web_answer = None
            if cfg["webiq_api_key"] and result.get("vendor") and wht and wht["rate_pct"] > 0:
                category = result["vendor"]["category"].lower()
                if category not in web_cache:
                    question = (
                        f"Current Thailand withholding tax rate when a company pays a domestic company "
                        f"for {category} services"
                    )
                    web_cache[category] = web_module.ask_web(client, question, cfg)
                web_answer, _sources = web_cache[category]
                print(f"[4 WEB IQ]   {web_answer.splitlines()[0]}")
            else:
                reason = "no WHT for this vendor" if cfg["webiq_api_key"] else "WEBIQ_API_KEY not set"
                print(f"[4 WEB IQ]   skipped ({reason})")

            memo = client.responses.create(
                model=cfg["chat_deployment"],
                instructions=(
                    "Write a short memo (max 120 words) for an AP Officer. Start with 'Recommendation: <OUTCOME>'. "
                    "Use ONLY the facts given. List exceptions and next actions as bullets. The outcome is already "
                    "decided by rules; do not change it. End with 'Final decision: AP Officer.'"
                ),
                input=json.dumps({
                    "invoice": invoice,
                    "verification": result,
                    "policy_guidance": guidance,
                    "web_check": web_answer,
                }),
            )
            print(f"[5 MEMO]\n{memo.output_text}")
    finally:
        if vector_store_created and vector_store_id and client:
            client.vector_stores.delete(vector_store_id)
            if policy_file_id:
                client.files.delete(policy_file_id)
            print("\nDeleted the temporary policy vector store.")
        db.close()


if __name__ == "__main__":
    main()
