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

ctx = sidebar("explorer")
theme.header("Planetary Explorer", "Fly over the target world, inspect real data layers and generate its environmental fingerprint.", "Workspace 02", "explorer")
t = ctx["target"]


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


tab3, tabl = st.tabs(["3D view", "Layers and fingerprint"])
with tab3:
    c1, c2 = st.columns([1, 3])
    with c1:
        world = st.radio("World", [t["body"], "Earth"], horizontal=True, help="Earth shows analogue candidates over real elevation and satellite imagery.")
        if world == "Earth":
            pool = ctx["cand_list"]
            cid = st.selectbox("Earth site", [c["id"] for c in pool], format_func=lambda i: ctx["cands"][i]["name"].split(" (")[0])
            c = ctx["cands"][cid]
            st.caption(f"{c['lat']:.3f}, {c['lon']:.3f} | {c['status']}")
            st.markdown(theme.badge(c.get("provenance_class", "demonstration")), unsafe_allow_html=True)
        else:
            st.caption(f"{t['name']}  \n{t['lat']:.2f}, {t['lon']:.2f}")
        st.caption("Terrain mode needs internet for real Earth elevation and imagery. Moon and Mars use an uploaded DEM, otherwise a labelled schematic surface.")
    with c2:
        if world == "Earth":
            mk = [{"label": x["name"].split(" (")[0], "lat": x["lat"], "lon": x["lon"], "color": P.COSMIC_CYAN, "bbox": x.get("bbox")} for x in ctx["cand_list"]]
            mk.insert(0, {"label": c["name"].split(" (")[0], "lat": c["lat"], "lon": c["lon"], "color": P.CELESTIAL_MINT, "main": True, "bbox": c.get("bbox")})
            html = viewer3d.explorer_html("Earth", c["lat"], c["lon"], c["name"].split(" (")[0], mk, start="terrain", zoom=12)
        else:
            ups = manager.user_rasters(t["body"])
            h, cell, schem, label = body_grid(t["body"], t["id"], t["morphology"], t["relief_m"] or 200.0, t["roughness"] or 0.3, ups[0]["id"] if ups else None)
            hs = demlib.downsample(h, 129)
            grid = viewer3d.grid_payload(hs, cell * h.shape[0] / 129, schem, label)
            others = [x for x in ctx["catalog"]["targets"] if x["body"] == t["body"]]
            mk = [{"label": x["name"].split(" (")[0], "lat": x["lat"], "lon": x["lon"], "color": P.COSMIC_CYAN} for x in others]
            mk.insert(0, {"label": t["name"].split(" (")[0], "lat": t["lat"], "lon": t["lon"], "color": P.CELESTIAL_MINT, "main": True})
            html = viewer3d.explorer_html(t["body"], t["lat"], t["lon"], t["name"].split(" (")[0], mk, grid=grid, exag=2.0)
        viewer3d.show(html, 650)
    models = viewer3d.available_models()
    if models:
        pick = st.selectbox("Mission hardware model", models, format_func=lambda p: p.name)
        viewer3d.show(viewer3d.model_viewer_html(pick), 420)
    else:
        st.caption("Hardware models: place NASA 3D Resources or other agency .glb/.gltf files (rovers, landers, orbiters) in assets/models/ and a model viewer appears here.")

with tabl:
    a, b = st.columns([1.2, 1])
    with a:
        st.markdown(f"#### Layers for {t['body']}")
        layer = st.selectbox("Layer", LAYERS)
        rows = registry.datasets_for(t["body"], layer)
        if rows:
            st.dataframe(pd.DataFrame(rows)[["title", "resolution", "crs", "units", "level", "temporal", "access", "status"]], hide_index=True, width="stretch")
        else:
            st.info(f"No catalogued dataset provides '{layer}' for {t['body']} yet. Upload one in Mission Control > Data sources.")
        up = manager.user_rasters(t["body"])
        st.caption(f"Uploaded rasters for {t['body']}: {len(up)}. Missingness is reported, never filled with invented values.")
    with b:
        st.markdown("#### Environmental fingerprint")
        fp = [("Lithology", t["lithology"], "-"), ("Minerals", ", ".join(t["minerals"]) or "unknown", "-"), ("Mean slope", t["slope_deg"], "deg"), ("Roughness index", t["roughness"], "0-1"),
              ("Relief", t["relief_m"], "m"), ("Mean temperature", t["temp_mean_c"], "deg C"), ("Temperature range", f"{t['temp_min_c']} to {t['temp_max_c']}", "deg C"),
              ("Water/ice indicator", t["water_ice"], "0-1 (" + str(t.get("water_basis") or "basis n/a") + ")"), ("Dust", t["dust"], "0-1"), ("Cave/lava-tube evidence", t["caves"], "0-1"),
              ("Resolution", t["resolution_m"], "m"), ("Data quality", t["data_quality"], "0-1")]
        df = pd.DataFrame([{"Feature": k, "Value": ("missing" if v is None else v), "Unit / basis": u} for k, v, u in fp]).astype(str)
        st.dataframe(df, hide_index=True, width="stretch")
        st.markdown(theme.badge(t.get("provenance_class", "demonstration")) + "".join(theme.badge("", s) for s in t["sources"][:3]), unsafe_allow_html=True)

    st.markdown("#### Terrain derivatives")
    ups = manager.user_rasters(t["body"])
    h, cell, schem, label = body_grid(t["body"], t["id"], t["morphology"], t["relief_m"] or 200.0, t["roughness"] or 0.3, ups[0]["id"] if ups else None)
    hh = demlib.downsample(h, 128); cc = cell * h.shape[0] / 128
    der = terrain.derivatives(hh, cc)
    st.caption(label + (". Replace with a measured DEM by uploading one." if schem else ""))
    cols = st.columns(3)
    for col, (name, ramp) in zip(cols, [("elevation", "elevation"), ("slope", "slope"), ("roughness", "roughness")]):
        with col:
            st.plotly_chart(charts.layer_image(terrain.colorize(der[name], ramp), name.capitalize()), width="stretch")
    m = demlib.terrain_metrics(hh, cc)
    mc = st.columns(4)
    mc[0].metric("Relief", f"{m['relief_m']:.0f} m"); mc[1].metric("Mean slope", f"{m['mean_slope_deg']:.1f} deg"); mc[2].metric("Slopes > 20 deg", f"{m['steep_fraction_gt20']:.0%}"); mc[3].metric("Cell size", f"{m['cell_size_m']:.0f} m")
    d, z, _ = demlib.transect(hh, cc, (0.05, 0.5), (0.95, 0.5))
    st.plotly_chart(charts.profiles({"West-east transect": (d, z)}, "Elevation profile", normalised=False), width="stretch")
