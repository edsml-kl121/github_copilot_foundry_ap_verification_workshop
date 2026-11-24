"""Shared SQL generation guardrails for Text2SQL and the MAF tool."""

import re

WRITE_KEYWORDS = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|replace)\b", re.I)


def assert_read_only(sql: str) -> str:
    statement = sql.strip().removesuffix(";").strip()
    if ";" in statement:
        raise ValueError("Only a single SQL statement is allowed.")
    if not re.match(r"^(select|with)\b", statement, re.I):
        raise ValueError("Only SELECT / WITH queries are allowed.")
    if WRITE_KEYWORDS.search(statement):
        raise ValueError("Query contains a write/DDL keyword.")
    return statement
