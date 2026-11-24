"""Ground AP policy answers with Foundry File Search (vector search)."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .common import POLICY_PDF, client_for, config
except ImportError:
    from common import POLICY_PDF, client_for, config

POLICY_INSTRUCTIONS = (
    "You are Contoso's AP policy assistant. Answer ONLY from the AP Invoice Verification Policy found with file search. "
    "Answer in Thai and quote the section number. If the policy does not cover the question, reply exactly: "
    "'ไม่พบข้อมูลนี้ในนโยบายบัญชีเจ้าหนี้ กรุณาติดต่อ ap-policy@contoso.example'"
)
DEFAULT_QUESTIONS = [
    "การตรวจเอกสารสามทางยอมให้ราคาต่อหน่วยต่างจาก PO ได้เท่าไร?",
    "บัญชีธนาคารในใบแจ้งหนี้ต่างจากทะเบียนผู้ขาย ต้องทำอย่างไร?",
    "ใครต้องอนุมัติใบแจ้งหนี้ยอดรวม 267,500 บาท?",
    "ใบแจ้งหนี้บริการ IT หักภาษี ณ ที่จ่ายอัตราใด และต้องออกเอกสารอะไร?",
    "คอนโทโซมีนโยบายทำงานจากที่บ้านอย่างไร?",
]


def ensure_policy_vector_store(client) -> tuple[str, bool, str | None]:
    import os

    existing = os.getenv("AP_POLICY_VECTOR_STORE_ID", "").strip()
    if existing:
        return existing, False, None
    with POLICY_PDF.open("rb") as policy_file:
        uploaded = client.files.create(file=policy_file, purpose="assistants")
    vector_store = client.vector_stores.create(name="contoso-ap-policy")
    try:
        client.vector_stores.file_batches.create_and_poll(
            vector_store_id=vector_store.id,
            file_ids=[uploaded.id],
        )
    except Exception:
        client.vector_stores.delete(vector_store.id)
        client.files.delete(uploaded.id)
        raise
    return vector_store.id, True, uploaded.id


def ask_policy(client, vector_store_id: str, question: str, model: str) -> str:
    response = client.responses.create(
        model=model,
        instructions=POLICY_INSTRUCTIONS,
        input=question,
        tools=[{"type": "file_search", "vector_store_ids": [vector_store_id], "max_num_results": 4}],
        include=["file_search_call.results"],
    )
    return response.output_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", nargs="*")
    parser.add_argument("--keep", action="store_true", help="Keep a newly created vector store.")
    args = parser.parse_args()
    cfg = config()
    client = client_for(cfg)
    vector_store_id, created, file_id = ensure_policy_vector_store(client)
    print(f"Vector store: {vector_store_id}")
    try:
        for question in args.questions or DEFAULT_QUESTIONS:
            answer = ask_policy(client, vector_store_id, question, cfg["chat_deployment"])
            print(f"\n[user] {question}\n[assistant] {answer}")
    finally:
        if created and not args.keep:
            client.vector_stores.delete(vector_store_id)
            if file_id:
                client.files.delete(file_id)
            print("\nDeleted the temporary vector store.")
        elif created:
            print(f"\nKeep it by setting AP_POLICY_VECTOR_STORE_ID={vector_store_id} in .env.")


if __name__ == "__main__":
    main()
