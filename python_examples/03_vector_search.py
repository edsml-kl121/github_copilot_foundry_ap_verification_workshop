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
    "Quote the section number. If the policy does not cover the question, reply exactly: "
    "'I cannot find that in the AP policy. Please contact ap-policy@contoso.example.'"
)
DEFAULT_QUESTIONS = [
    "What is the allowed unit price variance in the three-way match?",
    "The bank account on an invoice is different from our vendor master. What should I do?",
    "Who must approve an invoice with a total of THB 267,500?",
    "What withholding tax rate applies to IT service invoices, and what document do we issue?",
    "What is Contoso's policy on remote work?",
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
