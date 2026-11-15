"""Interactive 3D viewer (Three.js) embedded in Streamlit: globe + Google-Earth-style terrain.

Globe: Earth (Esri World Imagery), Moon (LROC WAC), Mars (Viking MDIM).
Earth terrain uses browser-fetched elevation and imagery tiles. Other bodies use
an uploaded DEM or an explicitly labelled schematic surface.

The viewer controls are placed in a toolbar outside the WebGL viewport. This
keeps the terrain unobstructed, including when two viewers are shown side by side.
"""
from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import numpy as np

from config import palette as P
from config.data_catalog import TILE_SOURCES
from config.settings import get_settings

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=2)
def _vendor(name: str) -> str:
    return (ROOT / "assets" / "vendor" / name).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _js() -> str:
    return (Path(__file__).with_name("viewer3d.js.txt")).read_text(encoding="utf-8")


def _j(o) -> str:
    return json.dumps(o, separators=(",", ":")).replace("</", "<\\/")


CSS = f"""
*{{box-sizing:border-box}}
html,body{{margin:0;width:100%;height:100%;background:{P.DEEP_SPACE};font-family:Inter,Segoe UI,system-ui,sans-serif;color:{P.STARLIGHT};overflow:hidden}}
#app{{display:flex;flex-direction:column;width:100%;height:100%;min-height:0;gap:7px;background:{P.DEEP_SPACE}}}

/* Header and controls are in normal document flow, never over the canvas. */
#header{{flex:0 0 auto;display:flex;flex-direction:column;gap:6px;min-width:0}}
#top{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:5px 9px;min-height:30px;background:rgba(16,28,50,.94);border:1px solid {P.STELLAR_SLATE};border-radius:9px}}
#top b{{font-size:12px;white-space:nowrap}}
#tinfo{{font-size:10.5px;color:{P.MOONLIGHT};min-width:0}}
#status{{font-size:10.5px;color:{P.MOONLIGHT};min-width:0;overflow-wrap:anywhere}}
#status.warn{{color:{P.MODERATE}}} #status.err{{color:{P.LOW}}}

/* Compact responsive toolbar above the 3D viewport. */
#ctl{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;padding:7px 8px;background:rgba(16,28,50,.96);border:1px solid {P.STELLAR_SLATE};border-radius:10px;min-width:0}}
#ctl label{{display:flex;align-items:center;gap:5px;color:{P.MOONLIGHT};font-size:10.5px;white-space:nowrap}}
#ctl select,#ctl button{{background:{P.ORBIT_BLUE};color:{P.STARLIGHT};border:1px solid {P.STELLAR_SLATE};border-radius:7px;padding:5px 7px;font-size:10.5px;max-width:150px}}
#ctl button{{cursor:pointer}}
#ctl button.on{{background:{P.NEBULA_BLUE};border-color:{P.NEBULA_BLUE};color:#fff}}
.seg{{display:flex;gap:4px;flex:0 0 auto}}
.seg button{{min-width:64px}}
#terrCtl,#globeCtl{{display:flex;align-items:center;flex-wrap:wrap;gap:7px}}
#terrCtl[style*="display: none"],#globeCtl[style*="display: none"]{{display:none!important}}
input[type=range]{{accent-color:{P.NEBULA_BLUE};width:76px;vertical-align:middle}}
input[type=checkbox]{{accent-color:{P.NEBULA_BLUE};vertical-align:middle}}
#exv{{color:{P.STARLIGHT};font-variant-numeric:tabular-nums}}
#reset{{margin-left:auto}}

/* The WebGL canvas has its own unobstructed viewport. */
#wrap{{position:relative;flex:1 1 auto;width:100%;height:auto;min-height:180px;min-width:0;border-radius:11px;overflow:hidden;border:1px solid {P.STELLAR_SLATE};background:radial-gradient(ellipse at 30% 20%,{P.ORBIT_BLUE},{P.DEEP_SPACE} 70%)}}
canvas{{display:block;width:100%;height:100%;cursor:grab;touch-action:none}}
canvas:active{{cursor:grabbing}}

/* Readouts and map legend sit below the viewport. */
#footer{{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;min-width:0}}
#bot{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;min-width:0;padding:5px 8px;background:rgba(16,28,50,.94);border:1px solid {P.STELLAR_SLATE};border-radius:8px;font-size:10px;line-height:1.35;max-width:100%}}
#cur{{color:{P.COSMIC_CYAN};font-variant-numeric:tabular-nums}}
#pick{{color:{P.CELESTIAL_MINT}}} #pick a{{color:{P.COSMIC_CYAN}}}
#outside{{color:{P.MODERATE}}}
#legend{{margin-left:auto;min-width:125px;max-width:230px;padding:5px 8px;background:rgba(16,28,50,.94);border:1px solid {P.STELLAR_SLATE};border-radius:8px;font-size:10px;color:{P.MOONLIGHT}}}
.lg{{display:flex;justify-content:space-between;gap:6px;color:{P.MOONLIGHT};font-size:9px;margin-top:3px}}
@media(max-width:560px){{
  #ctl{{align-items:flex-start}}
  #terrCtl,#globeCtl{{width:100%}}
  #ctl label{{white-space:normal}}
  #reset{{margin-left:0}}
  #wrap{{min-height:160px}}
  #footer{{align-items:stretch}}
  #legend{{margin-left:0;max-width:none;width:100%}}
}}
"""

UI = """
<div id="app">
  <div id="header">
    <div id="top">
      <b id="tt"></b>
      <span id="tinfo"></span>
      <span id="status">Initialising</span>
    </div>
    <div id="ctl">
      <div class="seg">
        <button id="bGlobe" class="on">Globe</button>
        <button id="bTerr">Terrain</button>
      </div>
      <label>Go to <select id="goto"><option value="">Select location</option></select></label>
      <div id="terrCtl" style="display:none">
        <label>Layer
          <select id="layer">
            <option value="satellite">Satellite</option>
            <option value="elevation">Elevation</option>
            <option value="slope">Slope</option>
            <option value="hillshade">Hillshade</option>
            <option value="volcanic">Thermal relief</option>
          </select>
        </label>
        <label>Vertical <input id="exag" type="range" min="0.5" max="6" step="0.1"><span id="exv"></span></label>
        <label>Sun azimuth <input id="sunaz" type="range" min="0" max="360" value="315"></label>
        <label>Sun elevation <input id="sunel" type="range" min="5" max="80" value="38"></label>
        <label id="zoomRow">Area
          <select id="zoom">
            <option value="11">Wide (~58 km)</option>
            <option value="12">Regional (~29 km)</option>
            <option value="13">Local (~14 km)</option>
            <option value="14">Detail (~7 km)</option>
          </select>
        </label>
        <label>Markers <input id="mk" type="checkbox" checked></label>
      </div>
      <div id="globeCtl">
        <label>Auto-rotate <input id="rot" type="checkbox"></label>
      </div>
      <button id="reset">Reset view</button>
    </div>
  </div>
  <div id="wrap"><canvas id="c"></canvas></div>
  <div id="footer">
    <div id="bot">
      <span id="cur">Drag to orbit, scroll to zoom, right-drag or shift-drag to pan</span>
      <span id="pick"></span>
      <span id="outside"></span>
    </div>
    <div id="legend"></div>
  </div>
</div>
"""


def _page(js: str, data: dict) -> str:
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<style>{CSS}</style></head><body>{UI}"
        f"<script>{_vendor('three.min.js')}</script>"
        f"<script>{js.replace('__DATA__', _j(data))}</script></body></html>"
    )


RAMPS = {
    "water": P.WATER,
    "veg": P.VEGETATION,
    "land": P.LAND,
    "ice": P.ICE,
    "slope": [P.VEGETATION[1], P.VEGETATION[4], P.LAND[3], P.VOLCANIC[2], P.VOLCANIC[0]],
    "volcanic": P.VOLCANIC,
}


def explorer_html(
    body: str,
    lat: float,
    lon: float,
    title: str,
    markers: Optional[List[dict]] = None,
    grid: Optional[dict] = None,
    start: str = "globe",
    zoom: int = 12,
    exag: float = 1.6,
    path: Optional[list] = None,
) -> str:
    """Build a viewer. Markers use label/lat/lon/color; grid contains a height array."""
    data = {
        "body": body,
        "lat": lat,
        "lon": lon,
        "title": title,
        "markers": markers or [],
        "tiles": TILE_SOURCES.get(body, {}),
        "ramps": RAMPS,
        "grid": grid,
        "start": start,
        "zoom": zoom,
        "exag": exag,
        "path": path or [],
    }
    return _page(_js(), data)


def grid_payload(h: np.ndarray, cell_m: float, schematic: bool, label: str) -> dict:
    h = np.asarray(h, dtype=float)
    return {
        "n": int(h.shape[0]),
        "h": [round(float(v), 2) for v in h.ravel()],
        "cell_m": float(cell_m),
        "schematic": schematic,
        "label": label,
    }


def available_models() -> List[Path]:
    return sorted(get_settings().models_dir.glob("*.glb")) + sorted(
        get_settings().models_dir.glob("*.gltf")
    )


def model_viewer_html(path: Path) -> str:
    """Orbit viewer for a user-supplied glTF/GLB model."""
    b64 = base64.b64encode(path.read_bytes()).decode()
    js = """
const wrap=document.getElementById('wrap'),canvas=document.getElementById('c');
const r=new THREE.WebGLRenderer({canvas,antialias:true});r.setClearColor(0x080F1E,1);
const sc=new THREE.Scene(),cam=new THREE.PerspectiveCamera(40,1,0.01,1000);
function rs(){r.setSize(wrap.clientWidth,wrap.clientHeight,false);cam.aspect=wrap.clientWidth/wrap.clientHeight;cam.updateProjectionMatrix();}
addEventListener('resize',rs);rs();
sc.add(new THREE.AmbientLight(0xA8B8CE,0.8));const d=new THREE.DirectionalLight(0xffffff,1.2);d.position.set(5,8,6);sc.add(d);
let th=0.6,ph=1.1,rad=4,drag=false,px=0,py=0;
canvas.onpointerdown=e=>{drag=true;px=e.clientX;py=e.clientY};
canvas.onpointerup=()=>drag=false;
canvas.onpointermove=e=>{if(!drag)return;th-=(e.clientX-px)*0.006;ph=Math.max(0.1,Math.min(3,ph-(e.clientY-py)*0.006));px=e.clientX;py=e.clientY};
canvas.onwheel=e=>{e.preventDefault();rad*=1+Math.sign(e.deltaY)*0.1};
const raw=atob(__B64__);const buf=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)buf[i]=raw.charCodeAt(i);
new THREE.GLTFLoader().parse(buf.buffer,'',g=>{const o=g.scene;const b=new THREE.Box3().setFromObject(o);const s=b.getSize(new THREE.Vector3()).length();o.scale.multiplyScalar(3/s);const b2=new THREE.Box3().setFromObject(o);o.position.sub(b2.getCenter(new THREE.Vector3()));sc.add(o);document.getElementById('st').textContent='Loaded';},e=>{document.getElementById('st').textContent='Could not parse model';});
(function L(){requestAnimationFrame(L);cam.position.set(rad*Math.sin(ph)*Math.sin(th),rad*Math.cos(ph),rad*Math.sin(ph)*Math.cos(th));cam.lookAt(0,0,0);r.render(sc,cam);})();
""".replace("__B64__", json.dumps(b64))
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
        f"<body><div id='app'><div id='top' class='pn'><b>{path.name}</b>"
        f"<span id='st' style='color:{P.MOONLIGHT}'>Loading</span></div>"
        f"<div id='wrap'><canvas id='c'></canvas></div></div>"
        f"<script>{_vendor('three.min.js')}</script>"
        f"<script>{_vendor('GLTFLoader.js')}</script><script>{js}</script></body></html>"
    )


def show(html: str, height: int = 600) -> None:
    """Embed generated HTML from the app's own data and bundled scripts."""
    import streamlit as st
    import streamlit.components.v1 as components

    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:  # pragma: no cover
        components.html(html, height=height, scrolling=False)
