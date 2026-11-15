"""Workspace 02: Planetary Explorer — Overhauled with Global ML Earth Analog Discovery,
Clickable Instrument Reference Fingerprints (MOLA/LOLA, CRISM/M3, HiRISE/CTX/LROC, THEMIS/Diviner, SHARAD/Mini-RF),
and Schematic Relief Measurement with Explicit Color-Range Legends.

Drop-in replacement for `views/02_Planetary_Explorer.py` in Asterris (`VishwaPatel06/Asterris`).
"""

from __future__ import annotations

from typing import Any, List
import pandas as pd
import streamlit as st

from components import charts, theme, viewer3d
from components.context import sidebar
from config import palette as P
from config.data_catalog import LAYERS
from data_sources import manager
from data_sources.global_earth_analogs import (
    PLANETARY_INSTRUMENT_SOURCES,
    SOIL_TYPES,
    SURROUNDING_MATERIALS,
    TERRAIN_TYPES,
    WEATHER_REGIMES,
    fetch_live_earth_point_climate,
)
from data_sources.planetary import registry
from geospatial import terrain
from scientific_engine import dem as demlib
from scientific_engine.planetary_ml import (
    build_instrument_fingerprint,
    run_global_ml_analog_search,
)


def _extract_ramp_hex_list(ramp: Any) -> List[str]:
    """Extracts flat hex color strings whether a palette ramp is a list of strings or [pos, hex] pairs."""
    if not ramp:
        return ["#101C32", "#48BFE3", "#F1F5FA"]
    out: List[str] = []
    for item in ramp:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append(str(item[-1]))
        elif isinstance(item, (list, tuple)) and len(item) == 1:
            out.append(str(item[0]))
        else:
            out.append(str(item))
    return out


# 1. Context & Header
ctx = sidebar("explorer")
theme.header(
    "Planetary Explorer",
    "Configure mission parameters to discover global Earth analogs via ML, inspect 3D planetary & terrestrial terrain, and compare against active orbital instrument references.",
    "Workspace 02",
    "explorer",
)
t = ctx["target"]

# Custom subtle styling for cleaner cards, clickable instrument pills, and color legends
st.markdown(
    """
    <style>
    div[data-testid="metric-container"] {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 12px 16px;
        border-radius: 8px;
    }
    .color-legend-box {
        background: rgba(16, 28, 50, 0.78);
        border: 1px solid rgba(168, 184, 206, 0.18);
        border-radius: 8px;
        padding: 10px 12px;
        margin-top: -6px;
        margin-bottom: 12px;
        font-size: 0.80rem;
    }
    .color-bar {
        height: 10px;
        border-radius: 5px;
        margin-bottom: 6px;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .inst-active-banner {
        background: linear-gradient(90deg, rgba(72, 191, 227, 0.16), rgba(167, 139, 250, 0.12));
        border-left: 4px solid #48BFE3;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 12px;
        font-size: 0.86rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def body_grid(body: str, tid: str, morph: str, relief: float, rough: float, upload_id: str | None):
    """Measured DEM if uploaded for this body, else a physics-calibrated schematic relief surface."""
    if upload_id:
        name, raw = manager.raster_bytes(upload_id)
        h, cell, msg = demlib.load_uploaded_dem(name, raw, n=160)
        if h is not None:
            return h, cell, False, f"Measured DEM: {name} ({msg})"
    h, cell = demlib.synthetic_dem(morph, 128, 20000.0, max(relief, 50.0), rough)
    return h, cell, True, f"Schematic {morph} relief model ({max(relief, 50.0):.0f} m target relief)"


# Pre-load DEM once so all tabs share it cleanly
ups = manager.user_rasters(t["body"])
upload_id = ups[0]["id"] if ups else None
h, cell, is_schematic, dem_label = body_grid(
    t["body"],
    t["id"],
    t["morphology"],
    t["relief_m"] or 200.0,
    t["roughness"] or 0.3,
    upload_id,
)

# 2. Top-Level Target Summary Bar
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Target Body & Site", f"{t['body']} — {t['name'].split(' (')[0]}", f"{t['lat']:.2f}°, {t['lon']:.2f}°")
kpi2.metric("Target Relief", f"{t['relief_m']:.0f} m" if t["relief_m"] is not None else "200 m (Schematic)", t["morphology"].capitalize())
kpi3.metric("Mean Surface Temp", f"{t['temp_mean_c']} °C" if t["temp_mean_c"] is not None else "N/A")
kpi4.metric(
    "Surface Model Basis",
    f"{t['data_quality']:.0%}" if t["data_quality"] is not None else "Schematic",
    "Measured DEM" if not is_schematic else "Measured Schematic Relief",
)

st.write("")

# 3. Main Navigation Tabs
tab_3d, tab_layers, tab_terrain = st.tabs(
    ["3D Surface & Models", "Layers & Fingerprint", "Terrain Derivatives"]
)

# ==========================================
# TAB 1: 3D SURFACE & GLOBAL ML ANALOG DISCOVERY
# ==========================================
with tab_3d:
    st.markdown(
        "#### Mission Parameter Configuration & Global Earth Analog ML Search"
    )
    st.caption(
        f"Configure mission terrain, thermal, weather, soil, mineralogical, and coordinate boundary parameters. "
        f"The multi-dimensional ML similarity engine evaluates locations across the **entire Earth** against **{t['name']} ({t['body']})**."
    )

    with st.expander("Configure Mission Parameters (Terrain, Temperature, Weather, Soil, Materials, Area & Exaggeration)", expanded=True):
        p_col1, p_col2, p_col3, p_col4 = st.columns(4)

        with p_col1:
            default_terrain_idx = (
                TERRAIN_TYPES.index(t["morphology"])
                if t.get("morphology") in TERRAIN_TYPES
                else 0
            )
            sel_terrain = st.selectbox(
                "Mission Terrain / Morphology",
                TERRAIN_TYPES,
                index=default_terrain_idx,
                help="Filter and weight terrestrial analog search by primary landform morphology.",
            )
            sel_weather = st.selectbox(
                "Weather / Aridity Regime",
                WEATHER_REGIMES,
                index=0,
                help="Select atmospheric precipitation and aridity regime on Earth.",
            )

        with p_col2:
            sel_soil = st.selectbox(
                "Soil / Regolith Simulant Class",
                SOIL_TYPES,
                index=0,
                help="Mechanical and chemical soil/regolith family.",
            )
            default_mats = [m for m in (t.get("minerals") or ["basalt", "plagioclase"]) if m in SURROUNDING_MATERIALS]
            if not default_mats:
                default_mats = ["basalt", "plagioclase", "pyroxene"]
            sel_materials = st.multiselect(
                "Surrounding Materials & Minerals",
                SURROUNDING_MATERIALS,
                default=default_mats,
                help="Target host-rock and surrounding mineralogical signatures.",
            )

        with p_col3:
            temp_range_c = st.slider(
                "Earth Mean Temperature Window (°C)",
                min_value=-50.0,
                max_value=45.0,
                value=(-30.0, 35.0),
                step=1.0,
                help="Acceptable mean annual surface temperature range for the terrestrial field campaign.",
            )
            max_slope_deg = st.slider(
                "Max Traversable Slope (°)",
                min_value=2.0,
                max_value=45.0,
                value=float(max(15.0, min(40.0, (t.get("slope_deg") or 12.0) + 10.0))),
                step=1.0,
            )

        with p_col4:
            exag = st.slider(
                "3D Vertical Exaggeration",
                min_value=0.5,
                max_value=5.0,
                value=2.0,
                step=0.25,
                help="Controls vertical relief amplification in the 3D Globe & Terrain viewport.",
            )
            target_roughness = st.slider(
                "Target Surface Roughness (0–1)",
                min_value=0.05,
                max_value=1.0,
                value=float(t.get("roughness") or 0.45),
                step=0.05,
            )

        # Area Scope & Additional Parameters Row
        a_col1, a_col2, a_col3 = st.columns([1.2, 1.8, 1.0])
        with a_col1:
            area_mode = st.radio(
                "Search Area Scope",
                ["Global (All Over Earth)", "Custom Coordinate Bounding Box"],
                horizontal=True,
            )
        with a_col2:
            if area_mode == "Custom Coordinate Bounding Box":
                b1, b2, b3, b4 = st.columns(4)
                lat_min = b1.number_input("Min Lat (°S/N)", min_value=-90.0, max_value=90.0, value=-45.0, step=5.0)
                lat_max = b2.number_input("Max Lat (°S/N)", min_value=-90.0, max_value=90.0, value=75.0, step=5.0)
                lon_min = b3.number_input("Min Lon (°W/E)", min_value=-180.0, max_value=180.0, value=-160.0, step=5.0)
                lon_max = b4.number_input("Max Lon (°W/E)", min_value=-180.0, max_value=180.0, value=165.0, step=5.0)
                lat_bounds = (min(lat_min, lat_max), max(lat_min, lat_max))
                lon_bounds = (min(lon_min, lon_max), max(lon_min, lon_max))
            else:
                lat_bounds = (-90.0, 90.0)
                lon_bounds = (-180.0, 180.0)
                st.caption("🌐 Scanning all 7 continents (-90° to +90° Lat, -180° to +180° Lon) across 30+ global analogs & seed pools.")

        with a_col3:
            subsurface_priority = st.slider(
                "Subsurface / Cave Priority",
                min_value=0.0,
                max_value=1.0,
                value=float(t.get("caves") or 0.30),
                step=0.05,
            )

    mission_params = {
        "terrain": sel_terrain,
        "weather": sel_weather,
        "soil": sel_soil,
        "materials": sel_materials,
        "temp_range_c": temp_range_c,
        "target_temp_c": float(t.get("temp_mean_c") or 10.0),
        "max_slope_deg": max_slope_deg,
        "target_roughness": target_roughness,
        "target_relief_m": float(t.get("relief_m") or 300.0),
        "water_ice_target": float(t.get("water_ice") or 0.30),
        "subsurface_priority": subsurface_priority,
        "area_mode": area_mode,
        "lat_bounds": lat_bounds,
        "lon_bounds": lon_bounds,
    }

    ml_results = run_global_ml_analog_search(t, ctx["cand_list"], mission_params)

    if not ml_results:
        st.info("No Earth locations fall inside the current coordinate bounding box. Expand the latitude/longitude limits or switch to 'Global (All Over Earth)'.")
    else:
        st.markdown(
            f"##### ML Recommended Global Earth Locations ({len(ml_results)} Worldwide Matches vs. {t['name']})"
        )
        st.caption(
            "Select any row in the table below (or use the location selector) to fly directly to that location's 3D Globe & Terrain view."
        )

        df_ml = pd.DataFrame(
            [
                {
                    "Rank": r["rank"],
                    "Location Name": r["name"],
                    "Country / Region": f"{r['country']} ({r['continent']})",
                    "Coordinates": f"{r['lat']:.3f}°, {r['lon']:.3f}°",
                    "ML Similarity": f"{r['ml_similarity']:.1%}",
                    "Similarities (vs Target & Params)": r["similarities_text"],
                    "Dissimilarities & Planetary Gaps": r["dissimilarities_text"],
                    "Other Mission Factors": r["other_factors_text"],
                    "Terrain": r["morphology"],
                    "Soil / Regolith": r["soil_type"],
                    "Weather": r["weather_regime"],
                    "Mean Temp (°C)": round(r["temp_mean_c"], 1),
                    "Slope (°)": round(r["slope_deg"], 1),
                    "Relief (m)": round(r["relief_m"], 0),
                }
                for r in ml_results
            ]
        )

        table_event = st.dataframe(
            df_ml,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="ml_global_table_select",
        )

        selected_row_idx = 0
        if table_event and hasattr(table_event, "selection") and table_event.selection.get("rows"):
            selected_row_idx = int(table_event.selection["rows"][0])

        ctrl_col, view_col = st.columns([1.05, 3.15], gap="large")

        with ctrl_col:
            with st.container(border=True):
                st.markdown("##### 🌍 3D Globe & Terrain Controls")
                world = st.radio(
                    "Active 3D World View",
                    ["Earth (Selected Analog)", f"{t['body']} (Target Reference)", "Dual Split View (Earth + Target)"],
                    index=0,
                    help="Switch between the selected Earth analog location (with Globe & Terrain modes as in NASA Trek), the target planetary body, or side-by-side.",
                )

                site_ids = [r["id"] for r in ml_results]
                by_id = {r["id"]: r for r in ml_results}
                picked_id = st.selectbox(
                    "Selected Recommended Location",
                    site_ids,
                    index=min(selected_row_idx, len(site_ids) - 1),
                    format_func=lambda i: f"#{by_id[i]['rank']} {by_id[i]['name'].split(' — ')[0]} ({by_id[i]['ml_similarity']:.0%})",
                )
                sel_site = by_id[picked_id]
                st.session_state["explorer_selected_earth_site"] = sel_site

                start_mode = st.radio(
                    "Initial 3D Camera Mode",
                    ["globe", "terrain"],
                    index=0,
                    horizontal=True,
                    format_func=lambda m: "🌐 Globe View (Full Sphere + Go-To)" if m == "globe" else "⛰️ 3D Terrain Mesh",
                    help="The 3D viewer includes top-right 'Globe' and 'Terrain' buttons, 'Go to' selector, 'Auto-rotate', and 'Reset view'.",
                )
                zoom_level = st.slider("Terrain Tile Zoom Level", min_value=8, max_value=16, value=12)
                show_siblings = st.checkbox("Show all recommended pins on Globe", value=True)

                if st.button("🌦️ Fetch Live Open-Meteo / ERA5 Climate", use_container_width=True):
                    live_cl = fetch_live_earth_point_climate(sel_site["lat"], sel_site["lon"])
                    if live_cl:
                        st.success(
                            f"Live ERA5 @ `{sel_site['lat']:.2f}, {sel_site['lon']:.2f}`: "
                            f"Mean **{live_cl['temp_mean_c']} °C** (Min {live_cl['temp_min_c']} °C / Max {live_cl['temp_max_c']} °C)"
                        )
                    else:
                        st.info(
                            f"Using curated climatology for {sel_site['name'].split(' — ')[0]}: "
                            f"Mean **{sel_site['temp_mean_c']} °C** ({sel_site['temp_min_c']} to {sel_site['temp_max_c']} °C)."
                        )

                st.divider()
                st.markdown(f"**📍 {sel_site['name']}**")
                st.caption(
                    f"`{sel_site['lat']:.3f}°, {sel_site['lon']:.3f}°` | {sel_site['country']}  \n"
                    f"**ML Similarity:** `{sel_site['ml_similarity']:.1%}` (Cosine `{sel_site['cosine_similarity']:.2f}`)  \n"
                    f"**Analog For:** {sel_site['analog_for']}  \n"
                    f"**Source:** [{sel_site['source_title']}]({sel_site['source_url']})"
                )
                st.markdown(theme.badge(sel_site.get("provenance_class", "real")), unsafe_allow_html=True)

        with view_col:
            earth_markers = [
                {
                    "label": sel_site["name"].split(" — ")[0],
                    "lat": sel_site["lat"],
                    "lon": sel_site["lon"],
                    "color": P.CELESTIAL_MINT,
                    "main": True,
                    "bbox": sel_site.get("bbox"),
                }
            ]
            if show_siblings:
                for x in ml_results[:25]:
                    if x["id"] != sel_site["id"]:
                        earth_markers.append(
                            {
                                "label": f"#{x['rank']} {x['name'].split(' — ')[0]}",
                                "lat": x["lat"],
                                "lon": x["lon"],
                                "color": P.COSMIC_CYAN,
                                "bbox": x.get("bbox"),
                            }
                        )

            hs = demlib.downsample(h, 129)
            target_grid = viewer3d.grid_payload(hs, cell * (h.shape[0] / 129), is_schematic, dem_label)
            target_markers = [
                {
                    "label": t["name"].split(" (")[0],
                    "lat": t["lat"],
                    "lon": t["lon"],
                    "color": P.CELESTIAL_MINT,
                    "main": True,
                }
            ]
            if show_siblings:
                others = [x for x in ctx["catalog"]["targets"] if x["body"] == t["body"] and x["id"] != t["id"]]
                for x in others:
                    target_markers.append(
                        {
                            "label": x["name"].split(" (")[0],
                            "lat": x["lat"],
                            "lon": x["lon"],
                            "color": P.COSMIC_CYAN,
                        }
                    )

            if world.startswith("Earth"):
                html_earth = viewer3d.explorer_html(
                    "Earth",
                    sel_site["lat"],
                    sel_site["lon"],
                    f"{sel_site['name'].split(' — ')[0]} (ML Match {sel_site['ml_similarity']:.0%})",
                    earth_markers,
                    start=start_mode,
                    zoom=zoom_level,
                    exag=exag,
                )
                viewer3d.show(html_earth, 620)
            elif world.startswith(t["body"]):
                html_target = viewer3d.explorer_html(
                    t["body"],
                    t["lat"],
                    t["lon"],
                    t["name"].split(" (")[0],
                    target_markers,
                    grid=target_grid,
                    start=start_mode,
                    exag=exag,
                )
                viewer3d.show(html_target, 620)
            else:
                v1, v2 = st.columns(2)
                with v1:
                    st.markdown(f"**🌐 Earth Analog: {sel_site['name'].split(' — ')[0]}**")
                    html_earth = viewer3d.explorer_html(
                        "Earth",
                        sel_site["lat"],
                        sel_site["lon"],
                        sel_site["name"].split(" — ")[0],
                        earth_markers,
                        start=start_mode,
                        zoom=zoom_level,
                        exag=exag,
                    )
                    viewer3d.show(html_earth, 540)
                with v2:
                    st.markdown(f"**🪐 Target Reference: {t['name'].split(' (')[0]} ({t['body']})**")
                    html_target = viewer3d.explorer_html(
                        t["body"],
                        t["lat"],
                        t["lon"],
                        t["name"].split(" (")[0],
                        target_markers,
                        grid=target_grid,
                        start=start_mode,
                        exag=exag,
                    )
                    viewer3d.show(html_target, 540)

            s_card1, s_card2, s_card3 = st.columns(3)
            with s_card1:
                with st.container(border=True):
                    st.markdown("###### ✅ Key Physical Similarities")
                    st.write(sel_site["similarities_text"])
            with s_card2:
                with st.container(border=True):
                    st.markdown("###### ⚠️ Key Dissimilarities & Physics Gaps")
                    st.write(sel_site["dissimilarities_text"])
            with s_card3:
                with st.container(border=True):
                    st.markdown("###### 🧭 Operational & Environmental Factors")
                    st.write(sel_site["other_factors_text"])

# ==========================================
# TAB 2: DATA LAYERS & CLICKABLE INSTRUMENT FINGERPRINT
# ==========================================
with tab_layers:
    inst_keys = list(PLANETARY_INSTRUMENT_SOURCES.keys())
    if "active_planetary_instrument" not in st.session_state:
        st.session_state["active_planetary_instrument"] = inst_keys[0]

    active_inst_key = st.session_state["active_planetary_instrument"]
    selected_earth = st.session_state.get("explorer_selected_earth_site")
    fp_rows, inst_meta = build_instrument_fingerprint(t, active_inst_key, selected_earth)

    col_layers, col_fp = st.columns([1.15, 1.15], gap="large")

    with col_layers:
        st.markdown(f"#### Available Planetary Data Layers ({t['body']})")
        default_layer = inst_meta["layer_filter"] if inst_meta["layer_filter"] in LAYERS else LAYERS[0]
        layer_idx = LAYERS.index(default_layer) if default_layer in LAYERS else 0
        layer = st.selectbox(
            "Select planetary data layer",
            LAYERS,
            index=layer_idx,
            help="Automatically syncs when you click an orbital instrument source button under the Environmental Fingerprint.",
        )
        rows = registry.datasets_for(t["body"], layer)
        if rows:
            df_layers = pd.DataFrame(rows)[
                ["title", "resolution", "crs", "units", "level", "temporal", "access", "status"]
            ]
            st.dataframe(df_layers, hide_index=True, use_container_width=True)
        else:
            st.info(
                f"No catalogued dataset provides **{layer}** for {t['body']} yet. Upload custom rasters in **Mission Control > Data sources**."
            )
        st.caption(
            f"Uploaded user rasters for {t['body']}: **{len(ups)}**. Missing values are explicitly reported and never interpolated."
        )

        with st.container(border=True):
            st.markdown(f"##### 🛰️ Active Reference Dataset: {inst_meta['short_label']}")
            st.markdown(
                f"- **Active Orbital Instrument ({t['body']}):** `{inst_meta['active_instrument']}`\n"
                f"- **Comparison Focus:** {inst_meta['focus']}\n"
                f"- **Reference Datum / Product:** `{inst_meta['datum']}` (`{inst_meta['resolution_m']} m` effective resolution)\n"
                f"- **Scientific Calibration Note:** {inst_meta['benchmark_note']}\n"
                f"- **Archive Source:** [{inst_meta['citation']}]({inst_meta['url']})"
            )

    with col_fp:
        st.markdown("#### Environmental Fingerprint & Reference Switcher")

        st.markdown(
            f"<div class='inst-active-banner'>"
            f"<strong>Active Reference Source: {inst_meta['short_label']}</strong> — {inst_meta['focus']}<br>"
            f"<span style='color:#A8B8CE;font-size:0.80rem;'>Click any orbital instrument button below the table to switch the active planetary reference dataset and update the environmental profile.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        df_fp = pd.DataFrame(fp_rows)
        display_cols = [c for c in df_fp.columns if c not in ("Category", "Priority")]

        f_all, f_pri, f_geo, f_topo, f_env = st.tabs(
            ["All", "★ Instrument Primary", "Geology", "Topography", "Environment"]
        )
        with f_all:
            st.dataframe(df_fp[display_cols], hide_index=True, use_container_width=True)
        with f_pri:
            st.dataframe(
                df_fp[df_fp["Priority"] == "★ Primary Instrument Metric"][display_cols],
                hide_index=True,
                use_container_width=True,
            )
        with f_geo:
            st.dataframe(
                df_fp[df_fp["Category"] == "Geology"][display_cols],
                hide_index=True,
                use_container_width=True,
            )
        with f_topo:
            st.dataframe(
                df_fp[df_fp["Category"] == "Topography"][display_cols],
                hide_index=True,
                use_container_width=True,
            )
        with f_env:
            st.dataframe(
                df_fp[df_fp["Category"] == "Environment"][display_cols],
                hide_index=True,
                use_container_width=True,
            )

        st.markdown("###### 🎛️ Click a Planetary Reference Data Source to Update Environmental Profile:")
        btn_cols = st.columns(len(inst_keys))
        for bcol, ikey in zip(btn_cols, inst_keys):
            icfg = PLANETARY_INSTRUMENT_SOURCES[ikey]
            is_active = ikey == active_inst_key
            if bcol.button(
                icfg["short_label"],
                key=f"inst_btn_{ikey}",
                type="primary" if is_active else "secondary",
                help=icfg["focus"],
                use_container_width=True,
            ):
                st.session_state["active_planetary_instrument"] = ikey
                st.rerun()

        b_col1, b_col2 = st.columns([2, 1])
        with b_col1:
            badges_html = (
                theme.badge(t.get("provenance_class", "real"))
                + theme.badge("real", inst_meta["short_label"])
            )
            st.markdown(badges_html, unsafe_allow_html=True)
        with b_col2:
            st.download_button(
                "⬇️ Export Fingerprint CSV",
                data=df_fp.to_csv(index=False).encode("utf-8"),
                file_name=f"{t['id']}_{inst_meta['short_label'].split()[1].lower()}_fingerprint.csv",
                mime="text/csv",
                use_container_width=True,
            )

# ==========================================
# TAB 3: TERRAIN DERIVATIVES & COLOR LEGENDS
# ==========================================
with tab_terrain:
    hh = demlib.downsample(h, 128)
    cc = cell * (h.shape[0] / 128)
    der = terrain.derivatives(hh, cc)
    m = demlib.terrain_metrics(hh, cc)

    elev_min = float(hh.min())
    elev_max = float(hh.max())
    slope_min = float(der["slope"].min())
    slope_max = float(der["slope"].max())
    rough_min = float(der["roughness"].min())
    rough_max = float(der["roughness"].max())

    st.caption(
        f"📐 **Active Surface Relief Grid:** {dem_label} — Measured Peak-to-Trough Relief: **{m['relief_m']:.1f} m** "
        f"(Elevation span `{elev_min:.1f} m` to `{elev_max:.1f} m`, Cell resolution `{m['cell_size_m']:.0f} m`)."
    )

    COLOR_LEGEND_META = {
        "elevation": {
            "title": "Elevation (Topographic Relief)",
            "ramp_colors": _extract_ramp_hex_list(
                P.LAYER_RAMPS.get("elevation", ["#101C32", "#263B59", "#48BFE3", "#A8754B", "#F1F5FA"])
            ),
            "low_label": f"Low / Basin Floor ({elev_min:.0f} m)",
            "mid_label": f"Mid Bench ({0.5*(elev_min+elev_max):.0f} m)",
            "high_label": f"High Rim / Crest ({elev_max:.0f} m)",
            "meaning": (
                "**Deep Navy / Slate (`#101C32` → `#263B59`):** Topographic depressions, crater floors, and valley bottoms.  \n"
                "**Teal / Ochre (`#48BFE3` → `#A8754B`):** Intermediate volcanic benches, ejecta blankets, and flank slopes.  \n"
                "**Warm Tan / Starlight White (`#D9A76A` → `#F1F5FA`):** Elevated crater rims, central peaks, and volcanic ridges."
            ),
        },
        "slope": {
            "title": "Slope Angle (Traversability Gradient)",
            "ramp_colors": _extract_ramp_hex_list(
                P.LAYER_RAMPS.get("slope", ["#1B4332", "#45C4A1", "#E6B84B", "#F07832", "#D64D62"])
            ),
            "low_label": f"Flat / Safe ({slope_min:.1f}°–5°)",
            "mid_label": "Moderate (5°–15°)",
            "high_label": f"Steep Hazard (>20°, max {slope_max:.1f}°)",
            "meaning": (
                "**Deep Green / Aurora Teal (`< 5°`):** Flat plains & safe landing/rover traverse corridors.  \n"
                "**Amber / Gold (`5° – 15°`):** Moderate gradients navigable by wheeled rovers with reduced speed.  \n"
                "**Volcanic Orange / Crimson (`> 15° – 20°+`):** Steep crater walls, scarps, and talus slopes posing slip/rollover hazards."
            ),
        },
        "roughness": {
            "title": "Surface Roughness (Sub-Grid Texture)",
            "ramp_colors": _extract_ramp_hex_list(
                P.LAYER_RAMPS.get("roughness", ["#101C32", "#3B528B", "#21908C", "#5DC863", "#FDE725"])
            ),
            "low_label": f"Smooth ({rough_min:.2f}–0.25)",
            "mid_label": "Moderate Rubble (0.25–0.60)",
            "high_label": f"Rugged / Blocky ({rough_max:.2f})",
            "meaning": (
                "**Dark Indigo / Slate (`< 0.25`):** Smooth dust mantles, playa flats, or unfractured lava sheets.  \n"
                "**Cyan / Emerald (`0.25 – 0.60`):** Moderately textured regolith, small cobbles, and hummocky ejecta.  \n"
                "**Bright Lime / Amber-Orange (`> 0.60`):** High local variance — jagged ’a’ā lava, boulder fields, or fractured rim breccia."
            ),
        },
    }

    cols = st.columns(3)
    for col, (name, ramp) in zip(cols, [("elevation", "elevation"), ("slope", "slope"), ("roughness", "roughness")]):
        with col:
            st.plotly_chart(
                charts.layer_image(terrain.colorize(der[name], ramp), COLOR_LEGEND_META[name]["title"]),
                use_container_width=True,
            )
            meta_leg = COLOR_LEGEND_META[name]
            grad_css = ", ".join(meta_leg["ramp_colors"])
            st.markdown(
                f"""<div class="color-legend-box">
                <div class="color-bar" style="background: linear-gradient(90deg, {grad_css});"></div>
                <div style="display:flex;justify-content:space-between;color:#F1F5FA;font-weight:600;font-size:0.74rem;margin-bottom:6px;">
                    <span>{meta_leg['low_label']}</span>
                    <span>{meta_leg['mid_label']}</span>
                    <span>{meta_leg['high_label']}</span>
                </div>
                <div style="color:#A8B8CE;line-height:1.38;">{meta_leg['meaning']}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    mc = st.columns(4)
    mc[0].metric(
        "Measured Schematic Relief" if is_schematic else "Measured DEM Relief",
        f"{m['relief_m']:.0f} m",
        f"{elev_min:.0f} m to {elev_max:.0f} m",
    )
    mc[1].metric("Mean Surface Slope", f"{m['mean_slope_deg']:.1f}°", f"Max {slope_max:.1f}°")
    mc[2].metric("Steep Terrain (>20°)", f"{m['steep_fraction_gt20']:.0%}", "Rover hazard fraction")
    mc[3].metric("Grid Cell Size", f"{m['cell_size_m']:.0f} m", "128×128 derivative grid")

    st.divider()

    t_head, t_ctrl = st.columns([2, 1.5])
    with t_head:
        st.markdown("#### Elevation Transect Profile")
    with t_ctrl:
        transect_dir = st.selectbox(
            "Transect direction",
            ["West → East", "North → South", "Northwest → Southeast", "Compare All"],
            label_visibility="collapsed",
        )

    transect_coords = {
        "West → East": ((0.05, 0.5), (0.95, 0.5)),
        "North → South": ((0.5, 0.05), (0.5, 0.95)),
        "Northwest → Southeast": ((0.1, 0.1), (0.9, 0.9)),
    }

    profiles_to_plot = {}
    if transect_dir == "Compare All":
        for label, (p1, p2) in transect_coords.items():
            d, z, _ = demlib.transect(hh, cc, p1, p2)
            profiles_to_plot[label] = (d, z)
    else:
        p1, p2 = transect_coords[transect_dir]
        d, z, _ = demlib.transect(hh, cc, p1, p2)
        profiles_to_plot[transect_dir] = (d, z)

    st.plotly_chart(
        charts.profiles(profiles_to_plot, "Elevation profile (m)", normalised=False),
        use_container_width=True,
    )