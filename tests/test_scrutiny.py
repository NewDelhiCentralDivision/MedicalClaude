"""Regression checks. Bill data here is charge descriptions and amounts only."""
from pathlib import Path

import pytest

from scrutiny import (
    MODE_CODE, MODE_LABELS, MODE_MANUAL, MODE_NOCODE, BillRow, RateSheetError,
    apply_cap, load_rates, resolve, summarize,
)
from scrutiny.export import to_csv, to_html
from scrutiny.matcher import suggest

ROOT = Path(__file__).resolve().parents[1]
RATES = load_rates(ROOT / "data" / "sample_rates.csv")

BILL = [
    ("Consultant", 500), ("Medicine", 3000), ("Injection IM/IV", 1280),
    ("IV Fluid", 2010), ("Emergency Management", 1000), ("B.P. Checkup", 100),
    ("Bed/3", 1310),
]


def bill(items=BILL, **kw):
    return [BillRow(n=i, description=d, amount=a, **kw) for i, (d, a) in enumerate(items, 1)]


def by_n(resolved):
    return {r.row.n: r for r in resolved}


def test_mode_labels_are_exact():
    assert list(MODE_LABELS.values()) == [
        "Automatic – Code Based",
        "Manual",
        "Diagnosis/Description Based – No Code Available",
    ]


def test_rate_is_a_cap_not_a_floor():
    assert apply_cap(500, 1, 350) == 350
    assert apply_cap(200, 1, 350) == 200
    assert apply_cap(500, 2, 350) == 500  # quantity raises the cap


def test_code_mode_pays_nothing_for_rows_without_codes():
    res = resolve(bill(), RATES, MODE_CODE)
    assert all(r.status == "no_code" and r.admissible == 0 for r in res)


def test_code_mode_uses_printed_code_and_caps():
    rows = [BillRow(1, "Consultant", 500, printed_code=" cn 002 ")]
    r = resolve(rows, RATES, MODE_CODE)[0]
    assert (r.status, r.entry.code, r.admissible) == ("matched", "CN002", 350)


def test_unknown_printed_code_is_unresolved_not_guessed():
    r = resolve([BillRow(1, "Consultant", 500, printed_code="ZZ999")], RATES, MODE_CODE)[0]
    assert r.status == "unresolved" and r.admissible == 0


def test_manual_mode_waits_for_officer():
    res = resolve(bill(), RATES, MODE_MANUAL)
    assert all(r.status == "awaiting" and r.admissible == 0 for r in res)
    chosen = resolve(bill(), RATES, MODE_MANUAL, overrides={1: "CN002"})
    assert by_n(chosen)[1].status == "officer" and by_n(chosen)[1].admissible == 350


def test_no_code_indoor_bill_scenario():
    res = resolve(bill(), RATES, MODE_NOCODE, setting="indoor")
    rows = by_n(res)
    assert rows[1].status == "suggested"
    assert rows[1].entry.code == "CN002"
    assert rows[1].admissible == 350  # 500 billed capped at 350
    assert all(rows[n].status == "unresolved" and rows[n].admissible == 0 for n in range(2, 8))
    s = summarize(res)
    assert s["billed_total"] == 9200
    assert (s["suggestions"], s["unresolved"]) == (1, 6)


def test_opd_setting_picks_the_opd_consultation_entry():
    r = resolve(bill(), RATES, MODE_NOCODE, setting="opd")[0]
    assert r.entry.code == "CN001" and r.admissible == 150


def test_consultation_needs_a_setting():
    r = resolve(bill(), RATES, MODE_NOCODE, setting=None)[0]
    assert r.status == "unresolved" and "Indoor" in r.note


def test_switching_modes_reuses_existing_rows():
    rows = bill()
    first = resolve(rows, RATES, MODE_CODE)
    second = resolve(rows, RATES, MODE_NOCODE, setting="indoor")
    assert sum(r.admissible for r in first) == 0
    assert sum(r.admissible for r in second) == 350


@pytest.mark.parametrize("desc", ["Medicine", "Injection IM/IV", "IV Fluid",
                                  "Emergency Management", "B.P. Checkup", "Bed/3"])
def test_generic_charges_never_get_a_suggestion(desc):
    assert suggest(desc, "indoor", RATES).kind == "generic"


def test_ambiguous_description_is_left_for_the_officer():
    r = resolve([BillRow(1, "X-Ray Chest", 300)], RATES, MODE_NOCODE, "indoor")[0]
    assert r.status == "unresolved" and len(r.candidates) >= 2 and r.admissible == 0


def test_unique_strong_description_is_suggested():
    r = resolve([BillRow(1, "X-Ray Chest PA", 300)], RATES, MODE_NOCODE, "indoor")[0]
    assert (r.status, r.entry.code, r.admissible) == ("suggested", "RD001", 150)
    assert r.source == "description"


def test_printed_code_still_wins_in_no_code_mode():
    r = resolve([BillRow(1, "Chest film", 300, printed_code="RD002")], RATES, MODE_NOCODE, "indoor")[0]
    assert (r.status, r.entry.code) == ("matched", "RD002")


def test_officer_choice_beats_automatic_match():
    r = resolve(bill(), RATES, MODE_NOCODE, "indoor", overrides={1: "CN001", 2: "LB001"})
    rows = by_n(r)
    assert rows[1].entry.code == "CN001" and rows[1].status == "officer"
    assert rows[2].entry.code == "LB001" and rows[2].admissible == 200


def test_repeated_consultations_are_legitimate():
    rows = [BillRow(1, "Consultant", 500), BillRow(2, "Consultant", 500)]
    res = resolve(rows, RATES, MODE_NOCODE, "indoor")
    assert [r.status for r in res] == ["suggested", "suggested"]


def test_repeated_copy_of_the_same_numbered_line_is_held_back():
    rows = [
        BillRow(1, "Consultant", 500, invoice_no="INV-7", line_no="1"),
        BillRow(2, "Consultant", 500, invoice_no="INV-7", line_no="1"),
        BillRow(3, "Consultant", 500, invoice_no="INV-7", line_no="2"),
    ]
    res = resolve(rows, RATES, MODE_NOCODE, "indoor")
    assert [r.status for r in res] == ["suggested", "held", "suggested"]
    assert res[1].admissible == 0


def test_rate_loader_checks_columns_and_amounts(tmp_path):
    with pytest.raises(RateSheetError):
        load_rates(b"code,description\nA1,Thing\n")
    with pytest.raises(RateSheetError):
        load_rates(b"code,description,rate\nA1,Thing,abc\n")
    with pytest.raises(RateSheetError):
        load_rates(b"code,description,rate\nA1,Thing,10\nA1,Other,20\n")


def test_rate_loader_reads_quoted_rupee_amounts():
    entries = load_rates('code,description,rate\nA1,Thing,"₹1,280.50"\n'.encode())
    assert entries[0].rate == 1280.50


def test_exports_are_escaped_and_complete():
    rows = [BillRow(1, "<script>alert(1)</script>", 100)]
    res = resolve(rows, RATES, MODE_CODE)
    assert "<script>" not in to_html(res, MODE_CODE)
    assert to_csv(res).splitlines()[0].startswith("row,description")
