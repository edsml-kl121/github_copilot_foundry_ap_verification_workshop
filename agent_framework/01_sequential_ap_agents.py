"""Lab 5, Exercise 1: sequential multi-agent AP verification with Microsoft Agent Framework.

    IntakeAgent ──▶ VerifierAgent ──▶ PolicyAgent ──▶ final AP memo
    (reads OCR)     (rules + SQL)      (policy + Web IQ)

Run from the repository root:

    python agent_framework/01_sequential_ap_agents.py                         # INV-TTS-2026-118.pdf
    python agent_framework/01_sequential_ap_agents.py INV-CMP-2026-0057.pdf
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from agent_framework import AgentResponseUpdate
from agent_framework.openai import OpenAIChatClient
from agent_framework.orchestrations import SequentialBuilder
from dotenv import load_dotenv

from ap_tools import get_database_schema, query_ap_database, read_invoice, read_policy, run_three_way_match, web_search

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def require(name: str) -> str:
    value = os.getenv(name, "")
    if not value or value.startswith(("replace-with", "https://YOUR-")):
        sys.exit(f"Missing {name}. Fill in .env first (workshop_guideline/01_setup_lab.md, Lab 1.6).")
    return value


def build_workflow():
    client = OpenAIChatClient(
        model=os.getenv("FOUNDRY_DEPLOYMENT_CHAT", "gpt-4.1-mini"),
        azure_endpoint=require("FOUNDRY_ENDPOINT"),
        api_key=require("FOUNDRY_API_KEY"),
    )

    intake = client.as_agent(
        name="IntakeAgent",
        instructions=(
            "You are an AP intake clerk. Call read_invoice for the file the user names. "
            "Summarize: invoice number, vendor, PO number, bank account, subtotal, VAT, total, and each line "
            "(item code, quantity, unit price). Do not judge the invoice."
        ),
        tools=[read_invoice],
    )

    verifier = client.as_agent(
        name="VerifierAgent",
        instructions=(
            "You are an AP verifier. Call run_three_way_match for the same file. Its outcome is final; never "
            "change it. Report the outcome, approver, withholding tax and every check that is not PASS. "
            "If useful, call get_database_schema and query_ap_database to add context (for example the PO "
            "lines, goods receipts, or the vendor's payment history)."
        ),
        tools=[run_three_way_match, get_database_schema, query_ap_database],
    )

    policy = client.as_agent(
        name="PolicyAgent",
        instructions=(
            "You are the AP policy advisor writing the final memo for a human approver. Call read_policy and "
            "cite the section number for each exception and for the approval route. If withholding tax applies, "
            "call web_search once to confirm the current Thai rate for this vendor category and cite the URL; if "
            "web search is unavailable, say so. If web and policy disagree, recommend escalation. "
            "Write at most 150 words with headings: Outcome, Exceptions, Next steps, Approver. "
            "You never approve or pay invoices."
        ),
        tools=[read_policy, web_search],
    )

    return SequentialBuilder(
        participants=[intake, verifier, policy],
        intermediate_output_from=[intake, verifier],
    ).build()


async def main() -> None:
    file_name = sys.argv[1] if len(sys.argv) > 1 else "INV-TTS-2026-118.pdf"
    workflow = build_workflow()

    last_author = None
    async for event in workflow.run(f"Verify invoice file {file_name}.", stream=True):
        if event.type in ("output", "intermediate") and isinstance(event.data, AgentResponseUpdate):
            update = event.data
            if update.author_name != last_author:
                last_author = update.author_name
                label = "FINAL MEMO" if event.type == "output" else "step"
                print(f"\n\n===== [{label}] {last_author} =====")
            print(update.text, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
