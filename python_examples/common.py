"""Shared configuration and Microsoft Foundry client for the Python labs."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INVOICE_DIR = DATA / "invoices"
POLICY_PDF = DATA / "Contoso_AP_Invoice_Policy.pdf"
GROUND_TRUTH = INVOICE_DIR / "ground_truth.json"

load_dotenv(ROOT / ".env")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "YOUR-" in value or value.startswith("replace-with"):
        raise ValueError(
            f"Missing or placeholder value for {name}. Copy .env.template to .env "
            "and fill in real values (see workshop_guideline/01_setup_lab.md)."
        )
    return value


def config() -> dict[str, str]:
    endpoint = required("FOUNDRY_ENDPOINT").rstrip("/") + "/"
    resource = endpoint.split("://", 1)[-1].split(".", 1)[0]
    return {
        "endpoint": endpoint,
        "api_key": required("FOUNDRY_API_KEY"),
        "docintel_endpoint": (
            os.getenv("FOUNDRY_DOCINTEL_ENDPOINT", "").strip()
            or f"https://{resource}.cognitiveservices.azure.com/"
        ).rstrip("/") + "/",
        "chat_deployment": os.getenv("FOUNDRY_DEPLOYMENT_CHAT", "gpt-4.1-mini"),
        "vision_deployment": os.getenv("FOUNDRY_DEPLOYMENT_VISION", "gpt-4.1"),
        "webiq_api_key": os.getenv("WEBIQ_API_KEY", "").strip(),
        "as_of_date": os.getenv("AP_AS_OF_DATE", "2026-11-24"),
    }


def client_for(cfg: dict[str, str] | None = None) -> OpenAI:
    cfg = cfg or config()
    return OpenAI(base_url=f"{cfg['endpoint']}openai/v1/", api_key=cfg["api_key"])


def json_response(client: OpenAI, *, model: str, instructions: str, input_data, name: str, schema: dict):
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_data,
        text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
    )
    import json

    return json.loads(response.output_text)
