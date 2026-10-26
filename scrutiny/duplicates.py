"""Duplicate-line handling.

Only a *repeated copy of the same numbered invoice line* is held back: same
invoice number, same line number and same description. Repeated consultations
on different lines (or with no line numbers) are legitimate and are never
held back.
"""
from __future__ import annotations

from typing import Iterable

from .models import BillRow
from .text import tokens


def _key(row: BillRow):
    invoice = row.invoice_no.strip().lower()
    line = str(row.line_no).strip().lower()
    if not invoice or not line:
        return None
    return (invoice, line, tuple(tokens(row.description)), round(float(row.amount), 2))


def held_back_duplicates(rows: Iterable[BillRow]) -> dict[int, str]:
    """Map row number -> reason for every row that repeats an earlier line."""
    seen: dict[tuple, int] = {}
    held: dict[int, str] = {}
    for row in rows:
        key = _key(row)
        if key is None:
            continue
        if key in seen:
            held[row.n] = f"Repeats invoice line {row.line_no} already counted in row {seen[key]}"
        else:
            seen[key] = row.n
    return held
