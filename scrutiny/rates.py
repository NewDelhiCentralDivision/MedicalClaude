"""Loading the CGHS rate master from a CSV file."""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Iterable, Union

from .models import RateEntry
from .text import CONSULT, tokens

REQUIRED_COLUMNS = ("code", "description", "rate")

_INDOOR_WORDS = {"inpatient", "indoor", "ipd", "admitted", "ward"}
_OPD_WORDS = {"opd", "outpatient"}


class RateSheetError(ValueError):
    """Raised when a rate sheet cannot be used."""


def parse_amount(value: object) -> float:
    """Parse '1,280', 'Rs. 350', '₹350.50' and similar into a float."""
    text = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if text in {"", "-", "."}:
        raise ValueError(f"not an amount: {value!r}")
    return float(text)


def infer_setting(description: str) -> str | None:
    toks = set(tokens(description, keep_generic=True))
    if toks & _INDOOR_WORDS:
        return "indoor"
    if toks & _OPD_WORDS:
        return "opd"
    return None


def _rows_from_text(text: str) -> Iterable[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise RateSheetError("The rate sheet is empty.")
    lowered = {name.strip().lower(): name for name in reader.fieldnames if name}
    missing = [c for c in REQUIRED_COLUMNS if c not in lowered]
    if missing:
        raise RateSheetError(
            "Rate sheet is missing column(s): " + ", ".join(missing)
            + ". Expected columns: code, description, rate."
        )
    for raw in reader:
        yield {key: (raw.get(orig) or "").strip() for key, orig in lowered.items()}


def load_rates(source: Union[str, Path, bytes, io.IOBase]) -> list[RateEntry]:
    """Load a rate master. `source` may be a path, bytes or an open file."""
    if isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8-sig")
    elif isinstance(source, bytes):
        text = source.decode("utf-8-sig")
    else:
        data = source.read()
        text = data.decode("utf-8-sig") if isinstance(data, bytes) else data

    entries: list[RateEntry] = []
    seen: set[str] = set()
    for line_no, row in enumerate(_rows_from_text(text), start=2):
        code = row["code"].upper().replace(" ", "")
        if not code:
            continue
        if code in seen:
            raise RateSheetError(f"Duplicate code {code} (row {line_no}).")
        try:
            rate = parse_amount(row["rate"])
        except ValueError as exc:
            raise RateSheetError(f"Row {line_no} ({code}): {exc}") from exc
        description = row["description"]
        setting = (row.get("setting") or "").lower() or infer_setting(description)
        category = "consultation" if CONSULT in tokens(description, keep_generic=True) else ""
        entries.append(RateEntry(code, description, rate, setting or None, category))
        seen.add(code)
    if not entries:
        raise RateSheetError("The rate sheet has no usable rows.")
    return entries


def index_by_code(rates: Iterable[RateEntry]) -> dict[str, RateEntry]:
    return {r.code: r for r in rates}
