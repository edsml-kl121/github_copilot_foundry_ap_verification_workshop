"""Server-side Python interfaces used by the FastAPI backend in Lab 3."""

from __future__ import annotations

import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path

from python_examples.common import ROOT, client_for, config

_EXAMPLES = Path(__file__).resolve().parent
sys.path.insert(0, str(_EXAMPLES))


def _load(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, _EXAMPLES / filename)
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load {filename}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract_invoice(file_path: str | Path, *, vision: bool = False) -> dict:
    module = _load("02_ocr_invoice.py", "ap_ocr")
    cfg = config()
    path = Path(file_path)
    return (
        module.extract_with_vision(path, cfg)
        if vision or path.suffix.lower() != ".pdf"
        else module.extract_with_document_intelligence(path, cfg)
    )


@lru_cache(maxsize=1)
def _policy_store() -> tuple[object, str]:
    cfg = config()
    client = client_for(cfg)
    module = _load("03_vector_search.py", "ap_policy_search")
    vector_store_id, _created, _file_id = module.ensure_policy_vector_store(client)
    return client, vector_store_id


def ask_policy(question: str, history: list[dict] | None = None) -> str:
    cfg = config()
    client, vector_store_id = _policy_store()
    module = _load("03_vector_search.py", "ap_policy_search")
    context = "\n".join(f"{message.get('role')}: {message.get('content')}" for message in (history or [])[-10:])
    prompt = f"Recent conversation:\n{context}\n\nQuestion: {question}" if context else question
    return module.ask_policy(client, vector_store_id, prompt, cfg["chat_deployment"])


def ask_data(question: str, history: list[dict] | None = None) -> dict:
    cfg = config()
    client = client_for(cfg)
    module = _load("04_text2sql.py", "ap_text2sql")
    context = "\n".join(f"{message.get('role')}: {message.get('content')}" for message in (history or [])[-10:])
    prompt = f"Recent conversation:\n{context}\n\nQuestion: {question}" if context else question
    return module.text2sql(client, prompt, cfg)


def ask_web(question: str, history: list[dict] | None = None) -> tuple[str, list[dict]]:
    cfg = config()
    client = client_for(cfg)
    module = _load("05_web_iq.py", "ap_web_iq")
    context = "\n".join(f"{message.get('role')}: {message.get('content')}" for message in (history or [])[-10:])
    prompt = f"Recent conversation:\n{context}\n\nQuestion: {question}" if context else question
    return module.ask_web(client, prompt, cfg)


def route_chat(question: str, history: list[dict] | None = None) -> str:
    cfg = config()
    client = client_for(cfg)
    response = client.responses.create(
        model=cfg["chat_deployment"],
        instructions=(
            "Classify the latest AP assistant question as exactly one of: policy, data, web, out_of_scope. "
            "policy means Contoso AP rules; data means internal invoice, vendor, PO, receipt or payment records; "
            "web means current external facts; out_of_scope means unrelated tasks. Reply with only the category."
        ),
        input=json.dumps({
            "recent_conversation": (history or [])[-10:],
            "question": question,
        }, ensure_ascii=False),
    )
    route = response.output_text.strip().lower()
    return route if route in {"policy", "data", "web", "out_of_scope"} else "clarify"
