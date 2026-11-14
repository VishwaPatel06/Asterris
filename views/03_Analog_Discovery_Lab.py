import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import charts, theme, viewer3d
from components.context import live_power, sidebar
from config import palette as P
from config.mission_presets import DIMENSION_LABELS, DIMENSIONS
from data_sources import manager
from geospatial import terrain, tiles
from scientific_engine import dem as demlib
from config.mission_presets import MISSION_FILTERS
from scientific_engine import discovery, synthetic, validation
from scientific_engine.explain import explain
from scientific_engine.similarity import rank_candidates, sensitivity_analysis

ctx = sidebar("discovery")
theme.header("Analog Discovery Lab", "Scan terrain for landforms, filter by mission constraints, then score separately against the target.", "Workspace 03", "discovery")
t, obj, W = ctx["target"], ctx["objective"], ctx["weights"]
tab_d, tab_r, tab_a, tab_s = st.tabs(["Discover", "Rankings and custom search", "Atlas", "Subsurface"])

REGIONS = {"Craters of the Moon lava field, Idaho (USA)": (-113.65, 43.15, -113.35, 43.35), "Pinacate volcanic field, Sonora (Mexico)": (-113.65, 31.65, -113.35, 31.95),
           "Myvatn-Krafla area (Iceland)": (-17.05, 65.55, -16.65, 65.75), "Timanfaya, Lanzarote (Spain)": (-13.85, 28.95, -13.65, 29.10),
           "Kilauea region, Hawaii (USA)": (-155.40, 19.30, -155.10, 19.50)}

# ------------------------------------------------------------------------------------------------ Discover
with tab_d:
    st.markdown("**Pipeline:** scan DEM, detect landforms, build boundaries, extract features, apply mission filters (this tab), then score and rank (next tab). Detection and scoring are separate steps.")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        src = st.radio("Terrain source", ["Earth region (live tiles)", "Uploaded DEM", "Synthetic demonstration"], horizontal=True)
        bbox, region_name, upload_id = None, "region", None
        if src.startswith("Earth"):
            preset = st.selectbox("Region", list(REGIONS) + ["Custom bounding box"])
            if preset == "Custom bounding box":
                b = st.columns(4); bbox = (b[0].number_input("West", value=-113.6, format="%.3f"), b[1].number_input("South", value=43.2, format="%.3f"),
                                           b[2].number_input("East", value=-113.4, format="%.3f"), b[3].number_input("North", value=43.3, format="%.3f")); region_name = "custom"
            else:
                bbox = REGIONS[preset]; region_name = preset.split(",")[0].split(" (")[0]
            z = tiles.choose_zoom(bbox); n_t = tiles.plan_tiles(bbox, z)["count"]
            st.caption(f"{n_t} elevation tiles at zoom {z} (~{tiles.meters_per_pixel((bbox[1] + bbox[3]) / 2, z):.0f} m/px). Needs internet. Cached after first fetch.")
        elif src == "Uploaded DEM":
            ups = manager.user_rasters("Earth")
            if ups:
                upload_id = st.selectbox("DEM", [u["id"] for u in ups], format_func=lambda i: next(u["original_name"] for u in ups if u["id"] == i))
                b = st.columns(4); bbox = (b[0].number_input("West", value=0.0, format="%.4f"), b[1].number_input("South", value=0.0, format="%.4f"),
                                           b[2].number_input("East", value=0.1, format="%.4f"), b[3].number_input("North", value=0.1, format="%.4f")); region_name = "uploaded"
                st.caption("Enter the raster's bounds; they are used to georeference detections (GeoTIFF CRS metadata is not yet used automatically).")
            else:
                st.info("No Earth DEM uploaded. Add one in Mission Control > Data sources.")
        else:
            st.caption("Planted craters, cones and a pit chain on fractal terrain. Not Earth data; used to demonstrate and benchmark the detector.")
            region_name = "synthetic"
    with c2:
        sens = st.slider("Detector sensitivity", 0.6, 1.6, 1.0, 0.1, help="Higher finds more, weaker features and more false positives.")
        mind = st.slider("Minimum feature diameter (m)", 100, 1500, 250, 50)
        maxs = st.slider("Maximum mean slope for this objective (deg)", 5, 45, int(MISSION_FILTERS.get(obj, {}).get("max_slope_deg", 45)))
        climate_on = st.checkbox("Attach NASA POWER climatology to candidates", value=src.startswith("Earth"), help="Real monthly temperature climatology at the region centre (public, no key).")
    go_run = st.button("Run discovery", type="primary", disabled=(src == "Uploaded DEM" and not upload_id))
    if go_run:
        grid = None
        with st.spinner("Scanning terrain..."):
            if src.startswith("Earth"):
                r = tiles.fetch_dem(bbox)
                if r["ok"]:
                    grid = discovery.Grid(r["dem"], r["cell_m"], r["bbox"], r["source"], "real", r["crs"])
                else:
                    st.error(r["error"]); st.caption("Nothing was invented. Try again online, upload a DEM, or use the synthetic demonstration.")
            elif src == "Uploaded DEM":
                name, raw = manager.raster_bytes(upload_id); h, cell, msg = demlib.load_uploaded_dem(name, raw, n=600)
                if h is not None:
                    grid = discovery.Grid(np.nan_to_num(h, nan=float(np.nanmedian(h))), cell, bbox, f"Uploaded DEM {name}", "local", "as uploaded")
                else:
                    st.error(msg)
            else:
                grid, truth = synthetic.planted_dem(4); st.session_state["synthetic_truth"] = truth
        if grid is not None:
            clim = None
            if climate_on and src.startswith("Earth"):
                cl = live_power((grid.bbox[1] + grid.bbox[3]) / 2, (grid.bbox[0] + grid.bbox[2]) / 2)
                if cl.get("ok"):
                    m = cl["monthly"]; clim = {"temp_mean_c": float(m.temp_mean_c.mean()), "temp_min_c": float(m.temp_min_c.min()), "temp_max_c": float(m.temp_max_c.max()), "source": cl["source"]}
                else:
                    st.warning("Climatology unavailable; temperature stays missing for these candidates.")
            res = discovery.run_discovery(grid, obj, region_name, clim, sens, {"max_slope_deg": maxs}, mind)
            st.session_state["disc_result"] = {"res": res, "grid": grid, "src": src}
    dr = st.session_state.get("disc_result")
    if dr:
        res, grid = dr["res"], dr["grid"]
        theme.note(res["coverage_note"] + " Detections are candidates, not confirmed features.")
        m = st.columns(4); m[0].metric("Landforms detected", res["detections"]); m[1].metric("Passed mission filters", len(res["candidates"]))
        m[2].metric("Rejected by filters", len(res["rejected"])); m[3].metric("Cell size", f"{res['cell_m']:.0f} m")
        v = validation.load_or_run() if (__import__("config.settings", fromlist=["x"]).get_settings().cache_dir / "verification.json").exists() else None
        if v:
            fr = v["detector"]["rows"][0]
            st.caption(f"Detector benchmark on synthetic planted features: precision {fr['precision']:.2f}, recall {fr['recall']:.2f} (fresh features). Unknown on real terrain. Details in Mission Engineering > Model accuracy.")
        else:
            st.caption("Detector accuracy has not been computed yet. Run it in Mission Engineering > Model accuracy.")
        der_hs = terrain.hillshade(grid.h, grid.cell_m, exag=2.0)
        rgb = (terrain.colorize(grid.h, "elevation").astype(float) * (0.35 + 0.65 * der_hs[..., None])).astype(np.uint8)
        fig = charts.layer_image(rgb, "Detected landforms over shaded relief")
        for grp, col, nm in (("candidates", P.CELESTIAL_MINT, "passed filters"), ("rejected", P.UNAVAILABLE, "rejected")):
            cs = res[grp]
            if cs:
                fig.add_trace(go.Scatter(x=[c["grid_rc"][1] for c in cs], y=[c["grid_rc"][0] for c in cs], mode="markers", name=nm, marker=dict(size=10, color=col, symbol="circle-open", line=dict(width=2.5, color=col)),
                                         text=[f"{c['name']}<br>{c['morphology']}, {c['diameter_m']:.0f} m, conf {c['detector_confidence']:.2f}" for c in cs], hoverinfo="text"))
        fig.update_layout(showlegend=True, height=520); st.plotly_chart(fig, width="stretch")
        if res["candidates"]:
            df = pd.DataFrame([{"id": c["id"], "type": c["morphology"], "diameter_m": round(c["diameter_m"]), "depth_or_height_m": round(c["depth_m"] or 0), "mean_slope_deg": round(c["slope_deg"], 1),
                                "confidence": round(c["detector_confidence"], 2), "lat": round(c["lat"], 4), "lon": round(c["lon"], 4)} for c in res["candidates"]])
            st.dataframe(df, hide_index=True, width="stretch")
            a1, a2 = st.columns(2)
            if a1.button("Add candidates to rankings", type="primary"):
                keep = [c for c in st.session_state["discovered"] if not c["id"].startswith("DISC-") or c["id"] not in {x["id"] for x in res["candidates"]}]
                st.session_state["discovered"] = keep + res["candidates"]; st.rerun()
            if a2.button("Clear discovered candidates"):
                st.session_state["discovered"] = []; st.rerun()
            if dr["src"].startswith("Earth"):
                mk = [{"label": c["id"][-4:] + " " + c["morphology"], "lat": c["lat"], "lon": c["lon"], "color": P.CELESTIAL_MINT, "bbox": c["bbox"]} for c in res["candidates"][:12]]
                viewer3d.show(viewer3d.explorer_html("Earth", mk[0]["lat"], mk[0]["lon"], "Discovered landforms", mk, start="terrain", zoom=12), 560)
            else:
                n0 = grid.h.shape[0]; hs = demlib.downsample(grid.h, 129); k = 128 / (n0 - 1)
                mk = [{"label": c["id"][-4:], "lat": 0, "lon": 0, "color": P.CELESTIAL_MINT, "cell": [c["grid_rc"][0] * k, c["grid_rc"][1] * k]} for c in res["candidates"][:15]]
                viewer3d.show(viewer3d.explorer_html("Moon", 0, 0, "Discovered landforms (grid)", mk, grid=viewer3d.grid_payload(hs, grid.cell_m * k ** -1, dr["src"].startswith("Synth"), grid.source), start="terrain", exag=2.0), 560)
        if res["rejected"]:
            with st.expander(f"Rejected by mission filters ({len(res['rejected'])})"):
                st.dataframe(pd.DataFrame([{"id": c["id"], "type": c["morphology"], "reason": c["rejected_because"]} for c in res["rejected"]]), hide_index=True, width="stretch")

# ------------------------------------------------------------------------------------------------ Rankings
with tab_r:
    rows = ctx["rows"]
    with st.expander("Custom search criteria", expanded=False):
        pool = ctx["cand_list"]
        f1, f2, f3 = st.columns(3)
        lith = f1.multiselect("Lithology", sorted({c["lithology"] for c in pool if c.get("lithology")})); morph = f2.multiselect("Morphology", sorted({c["morphology"] for c in pool}))
        scale = f3.multiselect("Scale", sorted({c["scale"] for c in pool}))
        g1, g2, g3 = st.columns(3)
        smax = g1.slider("Max mean slope (deg)", 0, 60, 60); mincov = g2.slider("Minimum data coverage", 0.0, 1.0, 0.0, 0.05)
        excl = g3.multiselect("Exclude status", sorted({c["status"] for c in pool}))
        tr = st.slider("Mean temperature range (deg C)", -80, 60, (-80, 60))

        def ok(c, r):
            return ((not lith or c.get("lithology") in lith) and (not morph or c["morphology"] in morph) and (not scale or c["scale"] in scale) and (c["slope_deg"] is None or c["slope_deg"] <= smax)
                    and r["coverage"] >= mincov and c["status"] not in excl and (c["temp_mean_c"] is None or tr[0] <= c["temp_mean_c"] <= tr[1]))
        rows = [r for r in rows if ok(ctx["cands"][r["id"]], r)]
        st.caption(f"{len(rows)} candidate(s) match. Candidates with missing values are kept, not dropped as zero.")
    if not rows:
        st.info("No candidates match these criteria.")
    else:
        df = pd.DataFrame([{"rank": r["rank"], "name": r["name"].split(" (")[0], "type": ctx["cands"][r["id"]]["status"], "similarity index": r["total"], "fidelity": r["fidelity"], "suitability": r["suitability"], "transferability": r["transferability"],
                            "coverage": r["coverage"], "interval 5-95%": ("n/a" if not r["interval"] else f"{r['interval'][0]:.2f}-{r['interval'][1]:.2f}"), "missing": ", ".join(DIMENSION_LABELS[d] for d in r["missing_dimensions"]) or "-"} for r in rows])
        st.dataframe(df.style.format({c: "{:.2f}" for c in ["similarity index", "fidelity", "suitability", "transferability", "coverage"]}, na_rep="n/a"), hide_index=True, width="stretch")
        names = {r["id"]: r["name"].split(" (")[0] for r in rows}
        sel = st.multiselect("Compare candidates", list(names), default=list(names)[:3], format_func=names.get)
        chosen = [r for r in rows if r["id"] in sel]
        if chosen:
            kind = st.radio("Chart", ["Dumbbell", "Grouped bars", "Heatmap", "Difference", "Radar"], horizontal=True)
            fig = {"Dumbbell": lambda: charts.dumbbell(chosen), "Grouped bars": lambda: charts.hbar(chosen), "Heatmap": lambda: charts.heatmap(rows[:15], DIMENSIONS),
                   "Difference": lambda: charts.difference_card(chosen), "Radar": lambda: charts.radar(chosen)}[kind]()
            st.plotly_chart(fig, width="stretch")
            st.plotly_chart(charts.score_bars(chosen), width="stretch")
            p = chosen[0]
            with st.expander(f"Profile and explanation: {p['name']}", expanded=False):
                cand = ctx["cands"][p["id"]]
                st.markdown(theme.badge(cand.get("provenance_class", "demonstration")) + theme.badge("", cand["status"]), unsafe_allow_html=True)
                st.caption(f"{cand['lat']:.4f}, {cand['lon']:.4f} | {cand['scale']} | resolution {cand['resolution_m']} m | sources: {'; '.join(cand['sources'])}")
                for q, lines in explain(t, cand, p, obj).items():
                    st.markdown(f"**{q}**"); [st.markdown(f"- {l}") for l in lines]
        with st.expander("How rankings change with the weights"):
            sa = sensitivity_analysis(t, ctx["cand_list"], W, obj)
            st.dataframe(pd.DataFrame(sa)[["name", "mean_rank", "rank_std", "best_rank", "worst_rank", "p_top3"]].round(2), hide_index=True, width="stretch")
            st.caption("Weights perturbed around the current setting (Dirichlet draws). Low rank_std = robust to weight choice.")

# ------------------------------------------------------------------------------------------------ Atlas
with tab_a:
    rows = ctx["rows"]; by = {r["id"]: r["total"] for r in rows}
    f = st.columns(4)
    stat = f[0].multiselect("Status", sorted({c["status"] for c in ctx["cand_list"]}), key="at_s"); minsim = f[1].slider("Minimum index", 0.0, 1.0, 0.0, 0.05, key="at_m")
    sat = f[2].toggle("Satellite imagery", value=False); region = f[3].selectbox("Region", ["World", "Americas", "Europe and Africa", "Asia and Oceania"])
    cs = [c for c in ctx["cand_list"] if (not stat or c["status"] in stat) and (by.get(c["id"]) or 0) >= minsim]
    centers = {"World": ((18, 20), 0.9), "Americas": ((10, -90), 1.6), "Europe and Africa": ((30, 20), 1.8), "Asia and Oceania": ((20, 100), 1.6)}
    cen, zm = centers[region]
    if cs:
        st.plotly_chart(charts.candidate_map(cs, by, 540, cen, zm, sat), width="stretch")
        st.caption("Marker colour and size follow the similarity index for the selected target and objective. Markers are actual catalogue or discovered records. For real-terrain 3D, use Planetary Explorer > World: Earth.")
        pick = st.selectbox("Open candidate profile", [c["id"] for c in cs], format_func=lambda i: ctx["cands"][i]["name"])
        c = ctx["cands"][pick]; r = next(x for x in rows if x["id"] == pick)
        a, b = st.columns(2)
        a.markdown(f"**{c['name']}**  \n{c['lat']:.4f}, {c['lon']:.4f} | {c['status']} | {c['scale']}  \nLithology {c.get('lithology') or 'unknown'}; slope {c['slope_deg']}; relief {c['relief_m']} m")
        b.markdown(f"Index {r['total']:.2f} | fidelity {r['fidelity']:.2f} | coverage {r['coverage']:.0%}" if r["total"] is not None else "Insufficient data")
    else:
        st.info("No candidates under these filters.")

# ------------------------------------------------------------------------------------------------ Subsurface
with tab_s:
    st.markdown("Lava tubes, caves, mines and subsurface ice sites. Each property is labelled measured, inferred or unknown.")
    cave = [c for c in ctx["cand_list"] if (c.get("caves") or 0) >= 0.5 or c["morphology"] == "lava_tube" or c["scale"] == "cave"]
    by = {r["id"]: r for r in ctx["rows"]}
    if not cave:
        st.info("No cave or lava-tube candidates in the current pool. Run discovery on a lava field (for example Craters of the Moon) or upload a table.")
    else:
        rec = []
        for c in cave:
            derived = c.get("provenance_class") == "derived"
            rec.append({"site": c["name"].split(" (")[0], "lat": round(c["lat"], 4), "lon": round(c["lon"], 4), "geology": c.get("lithology") or "unknown",
                        "dimension": (f"{c['diameter_m']:.0f} m length (DEM-derived)" if derived and c.get("diameter_m") else "not recorded"),
                        "evidence": "inferred from DEM pit chain" if derived else f"catalogue cave index {c['caves']} (demonstration)", "cave index": c["caves"],
                        "mean slope": c["slope_deg"], "access": "unknown (no access data)" if c.get("operations") is None else c["operations"],
                        "confidence": c.get("detector_confidence", c.get("data_quality")), "similarity": by[c["id"]]["total"]})
        st.dataframe(pd.DataFrame(rec).astype(str), hide_index=True, width="stretch")
    theme.note("Relevance: intact tubes could offer radiation and thermal shielding and a test bed for underground navigation, and skylights can be rover or drone targets. "
               "A terrestrial cave does not automatically reproduce a lunar or Martian lava tube: scale (lunar tubes are predicted far larger because of low gravity), "
               "vacuum, regolith cover and thermal regime differ. Entrance geometry, internal dimensions and stability need field or GPR confirmation.")
