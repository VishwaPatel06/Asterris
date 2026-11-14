import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import charts, theme
from components.context import sidebar
from config import palette as P
from config import scoring_config as cfg
from config.mission_presets import DIMENSION_LABELS, DIMENSIONS
from config.planetary_constants import PLANETS
from optimization import campaign as camp
from reports import generators as gen
from scientific_engine.explain import EXPERIMENTS, explain
from simulations import physics

ctx = sidebar("campaign")
theme.header("Field Campaign and Reports", "Turn the analysis into a proposed campaign: sites, measurements, engineering compensation, limitations and exports.", "Workspace 06", "campaign")
t, rows, cands, obj, W = ctx["target"], ctx["rows"], ctx["cands"], ctx["objective"], ctx["weights"]
theme.note(gen.TITLE + ". Generated from the current analysis settings.")

a, b = st.columns([1, 2])
with a:
    k = st.slider("Number of sites", 1, min(5, len(rows)), min(3, len(rows)))
    mass = st.number_input("Rover mass for offload estimate (kg)", 20.0, 1000.0, 150.0, 10.0)
    chosen = camp.select_campaign(rows, cands, W, k)
    ids = [c["id"] for c in chosen]
    st.metric("Route between sites", f"{camp.route_length_km(ids, cands):,.0f} km", "straight-line, in selection order")
with b:
    cov = camp.campaign_coverage(chosen, rows)
    fig = go.Figure(go.Bar(y=[DIMENSION_LABELS[d] for d in DIMENSIONS], x=[cov[d] or 0 for d in DIMENSIONS], orientation="h", marker_color=[P.UNAVAILABLE if cov[d] is None else charts.sim_color(cov[d]) for d in DIMENSIONS],
                           text=["no data" if cov[d] is None else f"{cov[d]:.2f}" for d in DIMENSIONS], textposition="outside"))
    fig.update_layout(title="Best dimension similarity reached by the campaign", xaxis=dict(range=[0, 1.15]), yaxis=dict(autorange="reversed"))
    st.plotly_chart(charts.base(fig, 330, False), width="stretch")
tb = pd.DataFrame([{"Order": c["order"], "Site": c["name"].split(" (")[0], "Coordinates": f"{cands[c['id']]['lat']:.3f}, {cands[c['id']]['lon']:.3f}", "Adds coverage of": ", ".join(DIMENSION_LABELS[d] for d in c["new_coverage"]) or "marginal"} for c in chosen])
st.dataframe(tb, hide_index=True, width="stretch")

g = PLANETS[t["body"]]["gravity"]
o = physics.gravity_offload(mass, 4, 0.2, 0.12, g, 0, physics.SOILS[list(physics.SOILS)[2]], 1.0)
extras = "\n".join([
    "## Campaign plan", f"- Mission objective: {obj}", f"- Planetary target: {t['name']} ({t['body']}) at {t['lat']}, {t['lon']}",
    "- Recommended Earth sites: " + "; ".join(f"{c['order']}. {c['name'].split(' (')[0]} ({cands[c['id']]['lat']:.3f}, {cands[c['id']]['lon']:.3f})" for c in chosen),
    "- Measurements and procedures: " + "; ".join(EXPERIMENTS.get(obj, ["not defined for this objective"])),
    f"- Engineering compensation (conceptual): a {mass:.0f} kg rover on {t['body']} gravity ({g} m/s2) needs about {o['offload_force_N']:.0f} N of offload ({o['offload_mass_equiv_kg']:.0f} kg equivalent); "
    f"terramechanics estimate of wheel sinkage {o['sinkage_target_mm']:.1f} mm at target gravity vs {o['sinkage_earth_mm']:.1f} mm on Earth (illustrative soil, unvalidated).",
    "- Logistics: route length " + f"{camp.route_length_km(ids, cands):,.0f} km straight-line; access data are missing for discovered sites and must be surveyed.",
    "- Limitations: Earth cannot reproduce target gravity, vacuum or radiation; similarity indices are not probabilities; see Scientific Comparison.",
    f"- Model {cfg.MODEL_VERSION}; catalogue {cfg.DATA_VERSION}; datasets per site are listed below."])
with st.expander("Per-site rationale and provenance"):
    for c in chosen:
        r = next(x for x in rows if x["id"] == c["id"]); cd = cands[c["id"]]
        st.markdown(f"**{c['name']}**  " + theme.badge(cd.get("provenance_class", "demonstration")), unsafe_allow_html=True)
        for q, items in explain(t, cd, r, obj).items():
            if q.startswith(("Why", "Where")):
                st.markdown(f"*{q}*"); [st.markdown(f"- {i}") for i in items]
        st.caption("Datasets: " + "; ".join(cd["sources"]) + f" | resolution {cd['resolution_m']} m | coverage {r['coverage']:.0%}")

st.markdown("#### Export")
n = st.slider("Detailed write-ups for top N sites", 1, min(8, len(rows)), 3)
e = st.columns(4)
e[0].download_button("PDF brief", gen.to_pdf(rows, cands, t, obj, W, n, extras), "campaign_brief.pdf", "application/pdf", width="stretch")
e[1].download_button("Markdown", gen.to_markdown(rows, cands, t, obj, W, n, extras), "campaign_brief.md", "text/markdown", width="stretch")
e[2].download_button("CSV table", gen.to_csv(rows, cands), "candidates.csv", "text/csv", width="stretch")
e[3].download_button("GeoJSON", gen.to_geojson(rows, cands, t, obj, W), "candidates.geojson", "application/geo+json", width="stretch")
st.caption("Exports include the generation date, model and data versions, weights, coverage, intervals, provenance class and limitations.")
