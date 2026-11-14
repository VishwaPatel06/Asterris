import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import charts, theme
from components.context import live_monthly, live_power, sidebar
from config import palette as P
from config.planetary_constants import COMPARISON_ROWS, PLANETS, SOURCE_NOTES
from scientific_engine import seasonal, spectral
from scientific_engine.explain import compare_conditions, physical_scorecard, processes_for

ctx = sidebar("comparison")
theme.header("Scientific Comparison", "What an Earth analogue reproduces, where the comparison breaks down, and how Earth, the Moon and Mars differ.", "Workspace 04", "comparison")
t, rows = ctx["target"], ctx["rows"]
tab_c, tab_p, tab_s = st.tabs(["Candidate vs target", "Earth, Moon and Mars", "Spectra and seasons"])

with tab_c:
    names = {r["id"]: r["name"].split(" (")[0] for r in rows}
    cid = st.selectbox("Earth candidate", list(names), format_func=names.get)
    r = next(x for x in rows if x["id"] == cid); c = ctx["cands"][cid]
    m = st.columns(3)
    m[0].metric("Analogue fidelity", "n/a" if r["fidelity"] is None else f"{r['fidelity']:.2f}", "How closely it resembles the target")
    m[1].metric("Mission suitability", "n/a" if r["suitability"] is None else f"{r['suitability']:.2f}", r["suitability_basis"])
    m[2].metric("Transferability (heuristic)", "n/a" if r["transferability"] is None else f"{r['transferability']:.2f}", "Penalised by physical mismatch")
    theme.note("The three scores answer different questions and are never merged. Transferability is a transparent heuristic: fidelity reduced by the Earth/target gravity, pressure and radiation mismatches weighted by the objective.")
    a, b = st.columns(2)
    with a:
        st.plotly_chart(charts.dumbbell([r], t["name"].split(" (")[0] + " (reference)"), width="stretch")
    with b:
        st.markdown("**Where it works and where it breaks down**")
        cond = pd.DataFrame(compare_conditions(t, c)).astype(str)
        st.dataframe(cond, hide_index=True, width="stretch")
    st.markdown("**Physical differences Earth cannot remove**")
    sc = pd.DataFrame(physical_scorecard(t["body"])).astype(str)
    st.dataframe(sc, hide_index=True, width="stretch")
    st.markdown("**Geological process comparison**")
    pr = processes_for(c)
    if pr:
        st.dataframe(pd.DataFrame(pr), hide_index=True, width="stretch")
    else:
        st.caption("No process tags recorded for this site.")
    if len(rows) >= 2:
        st.markdown("**Terrain cross-sections (normalised)**")
        from scientific_engine import dem
        ser = {}
        for lab, rec in ((t["name"].split(" (")[0] + " (target)", t), (names[cid], c)):
            h, cell = dem.synthetic_dem(rec["morphology"], 96, 2000.0, max(rec["relief_m"] or 100, 50), rec["roughness"] or 0.3)
            d, z, _ = dem.transect(h, cell, (0.05, 0.5), (0.95, 0.5)); ser[lab] = (d, dem.normalised_profile(z))
        st.plotly_chart(charts.profiles(ser, "Schematic cross-sections by morphology class"), width="stretch")
        st.caption("Schematic shapes generated from each site's morphology class, not surveyed profiles. Use uploaded DEMs for real cross-sections.")

with tab_p:
    st.markdown("#### Earth versus Moon versus Mars")
    tab = pd.DataFrame([{"Quantity": lab, "Unit": unit, **{b: fmt.format(PLANETS[b][k]) for b in ("Earth", "Moon", "Mars")}} for lab, k, unit, fmt in COMPARISON_ROWS])
    st.dataframe(tab, hide_index=True, width="stretch")
    view = st.radio("Compare", ["Earth vs Moon", "Earth vs Mars", "Moon vs Mars", "All three"], horizontal=True, index=3)
    pair = {"Earth vs Moon": ("Earth", "Moon"), "Earth vs Mars": ("Earth", "Mars"), "Moon vs Mars": ("Moon", "Mars"), "All three": ("Earth", "Moon", "Mars")}[view]
    ref = pair[0]
    metrics = [("Gravity", "gravity", "m/s2"), ("Pressure", "pressure_kpa", "kPa"), ("Radiation", "radiation_msv_day", "mSv/day"), ("Solar flux", "solar_flux_wm2", "W/m2"),
               ("Escape velocity", "escape_kms", "km/s"), ("Radius", "radius_km", "km")]
    ratio = pd.DataFrame([{"Quantity": lab, **{b: PLANETS[b][k] / PLANETS[ref][k] for b in pair}} for lab, k, _ in metrics])
    fig = go.Figure()
    for b in pair:
        fig.add_trace(go.Bar(y=ratio["Quantity"], x=ratio[b], orientation="h", name=b, marker_color=P.BODY_COLOR[b], text=[f"{v:.3g}x" for v in ratio[b]], textposition="outside"))
    fig.update_layout(barmode="group", title=f"Values relative to {ref} (log scale; 1 = same as {ref})", xaxis=dict(type="log", title=f"ratio to {ref}"), yaxis=dict(autorange="reversed"))
    st.plotly_chart(charts.base(fig, 460), width="stretch")
    tfig = go.Figure()
    for b in pair:
        p = PLANETS[b]
        tfig.add_trace(go.Bar(x=[b], y=[p["temp_max_c"] - p["temp_min_c"]], base=[p["temp_min_c"]], name=b, marker_color=P.BODY_COLOR[b], text=[f"{p['temp_min_c']:.0f} to {p['temp_max_c']:.0f} C"], textposition="inside"))
        tfig.add_trace(go.Scatter(x=[b], y=[p["temp_mean_c"]], mode="markers", marker=dict(color=P.STARLIGHT, size=10, symbol="diamond"), showlegend=False, hovertemplate="mean %{y} C<extra></extra>"))
    tfig.update_layout(title="Surface temperature extremes (bar) and mean (diamond), deg C", yaxis_title="deg C", showlegend=False)
    st.plotly_chart(charts.base(tfig, 380), width="stretch")
    g = st.columns(3)
    tb = t["body"]
    g[0].metric(f"Gravity: {tb} / Earth", f"{PLANETS[tb]['gravity'] / PLANETS['Earth']['gravity']:.2f}")
    g[1].metric(f"Pressure: {tb} / Earth", f"{PLANETS[tb]['pressure_kpa'] / PLANETS['Earth']['pressure_kpa']:.2g}")
    g[2].metric(f"Radiation: {tb} / Earth", f"{PLANETS[tb]['radiation_msv_day'] / PLANETS['Earth']['radiation_msv_day']:.0f}x")
    with st.expander("Sources and caveats"):
        for k, v in SOURCE_NOTES.items():
            st.markdown(f"- **{k}**: {v}")
        st.caption("Representative values; local and temporal variation applies. These are reference constants, not live measurements.")

with tab_s:
    st.markdown("#### Spectral reflectance matcher")
    theme.note("Reference curves are SCHEMATIC Gaussian absorption models at commonly cited band centres, not the USGS spectral library. Register real library spectra via spectral.register_spectrum. "
               "Grain size, mixtures, illumination, atmosphere and calibration all change real spectra.")
    mins = spectral.minerals()
    s1, s2 = st.columns(2)
    ma = s1.selectbox("Target mineral", mins, index=mins.index("olivine")); mb = s2.selectbox("Earth site mineral", mins, index=mins.index("pyroxene"))
    fig = go.Figure()
    for nm, col in ((ma, P.COSMIC_CYAN), (mb, P.VOLCANIC[3])):
        fig.add_trace(go.Scatter(x=spectral.WAVELENGTHS, y=spectral.spectrum(nm), name=nm, line=dict(color=col, width=3)))
        for cen, depth in spectral.absorption_bands(spectral.spectrum(nm)):
            fig.add_vline(x=cen, line=dict(color=col, width=1, dash="dot"), opacity=.4)
    fig.update_layout(title="Reflectance 400-2500 nm (dotted: absorption bands)", xaxis_title="wavelength (nm)", yaxis_title="reflectance")
    st.plotly_chart(charts.base(fig, 380), width="stretch")
    mt = spectral.match(ma, mb)
    st.metric("Spectral-angle similarity (continuum removed)", f"{mt['similarity']:.2f}", f"angle {mt['angle_rad']:.2f} rad")

    st.markdown("#### Seasonal deployment calendar")
    names = {r["id"]: r["name"].split(" (")[0] for r in rows}
    cid2 = st.selectbox("Site", list(names), format_func=names.get, key="seas_c"); c = ctx["cands"][cid2]
    src_lab, monthly = "", pd.DataFrame()
    live = live_power(c["lat"], c["lon"])
    if live.get("ok"):
        monthly, src_lab = live["monthly"], live["source"] + ", fetched live"
    else:
        lm = live_monthly(c["lat"], c["lon"])
        if lm.get("ok") and "monthly" in lm:
            monthly, src_lab = lm["monthly"], "Open-Meteo archive, fetched live"
    if monthly.empty:
        monthly = seasonal.estimate_monthly(c); src_lab = "Sinusoidal ESTIMATE from catalogue statistics (live archives unreachable)" if not monthly.empty else ""
    if monthly.empty:
        st.info("No temperature data for this site and live archives are unreachable. Nothing is estimated.")
    else:
        w = seasonal.suitability_window(monthly)
        st.caption(f"Source: {src_lab}. Historical climatology, not a forecast.")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=w["month_name"], y=w["suitability"], name="Suitability (0-1)", marker_color=[P.GOOD if v >= .66 else P.MODERATE if v >= .4 else P.LOW for v in w["suitability"]], yaxis="y2", opacity=.55))
        fig.add_trace(go.Scatter(x=w["month_name"], y=w["temp_mean_c"], name="Mean temp (C)", line=dict(color=P.VOLCANIC[3], width=3)))
        if "temp_max_c" in w:
            fig.add_trace(go.Scatter(x=w["month_name"], y=w["temp_max_c"], name="Max", line=dict(color=P.VOLCANIC[1], dash="dot")))
            fig.add_trace(go.Scatter(x=w["month_name"], y=w["temp_min_c"], name="Min", line=dict(color=P.WATER[3], dash="dot")))
        if w["precip_mm"].notna().any():
            fig.add_trace(go.Bar(x=w["month_name"], y=w["precip_mm"], name="Precipitation (mm)", marker_color=P.WATER[2], opacity=.35))
        fig.update_layout(title="Monthly conditions and field-test suitability", yaxis=dict(title="deg C / mm"), yaxis2=dict(overlaying="y", side="right", range=[0, 1], title="suitability"))
        st.plotly_chart(charts.base(fig, 400), width="stretch")
        best = w.sort_values("suitability", ascending=False).head(3)
        st.write("Best historical windows: " + ", ".join(f"{r.month_name} ({r.suitability:.2f})" for r in best.itertuples()) + ". Comfort band -10 to 30 C is an assumption; interannual variability is not included.")
