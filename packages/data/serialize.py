from datetime import date, datetime
from decimal import Decimal
from typing import Any


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: serialize_value(value) for key, value in row.items()}


def serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize_row(row) for row in rows]


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
