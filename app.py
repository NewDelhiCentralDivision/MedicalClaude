"""Streamlit interface for the medical claim scrutiny toolkit.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

from scrutiny import (
    MODE_CODE, MODE_LABELS, MODE_MANUAL, MODE_NOCODE, SETTING_LABELS,
    STATUS_LABELS, BillRow, RateSheetError, load_rates, resolve, summarize,
)
from scrutiny.export import to_csv, to_html
from scrutiny.rates import parse_amount

SAMPLE_RATES = Path(__file__).parent / "data" / "sample_rates.csv"
BILL_COLUMNS = ["Charge description", "Amount", "Qty", "Printed code", "Invoice no", "Line no"]

# Charge descriptions and amounts only. No claimant details are stored anywhere.
DEMO_BILL = [
    ("Consultant", 500), ("Medicine", 3000), ("Injection IM/IV", 1280),
    ("IV Fluid", 2010), ("Emergency Management", 1000), ("B.P. Checkup", 100),
    ("Bed/3", 1310),
]

st.set_page_config(page_title="Medical claim scrutiny", page_icon="\U0001FA7A", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1120px; padding-top: 2rem;}
    h1, h2, h3 {letter-spacing: -0.01em;}
    /* Large, easy-to-click radio options (descendant selectors survive wrapper changes) */
    [data-testid="stRadio"] [role="radiogroup"] {gap: 0.75rem;}
    [data-testid="stRadio"] label {
        min-height: 3.5rem; padding: 0.75rem 1.25rem; border-radius: 14px;
        border: 2px solid #e4e0f0; background: #fcfbff; cursor: pointer;
        align-items: center; width: 100%;
    }
    [data-testid="stRadio"] label:hover {background: #f3effd;}
    [data-testid="stRadio"] label:has(input:checked) {background: #efeafc; border-color: #5b4bb7;}
    [data-testid="stRadio"] label p {font-size: 1.15rem !important; font-weight: 600;}
    [data-testid="stRadio"] label > div:first-child {transform: scale(1.5); margin-right: 0.9rem;}
    div[data-testid="stMetric"] {background: #fcfbff; border: 1px solid #e4e0f0;
        border-radius: 14px; padding: 0.9rem 1.1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def inr(value: float) -> str:
    """Rupees with Indian digit grouping, e.g. \u20b91,23,456.00."""
    whole, frac = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        whole = head + "," + tail
    return ("-" if value < 0 else "") + "\u20b9" + whole + "." + frac


def section(num: str, title: str, hint: str = "") -> None:
    st.markdown(f"### {num} — {title}")
    if hint:
        st.caption(hint)


def empty_bill() -> pd.DataFrame:
    return pd.DataFrame(
        {"Charge description": pd.Series(dtype="str"), "Amount": pd.Series(dtype="float"),
         "Qty": pd.Series(dtype="int"), "Printed code": pd.Series(dtype="str"),
         "Invoice no": pd.Series(dtype="str"), "Line no": pd.Series(dtype="str")}
    )


def rows_from_df(df: pd.DataFrame) -> list[BillRow]:
    rows: list[BillRow] = []
    for i, rec in enumerate(df.to_dict("records"), start=1):
        desc = str(rec.get("Charge description") or "").strip()
        if not desc:
            continue
        try:
            amount = parse_amount(rec.get("Amount"))
        except ValueError:
            continue
        qty = rec.get("Qty")
        qty = int(qty) if pd.notna(qty) and int(qty) > 0 else 1
        rows.append(BillRow(
            n=i, description=desc, amount=amount, qty=qty,
            printed_code=str(rec.get("Printed code") or "").strip(),
            invoice_no=str(rec.get("Invoice no") or "").strip(),
            line_no=str(rec.get("Line no") or "").strip(),
        ))
    return rows


st.title("Medical claim scrutiny")
st.caption(
    "Check a medical reimbursement bill against the CGHS rate sheet. The rate is a cap: "
    "the admissible amount is the lower of the billed amount and the CGHS rate."
)

# ---------------------------------------------------------------- 01 rate sheet
section("01", "Rate sheet", "Upload the official CGHS rate master (CSV with code, description, rate).")
uploaded = st.file_uploader("Rate sheet CSV", type=["csv"], label_visibility="collapsed")
rates, using_sample = None, False
try:
    if uploaded is not None:
        rates = load_rates(uploaded.getvalue())
    else:
        rates = load_rates(SAMPLE_RATES)
        using_sample = True
except RateSheetError as exc:
    st.error(str(exc))
if using_sample:
    st.warning(
        "Using the bundled SAMPLE rate sheet. Its rates are placeholders for testing only. "
        "Upload the official CGHS rate master before reviewing a real claim."
    )
if rates is None:
    st.stop()
st.caption(f"{len(rates)} rate-sheet entries loaded.")

# ---------------------------------------------------------------- 02 bill rows
section("02", "Bill rows", "Enter or paste the charge lines. Printed code, invoice and line numbers are optional.")
if "bill_base" not in st.session_state:
    st.session_state["bill_base"] = empty_bill()
c1, c2, _ = st.columns([1, 1, 3])
if c1.button("Load demo rows", width="stretch"):
    st.session_state["bill_base"] = pd.DataFrame(
        [{"Charge description": d, "Amount": float(a), "Qty": 1, "Printed code": "",
          "Invoice no": "", "Line no": ""} for d, a in DEMO_BILL]
    )
    st.session_state.pop("bill_editor", None)
    st.rerun()
bill_upload = c2.file_uploader("Import bill CSV", type=["csv"], label_visibility="collapsed", key="bill_csv")
if bill_upload is not None and st.session_state.get("_bill_csv_name") != bill_upload.name:
    try:
        imp = pd.read_csv(bill_upload)
        for col in BILL_COLUMNS:
            if col not in imp.columns:
                imp[col] = "" if col not in ("Amount", "Qty") else (0 if col == "Amount" else 1)
        st.session_state["bill_base"] = imp[BILL_COLUMNS]
        st.session_state["_bill_csv_name"] = bill_upload.name
        st.session_state.pop("bill_editor", None)
        st.rerun()
    except Exception as exc:  # unreadable CSV: show a plain message
        st.error(f"Could not read that CSV: {exc}")

bill_df = st.data_editor(
    st.session_state["bill_base"], num_rows="dynamic", width="stretch", key="bill_editor",
    column_config={
        "Amount": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
        "Qty": st.column_config.NumberColumn(min_value=1, step=1, default=1),
    },
)
rows = rows_from_df(bill_df)
if not rows:
    st.info("Add at least one bill row to continue.")
    st.stop()

# ---------------------------------------------------------------- 03 scrutinize
section("03", "Scrutinize CGHS rates",
       "Switching the mode re-scrutinizes every row immediately. No re-upload needed.")
has_printed_codes = any(r.printed_code for r in rows)
if "mode" not in st.session_state:
    # Bills with no printed codes would pay \u20b90 in Code Based mode, so start in No Code mode.
    st.session_state["mode"] = MODE_LABELS[MODE_CODE if has_printed_codes else MODE_NOCODE]
mode_label = st.radio(
    "Matching mode", [MODE_LABELS[MODE_CODE], MODE_LABELS[MODE_MANUAL], MODE_LABELS[MODE_NOCODE]],
    key="mode", label_visibility="collapsed",
)
mode = {v: k for k, v in MODE_LABELS.items()}[mode_label]

setting = None
if mode == MODE_NOCODE:
    st.markdown("**Treatment setting** (as documented in the claim)")
    setting_label = st.radio(
        "Treatment setting", [SETTING_LABELS["indoor"], SETTING_LABELS["opd"]],
        key="setting", horizontal=True, label_visibility="collapsed",
    )
    setting = {v: k for k, v in SETTING_LABELS.items()}[setting_label]

if mode == MODE_CODE and not has_printed_codes:
    st.warning(
        "None of these rows has a printed code, so Code Based mode pays \u20b90. "
        "Switch to Manual or Diagnosis/Description Based \u2013 No Code Available."
    )

# Officer overrides live in their own small editor, keyed by row number.
code_options = [""] + [e.code for e in rates]
overrides_state = st.session_state.get("officer_choices", {})
resolved = resolve(rows, rates, mode, setting, overrides_state)
summary = summarize(resolved)

m1, m2, m3 = st.columns(3)
m1.metric("Billed total", f"₹{summary['billed_total']:,.2f}")
m2.metric("Admissible so far", f"₹{summary['admissible_total']:,.2f}")
if mode == MODE_NOCODE:
    m3.metric("Needs officer", f"{summary['suggestions']} suggested · {summary['unresolved']} unresolved")
else:
    m3.metric("Needs officer", f"{summary['needs_officer']} rows")

table = pd.DataFrame([
    {
        "#": r.row.n,
        "Charge": r.row.description,
        "Billed": inr(r.row.amount),
        "CGHS match": f"{r.entry.code} · {r.entry.description}" if r.entry else "—",
        "Match source": r.source or r.note,
        "Rate cap": inr(r.rate_cap) if r.rate_cap is not None else "\u2014",
        "Admissible": inr(r.admissible),
        "Status": STATUS_LABELS.get(r.status, r.status),
    }
    for r in resolved
])
st.dataframe(
    table, width="stretch", hide_index=True,
    column_config={
        "Billed": st.column_config.TextColumn(width="small"),
        "Rate cap": st.column_config.TextColumn(width="small"),
        "Admissible": st.column_config.TextColumn(width="small"),
        "CGHS match": st.column_config.TextColumn(width="large"),
    },
)

with st.expander("Officer: confirm, change or set a match", expanded=(mode == MODE_MANUAL)):
    st.caption("Choose a rate-sheet code for any row. An officer choice always overrides the automatic match.")
    base = pd.DataFrame({
        "#": [r.row.n for r in resolved],
        "Charge": [r.row.description for r in resolved],
        "Officer choice": [overrides_state.get(r.row.n, "") for r in resolved],
    })
    edited = st.data_editor(
        base, hide_index=True, width="stretch", key="officer_editor",
        disabled=["#", "Charge"],
        column_config={"Officer choice": st.column_config.SelectboxColumn(options=code_options)},
    )
    new_choices = {int(n): c for n, c in zip(edited["#"], edited["Officer choice"]) if c}
    if new_choices != overrides_state:
        st.session_state["officer_choices"] = new_choices
        st.rerun()

for r in resolved:
    if r.status == "unresolved" and r.candidates:
        names = ", ".join(f"{c.entry.code} ({c.entry.description})" for c in r.candidates)
        st.caption(f"Row {r.row.n} — {r.row.description}: {r.note} Closest entries: {names}")

st.info(
    "Officer review comes first. Inferred matches are suggestions only; confirm each one and "
    "resolve every unmatched charge before sanction."
)

# ---------------------------------------------------------------- 04 export
section("04", "Export")
d1, d2 = st.columns(2)
d1.download_button("Download CSV", to_csv(resolved), "scrutiny.csv", "text/csv", width="stretch")
d2.download_button("Download printable sheet (HTML)", to_html(resolved, mode, setting),
                   "scrutiny.html", "text/html", width="stretch")
