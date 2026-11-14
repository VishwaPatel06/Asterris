"""Shared sidebar + analysis context used by every page (target, objective, editable weights, candidate pool)."""
from __future__ import annotations

import streamlit as st

from components.theme import apply_theme
from config.mission_presets import DIMENSION_LABELS, DIMENSIONS, PRESETS
from data_sources import catalog, live_earth
from scientific_engine.similarity import normalise_weights, rank_candidates


def _apply_preset() -> None:
    for d in DIMENSIONS:
        st.session_state[f"w_{d}"] = int(round(PRESETS[st.session_state["objective"]][d] * 100))


def _reset_target() -> None:
    st.session_state["target_id"] = catalog.targets_for(st.session_state["body"])[0]["id"]


def _persist(keys) -> None:
    for k in keys:   # widgets not rendered on the current page would lose state; re-assigning keeps it
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]


def init_state() -> None:
    st.session_state.setdefault("body", "Moon")
    st.session_state.setdefault("objective", "Polar Ice Drilling")
    st.session_state.setdefault("target_id", catalog.targets_for(st.session_state["body"])[0]["id"])
    st.session_state.setdefault("discovered", [])
    if "w_geology" not in st.session_state:
        _apply_preset()
    _persist(["body", "objective", "target_id", "discovered"] + [f"w_{d}" for d in DIMENSIONS])


def current_weights() -> dict:
    return {d: st.session_state[f"w_{d}"] / 100.0 for d in DIMENSIONS}


def sidebar(accent: str = "overview", selectors: bool = True) -> dict:
    """Render the global selectors and return the analysis context."""
    apply_theme(accent)
    init_state()
    cat = catalog.load_catalog()
    if not selectors:   # page renders its own world/target/objective controls (avoids duplicate widget keys)
        opts0 = [t for t in cat["targets"] if t["body"] == st.session_state["body"]]
        if st.session_state["target_id"] not in [t["id"] for t in opts0]:
            st.session_state["target_id"] = opts0[0]["id"]
    with st.sidebar:
        st.markdown("#### Mission setup")
        if not selectors:
            st.caption("World, region, objective and weights are set on this page.")
    if selectors:
      with st.sidebar:
        st.radio("Target world", ["Moon", "Mars"], key="body", horizontal=True, on_change=_reset_target)
        opts = [t for t in cat["targets"] if t["body"] == st.session_state["body"]]
        ids = [t["id"] for t in opts]
        if st.session_state["target_id"] not in ids:
            st.session_state["target_id"] = ids[0]
        st.selectbox("Target region", ids, key="target_id", format_func=lambda i: next(t["name"] for t in opts if t["id"] == i))
        st.selectbox("Mission objective", list(PRESETS), key="objective", on_change=_apply_preset)
        w = normalise_weights(current_weights())
        st.caption("Weights: " + ", ".join(f"{DIMENSION_LABELS[d]} {v:.0%}" for d, v in w.items() if v > 0))
        if st.session_state["discovered"]:
            st.caption(f"{len(st.session_state['discovered'])} discovered candidate(s) included in rankings.")
    target = next(t for t in cat["targets"] if t["id"] == st.session_state["target_id"])
    objective = st.session_state["objective"]
    weights = current_weights()
    pool = cat["candidates"] + list(st.session_state["discovered"])
    rows = rank_candidates(target, pool, weights, objective)
    return {"target": target, "objective": objective, "weights": weights, "rows": rows, "cands": {c["id"]: c for c in pool}, "cand_list": pool,
            "catalog": cat, "body": st.session_state["body"]}


@st.cache_data(ttl=600, show_spinner=False)
def live_current(lat: float, lon: float) -> dict:
    return live_earth.open_meteo_current(lat, lon)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def live_monthly(lat: float, lon: float) -> dict:
    return live_earth.open_meteo_monthly(lat, lon)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def live_power(lat: float, lon: float) -> dict:
    return live_earth.nasa_power_climatology(lat, lon)


@st.cache_data(ttl=300, show_spinner=False)
def live_quakes(lat: float, lon: float, radius_km: float) -> dict:
    return live_earth.usgs_quakes_near(lat, lon, radius_km)
