import os

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scientific_engine import validation, validation_data as VD
from simulations import physics as P

PAGES = ["00_Home", "01_Mission_Control", "02_Planetary_Explorer", "03_Analog_Discovery_Lab", "04_Scientific_Comparison", "05_Mission_Engineering", "06_Field_Campaign_Reports", "07_AI_Research_Assistant"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _leaks(at):
    """Any rendered element that contains Streamlit internals means a bare expression was printed."""
    bad = [("help", None) for _ in at.get("help")]          # st.help panel = Streamlit magic printed a bare expression
    for kind in ("markdown", "code", "text", "json", "caption", "exception"):
        for el in at.get(kind):
            if "DeltaGenerator" in str(getattr(el, "value", "")) or "Creator of Delta" in str(getattr(el, "value", "")):
                bad.append((kind, None))
    return bad


@pytest.mark.parametrize("page", PAGES)
def test_no_code_printed_on_any_page(page):
    at = AppTest.from_file(os.path.join(ROOT, "views", page + ".py"), default_timeout=180).run()
    assert not at.exception
    assert not _leaks(at)


def test_leak_detector_catches_bare_expression(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("import streamlit as st\nerrs = []\nst.dataframe([1]) if errs else st.caption('None.')\n")
    assert _leaks(AppTest.from_file(str(f)).run())


def test_explorer_source_switch_changes_profile():
    at = AppTest.from_file(os.path.join(ROOT, "views", "02_Planetary_Explorer.py"), default_timeout=180)
    at.session_state["body"] = "Mars"; at.run()
    first = [d.value.to_dict("records") if hasattr(d.value, "to_dict") else None for d in at.dataframe]
    at.session_state["fp_source"] = "CRISM"; at.run()
    assert not at.exception and not _leaks(at)
    feats = [r["Feature"] for d in at.dataframe for r in (d.value.to_dict("records") if hasattr(d.value, "to_dict") else []) if "Feature" in r]
    assert "Lithology" in feats and "Mean slope" not in feats        # CRISM informs mineralogy, not slope


def test_closed_form_agreement_and_bounds():
    pe = validation.physics_extended()
    assert pe["closed_form"]["mean_pct"] < 5 and pe["strength_bound"]["violations"] == 0
    assert pe["convergence"][-1]["load error %"] < 0.01


def test_physics_calibration_reduces_error():
    true = P.Soil("t", 1.0, 2.0, 1000.0, 2.0, 30.0, 0.015, "t")
    base = P.SOILS["Dry sand (Wong textbook values)"]; rng = np.random.default_rng(0); rows = []
    for ld in (40, 60, 90):
        for s in (0.05, 0.1, 0.2, 0.35, 0.5):
            f = P.wheel_forces(true, ld, 0.2, 0.12, s)
            rows.append(dict(wheel_load_N=ld, slip=s, wheel_radius_m=0.2, wheel_width_m=0.12, drawbar_pull_N=float(f["DP_N"]) * (1 + rng.normal(0, .03)), sinkage_mm=float(f["sinkage_m"]) * 1000))
    df = pd.DataFrame(rows)
    before = VD.evaluate_physics(df, base)["metrics"]["drawbar_pull_N"]["MAPE_pct"]
    cal = VD.calibrate_soil(df, base)
    assert cal["ok"] and cal["after"]["drawbar_pull_N"]["MAPE_pct"] < before / 3
    assert not VD.evaluate_physics(pd.DataFrame({"a": [1]}), base)["ok"]


def test_ranking_evaluation_uses_labels():
    from data_sources.seed_catalog import CANDIDATES, TARGETS
    ev = VD.evaluate_ranking(VD.LITERATURE_PAIRS, TARGETS, CANDIDATES)
    assert ev["ok"] and 0 <= ev["auc"] <= 1 and ev["n_targets"] >= 5
    perfect = [(TARGETS[0]["id"], CANDIDATES[0]["id"], 1)]
    assert VD.evaluate_ranking(perfect, TARGETS, CANDIDATES)["ok"]
    assert not VD.parse_pairs(pd.DataFrame({"x": [1]}))[1] == ""


def test_inventory_matching():
    cands = [{"morphology": "crater", "lat": 10.0, "lon": 20.0, "diameter_m": 1000}, {"morphology": "crater", "lat": 11.0, "lon": 21.0, "diameter_m": 500}]
    inv = pd.DataFrame({"lat": [10.001, 30.0], "lon": [20.001, 40.0], "diameter_m": [1100, 800]})
    ev = VD.evaluate_inventory(cands, inv)
    assert ev["tp"] == 1 and ev["fp"] == 1 and ev["fn"] == 1 and abs(ev["diameter_bias_pct"] + 9.09) < 0.5
