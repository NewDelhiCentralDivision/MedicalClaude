"""Smoke test of the Streamlit screen using Streamlit's AppTest runner."""
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CODE = "Automatic – Code Based"
NOCODE = "Diagnosis/Description Based – No Code Available"


def _seeded_app(printed_code=""):
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["bill_base"] = pd.DataFrame(
        [{"Charge description": d, "Amount": float(a), "Qty": 1, "Printed code": printed_code if d == "Consultant" else "",
          "Invoice no": "", "Line no": ""}
         for d, a in [("Consultant", 500), ("Medicine", 3000), ("Bed/3", 1310)]]
    )
    return at


def _metrics(at):
    return {m.label: m.value for m in at.metric}


def test_bill_without_codes_starts_in_no_code_mode():
    at = _seeded_app().run()
    assert not at.exception
    assert at.radio(key="mode").value == NOCODE
    assert _metrics(at)["Admissible so far"] == "₹350.00"
    assert _metrics(at)["Needs officer"] == "1 suggested · 2 unresolved"


def test_code_mode_warns_when_no_row_has_a_code():
    at = _seeded_app().run()
    at.radio(key="mode").set_value(CODE).run()
    assert not at.exception
    assert _metrics(at)["Admissible so far"] == "₹0.00"
    assert any("printed code" in w.value for w in at.warning)


def test_bill_with_printed_codes_starts_in_code_mode():
    at = _seeded_app(printed_code="CN002").run()
    assert at.radio(key="mode").value == CODE
    assert _metrics(at)["Admissible so far"] == "₹350.00"


def test_indian_rupee_grouping():
    # inr() lives in app.py, which runs Streamlit code; check it through a rendered page instead.
    at = _seeded_app().run()
    assert _metrics(at)["Billed total"] == "₹4,810.00"
