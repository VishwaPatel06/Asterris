import pandas as pd
import streamlit as st

from components import charts, theme, viewer3d
from components.context import sidebar
from config import palette as P
from config.data_catalog import LAYERS
from data_sources import manager
from data_sources.planetary import registry
from geospatial import terrain
from scientific_engine import dem as demlib

# 1. Context & Header
ctx = sidebar("explorer")
theme.header(
    "Planetary Explorer",
    "Fly over the target world, inspect real data layers, and generate its environmental fingerprint.",
    "Workspace 02",
    "explorer",
)
t = ctx["target"]

# Custom subtle styling for cleaner cards and spacing
st.markdown(
    """
    <style>
    div[data-testid="metric-container"] {
        background-color: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 12px 16px;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def body_grid(body: str, tid: str, morph: str, relief: float, rough: float, upload_id: str | None):
    """Measured DEM if uploaded for this body, else a clearly labelled schematic surface."""
    if upload_id:
        name, raw = manager.raster_bytes(upload_id)
        h, cell, msg = demlib.load_uploaded_dem(name, raw, n=160)
        if h is not None:
            return h, cell, False, f"Uploaded DEM: {name}. {msg}"
    h, cell = demlib.synthetic_dem(morph, 128, 20000.0, max(relief, 50.0), rough)
    return h, cell, True, f"Schematic {morph} relief (not measured)"


# Pre-load DEM once so both tabs share it cleanly
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
kpi1.metric("Target Body", t["body"], f"{t['lat']:.2f}°, {t['lon']:.2f}°")
kpi2.metric("Relief", f"{t['relief_m']:.0f} m" if t["relief_m"] is not None else "N/A", t["morphology"].capitalize())
kpi3.metric("Mean Temp", f"{t['temp_mean_c']} °C" if t["temp_mean_c"] is not None else "N/A")
kpi4.metric(
    "Data Quality",
    f"{t['data_quality']:.0%}" if t["data_quality"] is not None else "N/A",
    "Measured DEM" if not is_schematic else "Schematic DEM",
)

st.write("")  # Visual breathing room

# 3. Main Navigation Tabs
tab_3d, tab_layers, tab_terrain = st.tabs(
    ["🌍 3D Surface & Models", "🧬 Layers & Fingerprint", "⛰️ Terrain Derivatives"]
)

# ==========================================
# TAB 1: 3D SURFACE & HARDWARE MODELS
# ==========================================
with tab_3d:
    ctrl_col, view_col = st.columns([1, 3.2], gap="large")

    with ctrl_col:
        with st.container(border=True):
            st.markdown("##### Viewport Controls")
            world = st.radio(
                "World",
                [t["body"], "Earth"],
                horizontal=True,
                help="Earth shows terrestrial analogue candidates over real elevation and satellite imagery.",
            )

            if world == "Earth":
                pool = ctx["cand_list"]
                cid = st.selectbox(
                    "Analogue site",
                    [c["id"] for c in pool],
                    format_func=lambda i: ctx["cands"][i]["name"].split(" (")[0],
                )
                c = ctx["cands"][cid]
                st.caption(f"📍 `{c['lat']:.3f}, {c['lon']:.3f}` | **{c['status']}**")
                st.markdown(theme.badge(c.get("provenance_class", "demonstration")), unsafe_allow_html=True)
                zoom_level = st.slider("Initial Zoom", min_value=8, max_value=16, value=12)
                show_siblings = st.checkbox("Show all candidate pins", value=True)
            else:
                st.caption(f"📍 **{t['name']}** (`{t['lat']:.2f}, {t['lon']:.2f}`)")
                exag = st.slider("Vertical Exaggeration", min_value=0.5, max_value=5.0, value=2.0, step=0.25)
                show_siblings = st.checkbox(f"Show other {t['body']} targets", value=True)

            st.divider()
            st.caption(
                "ℹ️ Earth terrain requires internet access. Moon and Mars render an uploaded DEM or a schematic surface."
            )

    with view_col:
        if world == "Earth":
            mk = []
            if show_siblings:
                mk = [
                    {
                        "label": x["name"].split(" (")[0],
                        "lat": x["lat"],
                        "lon": x["lon"],
                        "color": P.COSMIC_CYAN,
                        "bbox": x.get("bbox"),
                    }
                    for x in ctx["cand_list"]
                    if x["id"] != cid
                ]
            mk.insert(
                0,
                {
                    "label": c["name"].split(" (")[0],
                    "lat": c["lat"],
                    "lon": c["lon"],
                    "color": P.CELESTIAL_MINT,
                    "main": True,
                    "bbox": c.get("bbox"),
                },
            )
            html = viewer3d.explorer_html(
                "Earth", c["lat"], c["lon"], c["name"].split(" (")[0], mk, start="terrain", zoom=zoom_level
            )
        else:
            hs = demlib.downsample(h, 129)
            grid = viewer3d.grid_payload(hs, cell * (h.shape[0] / 129), is_schematic, dem_label)
            mk = []
            if show_siblings:
                others = [x for x in ctx["catalog"]["targets"] if x["body"] == t["body"] and x["id"] != t["id"]]
                mk = [
                    {"label": x["name"].split(" (")[0], "lat": x["lat"], "lon": x["lon"], "color": P.COSMIC_CYAN}
                    for x in others
                ]
            mk.insert(
                0,
                {
                    "label": t["name"].split(" (")[0],
                    "lat": t["lat"],
                    "lon": t["lon"],
                    "color": P.CELESTIAL_MINT,
                    "main": True,
                },
            )
            html = viewer3d.explorer_html(
                t["body"], t["lat"], t["lon"], t["name"].split(" (")[0], mk, grid=grid, exag=exag
            )

        viewer3d.show(html, 620)

    # Collapsible Hardware Model Viewer
    with st.expander("🛰️ Mission Hardware 3D Inspector", expanded=False):
        models = viewer3d.available_models()
        if models:
            pick = st.selectbox("Select spacecraft or rover model", models, format_func=lambda p: p.name)
            viewer3d.show(viewer3d.model_viewer_html(pick), 420)
        else:
            st.info(
                "No 3D hardware models found. Drop `.glb` or `.gltf` files (e.g., from NASA 3D Resources) into `assets/models/` to inspect them here."
            )

# ==========================================
# TAB 2: DATA LAYERS & FINGERPRINT
# ==========================================
with tab_layers:
    col_layers, col_fp = st.columns([1.25, 1], gap="large")

    with col_layers:
        st.markdown(f"#### Available Data Layers ({t['body']})")
        layer = st.selectbox("Select planetary data layer", LAYERS, label_visibility="collapsed")
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

    with col_fp:
        st.markdown("#### Environmental Fingerprint")

        fp_all = [
            ("Geology", "Lithology", t["lithology"], "-"),
            ("Geology", "Minerals", ", ".join(t["minerals"]) or "unknown", "-"),
            ("Geology", "Dust cover", t["dust"], "0-1 index"),
            ("Topography", "Mean slope", t["slope_deg"], "deg"),
            ("Topography", "Roughness index", t["roughness"], "0-1 index"),
            ("Topography", "Relief", t["relief_m"], "m"),
            ("Topography", "Cave / lava-tube evidence", t["caves"], "0-1 index"),
            ("Environment", "Mean temperature", t["temp_mean_c"], "°C"),
            ("Environment", "Temperature range", f"{t['temp_min_c']} to {t['temp_max_c']}", "°C"),
            ("Environment", "Water / ice indicator", t["water_ice"], f"0-1 ({t.get('water_basis') or 'basis n/a'})"),
            ("Metadata", "Spatial resolution", t["resolution_m"], "m"),
            ("Metadata", "Data quality score", t["data_quality"], "0-1 index"),
        ]

        df_fp = pd.DataFrame(
            [
                {"Category": cat, "Feature": k, "Value": ("missing" if v is None else str(v)), "Unit / Basis": u}
                for cat, k, v, u in fp_all
            ]
        )

        # Sub-tabs to make scanning attributes effortless
        f_all, f_geo, f_topo, f_env = st.tabs(["All", "Geology", "Topography", "Environment"])
        with f_all:
            st.dataframe(df_fp[["Feature", "Value", "Unit / Basis"]], hide_index=True, use_container_width=True)
        with f_geo:
            st.dataframe(
                df_fp[df_fp["Category"] == "Geology"][["Feature", "Value", "Unit / Basis"]],
                hide_index=True,
                use_container_width=True,
            )
        with f_topo:
            st.dataframe(
                df_fp[df_fp["Category"] == "Topography"][["Feature", "Value", "Unit / Basis"]],
                hide_index=True,
                use_container_width=True,
            )
        with f_env:
            st.dataframe(
                df_fp[df_fp["Category"] == "Environment"][["Feature", "Value", "Unit / Basis"]],
                hide_index=True,
                use_container_width=True,
            )

        # Provenance badges + CSV Export
        b_col1, b_col2 = st.columns([2, 1])
        with b_col1:
            badges_html = theme.badge(t.get("provenance_class", "demonstration")) + "".join(
                theme.badge("", s) for s in t["sources"][:3]
            )
            st.markdown(badges_html, unsafe_allow_html=True)
        with b_col2:
            st.download_button(
                "⬇️ Export CSV",
                data=df_fp.to_csv(index=False).encode("utf-8"),
                file_name=f"{t['id']}_fingerprint.csv",
                mime="text/csv",
                use_container_width=True,
            )

# ==========================================
# TAB 3: TERRAIN DERIVATIVES & PROFILES
# ==========================================
with tab_terrain:
    hh = demlib.downsample(h, 128)
    cc = cell * (h.shape[0] / 128)
    der = terrain.derivatives(hh, cc)

    if is_schematic:
        st.warning(f"⚠️ **{dem_label}** — Upload a measured GeoTIFF DEM to compute true surface derivatives.")
    else:
        st.success(f"✅ **{dem_label}**")

    # 3-Column Raster Maps
    cols = st.columns(3)
    for col, (name, ramp) in zip(cols, [("elevation", "elevation"), ("slope", "slope"), ("roughness", "roughness")]):
        with col:
            st.plotly_chart(
                charts.layer_image(terrain.colorize(der[name], ramp), name.capitalize()),
                use_container_width=True,
            )

    # Computed Terrain Metrics
    m = demlib.terrain_metrics(hh, cc)
    mc = st.columns(4)
    mc[0].metric("Computed Relief", f"{m['relief_m']:.0f} m")
    mc[1].metric("Mean Slope", f"{m['mean_slope_deg']:.1f}°")
    mc[2].metric("Steep Terrain (>20°)", f"{m['steep_fraction_gt20']:.0%}")
    mc[3].metric("Grid Cell Size", f"{m['cell_size_m']:.0f} m")

    st.divider()

    # Interactive Transect Selector
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
        charts.profiles(profiles_to_plot, "Elevation profile", normalised=False),
        use_container_width=True,
    )