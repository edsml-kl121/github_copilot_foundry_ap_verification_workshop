"""Check configuration and local data; run live connectivity checks only when configured."""

from __future__ import annotations

import json
import sqlite3
import sys
import urllib.request

try:
    from .common import DATA, client_for, config
except ImportError:
    from common import DATA, client_for, config


def main() -> None:
    results: list[tuple[str, str, str]] = []
    try:
        cfg = config()
        results.append((".env configuration", "PASS", cfg["endpoint"]))
    except ValueError as exc:
        print(f".env configuration: FAIL: {exc}")
        sys.exit(1)

    client = client_for(cfg)
    for label, deployment in (
        ("Chat model", cfg["chat_deployment"]),
        ("Vision model", cfg["vision_deployment"]),
    ):
        try:
            response = client.responses.create(model=deployment, input="Reply with the single word: ready")
            results.append((f"{label} ({deployment})", "PASS", response.output_text[:40]))
        except Exception as exc:
            results.append((f"{label} ({deployment})", "FAIL", str(exc).splitlines()[0]))

    try:
        url = f"{cfg['docintel_endpoint']}documentintelligence/documentModels/prebuilt-layout?api-version=2024-11-30"
        request = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": cfg["api_key"]})
        with urllib.request.urlopen(request, timeout=30):
            results.append(("Document Intelligence (OCR)", "PASS", cfg["docintel_endpoint"]))
    except Exception as exc:
        results.append(("Document Intelligence (OCR)", "FAIL", str(exc)))

    if cfg["webiq_api_key"]:
        try:
            request = urllib.request.Request(
                "https://api.microsoft.ai/v3/search/web",
                data=json.dumps(
                    {"query": "Thailand VAT rate", "maxResults": 1, "contentFormat": "passage", "maxLength": 200}
                ).encode(),
                headers={"x-apikey": cfg["webiq_api_key"], "content-type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
            results.append(("Web IQ", "PASS", f"{len(body.get('webResults', []))} result(s)"))
        except Exception as exc:
            results.append(("Web IQ", "FAIL", str(exc)))
    else:
        results.append(("Web IQ", "SKIP", "WEBIQ_API_KEY not set"))

    try:
        conn = sqlite3.connect(":memory:")
        conn.executescript((DATA / "ap_database.sql").read_text(encoding="utf-8"))
        count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        results.append(("AP database", "PASS", f"{count} invoices loaded"))
    except Exception as exc:
        results.append(("AP database", "FAIL", str(exc)))

    for name, status, detail in results:
        print(f"{status:5} {name:36} {detail}")
    failures = sum(status == "FAIL" for _, status, _ in results)
    print("\nAll required checks passed." if not failures else f"\n{failures} check(s) failed.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
