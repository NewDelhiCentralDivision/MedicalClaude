"""Mode-specific resolution of bill rows and the rate cap.

The CGHS rate is a cap: admissible = min(billed amount, rate x quantity).
"""
from __future__ import annotations

from typing import Mapping, Optional

from .duplicates import held_back_duplicates
from .matcher import find_by_code, normalize_code, suggest
from .models import BillRow, RateEntry, ResolvedRow

MODE_CODE = "code"
MODE_MANUAL = "manual"
MODE_NOCODE = "nocode"

MODE_LABELS = {
    MODE_CODE: "Automatic – Code Based",
    MODE_MANUAL: "Manual",
    MODE_NOCODE: "Diagnosis/Description Based – No Code Available",
}
SETTING_LABELS = {"indoor": "Indoor Treatment", "opd": "OPD"}

STATUS_LABELS = {
    "matched": "Matched by printed code",
    "suggested": "Suggested · confirm",
    "officer": "Set by officer",
    "awaiting": "Awaiting officer",
    "unresolved": "Unresolved",
    "no_code": "No code · ₹0",
    "held": "Held back · duplicate",
}


def apply_cap(amount: float, qty: int, rate: float) -> float:
    """Lower of the billed amount and the CGHS rate (per unit x quantity)."""
    return round(min(float(amount), float(rate) * max(int(qty), 1)), 2)


def _with_entry(row: BillRow, status: str, entry: RateEntry, source: str, **extra) -> ResolvedRow:
    cap = round(entry.rate * max(row.qty, 1), 2)
    return ResolvedRow(
        row=row,
        status=status,
        entry=entry,
        source=source,
        rate_cap=cap,
        admissible=apply_cap(row.amount, row.qty, entry.rate),
        **extra,
    )


def resolve(
    rows: list[BillRow],
    rates: list[RateEntry],
    mode: str,
    setting: Optional[str] = None,
    overrides: Optional[Mapping[int, str]] = None,
) -> list[ResolvedRow]:
    """Resolve every bill row under `mode`.

    `overrides` maps a row number to an officer-chosen rate code. It is applied
    in every mode and always beats an automatic match.
    """
    if mode not in MODE_LABELS:
        raise ValueError(f"Unknown mode: {mode!r}")
    overrides = overrides or {}
    held = held_back_duplicates(rows)
    out: list[ResolvedRow] = []

    for row in rows:
        if row.n in held:
            out.append(ResolvedRow(row, "held", note=held[row.n]))
            continue

        chosen = find_by_code(overrides.get(row.n, ""), rates)
        if chosen is not None:
            out.append(_with_entry(row, "officer", chosen, "officer choice"))
            continue

        printed = find_by_code(row.printed_code, rates)
        if printed is not None and mode in (MODE_CODE, MODE_NOCODE):
            out.append(_with_entry(row, "matched", printed, "printed code"))
            continue

        if mode == MODE_CODE:
            if normalize_code(row.printed_code):
                out.append(ResolvedRow(
                    row, "unresolved",
                    note=f"Printed code {normalize_code(row.printed_code)} is not in the rate sheet",
                ))
            else:
                out.append(ResolvedRow(row, "no_code", note="No printed code on this bill row"))
            continue

        if mode == MODE_MANUAL:
            out.append(ResolvedRow(row, "awaiting", note="Pick an entry from the rate sheet"))
            continue

        # MODE_NOCODE
        hint = suggest(row.description, setting, rates)
        if hint.kind == "match" and hint.entry is not None:
            out.append(_with_entry(
                row, "suggested", hint.entry, hint.source, candidates=hint.candidates,
            ))
        else:
            out.append(ResolvedRow(
                row, "unresolved", note=hint.note, candidates=hint.candidates,
            ))
    return out


def summarize(resolved: list[ResolvedRow]) -> dict:
    """Totals and counts for the summary strip."""
    return {
        "billed_total": round(sum(r.row.amount for r in resolved), 2),
        "admissible_total": round(sum(r.admissible for r in resolved), 2),
        "suggestions": sum(r.status == "suggested" for r in resolved),
        "unresolved": sum(r.status in {"unresolved", "no_code", "awaiting"} for r in resolved),
        "held": sum(r.status == "held" for r in resolved),
        "needs_officer": sum(r.needs_officer for r in resolved),
    }
