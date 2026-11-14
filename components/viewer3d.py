"""Interactive 3D viewer (Three.js) embedded in Streamlit: globe + Google-Earth-style terrain.

* Globe: Earth (Esri World Imagery, reprojected), Moon (LROC WAC via NASA Moon Trek), Mars (Viking MDIM via NASA Mars Trek).
* Terrain (Earth): real elevation from AWS Terrain Tiles (SRTM/3DEP blend) draped with satellite imagery, built in the browser.
* Terrain (any body): a prepared height grid from Python (uploaded DEM, or an explicitly labelled schematic surface).
Tiles are fetched by the user's browser from public services; the server never downloads imagery. If tiles are unreachable
the viewer says so and falls back to a plain colour surface; it never fabricates imagery or elevation.
Optional hardware models: drop .glb files into assets/models/ and open the model viewer (GLTFLoader bundled).
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
html,body{{margin:0;height:100%;background:{P.DEEP_SPACE};font-family:Inter,Segoe UI,system-ui,sans-serif;color:{P.STARLIGHT};overflow:hidden}}
#wrap{{position:relative;width:100%;height:100%;border-radius:14px;overflow:hidden;border:1px solid {P.STELLAR_SLATE};background:radial-gradient(ellipse at 30% 20%,{P.ORBIT_BLUE},{P.DEEP_SPACE} 70%)}}
canvas{{display:block;width:100%;height:100%;cursor:grab;touch-action:none}} canvas:active{{cursor:grabbing}}
.pn{{position:absolute;background:rgba(16,28,50,.86);border:1px solid {P.STELLAR_SLATE};border-radius:12px;padding:.55rem .75rem;font-size:12px;line-height:1.4;backdrop-filter:blur(8px)}}
#top{{left:12px;top:12px;max-width:44%}} #top b{{font-size:13.5px}} #status{{margin-top:.25rem;color:{P.MOONLIGHT}}} #status.warn{{color:{P.MODERATE}}} #status.err{{color:{P.LOW}}}
#ctl{{right:12px;top:12px;display:flex;flex-direction:column;gap:.45rem;min-width:190px}}
#ctl label{{display:flex;justify-content:space-between;align-items:center;gap:.5rem;color:{P.MOONLIGHT}}}
#ctl select,#ctl button{{background:{P.ORBIT_BLUE};color:{P.STARLIGHT};border:1px solid {P.STELLAR_SLATE};border-radius:8px;padding:.25rem .45rem;font-size:12px}}
#ctl button{{cursor:pointer}} #ctl button.on{{background:{P.NEBULA_BLUE};border-color:{P.NEBULA_BLUE};color:#fff}}
.seg{{display:flex;gap:.3rem}} .seg button{{flex:1}}
input[type=range]{{accent-color:{P.NEBULA_BLUE};width:90px}}
#bot{{left:12px;bottom:12px;max-width:52%}} #cur{{color:{P.COSMIC_CYAN};font-variant-numeric:tabular-nums}} #pick{{color:{P.CELESTIAL_MINT};margin-top:.2rem}} #pick a{{color:{P.COSMIC_CYAN}}}
#legend{{right:12px;bottom:12px;width:220px}} .lg{{display:flex;justify-content:space-between;color:{P.MOONLIGHT};font-size:11px;margin-top:3px}}
#outside{{color:{P.MODERATE}}}
"""

UI = """
<div id='top' class='pn'><b id='tt'></b><div id='tinfo' style='color:#A8B8CE'></div><div id='status'>Initialising</div></div>
<div id='ctl' class='pn'>
  <div class='seg'><button id='bGlobe' class='on'>Globe</button><button id='bTerr'>Terrain</button></div>
  <label>Go to<select id='goto'><option value=''>select</option></select></label>
  <div id='terrCtl' style='display:none;flex-direction:column;gap:.45rem'>
    <label>Layer<select id='layer'><option value='satellite'>Satellite</option><option value='elevation'>Elevation</option><option value='slope'>Slope</option><option value='hillshade'>Hillshade</option><option value='volcanic'>Thermal relief</option></select></label>
    <label>Vertical<input id='exag' type='range' min='0.5' max='6' step='0.1'><span id='exv'></span></label>
    <label>Sun azimuth<input id='sunaz' type='range' min='0' max='360' value='315'></label>
    <label>Sun elevation<input id='sunel' type='range' min='5' max='80' value='38'></label>
    <label id='zoomRow'>Area<select id='zoom'><option value='11'>Wide (~58 km)</option><option value='12'>Regional (~29 km)</option><option value='13'>Local (~14 km)</option><option value='14'>Detail (~7 km)</option></select></label>
    <label>Markers<input id='mk' type='checkbox' checked></label>
  </div>
  <div id='globeCtl' style='display:flex;flex-direction:column;gap:.45rem'><label>Auto-rotate<input id='rot' type='checkbox'></label></div>
  <button id='reset'>Reset view</button>
</div>
<div id='bot' class='pn'><div id='cur'>drag to orbit, scroll to zoom, right-drag or shift-drag to pan</div><div id='pick'></div><div id='outside'></div></div>
<div id='legend' class='pn'></div>
"""


def _page(js: str, data: dict) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head>"
            f"<body><div id='wrap'><canvas id='c'></canvas>{UI}</div><script>{_vendor('three.min.js')}</script><script>{js.replace('__DATA__', _j(data))}</script></body></html>")


RAMPS = {"water": P.WATER, "veg": P.VEGETATION, "land": P.LAND, "ice": P.ICE, "slope": [P.VEGETATION[1], P.VEGETATION[4], P.LAND[3], P.VOLCANIC[2], P.VOLCANIC[0]],
         "volcanic": P.VOLCANIC}


def explorer_html(body: str, lat: float, lon: float, title: str, markers: Optional[List[dict]] = None, grid: Optional[dict] = None,
                  start: str = "globe", zoom: int = 12, exag: float = 1.6, path: Optional[list] = None) -> str:
    """markers: [{label, lat, lon, color, line?, main?, bbox?, cell?}]. grid: {h(flat list), n, cell_m, schematic, label}."""
    data = {"body": body, "lat": lat, "lon": lon, "title": title, "markers": markers or [], "tiles": TILE_SOURCES.get(body, {}), "ramps": RAMPS,
            "grid": grid, "start": start, "zoom": zoom, "exag": exag, "path": path or []}
    return _page(_js(), data)


def grid_payload(h: np.ndarray, cell_m: float, schematic: bool, label: str) -> dict:
    h = np.asarray(h, dtype=float)
    return {"n": int(h.shape[0]), "h": [round(float(v), 2) for v in h.ravel()], "cell_m": float(cell_m), "schematic": schematic, "label": label}


def available_models() -> List[Path]:
    return sorted(get_settings().models_dir.glob("*.glb")) + sorted(get_settings().models_dir.glob("*.gltf"))


def model_viewer_html(path: Path) -> str:
    """Orbit viewer for a user-supplied glTF/GLB (e.g. NASA 3D Resources rover or lander models)."""
    b64 = base64.b64encode(path.read_bytes()).decode()
    js = """
const wrap=document.getElementById('wrap'),canvas=document.getElementById('c');const r=new THREE.WebGLRenderer({canvas,antialias:true});r.setClearColor(0x080F1E,1);
const sc=new THREE.Scene(),cam=new THREE.PerspectiveCamera(40,1,0.01,1000);function rs(){r.setSize(wrap.clientWidth,wrap.clientHeight,false);cam.aspect=wrap.clientWidth/wrap.clientHeight;cam.updateProjectionMatrix();}addEventListener('resize',rs);rs();
sc.add(new THREE.AmbientLight(0xA8B8CE,0.8));const d=new THREE.DirectionalLight(0xffffff,1.2);d.position.set(5,8,6);sc.add(d);
let th=0.6,ph=1.1,rad=4,drag=false,px=0,py=0;canvas.onpointerdown=e=>{drag=true;px=e.clientX;py=e.clientY};canvas.onpointerup=()=>drag=false;
canvas.onpointermove=e=>{if(!drag)return;th-=(e.clientX-px)*0.006;ph=Math.max(0.1,Math.min(3,ph-(e.clientY-py)*0.006));px=e.clientX;py=e.clientY};canvas.onwheel=e=>{e.preventDefault();rad*=1+Math.sign(e.deltaY)*0.1};
const raw=atob(__B64__);const buf=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)buf[i]=raw.charCodeAt(i);
new THREE.GLTFLoader().parse(buf.buffer,'',g=>{const o=g.scene;const b=new THREE.Box3().setFromObject(o);const s=b.getSize(new THREE.Vector3()).length();o.scale.multiplyScalar(3/s);const b2=new THREE.Box3().setFromObject(o);o.position.sub(b2.getCenter(new THREE.Vector3()));sc.add(o);document.getElementById('st').textContent='Loaded';},e=>{document.getElementById('st').textContent='Could not parse model';});
(function L(){requestAnimationFrame(L);cam.position.set(rad*Math.sin(ph)*Math.sin(th),rad*Math.cos(ph),rad*Math.sin(ph)*Math.cos(th));cam.lookAt(0,0,0);r.render(sc,cam);})();
""".replace("__B64__", json.dumps(b64))
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div id='wrap'><canvas id='c'></canvas>"
            f"<div class='pn' style='left:12px;top:12px'><b>{path.name}</b><div id='st' style='color:{P.MOONLIGHT}'>Loading</div></div></div>"
            f"<script>{_vendor('three.min.js')}</script><script>{_vendor('GLTFLoader.js')}</script><script>{js}</script></body></html>")


def show(html: str, height: int = 600) -> None:
    """Embed generated HTML. Built only from this app's own data and bundled scripts, never user markup."""
    import streamlit as st
    import streamlit.components.v1 as components
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:  # pragma: no cover
        components.html(html, height=height, scrolling=False)
