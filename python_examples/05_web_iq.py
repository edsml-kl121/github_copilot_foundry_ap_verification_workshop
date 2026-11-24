"""Search live web passages with Web IQ and answer with source citations."""

from __future__ import annotations

import argparse
import json
import urllib.request

try:
    from .common import client_for, config
except ImportError:
    from common import client_for, config

DEFAULT_QUESTIONS = [
    "อัตราภาษีมูลค่าเพิ่มของไทยในปัจจุบันเท่าไร และอัตราลดใช้ถึงเมื่อไร?",
    "บริษัทไทยจ่ายค่าขนส่งให้บริษัทในประเทศต้องหักภาษี ณ ที่จ่ายอัตราเท่าไร?",
]


def web_iq_search(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    if not api_key:
        raise ValueError("WEBIQ_API_KEY is not set. See workshop_guideline/01_setup_lab.md, Lab 1.5.")
    request = urllib.request.Request(
        "https://api.microsoft.ai/v3/search/web",
        data=json.dumps(
            {"query": query, "maxResults": max_results, "contentFormat": "passage", "maxLength": 3000}
        ).encode(),
        headers={"x-apikey": api_key, "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read())
    return [
        {"title": item.get("title"), "url": item.get("url"), "content": item.get("content"),
         "crawledAt": item.get("crawledAt")}
        for item in body.get("webResults", [])
    ]


def ask_web(client, question: str, cfg: dict[str, str]) -> tuple[str, list[dict]]:
    sources = web_iq_search(question, cfg["webiq_api_key"])
    context = "\n\n".join(
        f"[{i}] {s.get('title')}\nURL: {s.get('url')}\nCrawled: {s.get('crawledAt') or 'n/a'}\n{s.get('content')}"
        for i, s in enumerate(sources, start=1)
    )
    response = client.responses.create(
        model=cfg["chat_deployment"],
        instructions=(
            "You are an AP research assistant. Answer using ONLY the numbered web sources. Cite sources inline like [1]. "
            "Prefer official government sources (for example rd.go.th, bot.or.th). If sources disagree or are outdated, "
            "say so. Answer in Thai. End with: 'ตรวจสอบกับทีมภาษีก่อนเปลี่ยนแปลงการจ่ายเงิน'"
        ),
        input=f"Question: {question}\n\nWeb sources:\n{context or '(no results)'}",
    )
    return response.output_text, sources


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", nargs="*")
    args = parser.parse_args()
    cfg = config()
    client = client_for(cfg)
    for question in args.questions or DEFAULT_QUESTIONS:
        answer, sources = ask_web(client, question, cfg)
        print(f"\n[user] {question}\n[assistant] {answer}")
        for index, source in enumerate(sources, start=1):
            print(f"  [{index}] {source.get('title')} - {source.get('url')}")


if __name__ == "__main__":
    main()
