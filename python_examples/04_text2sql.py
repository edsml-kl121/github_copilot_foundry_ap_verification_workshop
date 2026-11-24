"""Translate AP questions into read-only SQLite SQL and answer from its rows."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3

try:
    from .common import DATA, client_for, config, json_response
    from .text2sql import assert_read_only
except ImportError:
    from common import DATA, client_for, config, json_response
    from text2sql import assert_read_only

DEFAULT_QUESTIONS = [
    "มีใบแจ้งหนี้ใดพักรายการอยู่ เพราะอะไร?",
    "ใบแจ้งหนี้ใดอนุมัติแล้วแต่เลยกำหนดชำระและยังไม่ได้จ่าย?",
    "ปี 2026 จ่ายเงินให้บริษัท พระรามบริหารทรัพย์สิน จำกัด ไปเท่าไร และหักภาษี ณ ที่จ่ายเท่าไร?",
    "ใบแจ้งหนี้ INV-SOS-2026-0388 ถูกส่งมากกว่าหนึ่งครั้งหรือไม่?",
    "PO-2026-0103 สั่งซื้อและรับสินค้าจริงแต่ละรายการจำนวนเท่าไร?",
]
SQL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sql", "reasoning"],
    "properties": {
        "reasoning": {"type": "string", "description": "One sentence about the tables and joins used."},
        "sql": {"type": "string", "description": "A single SQLite SELECT or WITH ... SELECT statement."},
    },
}
def open_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript((DATA / "ap_database.sql").read_text(encoding="utf-8"))
    return conn


def generate_sql(client, cfg: dict[str, str], schema: str, question: str, previous_error: str = "") -> dict:
    prompt = f"Question: {question}"
    if previous_error:
        prompt += f"\nYour previous SQL failed with: {previous_error}\nReturn one corrected query."
    return json_response(
        client,
        model=cfg["chat_deployment"],
        name="sql_query",
        schema=SQL_SCHEMA,
        instructions=(
            "Translate Accounts Payable questions into SQLite SQL. "
            f"Today's date is {cfg['as_of_date']}; use that literal instead of date('now'). "
            "Dates are ISO text (YYYY-MM-DD). Money is THB. Use explicit columns and readable aliases. "
            "An invoice is unpaid if it has no row in payments. Limit results to 50 rows. "
            "Return only a read-only SELECT or WITH query.\nDatabase schema:\n" + schema
            + "\nVendor names and descriptive values are Thai. When filtering by a vendor's name, "
            "use a distinctive Thai substring with LIKE, not an English translation."
        ),
        input_data=prompt,
    )


def text2sql(client, question: str, cfg: dict[str, str]) -> dict:
    conn = open_database()
    schema = "\n".join(
        row[0] for row in conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")
    )
    attempt = generate_sql(client, cfg, schema, question)
    try:
        safe_sql = assert_read_only(attempt["sql"])
        rows = [dict(row) for row in conn.execute(safe_sql).fetchmany(50)]
    except (ValueError, sqlite3.Error) as exc:
        attempt = generate_sql(client, cfg, schema, question, str(exc))
        safe_sql = assert_read_only(attempt["sql"])
        rows = [dict(row) for row in conn.execute(safe_sql).fetchmany(50)]
    answer = client.responses.create(
        model=cfg["chat_deployment"],
        instructions=(
            "You are an AP analyst. Answer using ONLY the SQL result rows. Be brief, use THB with thousands "
            "separators, and mention invoice numbers. Answer in Thai and preserve Thai names. "
            "If there are no rows, say nothing matched."
        ),
        input=f"Question: {question}\nSQL: {safe_sql}\nRows (JSON): {json.dumps(rows)}",
    )
    return {"sql": safe_sql, "reasoning": attempt["reasoning"], "rows": rows, "answer": answer.output_text}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", nargs="*")
    args = parser.parse_args()
    cfg = config()
    client = client_for(cfg)
    print(f"Deployment: {cfg['chat_deployment']} | as-of date: {cfg['as_of_date']}")
    for question in args.questions or DEFAULT_QUESTIONS:
        print(f"\n[user] {question}")
        try:
            result = text2sql(client, question, cfg)
        except ValueError as exc:
            print(f"[blocked] {exc}")
            continue
        print(f"[sql] {result['sql']}")
        print(json.dumps(result["rows"], indent=2, ensure_ascii=False))
        print(f"[assistant] {result['answer']}")


if __name__ == "__main__":
    main()
