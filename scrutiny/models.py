"""Plain data containers used across the toolkit (standard library only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RateEntry:
    """One line of the CGHS rate master."""

    code: str
    description: str
    rate: float
    # "indoor", "opd" or None. Inferred from the description when not given.
    setting: Optional[str] = None
    # "consultation" or "" (used to separate generic consultation charges).
    category: str = ""


@dataclass
class BillRow:
    """One charge line from the claimant's bill.

    Only charge-level data lives here. The toolkit deliberately has no field
    for claimant identity.
    """

    n: int
    description: str
    amount: float
    qty: int = 1
    printed_code: str = ""
    invoice_no: str = ""
    line_no: str = ""


@dataclass
class Candidate:
    entry: RateEntry
    score: float


@dataclass
class ResolvedRow:
    row: BillRow
    # matched | suggested | officer | awaiting | unresolved | no_code | held
    status: str
    entry: Optional[RateEntry] = None
    source: str = ""
    note: str = ""
    rate_cap: Optional[float] = None
    admissible: float = 0.0
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def needs_officer(self) -> bool:
        """True while an officer still has to confirm or decide this row."""
        return self.status in {"suggested", "unresolved", "awaiting", "no_code"}
