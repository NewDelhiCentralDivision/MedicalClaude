"""Export the scrutiny result as CSV and as a printable HTML sheet."""
from __future__ import annotations

import csv
import io
from html import escape
from typing import Optional

from .models import ResolvedRow
from .review import MODE_LABELS, SETTING_LABELS, STATUS_LABELS, summarize

CSV_COLUMNS = [
    "row", "description", "qty", "billed", "rate_code", "rate_description",
    "rate_cap", "admissible", "status", "match_source", "note",
]


def _line(r: ResolvedRow) -> list:
    return [
        r.row.n,
        r.row.description,
        r.row.qty,
        f"{r.row.amount:.2f}",
        r.entry.code if r.entry else "",
        r.entry.description if r.entry else "",
        f"{r.rate_cap:.2f}" if r.rate_cap is not None else "",
        f"{r.admissible:.2f}",
        STATUS_LABELS.get(r.status, r.status),
        r.source,
        r.note,
    ]


def to_csv(resolved: list[ResolvedRow]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for r in resolved:
        writer.writerow(_line(r))
    return buf.getvalue()


def _inr(value: float) -> str:
    return f"₹{value:,.2f}"


def to_html(resolved: list[ResolvedRow], mode: str, setting: Optional[str] = None) -> str:
    """A self-contained, print-friendly scrutiny sheet. Every value is escaped."""
    s = summarize(resolved)
    rows_html = []
    for r in resolved:
        cells = _line(r)
        rows_html.append(
            "<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in cells) + "</tr>"
        )
    head = "".join(f"<th>{escape(c.replace('_', ' '))}</th>" for c in CSV_COLUMNS)
    setting_line = (
        f"<p>Treatment setting: {escape(SETTING_LABELS.get(setting or '', 'not set'))}</p>"
        if mode == "nocode" else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>CGHS rate scrutiny</title>
<style>
body{{font-family:system-ui,sans-serif;color:#2a2d3a;margin:32px;background:#fff}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border:1px solid #d9d4ec;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#efeafc;text-transform:capitalize}}
.note{{background:#e6e0fa;padding:10px 14px;border-radius:8px;margin-top:16px}}
</style></head><body>
<h1>CGHS rate scrutiny</h1>
<p>Matching mode: {escape(MODE_LABELS[mode])}</p>
{setting_line}
<p>Billed total: {_inr(s['billed_total'])} &middot; Admissible so far: {_inr(s['admissible_total'])}
&middot; Needs officer: {s['needs_officer']}</p>
<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows_html)}</tbody></table>
<p class="note">Inferred matches are suggestions. An officer must confirm them and resolve every
unmatched charge before sanction.</p>
</body></html>
"""
