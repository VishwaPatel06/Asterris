"""Workspace 03: Analog Discovery Lab — Preserves Discover, Rankings & Atlas tabs intact
while substantially upgrading the Subsurface Tab into a Scientifically Grounded Subsurface
Exploration Workspace (Sections 1–13 of the Asterris Subsurface Specification).

Drop-in replacement for `views/03_Analog_Discovery_Lab.py` in Asterris (`VishwaPatel06/Asterris`).
Compatible with both Plotly 6.x (`go.Scattermap` / `layout.map`) and Plotly 5.x (`go.Scattermapbox` / `layout.mapbox`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import charts, theme, viewer3d
from components.context import live_power, sidebar
from config import palette as P
from config.mission_presets import DIMENSION_LABELS, DIMENSIONS, MISSION_FILTERS
from data_sources import manager
from data_sources.subsurface_catalog import (
    EVIDENCE_CLASSES,
    PLANETARY_SUBSURFACE_REFERENCES,
    SUBSURFACE_CATEGORIES,
    SUBSURFACE_DATASET_REGISTRY,
    SUBSURFACE_MISSION_OBJECTIVES,
    SUBSURFACE_PALETTE as SP,
    build_subsurface_catalog,
    get_provider_adapter_status,
)
from geospatial import terrain, tiles
from scientific_engine import dem as demlib, discovery, synthetic, validation
from scientific_engine.explain import explain
from scientific_engine.similarity import sensitivity_analysis
from scientific_engine.subsurface_engine import (
    build_earth_moon_mars_comparison,
    evaluate_site_for_objective,
    evidence_badge_html,
    flatten_site_properties_table,
    format_property_value,
    generate_subsurface_assessment_report_md,
    generate_subsurface_geojson,
    plot_cross_section_scale_diagram,
    subsurface_3d_viewer_html,
)

# Plotly 6.x vs 5.x MapLibre/Mapbox compatibility
_HAS_SCATTERMAP = hasattr(go, "Scattermap")
_HAS_SCATTERMAPBOX = hasattr(go, "Scattermapbox")

ctx = sidebar("discovery")
theme.header(
    "Analog Discovery Lab",
    "Scan terrain for landforms, filter by mission constraints, then score separately against the target.",
    "Workspace 03",
    "discovery",
)
t, obj, W = ctx["target"], ctx["objective"], ctx["weights"]
tab_d, tab_r, tab_a, tab_s = st.tabs(["Discover", "Rankings and custom search", "Atlas", "Subsurface"])

REGIONS = {
    "Craters of the Moon lava field, Idaho (USA)": (-113.65, 43.15, -113.35, 43.35),
    "Pinacate volcanic field, Sonora (Mexico)": (-113.65, 31.65, -113.35, 31.95),
    "Myvatn-Krafla area (Iceland)": (-17.05, 65.55, -16.65, 65.75),
    "Timanfaya, Lanzarote (Spain)": (-13.85, 28.95, -13.65, 29.10),
    "Kilauea region, Hawaii (USA)": (-155.40, 19.30, -155.10, 19.50),
}

# --------------------------------------------------------------------------- Discover (Preserved Intact)
with tab_d:
    st.markdown(
        "**Pipeline:** scan DEM, detect landforms, build boundaries, extract features, apply mission filters (this tab), then score and rank (next tab). Detection and scoring are separate steps."
    )
    c1, c2 = st.columns([1.2, 1])
    with c1:
        src = st.radio(
            "Terrain source",
            ["Earth region (live tiles)", "Uploaded DEM", "Synthetic demonstration"],
            horizontal=True,
        )
        bbox, region_name, upload_id = None, "region", None
        if src.startswith("Earth"):
            preset = st.selectbox("Region", list(REGIONS) + ["Custom bounding box"])
            if preset == "Custom bounding box":
                b = st.columns(4)
                bbox = (
                    b[0].number_input("West", value=-113.6, format="%.3f"),
                    b[1].number_input("South", value=43.2, format="%.3f"),
                    b[2].number_input("East", value=-113.4, format="%.3f"),
                    b[3].number_input("North", value=43.3, format="%.3f"),
                )
                region_name = "custom"
            else:
                bbox = REGIONS[preset]
                region_name = preset.split(",")[0].split(" (")[0]
            z = tiles.choose_zoom(bbox)
            n_t = tiles.plan_tiles(bbox, z)["count"]
            st.caption(
                f"{n_t} elevation tiles at zoom {z} (~{tiles.meters_per_pixel((bbox[1] + bbox[3]) / 2, z):.0f} m/px). Needs internet. Cached after first fetch."
            )
        elif src == "Uploaded DEM":
            ups = manager.user_rasters("Earth")
            if ups:
                upload_id = st.selectbox(
                    "DEM",
                    [u["id"] for u in ups],
                    format_func=lambda i: next(u["original_name"] for u in ups if u["id"] == i),
                )
                b = st.columns(4)
                bbox = (
                    b[0].number_input("West", value=0.0, format="%.4f"),
                    b[1].number_input("South", value=0.0, format="%.4f"),
                    b[2].number_input("East", value=0.1, format="%.4f"),
                    b[3].number_input("North", value=0.1, format="%.4f"),
                )
                region_name = "uploaded"
                st.caption(
                    "Enter the raster's bounds; they are used to georeference detections (GeoTIFF CRS metadata is not yet used automatically)."
                )
            else:
                st.info("No Earth DEM uploaded. Add one in Mission Control > Data sources.")
        else:
            st.caption(
                "Planted craters, cones and a pit chain on fractal terrain. Not Earth data; used to demonstrate and benchmark the detector."
            )
            region_name = "synthetic"
    with c2:
        sens = st.slider(
            "Detector sensitivity",
            0.6,
            1.6,
            1.0,
            0.1,
            help="Higher finds more, weaker features and more false positives.",
        )
        mind = st.slider("Minimum feature diameter (m)", 100, 1500, 250, 50)
        maxs = st.slider(
            "Maximum mean slope for this objective (deg)",
            5,
            45,
            int(MISSION_FILTERS.get(obj, {}).get("max_slope_deg", 45)),
        )
        climate_on = st.checkbox(
            "Attach NASA POWER climatology to candidates",
            value=src.startswith("Earth"),
            help="Real monthly temperature climatology at the region centre (public, no key).",
        )
        go_run = st.button("Run discovery", type="primary", disabled=(src == "Uploaded DEM" and not upload_id))
        if go_run:
            grid = None
            with st.spinner("Scanning terrain..."):
                if src.startswith("Earth") and bbox is not None:
                    r = tiles.fetch_dem(bbox)
                    if r["ok"]:
                        grid = discovery.Grid(r["dem"], r["cell_m"], r["bbox"], r["source"], "real", r["crs"])
                    else:
                        st.error(r["error"])
                        st.caption(
                            "Nothing was invented. Try again online, upload a DEM, or use the synthetic demonstration."
                        )
                elif src == "Uploaded DEM" and upload_id and bbox is not None:
                    name, raw = manager.raster_bytes(upload_id) or ("", b"")
                    h, cell, msg = demlib.load_uploaded_dem(name, raw, n=600)
                    if h is not None:
                        grid = discovery.Grid(
                            np.nan_to_num(h, nan=float(np.nanmedian(h))),
                            cell,
                            bbox,
                            f"Uploaded DEM {name}",
                            "local",
                            "as uploaded",
                        )
                    else:
                        st.error(msg)
                else:
                    grid, truth = synthetic.planted_dem(4)
                    st.session_state["synthetic_truth"] = truth
            if grid is not None:
                clim = None
                if climate_on and src.startswith("Earth"):
                    cl = live_power((grid.bbox[1] + grid.bbox[3]) / 2, (grid.bbox[0] + grid.bbox[2]) / 2)
                    if cl.get("ok"):
                        m = cl["monthly"]
                        clim = {
                            "temp_mean_c": float(m.temp_mean_c.mean()),
                            "temp_min_c": float(m.temp_min_c.min()),
                            "temp_max_c": float(m.temp_max_c.max()),
                            "source": cl["source"],
                        }
                    else:
                        st.warning("Climatology unavailable; temperature stays missing for these candidates.")
                res = discovery.run_discovery(grid, obj, region_name, clim, sens, {"max_slope_deg": maxs}, mind)
                st.session_state["disc_result"] = {"res": res, "grid": grid, "src": src}
    dr = st.session_state.get("disc_result")
    if dr:
        res, grid = dr["res"], dr["grid"]
        theme.note(res["coverage_note"] + "Detections are candidates, not confirmed features.")
        m = st.columns(4)
        m[0].metric("Landforms detected", res["detections"])
        m[1].metric("Passed mission filters", len(res["candidates"]))
        m[2].metric("Rejected by filters", len(res["rejected"]))
        m[3].metric("Cell size", f"{res['cell_m']:.0f} m")
        v = (
            validation.load_or_run()
            if (__import__("config.settings", fromlist=["x"]).get_settings().cache_dir / "verification.json").exists()
            else None
        )
        if v:
            fr = v["detector"]["rows"][0]
            st.caption(
                f"Detector benchmark on synthetic planted features: precision {fr['precision']:.2f}, recall {fr['recall']:.2f} (fresh features). Unknown on real terrain. Details in Mission Engineering > Model accuracy."
            )
        else:
            st.caption("Detector accuracy has not been computed yet. Run it in Mission Engineering > Model accuracy.")
        der_hs = terrain.hillshade(grid.h, grid.cell_m, exag=2.0)
        rgb = (terrain.colorize(grid.h, "elevation").astype(float) * (0.35 + 0.65 * der_hs[..., None])).astype(
            np.uint8
        )
        fig = charts.layer_image(rgb, "Detected landforms over shaded relief")
        for grp, col, nm in (("candidates", P.CELESTIAL_MINT, "passed filters"), ("rejected", P.UNAVAILABLE, "rejected")):
            cs = res[grp]
            if cs:
                fig.add_trace(
                    go.Scatter(
                        x=[c["grid_rc"][1] for c in cs],
                        y=[c["grid_rc"][0] for c in cs],
                        mode="markers",
                        name=nm,
                        marker=dict(size=10, color=col, symbol="circle-open", line=dict(width=2.5, color=col)),
                        text=[
                            f"{c['name']}<br>{c['morphology']}, {c['diameter_m']:.0f} m, conf {c['detector_confidence']:.2f}"
                            for c in cs
                        ],
                        hoverinfo="text",
                    )
                )
        fig.update_layout(showlegend=True, height=520)
        st.plotly_chart(fig, width="stretch")
        if res["candidates"]:
            df = pd.DataFrame(
                [
                    {
                        "id": c["id"],
                        "type": c["morphology"],
                        "diameter_m": round(c["diameter_m"]),
                        "depth_or_height_m": round(c["depth_m"] or 0),
                        "mean_slope_deg": round(c["slope_deg"], 1),
                        "confidence": round(c["detector_confidence"], 2),
                        "lat": round(c["lat"], 4),
                        "lon": round(c["lon"], 4),
                    }
                    for c in res["candidates"]
                ]
            )
            st.dataframe(df, hide_index=True, width="stretch")
            a1, a2 = st.columns(2)
            if a1.button("Add candidates to rankings", type="primary"):
                keep = [
                    c
                    for c in st.session_state["discovered"]
                    if not c["id"].startswith("DISC-") or c["id"] not in {x["id"] for x in res["candidates"]}
                ]
                st.session_state["discovered"] = keep + res["candidates"]
                st.rerun()
            if a2.button("Clear discovered candidates"):
                st.session_state["discovered"] = []
                st.rerun()
            if dr["src"].startswith("Earth"):
                mk = [
                    {
                        "label": c["id"][-4:] + " " + c["morphology"],
                        "lat": c["lat"],
                        "lon": c["lon"],
                        "color": P.CELESTIAL_MINT,
                        "bbox": c["bbox"],
                    }
                    for c in res["candidates"][:12]
                ]
                viewer3d.show(
                    viewer3d.explorer_html("Earth", mk[0]["lat"], mk[0]["lon"], "Discovered landforms", mk, start="terrain", zoom=12),
                    560,
                )
            else:
                n0 = grid.h.shape[0]
                hs = demlib.downsample(grid.h, 129)
                k = 128 / (n0 - 1)
                mk = [
                    {
                        "label": c["id"][-4:],
                        "lat": 0,
                        "lon": 0,
                        "color": P.CELESTIAL_MINT,
                        "cell": [c["grid_rc"][0] * k, c["grid_rc"][1] * k],
                    }
                    for c in res["candidates"][:15]
                ]
                viewer3d.show(
                    viewer3d.explorer_html(
                        "Moon",
                        0,
                        0,
                        "Discovered landforms (grid)",
                        mk,
                        grid=viewer3d.grid_payload(hs, grid.cell_m * k**-1, dr["src"].startswith("Synth"), grid.source),
                        start="terrain",
                        exag=2.0,
                    ),
                    560,
                )
        if res["rejected"]:
            with st.expander(f"Rejected by mission filters ({len(res['rejected'])})"):
                st.dataframe(
                    pd.DataFrame(
                        [{"id": c["id"], "type": c["morphology"], "reason": c["rejected_because"]} for c in res["rejected"]]
                    ),
                    hide_index=True,
                    width="stretch",
                )

# --------------------------------------------------------------------------- Rankings (Preserved Intact)
with tab_r:
    rows = ctx["rows"]
    with st.expander("Custom search criteria", expanded=False):
        pool = ctx["cand_list"]
        f1, f2, f3 = st.columns(3)
        lith = f1.multiselect("Lithology", sorted({c["lithology"] for c in pool if c.get("lithology")}))
        morph = f2.multiselect("Morphology", sorted({c["morphology"] for c in pool}))
        scale = f3.multiselect("Scale", sorted({c["scale"] for c in pool}))
        g1, g2, g3 = st.columns(3)
        smax = g1.slider("Max mean slope (deg)", 0, 60, 60)
        mincov = g2.slider("Minimum data coverage", 0.0, 1.0, 0.0, 0.05)
        excl = g3.multiselect("Exclude status", sorted({c["status"] for c in pool}))
        tr = st.slider("Mean temperature range (deg C)", -80, 60, (-80, 60))

        def ok(c, r):
            return (
                (not lith or c.get("lithology") in lith)
                and (not morph or c["morphology"] in morph)
                and (not scale or c["scale"] in scale)
                and (c["slope_deg"] is None or c["slope_deg"] <= smax)
                and r["coverage"] >= mincov
                and c["status"] not in excl
                and (c["temp_mean_c"] is None or tr[0] <= c["temp_mean_c"] <= tr[1])
            )

        rows = [r for r in rows if ok(ctx["cands"][r["id"]], r)]
        st.caption(f"{len(rows)} candidate(s) match. Candidates with missing values are kept, not dropped as zero.")
    if not rows:
        st.info("No candidates match these criteria.")
    else:
        df = pd.DataFrame(
            [
                {
                    "rank": r["rank"],
                    "name": r["name"].split(" (")[0],
                    "type": ctx["cands"][r["id"]]["status"],
                    "similarity index": r["total"],
                    "fidelity": r["fidelity"],
                    "suitability": r["suitability"],
                    "transferability": r["transferability"],
                    "coverage": r["coverage"],
                    "interval 5-95%": ("n/a" if not r["interval"] else f"{r['interval'][0]:.2f}-{r['interval'][1]:.2f}"),
                    "missing": ", ".join(DIMENSION_LABELS[d] for d in r["missing_dimensions"]) or "-",
                }
                for r in rows
            ]
        )
        st.dataframe(
            df.style.format(
                {c: "{:.2f}" for c in ["similarity index", "fidelity", "suitability", "transferability", "coverage"]},
                na_rep="n/a",
            ),
            hide_index=True,
            width="stretch",
        )
        names = {r["id"]: r["name"].split(" (")[0] for r in rows}
        sel = st.multiselect("Compare candidates", list(names), default=list(names)[:3], format_func=names.get)
        chosen = [r for r in rows if r["id"] in sel]
        if chosen:
            kind = st.radio("Chart", ["Dumbbell", "Grouped bars", "Heatmap", "Difference", "Radar"], horizontal=True)
            fig = {
                "Dumbbell": lambda: charts.dumbbell(chosen),
                "Grouped bars": lambda: charts.hbar(chosen),
                "Heatmap": lambda: charts.heatmap(rows[:15], DIMENSIONS),
                "Difference": lambda: charts.difference_card(chosen),
                "Radar": lambda: charts.radar(chosen),
            }[kind]()
            st.plotly_chart(fig, width="stretch")
            st.plotly_chart(charts.score_bars(chosen), width="stretch")
            p = chosen[0]
            with st.expander(f"Profile and explanation: {p['name']}", expanded=False):
                cand = ctx["cands"][p["id"]]
                st.markdown(
                    theme.badge(cand.get("provenance_class", "demonstration")) + theme.badge("", cand["status"]),
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"{cand['lat']:.4f}, {cand['lon']:.4f} | {cand['scale']} | resolution {cand['resolution_m']} m | sources: {'; '.join(cand['sources'])}"
                )
                for q, lines in explain(t, cand, p, obj).items():
                    st.markdown(f"**{q}**")
                    for line in lines:
                        st.markdown(f"- {line}")
            with st.expander("How rankings change with the weights"):
                sa = sensitivity_analysis(t, ctx["cand_list"], W, obj)
                st.dataframe(
                    pd.DataFrame(sa)[["name", "mean_rank", "rank_std", "best_rank", "worst_rank", "p_top3"]].round(2),
                    hide_index=True,
                    width="stretch",
                )
                st.caption("Weights perturbed around the current setting (Dirichlet draws). Low rank_std = robust to weight choice.")

# --------------------------------------------------------------------------- Atlas (Preserved Intact)
with tab_a:
    rows = ctx["rows"]
    by = {r["id"]: r["total"] for r in rows}
    f = st.columns(4)
    stat = f[0].multiselect("Status", sorted({c["status"] for c in ctx["cand_list"]}), key="at_s")
    minsim = f[1].slider("Minimum index", 0.0, 1.0, 0.0, 0.05, key="at_m")
    sat = f[2].toggle("Satellite imagery", value=False)
    region = f[3].selectbox("Region", ["World", "Americas", "Europe and Africa", "Asia and Oceania"])
    cs = [c for c in ctx["cand_list"] if (not stat or c["status"] in stat) and (by.get(c["id"]) or 0) >= minsim]
    centers = {
        "World": ((18, 20), 0.9),
        "Americas": ((10, -90), 1.6),
        "Europe and Africa": ((30, 20), 1.8),
        "Asia and Oceania": ((20, 100), 1.6),
    }
    cen, zm = centers[region]
    if cs:
        st.plotly_chart(charts.candidate_map(cs, by, 540, cen, zm, sat), width="stretch")
        st.caption(
            "Marker colour and size follow the similarity index for the selected target and objective. Markers are actual catalogue or discovered records. For real-terrain 3D, use Planetary Explorer > World: Earth."
        )
        pick = st.selectbox("Open candidate profile", [c["id"] for c in cs], format_func=lambda i: ctx["cands"][i]["name"])
        c = ctx["cands"][pick]
        r = next(x for x in rows if x["id"] == pick)
        a, b = st.columns(2)
        a.markdown(
            f"**{c['name']}**  \n{c['lat']:.4f}, {c['lon']:.4f} | {c['status']} | {c['scale']}  \nLithology {c.get('lithology') or 'unknown'}; slope {c['slope_deg']}; relief {c['relief_m']} m"
        )
        b.markdown(
            f"Index {r['total']:.2f} | fidelity {r['fidelity']:.2f} | coverage {r['coverage']:.0%}"
            if r["total"] is not None
            else "Insufficient data"
        )
    else:
        st.info("No candidates under these filters.")

# ===========================================================================
# TAB 4: REDESIGNED SUBSURFACE EXPLORATION WORKSPACE (Sections 1–13)
# ===========================================================================
with tab_s:
    all_sub_sites = build_subsurface_catalog(ctx["cand_list"])

    st.markdown(
        f"""
        <div style="background:linear-gradient(90deg, {SP['NEBULA_NAVY']}, #192B46);
                    border:1px solid rgba(72,191,227,0.28);border-radius:10px;padding:14px 18px;margin-bottom:14px;">
            <div style="color:{SP['COSMIC_CYAN']};font-size:0.76rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">
                Asterris Subsurface Exploration & Speleological Analogue Lab
            </div>
            <div style="color:{SP['STARLIGHT_WHITE']};font-size:1.15rem;font-weight:600;margin-top:2px;">
                Terrestrial Lava Tubes, Caves, Karst, Cryo-Permafrost & Deep Underground Analogues
            </div>
            <div style="color:#A8B8CE;font-size:0.85rem;margin-top:4px;">
                Discover, visualize in 3D, characterize, and evaluate terrestrial subsurface environments against Lunar and Martian skylights with strict evidence provenance (<code>MEASURED</code>, <code>DERIVED</code>, <code>INFERRED</code>, <code>DEMONSTRATION</code>, <code>UNKNOWN</code>).
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # SECTION 2: SUBSURFACE EXPLORATION DASHBOARD & FILTERS
    # -----------------------------------------------------------------------
    with st.expander("Subsurface Exploration Filters, Mission Objective & Search", expanded=True):
        f_row1 = st.columns([1.3, 1.3, 1.1, 1.1])
        with f_row1[0]:
            sub_obj = st.selectbox(
                "Subsurface Mission Objective",
                SUBSURFACE_MISSION_OBJECTIVES,
                index=1 if t["body"] == "Moon" else 2,
                help="Evaluates Analogue Fidelity, Mission Suitability, and Transferability specifically for this subsurface objective.",
            )
        with f_row1[1]:
            sel_cats = st.multiselect(
                "Subsurface Environment Type",
                list(SUBSURFACE_CATEGORIES.keys()),
                default=[],
                placeholder="All 6 subsurface categories",
            )
        with f_row1[2]:
            all_liths = sorted({s.get("lithology", "basalt") for s in all_sub_sites})
            sel_liths = st.multiselect("Geological Composition", all_liths, default=[], placeholder="All lithologies")
        with f_row1[3]:
            all_countries = sorted({s.get("country", "Unknown") for s in all_sub_sites})
            sel_countries = st.multiselect("Country / Region", all_countries, default=[], placeholder="All countries")

        f_row2 = st.columns([1.1, 1.1, 1.1, 1.5])
        with f_row2[0]:
            sel_ev_classes = st.multiselect(
                "Evidence Classification",
                list(EVIDENCE_CLASSES.keys()),
                default=[],
                placeholder="All evidence classes",
            )
        with f_row2[1]:
            avail_opts = ["All", "Measured 3D/Survey Geometry Only", "Partial / Inferred Records Only"]
            sel_avail = st.selectbox("Data Availability", avail_opts, index=0)
        with f_row2[2]:
            conf_range = st.slider(
                "Confidence / Data Quality Range",
                min_value=0.0,
                max_value=1.0,
                value=(0.0, 1.0),
                step=0.05,
            )
        with f_row2[3]:
            search_query = st.text_input(
                "Search by Site Name, Formation, Mineral, or Coordinates",
                value="",
                placeholder="e.g., Valentine, Lanzarote, basalt, jarosite, 41.7, -121.5...",
            ).strip().lower()

    def _matches_subsurface_filters(s: dict) -> bool:
        if sel_cats and s["category"] not in sel_cats:
            return False
        if sel_liths and s.get("lithology") not in sel_liths:
            return False
        if sel_countries and s.get("country") not in sel_countries:
            return False
        if sel_ev_classes and s.get("evidence_class") not in sel_ev_classes:
            return False
        if sel_avail == "Measured 3D/Survey Geometry Only" and not s.get("has_measured_geometry"):
            return False
        if sel_avail == "Partial / Inferred Records Only" and s.get("has_measured_geometry"):
            return False
        c_val = float(s.get("confidence") or s.get("data_quality") or 0.5)
        if not (conf_range[0] <= c_val <= conf_range[1]):
            return False
        if search_query:
            haystack = " ".join(
                [
                    str(s.get("name", "")),
                    str(s.get("id", "")),
                    str(s.get("country", "")),
                    str(s.get("region", "")),
                    str(s.get("geological_classification", "")),
                    str(s.get("formation_process", "")),
                    " ".join(s.get("minerals", [])),
                    f"{s.get('lat', '')} {s.get('lon', '')}",
                ]
            ).lower()
            if search_query not in haystack:
                return False
        return True

    filtered_sites = [s for s in all_sub_sites if _matches_subsurface_filters(s)]

    total_sites_count = len(all_sub_sites)
    lava_tubes_count = sum(1 for s in all_sub_sites if s["category"] == "Volcanic lava tubes")
    caves_and_other_count = sum(1 for s in all_sub_sites if s["category"] != "Volcanic lava tubes")
    measured_geom_count = sum(1 for s in all_sub_sites if s.get("has_measured_geometry"))
    inferred_or_unknown_count = sum(
        1
        for s in all_sub_sites
        if not s.get("has_measured_geometry")
        or any(
            p.get("evidence") in ("INFERRED", "UNKNOWN", "DEMONSTRATION")
            for sec in ("geometry", "terrain", "environment")
            for p in s.get(sec, {}).values()
        )
    )
    evaluated_candidates_count = len(filtered_sites)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Subsurface Sites", total_sites_count, "Catalog + Discovered")
    k2.metric("Volcanic Lava Tubes", lava_tubes_count, "Rheogenic Pyroducts")
    k3.metric("Caves, Karst, Ice & Mines", caves_and_other_count, "5 Non-Volcanic Classes")
    k4.metric("Measured Geometry", measured_geom_count, "TLS / Grade-5 Survey")
    k5.metric("With Inferred/Unknown Props", inferred_or_unknown_count, "Explicit Uncertainty")
    k6.metric("Evaluated for Objective", evaluated_candidates_count, sub_obj[:18] + "...")

    if not filtered_sites:
        st.warning("No subsurface analogue sites match the current filter combination. Reset one or more filters above.")
    else:
        eval_by_id = {
            s["id"]: evaluate_site_for_objective(s, sub_obj, t["body"])
            for s in filtered_sites
        }
        site_by_id = {s["id"]: s for s in filtered_sites}

        sel_col1, sel_col2 = st.columns([2.2, 1.8])
        with sel_col1:
            active_sub_id = st.selectbox(
                "Active Subsurface Analogue Site (Inspect across Map, 3D Viewer, Scientific Analysis & Planetary Comparison)",
                [s["id"] for s in filtered_sites],
                format_func=lambda sid: (
                    f"{site_by_id[sid]['name']} [{site_by_id[sid]['category']}] — "
                    f"Fidelity {eval_by_id[sid]['analogue_fidelity']:.2f} | Suitability {eval_by_id[sid]['mission_suitability']:.2f}"
                ),
                key="subsurface_active_site_id",
            )
        active_site = site_by_id[active_sub_id]
        active_eval = eval_by_id[active_sub_id]

        with sel_col2:
            st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
            st.markdown(
                evidence_badge_html(active_site["evidence_class"], f"Primary Record: {active_site['evidence_class']}")
                + evidence_badge_html(
                    "MEASURED" if active_site.get("has_measured_geometry") else "UNKNOWN",
                    "3D Geometry: MEASURED" if active_site.get("has_measured_geometry") else "Geometry: UNMEASURED",
                )
                + f"<span style='color:#A8B8CE;font-size:0.80rem;'>Coverage: <strong>{active_eval['data_coverage']:.0%}</strong> | "
                f"Confidence: <strong>{active_site['confidence']:.0%}</strong></span>",
                unsafe_allow_html=True,
            )

        sub_tab_map, sub_tab_3d, sub_tab_sci, sub_tab_planet, sub_tab_suit, sub_tab_export = st.tabs(
            [
                "🗺️ Map & Site Profile",
                "🕸️ 3D Cave Geometry Viewer",
                "📐 Geometry, Terrain & Evidence",
                "🪐 Earth vs Moon/Mars Comparison",
                "🎯 Mission Suitability & Multi-Site Compare",
                "📚 Provenance & Export Reports",
            ]
        )

        # ===================================================================
        # SUB-TAB 1: INTERACTIVE SUBSURFACE ANALOGUE MAP & CANDIDATE PROFILE (Section 3)
        # ===================================================================
        with sub_tab_map:
            m_col, prof_col = st.columns([1.35, 1.05], gap="large")

            with m_col:
                mc1, mc2 = st.columns([1, 1])
                basemap_mode = mc1.radio(
                    "Basemap Imagery",
                    ["Dark Scientific Vector Map", "Esri World Satellite Imagery"],
                    horizontal=True,
                )
                color_mode = mc2.radio(
                    "Marker Color Encoding",
                    ["By Subsurface Category (6 Classes)", f"By Mission Suitability ({sub_obj[:16]}...)"],
                    horizontal=True,
                )

                fig_map = go.Figure()
                # Support Plotly 6 (go.Scattermap + layout.map), Plotly 5 (go.Scattermapbox + layout.mapbox), or fallback go.Scattergeo
                _TraceCls = (
                    getattr(go, "Scattermap", None)
                    or getattr(go, "Scattermapbox", None)
                    or go.Scattergeo
                )
                _map_layout_key = "map" if _HAS_SCATTERMAP else ("mapbox" if _HAS_SCATTERMAPBOX else "geo")

                if color_mode.startswith("By Subsurface Category"):
                    for cat_name, cat_cfg in SUBSURFACE_CATEGORIES.items():
                        cat_sites = [s for s in filtered_sites if s["category"] == cat_name]
                        if not cat_sites:
                            continue
                        fig_map.add_trace(
                            _TraceCls(
                                lat=[s["lat"] for s in cat_sites],
                                lon=[s["lon"] for s in cat_sites],
                                mode="markers",
                                name=cat_cfg["short"],
                                marker=dict(
                                    size=[16 if s["id"] == active_sub_id else 11 for s in cat_sites],
                                    color=cat_cfg["color"],
                                    opacity=0.92,
                                ),
                                text=[
                                    f"<b>{s['name']}</b><br>"
                                    f"Category: {s['category']}<br>"
                                    f"Coords: {s['lat']:.4f}°, {s['lon']:.4f}° ({s['coord_precision'][:38]}...)<br>"
                                    f"Evidence: {s['evidence_class']} | Fidelity: {eval_by_id[s['id']]['analogue_fidelity']:.2f} | "
                                    f"Suitability: {eval_by_id[s['id']]['mission_suitability']:.2f}"
                                    for s in cat_sites
                                ],
                                hoverinfo="text",
                            )
                        )
                else:
                    suit_vals = [eval_by_id[s["id"]]["mission_suitability"] for s in filtered_sites]
                    fig_map.add_trace(
                        _TraceCls(
                            lat=[s["lat"] for s in filtered_sites],
                            lon=[s["lon"] for s in filtered_sites],
                            mode="markers",
                            name="Mission Suitability",
                            marker=dict(
                                size=[16 if s["id"] == active_sub_id else 12 for s in filtered_sites],
                                color=suit_vals,
                                colorscale=[[0.0, "#D64D62"], [0.5, "#E6B84B"], [1.0, "#45C4A1"]],
                                cmin=0.3,
                                cmax=1.0,
                                showscale=True,
                                colorbar=dict(title="Suitability"),
                            ),
                            text=[
                                f"<b>{s['name']}</b> ({s['category']})<br>"
                                f"Suitability: {eval_by_id[s['id']]['mission_suitability']:.2f} | "
                                f"Fidelity: {eval_by_id[s['id']]['analogue_fidelity']:.2f}"
                                for s in filtered_sites
                            ],
                            hoverinfo="text",
                        )
                    )

                if _map_layout_key in ("map", "mapbox"):
                    if basemap_mode == "Esri World Satellite Imagery":
                        map_cfg = dict(
                            style="white-bg",
                            layers=[
                                dict(
                                    below="traces",
                                    sourcetype="raster",
                                    sourceattribution="Esri World Imagery",
                                    source=[
                                        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                                    ],
                                )
                            ],
                            center=dict(lat=active_site["lat"], lon=active_site["lon"]),
                            zoom=2.2,
                        )
                    else:
                        map_cfg = dict(
                            style="carto-darkmatter",
                            center=dict(lat=active_site["lat"], lon=active_site["lon"]),
                            zoom=2.2,
                        )
                    fig_map.update_layout(**{_map_layout_key: map_cfg})
                else:
                    fig_map.update_layout(
                        geo=dict(
                            bgcolor=SP["DEEP_SPACE_NAVY"],
                            showland=True,
                            landcolor=SP["NEBULA_NAVY"],
                            showocean=True,
                            oceancolor=SP["DEEP_SPACE_NAVY"],
                            center=dict(lat=active_site["lat"], lon=active_site["lon"]),
                        )
                    )

                fig_map.update_layout(
                    height=500,
                    margin=dict(l=0, r=0, t=0, b=0),
                    paper_bgcolor=SP["DEEP_SPACE_NAVY"],
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=0.01,
                        xanchor="left",
                        x=0.01,
                        bgcolor="rgba(8, 15, 30, 0.82)",
                        font=dict(color=SP["STARLIGHT_WHITE"], size=11),
                    ),
                )
                st.plotly_chart(fig_map, use_container_width=True)
                st.caption(
                    " **Category Marker Legend:** "
                    "Volcanic lava tubes (`#F07832`) |  Natural caves (`#A8754B`) | "
                    "Karst systems (`#45C4A1`) |  Glacial & subglacial (`#48BFE3`) | "
                    "Underground ice & permafrost (`#A78BFA`) |  Mines & underground labs (`#F1F5FA`)."
                )

            with prof_col:
                with st.container(border=True):
                    st.markdown(f"####  Candidate Site Profile: {active_site['name']}")
                    st.markdown(
                        evidence_badge_html(active_site["evidence_class"])
                        + f"**ID:** `{active_site['id']}` | **Category:** `{active_site['category']}`",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"- **Country & Region:** {active_site['country']} — {active_site['region']}\n"
                        f"- **Coordinates:** `{active_site['lat']:.4f}°, {active_site['lon']:.4f}°`\n"
                        f"- **Coordinate Precision & Uncertainty:** `{active_site['coord_precision']}` (±{active_site['coord_uncertainty_m']:.0f} m)\n"
                        f"- **Geological Classification:** {active_site['geological_classification']}\n"
                        f"- **Host Lithology & Minerals:** `{active_site['lithology']}` ({', '.join(active_site.get('minerals', []))})\n"
                        f"- **Formation Process:** {active_site['formation_process']}\n"
                        f"- **Known Dimensions:** Length `{format_property_value(active_site['geometry']['total_length_m'])}` | "
                        f"Max Width `{format_property_value(active_site['geometry']['max_width_m'])}` | "
                        f"Max Height `{format_property_value(active_site['geometry']['max_height_m'])}`\n"
                        f"- **Entrance Characteristics:** {format_property_value(active_site['geometry']['num_entrances'])} "
                        f"(Width `{format_property_value(active_site['geometry']['entrance_width_m'])}`, "
                        f"Drop `{format_property_value(active_site['geometry']['entrance_height_m'])}`)\n"
                        f"- **Data Availability:** {active_site['data_availability']}"
                    )

                    st.markdown("######  Traceable Dataset References & Source URLs")
                    for dref in active_site.get("dataset_references", []):
                        st.markdown(
                            f"- **{dref['provider']}:** [{dref['title']}]({dref['url']}) "
                            f"(`{dref['resolution']}`, {dref['date']})"
                        )

                    st.markdown("######  Scientific & Operational Data Limitations")
                    st.caption(active_site.get("limitations", "No additional limitations documented."))

        # ===================================================================
        # SUB-TAB 2: 3D CAVE AND LAVA TUBE GEOMETRY VIEWER (Section 4)
        # ===================================================================
        with sub_tab_3d:
            v_ctrl, v_main = st.columns([1.05, 2.95], gap="large")
            meta_3d = active_site.get("model_metadata", {})

            with v_ctrl:
                with st.container(border=True):
                    st.markdown("#####  3D Cave & Lava Tube Controls")
                    geom_source_mode = st.radio(
                        "3D Geometry Source",
                        [
                            "Selected Site Survey / Parametric Geometry",
                            "Upload Custom .GLB / .GLTF Cave Scan",
                            "Local Assets Models (assets/models/)",
                            "Empty State / Clear Model",
                        ],
                        index=0,
                    )

                    uploaded_glb_bytes = None
                    uploaded_glb_name = None
                    if geom_source_mode == "Upload Custom .GLB / .GLTF Cave Scan":
                        up_file = st.file_uploader(
                            "Upload 3D Cave/Lava Tube Mesh (.glb, .gltf)",
                            type=["glb", "gltf"],
                            help="Upload a LiDAR or photogrammetric 3D cave model.",
                        )
                        if up_file is not None:
                            uploaded_glb_bytes = up_file.read()
                            uploaded_glb_name = up_file.name

                    cross_sec_pct = st.slider(
                        "Axial Cross-Section Slice (%)",
                        min_value=15,
                        max_value=100,
                        value=100,
                        step=5,
                        help="Slice the 3D lava tube/cave along its longitudinal Z-axis to inspect internal arch cross-sections.",
                    )
                    show_axes = st.checkbox("Display 3D Coordinate Axes & Scale Grid", value=True)
                    show_wire = st.checkbox("Display Structural Wireframe Mesh", value=False)
                    force_demo = st.checkbox(
                        "Preview Synthetic Demonstration Geometry",
                        value=False,
                        help="Clearly labelled synthetic demonstration mode.",
                    )

                    st.divider()
                    st.markdown("######  3D Model Provenance Metadata")
                    st.markdown(
                        evidence_badge_html(
                            "DEMONSTRATION" if force_demo else meta_3d.get("geometry_class", "UNKNOWN")
                        ),
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"- **Model Source:** [{meta_3d.get('source', 'Unknown')}]({meta_3d.get('url', 'https://www.usgs.gov')})\n"
                        f"- **Original Units:** `{meta_3d.get('original_units', 'meters')}`\n"
                        f"- **Valid Physical Scale:** `{'Yes (Measurement Tool Active)' if (meta_3d.get('scale_valid') and not force_demo) else 'No (Conceptual Only)'}`\n"
                        f"- **Coordinate Reference (CRS):** `{meta_3d.get('crs', 'Local')}`\n"
                        f"- **Spatial Resolution:** `{meta_3d.get('resolution', 'N/A')}`\n"
                        f"- **Acquisition Date:** `{meta_3d.get('acquisition_date', 'N/A')}`"
                    )
                    st.caption(f"ℹ **Limitations:** {meta_3d.get('limitations', '-')}")

            with v_main:
                if geom_source_mode == "Empty State / Clear Model" or (
                    geom_source_mode == "Upload Custom .GLB / .GLTF Cave Scan" and not uploaded_glb_bytes
                ):
                    st.info(
                        " **Clean Empty 3D State:** No 3D geometry file is currently loaded. "
                        "Upload a `.glb`/`.gltf` cave scan on the left or switch to **'Selected Site Survey / Parametric Geometry'**."
                    )
                elif geom_source_mode == "Local Assets Models (assets/models/)":
                    local_models = viewer3d.available_models()
                    if local_models:
                        pick_m = st.selectbox("Select local .glb/.gltf model", local_models, format_func=lambda p: p.name)
                        viewer3d.show(viewer3d.model_viewer_html(pick_m), 580)
                    else:
                        st.info(
                            "No `.glb` or `.gltf` files found in `assets/models/`. Use **'Selected Site Survey / Parametric Geometry'** or upload a `.glb`/`.gltf` file."
                        )
                else:
                    if not active_site.get("has_measured_geometry") or force_demo:
                        st.warning(
                            " **Scientific Distinction Notice:** A full 3D laser scan is unavailable for this record (or synthetic preview is enabled). "
                            "The viewport below displays a **clearly labelled synthetic demonstration tunnel** and never implies that conceptual geometry represents the actual dimensions of a named cave."
                        )
                    html_cave = subsurface_3d_viewer_html(
                        active_site,
                        uploaded_glb_bytes=uploaded_glb_bytes,
                        uploaded_glb_name=uploaded_glb_name,
                        cross_section_pct=cross_sec_pct,
                        show_axes=show_axes,
                        show_wireframe=show_wire,
                        synthetic_demo_override=force_demo,
                    )
                    viewer3d.show(html_cave, 580)

        # ===================================================================
        # SUB-TAB 3: SUBSURFACE GEOMETRY, TERRAIN & ENVIRONMENTAL ANALYSIS (Sections 5 & 7)
        # ===================================================================
        with sub_tab_sci:
            st.markdown(f"####  Scientific Characterization & Evidence Classification: {active_site['name']}")
            st.caption(
                "Every property displays its documented value, unit, traceable source, calculation assumptions, and Evidence Classification (`MEASURED`, `DERIVED`, `INFERRED`, `DEMONSTRATION`, `UNKNOWN`). Missing properties are explicitly shown as `'Unknown / Not measured'` — never substituted with zero."
            )

            leg_html = "".join(
                evidence_badge_html(k, f"{k}: {v['definition']}") for k, v in EVIDENCE_CLASSES.items()
            )
            st.markdown(f"<div style='margin-bottom:12px;'>{leg_html}</div>", unsafe_allow_html=True)

            g_df = pd.DataFrame(flatten_site_properties_table(active_site, "geometry"))
            t_df = pd.DataFrame(flatten_site_properties_table(active_site, "terrain"))
            e_df = pd.DataFrame(flatten_site_properties_table(active_site, "environment"))

            sci_col1, sci_col2 = st.columns(2, gap="large")
            with sci_col1:
                st.markdown("##### 1. Subsurface Geometry Properties")
                st.dataframe(
                    g_df[["Property", "Value", "Unit", "Evidence Class", "Source / Dataset", "Method / Assumptions", "Confidence"]],
                    hide_index=True,
                    use_container_width=True,
                )
                st.markdown("##### 2. Internal Terrain & Navigability Properties")
                st.dataframe(
                    t_df[["Property", "Value", "Unit", "Evidence Class", "Source / Dataset", "Method / Assumptions", "Confidence"]],
                    hide_index=True,
                    use_container_width=True,
                )

            with sci_col2:
                st.markdown("##### 3. Subsurface Environmental & Shielding Characteristics")
                st.dataframe(
                    e_df[["Property", "Value", "Unit", "Evidence Class", "Source / Dataset", "Method / Assumptions", "Confidence"]],
                    hide_index=True,
                    use_container_width=True,
                )

                all_ev = (
                    list(g_df["Evidence Class"])
                    + list(t_df["Evidence Class"])
                    + list(e_df["Evidence Class"])
                )
                ev_counts = {k: all_ev.count(k) for k in EVIDENCE_CLASSES if all_ev.count(k) > 0}
                fig_ev = go.Figure(
                    data=[
                        go.Pie(
                            labels=list(ev_counts.keys()),
                            values=list(ev_counts.values()),
                            hole=0.58,
                            marker=dict(colors=[EVIDENCE_CLASSES[k]["color"] for k in ev_counts]),
                        )
                    ]
                )
                fig_ev.update_layout(
                    title=f"Evidence Provenance Breakdown ({len(all_ev)} Subsurface Properties)",
                    template="plotly_dark",
                    paper_bgcolor=SP["DEEP_SPACE_NAVY"],
                    plot_bgcolor=SP["NEBULA_NAVY"],
                    height=290,
                    margin=dict(l=20, r=20, t=45, b=20),
                )
                st.plotly_chart(fig_ev, use_container_width=True)

        # ===================================================================
        # SUB-TAB 4: EARTH VS MOON/MARS SUBSURFACE COMPARISON (Section 6)
        # ===================================================================
        with sub_tab_planet:
            st.markdown("####  Earth vs. Moon vs. Mars Subsurface Comparative Planetology")
            st.info(
                " **Fundamental Planetary Physics Distinction:** Terrestrial caves and lava tubes provide high-fidelity analogues for basaltic roof stratigraphy, skylight collapse mechanics, LiDAR/GPR sensing, and chemolithoautotrophic biosignatures, **but cannot reproduce Lunar (1.62 m/s²) or Martian (3.72 m/s²) gravity, lunar hard vacuum, Martian 6-mbar CO₂ atmosphere, primary Galactic Cosmic Ray (GCR) heavy-ion spectra, or cryogenic polar cold-trapping (<110 K).**"
            )

            pc1, pc2, pc3 = st.columns(3)
            with pc1:
                cmp_earth_id = st.selectbox(
                    "Terrestrial Subsurface Analogue",
                    [s["id"] for s in filtered_sites],
                    index=[s["id"] for s in filtered_sites].index(active_sub_id),
                    format_func=lambda i: site_by_id[i]["name"],
                )
                cmp_earth = site_by_id[cmp_earth_id]
            with pc2:
                moon_refs = PLANETARY_SUBSURFACE_REFERENCES["Moon"]
                cmp_moon_idx = st.selectbox(
                    "Lunar Subsurface Reference Feature",
                    range(len(moon_refs)),
                    format_func=lambda i: moon_refs[i]["name"],
                )
                cmp_moon = moon_refs[cmp_moon_idx]
            with pc3:
                mars_refs = PLANETARY_SUBSURFACE_REFERENCES["Mars"]
                cmp_mars_idx = st.selectbox(
                    "Martian Subsurface Reference Feature",
                    range(len(mars_refs)),
                    format_func=lambda i: mars_refs[i]["name"],
                )
                cmp_mars = mars_refs[cmp_mars_idx]

            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                with st.container(border=True):
                    st.markdown(f"#####  {cmp_earth['name'].split(' — ')[0]}")
                    st.caption(f"{cmp_earth['region']}, {cmp_earth['country']} | `9.81 m/s² (1.0g)`")
                    st.markdown(
                        f"- **Evidence Status:** {cmp_earth['data_availability']}\n"
                        f"- **Max Span × Height:** `{format_property_value(cmp_earth['geometry']['max_width_m'])}` × `{format_property_value(cmp_earth['geometry']['max_height_m'])}`\n"
                        f"- **Internal Temp:** `{format_property_value(cmp_earth['environment']['temp_mean_c'])}`"
                    )
            with sc2:
                with st.container(border=True):
                    st.markdown(f"#####  {cmp_moon['name'].split(' — ')[0]}")
                    st.caption(f"{cmp_moon['region']} (`{cmp_moon['lat']:.2f}°, {cmp_moon['lon']:.2f}°`) | `1.62 m/s² (0.165g)`")
                    st.markdown(
                        f"- **Observation vs Inference:** {cmp_moon['observation_status']}\n"
                        f"- **Measured Skylight:** `{cmp_moon['skylight_diameter_m']:.0f} m` wide × `{cmp_moon['skylight_depth_m']:.0f} m` deep\n"
                        f"- **Source:** [{cmp_moon['source_title']}]({cmp_moon['source_url']})"
                    )
            with sc3:
                with st.container(border=True):
                    st.markdown(f"#####  {cmp_mars['name'].split(' — ')[0]}")
                    st.caption(f"{cmp_mars['region']} (`{cmp_mars['lat']:.2f}°, {cmp_mars['lon']:.2f}°`) | `3.72 m/s² (0.379g)`")
                    st.markdown(
                        f"- **Observation vs Inference:** {cmp_mars['observation_status']}\n"
                        f"- **Measured Skylight:** `{cmp_mars['skylight_diameter_m']:.0f} m` wide × `{cmp_mars['skylight_depth_m']:.0f} m` deep\n"
                        f"- **Source:** [{cmp_mars['source_title']}]({cmp_mars['source_url']})"
                    )

            cmp_rows, cmp_num = build_earth_moon_mars_comparison(cmp_earth, cmp_moon, cmp_mars)
            st.markdown("#####  10-Dimension Comparative Matrix (Measured vs. Inferred Evidence)")
            st.dataframe(pd.DataFrame(cmp_rows), hide_index=True, use_container_width=True)

            viz_col1, viz_col2 = st.columns([1.1, 1.0], gap="large")
            with viz_col1:
                fig_cross = plot_cross_section_scale_diagram(cmp_earth, cmp_moon, cmp_mars)
                # Keep the title separate from the long trace labels. The legend is
                # placed beneath the plot so it cannot collide with the heading.
                fig_cross.update_layout(
                    title=dict(
                        text="Tunnel cross-section scale comparison",
                        x=0.02,
                        xanchor="left",
                        y=0.98,
                        font=dict(size=15),
                    ),
                    legend=dict(
                        orientation="h",
                        yanchor="top",
                        y=-0.24,
                        xanchor="left",
                        x=0,
                        font=dict(size=9),
                        bgcolor="rgba(8, 15, 30, 0.65)",
                    ),
                    height=470,
                    margin=dict(l=65, r=18, t=75, b=125),
                    title_pad=dict(t=8),
                )
                st.plotly_chart(fig_cross, use_container_width=True)
            with viz_col2:
                ew_num = float(cmp_num["earth_width_m"]) if cmp_num["earth_width_m"] is not None else None
                eh_num = float(cmp_num["earth_height_m"]) if cmp_num["earth_height_m"] is not None else None
                ed_num = float(cmp_num["earth_entrance_drop_m"]) if cmp_num["earth_entrance_drop_m"] is not None else None
                fig_bar = go.Figure(
                    data=[
                        go.Bar(
                            name=f"Earth ({cmp_earth['name'].split(' — ')[0]} — MEASURED)",
                            x=["Entrance<br>span", "Pit<br>depth", "Tube<br>width", "Arch<br>height"],
                            y=[
                                (float(cmp_earth["geometry"]["entrance_width_m"]["value"]) if cmp_earth["geometry"]["entrance_width_m"]["value"] is not None else None),
                                ed_num,
                                ew_num,
                                eh_num,
                            ],
                            marker_color=SP["AURORA_TEAL"],
                        ),
                        go.Bar(
                            name=f"Moon ({cmp_moon['name'].split(' — ')[0]} — Skylight Measured / Tube Inferred)",
                            x=["Entrance<br>span", "Pit<br>depth", "Tube<br>width", "Arch<br>height"],
                            y=[
                                cmp_num["moon_skylight_w_m"],
                                cmp_num["moon_depth_m"],
                                cmp_num["moon_pred_w_m"],
                                cmp_num["moon_pred_h_m"],
                            ],
                            marker_color=SP["GALAXY_PURPLE"],
                        ),
                        go.Bar(
                            name=f"Mars ({cmp_mars['name'].split(' — ')[0]} — Skylight Measured / Tube Inferred)",
                            x=["Entrance<br>span", "Pit<br>depth", "Tube<br>width", "Arch<br>height"],
                            y=[
                                cmp_num["mars_skylight_w_m"],
                                cmp_num["mars_depth_m"],
                                cmp_num["mars_pred_w_m"],
                                cmp_num["mars_pred_h_m"],
                            ],
                            marker_color=SP["VOLCANIC_ORANGE"],
                        ),
                    ]
                )
                fig_bar.update_layout(
                    barmode="group",
                    title=dict(text="Geometric dimensions (m)", x=0.02, xanchor="left", font=dict(size=15)),
                    template="plotly_dark",
                    paper_bgcolor=SP["DEEP_SPACE_NAVY"],
                    plot_bgcolor=SP["NEBULA_NAVY"],
                    height=470,
                    legend=dict(
                        orientation="h",
                        yanchor="top",
                        y=-0.30,
                        xanchor="left",
                        x=0,
                        font=dict(size=9),
                        bgcolor="rgba(8, 15, 30, 0.65)",
                    ),
                    xaxis=dict(tickangle=0, automargin=True, title="Dimension"),
                    yaxis=dict(title="Measurement (m)", rangemode="tozero"),
                    margin=dict(l=55, r=18, t=75, b=140),
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            st.caption(
                "Dimensions are shown only where values are available. Lunar and Martian tube dimensions may be inferred from skylight observations; they are not direct measurements of subsurface tubes."
            )

        # ===================================================================
        # SUB-TAB 5: MISSION SUITABILITY & MULTI-CANDIDATE COMPARISON (Sections 8 & 9)
        # ===================================================================
        with sub_tab_suit:
            st.markdown(f"####  Subsurface Mission Suitability & Multi-Site Comparison ({sub_obj})")
            st.caption(
                "Analogue Fidelity, Mission Suitability, and Transferability are evaluated separately and never collapsed into a single unexplained score. High analogue fidelity does not automatically imply high operational suitability."
            )

            ms1, ms2, ms3, ms4 = st.columns(4)
            ms1.metric(
                "Analogue Fidelity",
                f"{active_eval['analogue_fidelity']:.2f}",
                f"5–95% CI: {active_eval['fidelity_interval'][0]:.2f}–{active_eval['fidelity_interval'][1]:.2f}",
            )
            ms2.metric(
                "Mission Suitability",
                f"{active_eval['mission_suitability']:.2f}",
                "Access, Safety, Slope & Roughness",
            )
            ms3.metric(
                "Transferability",
                f"{active_eval['transferability']:.2f}",
                f"{t['body']} Gravity/Vacuum Adjusted",
            )
            ms4.metric(
                "Data Coverage",
                f"{active_eval['data_coverage']:.0%}",
                f"{len(active_eval['missing_properties'])} unmeasured props",
            )

            with st.expander("Score Calculation Methodology, Weightings & Scientific Limitations", expanded=False):
                st.markdown(
                    f"- **Calculation Methodology:** {active_eval['methodology_note']}\n"
                    f"- **Planetary Physics & Gravity Scaling Constraint:** {active_eval['gravity_sensitivity_note']}\n"
                    f"- **Fidelity Axis Weights (`{sub_obj}`):** `{active_eval['fidelity_weights']}`\n"
                    f"- **Suitability Axis Weights (`{sub_obj}`):** `{active_eval['suitability_weights']}`\n"
                    f"- **Missing / Unmeasured Properties (Excluded from denominator, never penalized as zero):** "
                    f"`{', '.join(active_eval['missing_properties']) if active_eval['missing_properties'] else 'None (Complete)'}`"
                )

            st.markdown("#####  Compare Multiple Terrestrial Subsurface Sites")
            default_cmp_ids = [s["id"] for s in filtered_sites[: min(4, len(filtered_sites))]]
            if active_sub_id not in default_cmp_ids:
                default_cmp_ids[0] = active_sub_id

            cmp_site_ids = st.multiselect(
                "Select two or more terrestrial subsurface sites to compare side-by-side",
                [s["id"] for s in filtered_sites],
                default=default_cmp_ids,
                format_func=lambda i: f"{site_by_id[i]['name'].split(' — ')[0]} ({site_by_id[i]['category']})",
            )

            if len(cmp_site_ids) < 2:
                st.info("Select at least 2 terrestrial subsurface sites above to generate the comparative assessment.")
            else:
                cmp_evals = [eval_by_id[i] for i in cmp_site_ids]
                best_eval = max(
                    cmp_evals,
                    key=lambda e: 0.40 * e["analogue_fidelity"] + 0.40 * e["mission_suitability"] + 0.20 * e["transferability"],
                )
                best_site = site_by_id[best_eval["site_id"]]

                st.success(
                    f" **Recommended Site for '{sub_obj}' ({t['body']} Target): {best_site['name']}** — "
                    f"Combines **Analogue Fidelity `{best_eval['analogue_fidelity']:.2f}`**, **Operational Mission Suitability `{best_eval['mission_suitability']:.2f}`**, "
                    f"and **Transferability `{best_eval['transferability']:.2f}`** with **`{best_eval['data_coverage']:.0%}`** measured property coverage "
                    f"({best_site['category']}, `{best_site['lithology']}`)."
                )

                df_multi = pd.DataFrame(
                    [
                        {
                            "Site Name": site_by_id[i]["name"].split(" — ")[0],
                            "Category": site_by_id[i]["category"],
                            "Geology": site_by_id[i]["lithology"],
                            "Max Width × Height (m)": (
                                f"{format_property_value(site_by_id[i]['geometry']['max_width_m'])} × "
                                f"{format_property_value(site_by_id[i]['geometry']['max_height_m'])}"
                            ),
                            "Mean Temp (°C)": format_property_value(site_by_id[i]["environment"]["temp_mean_c"]),
                            "Evidence Class": site_by_id[i]["evidence_class"],
                            "Analogue Fidelity": eval_by_id[i]["analogue_fidelity"],
                            "Mission Suitability": eval_by_id[i]["mission_suitability"],
                            "Transferability": eval_by_id[i]["transferability"],
                            "5–95% CI": f"{eval_by_id[i]['fidelity_interval'][0]:.2f}–{eval_by_id[i]['fidelity_interval'][1]:.2f}",
                            "Data Coverage": f"{eval_by_id[i]['data_coverage']:.0%}",
                            "Missing Properties": len(eval_by_id[i]["missing_properties"]),
                        }
                        for i in cmp_site_ids
                    ]
                )
                st.dataframe(df_multi, hide_index=True, use_container_width=True)

                ch1, ch2 = st.columns(2, gap="large")
                with ch1:
                    fig_scores = go.Figure(
                        data=[
                            go.Bar(
                                name="Analogue Fidelity",
                                x=[site_by_id[i]["name"].split(" — ")[0] for i in cmp_site_ids],
                                y=[eval_by_id[i]["analogue_fidelity"] for i in cmp_site_ids],
                                marker_color=SP["GALAXY_PURPLE"],
                            ),
                            go.Bar(
                                name="Mission Suitability (Ops/Safety)",
                                x=[site_by_id[i]["name"].split(" — ")[0] for i in cmp_site_ids],
                                y=[eval_by_id[i]["mission_suitability"] for i in cmp_site_ids],
                                marker_color=SP["AURORA_TEAL"],
                            ),
                            go.Bar(
                                name="Transferability (Physics Scaled)",
                                x=[site_by_id[i]["name"].split(" — ")[0] for i in cmp_site_ids],
                                y=[eval_by_id[i]["transferability"] for i in cmp_site_ids],
                                marker_color=SP["COSMIC_CYAN"],
                            ),
                        ]
                    )
                    fig_scores.update_layout(
                        barmode="group",
                        title=f"Separate Score Comparison — {sub_obj}",
                        yaxis=dict(range=[0, 1.05], title="Score (0–1)"),
                        template="plotly_dark",
                        paper_bgcolor=SP["DEEP_SPACE_NAVY"],
                        plot_bgcolor=SP["NEBULA_NAVY"],
                        height=370,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    )
                    st.plotly_chart(fig_scores, use_container_width=True)

                with ch2:
                    fig_rad = go.Figure()
                    rad_axes = ["Geology", "Geometry", "Terrain", "Ice/Volatiles", "Shielding", "Accessibility"]
                    for idx_c, cid in enumerate(cmp_site_ids):
                        ev = eval_by_id[cid]
                        fd = ev["fidelity_dimensions"]
                        sd = ev["suitability_dimensions"]
                        vals = [
                            fd.get("geology") or 0.0,
                            fd.get("geometry") or 0.0,
                            fd.get("terrain") or 0.0,
                            fd.get("ice_env") or 0.0,
                            fd.get("shielding") or 0.0,
                            sd.get("access") or 0.0,
                        ]
                        vals.append(vals[0])
                        fig_rad.add_trace(
                            go.Scatterpolar(
                                r=vals,
                                theta=rad_axes + [rad_axes[0]],
                                fill="toself",
                                name=site_by_id[cid]["name"].split(" — ")[0],
                            )
                        )
                    fig_rad.update_layout(
                        title="Secondary Multi-Axis Radar Overview",
                        polar=dict(radialaxis=dict(visible=True, range=[0, 1.0])),
                        template="plotly_dark",
                        paper_bgcolor=SP["DEEP_SPACE_NAVY"],
                        height=370,
                    )
                    st.plotly_chart(fig_rad, use_container_width=True)

        # ===================================================================
        # SUB-TAB 6: DATA SOURCES, SCIENTIFIC INTEGRITY & EXPORT REPORTS (Sections 10 & 12)
        # ===================================================================
        with sub_tab_export:
            st.markdown("####  Traceable Data Sources, Provider Adapters & Scientific Assessment Exports")

            st.markdown("##### 1. Traceable Planetary & Speleological Dataset Provenance Registry")
            st.dataframe(pd.DataFrame(SUBSURFACE_DATASET_REGISTRY), hide_index=True, use_container_width=True)

            st.markdown("##### 2. Configurable External Provider Adapters (Environment Variable Status)")
            st.caption(
                "All external APIs are configurable via environment variables (`NASA_PDS_API_ENDPOINT`, `USGS_SCIENCEBASE_TOKEN`, `ESA_PSA_API_KEY`, `ASTERRIS_OFFLINE_ONLY`) and gracefully fall back to embedded survey catalogs so the workspace never blocks offline."
            )
            st.dataframe(pd.DataFrame(get_provider_adapter_status()), hide_index=True, use_container_width=True)

            st.divider()
            st.markdown(f"##### 3. Export Subsurface Analogue Scientific Assessment Report ({active_site['name']})")
            st.caption(
                "Generated reports are explicitly labelled as **Scientific Assessments & Proposed Field-Study Outputs (Not Official NASA Evaluations)**."
            )

            default_moon_ref = PLANETARY_SUBSURFACE_REFERENCES["Moon"][0]
            default_mars_ref = PLANETARY_SUBSURFACE_REFERENCES["Mars"][0]
            report_md = generate_subsurface_assessment_report_md(
                active_site, active_eval, default_moon_ref, default_mars_ref
            )
            geojson_str = generate_subsurface_geojson(filtered_sites, sub_obj, t["body"])

            csv_rows = []
            for s in filtered_sites:
                ev = eval_by_id[s["id"]]
                csv_rows.append(
                    {
                        "site_id": s["id"],
                        "site_name": s["name"],
                        "country": s["country"],
                        "region": s["region"],
                        "lat": s["lat"],
                        "lon": s["lon"],
                        "coord_precision": s["coord_precision"],
                        "category": s["category"],
                        "lithology": s.get("lithology"),
                        "evidence_class": s.get("evidence_class"),
                        "mission_objective": sub_obj,
                        "target_body": t["body"],
                        "analogue_fidelity": ev["analogue_fidelity"],
                        "mission_suitability": ev["mission_suitability"],
                        "transferability": ev["transferability"],
                        "data_coverage": ev["data_coverage"],
                        "confidence_interval_5_95": f"{ev['fidelity_interval'][0]:.2f}-{ev['fidelity_interval'][1]:.2f}",
                        "report_classification": "Scientific Assessment / Proposed Field-Study Output (Not an Official NASA Evaluation)",
                    }
                )
            df_export_csv = pd.DataFrame(csv_rows)

            ex1, ex2, ex3 = st.columns(3)
            with ex1:
                st.download_button(
                    "Download Assessment Report (.MD / Print-Ready)",
                    data=report_md.encode("utf-8"),
                    file_name=f"{active_site['id']}_subsurface_scientific_assessment.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with ex2:
                st.download_button(
                    "Export Evaluated Subsurface Catalog (.CSV)",
                    data=df_export_csv.to_csv(index=False).encode("utf-8"),
                    file_name=f"asterris_subsurface_{sub_obj.lower().replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with ex3:
                st.download_button(
                    "Export Subsurface Analogue GIS Layer (.GeoJSON)",
                    data=geojson_str.encode("utf-8"),
                    file_name="asterris_subsurface_analogues.geojson",
                    mime="application/geo+json",
                    use_container_width=True,
                )

            with st.expander("Preview Generated Subsurface Analogue Assessment Report", expanded=False):
                st.markdown(report_md)