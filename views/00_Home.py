import streamlit as st

from components import charts, theme, viewer3d
from components.context import sidebar

ctx = sidebar("overview")
t, rows = ctx["target"], ctx["rows"]
theme.apply_theme("overview")
st.markdown("<div class='ws-head'><div class='eyebrow'>NASA Space Apps Challenge 2026</div><h1>Celestial Cartographers</h1>"
            "<p>Discover worlds within our world. Find terrestrial sites that resemble lunar and Martian environments, score them transparently, "
            "and see exactly where the analogy breaks down.</p></div>", unsafe_allow_html=True)

top = rows[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Target", t["name"].split(" (")[0], t["body"])
c2.metric("Objective", ctx["objective"])
c3.metric("Top match", top["name"].split(" (")[0], f"index {top['total']:.2f}")
c4.metric("Candidates ranked", len(rows), f"{len(st.session_state['discovered'])} discovered")

left, right = st.columns([1.5, 1])
with left:
    by = {r["id"]: r["total"] for r in rows}
    markers = [{"label": c["name"].split(" (")[0], "lat": c["lat"], "lon": c["lon"], "color": charts.sim_color(by.get(c["id"])),
                "line": f"{c['status']}, index {by[c['id']]:.2f}" if by.get(c["id"]) is not None else c["status"]} for c in ctx["cand_list"]]
    viewer3d.show(viewer3d.explorer_html("Earth", 20.0, 30.0, "Earth: candidate analogues (colour = similarity index)", markers), 540)
with right:
    with st.container(border=True):
        st.markdown(f"#### {t['name']}")
        st.markdown(theme.badge(t.get("provenance_class", "demonstration")) + theme.badge("local" if t.get("provenance_class") == "local" else "warn", "not field validated"), unsafe_allow_html=True)
        st.caption(f"{t['lat']:.2f}, {t['lon']:.2f}  |  {t['lithology']}  |  {t['scale']}")
        st.write(f"Mission objective **{ctx['objective']}** sets the eight dimension weights. Open **Mission Control** to change the world, region, "
                 "objective or weights, and to add datasets.")
    st.markdown("**Workflow**")
    for h, p in [("Choose", "world, region, objective"), ("Explore", "3D globe and terrain of the target"), ("Discover", "scan terrain, detect landforms, rank"),
                 ("Compare", "Earth, Moon and Mars side by side"), ("Plan", "physics, traverse, drilling, brief")]:
        st.markdown(f"<span class='badge'>{h}</span><span class='tiny'>{p}</span>", unsafe_allow_html=True)
theme.demo_note()
