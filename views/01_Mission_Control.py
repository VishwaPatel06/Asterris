import pandas as pd
import streamlit as st

from components import theme
from components.context import _apply_preset, sidebar
from config import palette as P
from config.data_catalog import LAYERS
from config.mission_presets import DIMENSION_LABELS, DIMENSIONS, PRESETS
from data_sources import manager
from data_sources.planetary import registry
from scientific_engine.similarity import normalise_weights

ctx = sidebar("mission_control", selectors=False)
theme.header("Mission Control", "Choose the world, region and objective. The objective sets the similarity weights, which you can edit.", "Workspace 01", "mission_control")
tab_mc, tab_data = st.tabs(["Mission", "Data sources"])

with tab_mc:
    cat = ctx["catalog"]
    cols = st.columns(2)
    for col, body, blurb in zip(cols, ["Moon", "Mars"], ["Airless, cratered, polar cold traps. 1.62 m/s2.", "Thin CO2 atmosphere, volcanoes, ancient valleys. 3.72 m/s2."]):
        with col:
            sel = st.session_state["body"] == body
            tg = [x for x in cat["targets"] if x["body"] == body]
            st.markdown(f"<div class='pcard {'sel' if sel else ''}'><span class='dot' style='background:{P.BODY_COLOR[body]}'></span><b>{body}</b>"
                        f"<div class='tiny'>{blurb}</div><div class='tiny'>{len(tg)} target regions</div></div>", unsafe_allow_html=True)
            if st.button(f"Select {body}", key=f"pick_{body}", disabled=sel, width="stretch"):
                st.session_state["body"] = body; st.session_state["target_id"] = tg[0]["id"]; st.rerun()
    t = ctx["target"]
    a, b = st.columns([1.1, 1])
    with a:
        with st.container(border=True):
            q = st.text_input("Search regions or enter coordinates (lat, lon)", placeholder="e.g. Shackleton, or -89.9, 129")
            opts = [x for x in cat["targets"] if x["body"] == st.session_state["body"]]
            if q.strip():
                try:
                    la, lo = [float(v) for v in q.replace(";", ",").split(",")]
                    nearest = min(opts, key=lambda x: (x["lat"] - la) ** 2 + (x["lon"] - lo) ** 2)
                    st.info(f"Coordinates {la:.2f}, {lo:.2f}: nearest catalogued region is {nearest['name']}. Choose it in the sidebar.")
                except ValueError:
                    hits = [x["name"] for x in opts if q.lower() in x["name"].lower() or q.lower() in x["lithology"].lower()]
                    st.write("Matches: " + (", ".join(hits) if hits else "none. Add regions via Data sources > upload a target table."))
            st.selectbox("Target region", [x["id"] for x in opts], key="target_id", format_func=lambda i: next(x["name"] for x in opts if x["id"] == i))
            t = next(x for x in opts if x["id"] == st.session_state["target_id"])
            st.markdown(f"**{t['name']}**  \n{t['lat']:.2f}, {t['lon']:.2f}  |  {t['lithology']}  |  {t['scale']}")
            st.markdown(theme.badge(t.get("provenance_class", "demonstration")), unsafe_allow_html=True)
            n_ds = len(registry.datasets_for(t["body"]))
            st.caption(f"{n_ds} catalogued datasets for {t['body']} (see Data sources for status). Limitations: Earth cannot reproduce lunar or Martian "
                       "gravity, vacuum or radiation; see Scientific Comparison.")
    with b:
        with st.container(border=True):
            st.selectbox("Mission objective", list(PRESETS), key="objective", on_change=_apply_preset)
            st.caption("Weights below start from the objective preset. They are starting examples, not scientifically validated values.")
            wc = st.columns(2)
            for i, d in enumerate(DIMENSIONS):
                wc[i % 2].slider(DIMENSION_LABELS[d], 0, 100, key=f"w_{d}")
            st.button("Reset to preset", on_click=_apply_preset)
            nw = normalise_weights(ctx["weights"])
            st.caption("Normalised: " + ", ".join(f"{DIMENSION_LABELS[d]} {v:.0%}" for d, v in nw.items()))

    rows = ctx["rows"]
    st.markdown("#### Mission overview")
    m = st.columns(5)
    cov = sum(r["coverage"] for r in rows) / len(rows)
    short = [r for r in rows if r["total"] is not None and r["total"] >= 0.6]
    m[0].metric("Candidates discovered", len(rows)); m[1].metric("Shortlisted (index >= 0.60)", len(short))
    m[2].metric("Highest ranked", rows[0]["name"].split(" (")[0], f"{rows[0]['total']:.2f}")
    m[3].metric("Mean data coverage", f"{cov:.0%}"); lo, hi = rows[0]["interval"] or (None, None)
    m[4].metric("Top-score interval (5-95%)", f"{lo:.2f}-{hi:.2f}" if lo is not None else "n/a")
    top = rows[0]
    st.caption("Top candidate breakdown: " + ", ".join(f"{DIMENSION_LABELS[d]} " + ("n/a" if top["dimension_scores"][d] is None else f"{top['dimension_scores'][d]:.2f}") for d in DIMENSIONS))
    theme.note("Interval reflects measurement noise on the stated features only. Missing dimensions are excluded and lower coverage, not scored as zero. Scores are similarity indices, not probabilities.")

with tab_data:
    st.markdown("#### Providers")
    tests = registry.load_tests()
    df = pd.DataFrame(registry.provider_table())
    f1, f2 = st.columns([1, 3])
    body_f = f1.selectbox("World", ["All", "Earth", "Moon", "Mars"], key="dsb")
    view = df if body_f == "All" else df[df["Body"] == body_f]
    st.dataframe(view[["Provider", "Body", "Status", "Datasets", "Needs", "Last test"]], hide_index=True, width="stretch")
    c1, c2, c3 = st.columns([2, 1, 1])
    pid = c1.selectbox("Provider", list(registry.PROVIDERS), format_func=lambda i: registry.PROVIDERS[i].name, key="dsp")
    pr = registry.PROVIDERS[pid]
    if c2.button("Test connection", width="stretch"):
        r = registry.test_connection(pid); st.toast(f"{pr.name}: {r['detail']}")
        st.rerun()
    c3.link_button("Open portal", pr.homepage or "https://pds.nasa.gov", width="stretch")
    if pr.ingestion:
        st.markdown(f"**How to ingest:** {pr.ingestion}")
    if pr.env_vars:
        st.caption("Set in .env: " + ", ".join(pr.env_vars) + (" (all present)" if pr.credentials_present() else " (not set; the app keeps working without them)"))

    st.markdown("#### Dataset catalogue")
    dsr = registry.datasets_for(None if body_f == "All" else body_f)
    ld = pd.DataFrame(dsr)[["title", "body", "layer", "resolution", "crs", "units", "level", "temporal", "access", "status"]]
    st.dataframe(ld, hide_index=True, width="stretch")

    st.markdown("#### Upload data")
    st.caption("Supported: CSV, GeoJSON, JSON (candidate/target tables), GeoTIFF/TIFF/ASCII grid (rasters). Tables use the same columns as the template; missing values stay missing.")
    u1, u2, u3 = st.columns(3)
    ubody = u1.selectbox("Applies to", ["Earth", "Moon", "Mars"], key="ub"); ulayer = u2.selectbox("Layer", LAYERS, key="ul")
    u3.download_button("Download table template", manager.template_csv(), "candidate_template.csv", width="stretch")
    ups = st.file_uploader("Files", type=[e.strip(".") for e in manager.SUPPORTED], accept_multiple_files=True, key="upl")
    if ups and st.button("Register uploads", type="primary"):
        for f in ups:
            ok, msg = manager.register_upload(f.name, f.getvalue(), ubody, ulayer)
            if ok:
                st.success(msg)
            else:
                st.error(msg)
        st.rerun()
    ds = manager.list_datasets()
    if ds:
        st.dataframe(pd.DataFrame(ds)[["original_name", "kind", "body", "layer", "bytes", "uploaded_utc", "provenance_class"]], hide_index=True, width="stretch")
        r1, r2 = st.columns([3, 1]); rid = r1.selectbox("Remove dataset", [d["id"] for d in ds], format_func=lambda i: next(d["original_name"] for d in ds if d["id"] == i))
        if r2.button("Remove", width="stretch") and rid:
            manager.remove_dataset(rid); st.rerun()
        with st.expander("Dataset metadata and coverage"):
            for d in ds:
                st.json({k: d[k] for k in ("original_name", "kind", "body", "layer", "sha256", "meta")})
    else:
        st.caption("No uploads yet. Built-in demonstration values are in use.")
    k1, k2 = st.columns(2)
    if k1.button("Clear cached data (DEM tiles, verification)", width="stretch"):
        st.toast(f"Removed {manager.clear_cache()} cached file(s)")
    errs = manager.ingest_errors()
    with st.expander(f"Ingestion errors ({len(errs)})"):
        if errs:
            st.dataframe(pd.DataFrame(errs), hide_index=True, width="stretch")
            if st.button("Clear error log"):
                manager.clear_errors(); st.rerun()
        else:
            st.caption("None.")
