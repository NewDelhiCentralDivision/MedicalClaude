"""Matching billed charges to rate-sheet entries.

Principles
----------
* A printed, verified code always wins over any description guess.
* A description match is only *suggested* when exactly one entry is a strong
  match. Ambiguous or generic charges are never guessed.
* A diagnosis alone never creates a code. Only the billed description and the
  documented treatment setting are used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .models import Candidate, RateEntry
from .text import CONSULT, is_generic, tokens

# A billed description is a strong match for an entry when every billed token
# appears in the entry (coverage of the bill) and the entry is not mostly
# unrelated extra wording (coverage of the entry).
MIN_BILL_COVERAGE = 1.0
MIN_ENTRY_COVERAGE = 0.25
MAX_CANDIDATES = 4


@dataclass
class Suggestion:
    # match | ambiguous | generic | need_setting | none
    kind: str
    entry: Optional[RateEntry] = None
    source: str = ""
    note: str = ""
    candidates: list[Candidate] = field(default_factory=list)


def normalize_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "")


def find_by_code(code: str, rates: Iterable[RateEntry]) -> Optional[RateEntry]:
    wanted = normalize_code(code)
    if not wanted:
        return None
    for entry in rates:
        if entry.code == wanted:
            return entry
    return None


def _scored(bill_tokens: set[str], rates: Iterable[RateEntry]) -> list[tuple[float, float, float, RateEntry]]:
    scored = []
    for entry in rates:
        entry_tokens = set(tokens(entry.description))
        if not entry_tokens:
            continue
        common = bill_tokens & entry_tokens
        if not common:
            continue
        cov_bill = len(common) / len(bill_tokens)
        cov_entry = len(common) / len(entry_tokens)
        score = 0.7 * cov_bill + 0.3 * cov_entry
        scored.append((score, cov_bill, cov_entry, entry))
    scored.sort(key=lambda item: (-item[0], item[3].code))
    return scored


def suggest(description: str, setting: Optional[str], rates: list[RateEntry]) -> Suggestion:
    """Suggest a rate-sheet entry for a billed description (no printed code)."""
    toks = tokens(description)
    bill_tokens = set(toks)

    if not bill_tokens or is_generic(toks):
        return Suggestion(
            "generic",
            note="Generic charge. Choose a rate-sheet entry or leave unpaid.",
        )

    # A plain consultation charge is resolved by the documented setting.
    if bill_tokens == {CONSULT}:
        if setting not in {"indoor", "opd"}:
            return Suggestion(
                "need_setting",
                note="Choose Indoor Treatment or OPD to match a consultation charge.",
            )
        options = [
            e for e in rates if e.category == "consultation" and e.setting == setting
        ]
        label = "indoor" if setting == "indoor" else "OPD"
        cands = [Candidate(e, 1.0) for e in options[:MAX_CANDIDATES]]
        if len(options) == 1:
            return Suggestion(
                "match",
                entry=options[0],
                source=f"description + {label} setting",
                candidates=cands,
            )
        return Suggestion(
            "ambiguous" if options else "none",
            note=(f"{len(options)} {label} consultation entries in the rate sheet."
                  if options else f"No {label} consultation entry in the rate sheet."),
            candidates=cands,
        )

    scored = _scored(bill_tokens, rates)
    strong = [s for s in scored if s[1] >= MIN_BILL_COVERAGE and s[2] >= MIN_ENTRY_COVERAGE]
    cands = [Candidate(s[3], round(s[0], 3)) for s in scored[:MAX_CANDIDATES]]

    if len(strong) == 1:
        return Suggestion(
            "match",
            entry=strong[0][3],
            source="description",
            candidates=cands,
        )
    if len(strong) > 1:
        return Suggestion(
            "ambiguous",
            note=f"{len(strong)} rate-sheet entries fit this description equally well.",
            candidates=cands,
        )
    return Suggestion("none", note="No strong match in the rate sheet.", candidates=cands)
