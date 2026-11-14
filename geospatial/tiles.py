"""Web-mercator tile maths and elevation-tile decoding (Terrarium encoding).

Used to build a real-elevation DEM for a user-chosen bounding box from the public AWS Terrain Tiles
(no key). Network access happens only in `fetch_dem`; everything else is pure and unit-tested.
Elevation (m) = (R * 256 + G + B / 256) - 32768.
"""
from __future__ import annotations

import hashlib
import io
import math
from typing import Dict, Optional, Tuple

import numpy as np

from config.settings import get_settings

TILE = 256
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
MAX_TILES = 36


def lonlat_to_tile(lon: float, lat: float, z: int) -> Tuple[float, float]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat = max(min(lat, 85.0511), -85.0511)
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def tile_to_lonlat(x: float, y: float, z: int) -> Tuple[float, float]:
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def meters_per_pixel(lat: float, z: int) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


def decode_terrarium(rgb: np.ndarray) -> np.ndarray:
    rgb = rgb.astype(np.float64)
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


def plan_tiles(bbox: Tuple[float, float, float, float], z: int) -> Dict:
    """bbox = (west, south, east, north) degrees. Returns tile index ranges and counts."""
    w, s, e, n = bbox
    x0, y1 = lonlat_to_tile(w, s, z); x1, y0 = lonlat_to_tile(e, n, z)
    xs, xe, ys, ye = int(math.floor(x0)), int(math.floor(x1)), int(math.floor(y0)), int(math.floor(y1))
    return {"x0": xs, "x1": xe, "y0": ys, "y1": ye, "count": (xe - xs + 1) * (ye - ys + 1), "z": z}


def choose_zoom(bbox, max_tiles: int = MAX_TILES, zmax: int = 13) -> int:
    for z in range(zmax, 5, -1):
        if plan_tiles(bbox, z)["count"] <= max_tiles:
            return z
    return 6


def fetch_dem(bbox: Tuple[float, float, float, float], zoom: Optional[int] = None) -> Dict:
    """Fetch and stitch elevation tiles for bbox. Returns dict with ok, dem (m), cell_m, bbox actually covered, source info.

    Cached on disk. On any network failure returns ok=False with the error (the caller shows it; nothing is invented).
    """
    import requests
    from PIL import Image
    z = zoom or choose_zoom(bbox)
    plan = plan_tiles(bbox, z)
    if plan["count"] > MAX_TILES:
        return {"ok": False, "error": f"Area needs {plan['count']} tiles at z{z}; reduce the area (limit {MAX_TILES})."}
    key = hashlib.sha1(f"{bbox}-{z}".encode()).hexdigest()[:16]
    cache = get_settings().cache_dir / f"dem_{key}.npz"
    lat_c = (bbox[1] + bbox[3]) / 2
    if cache.exists():
        d = np.load(cache)
        mosaic, covered = d["dem"], tuple(d["bbox"])
        cached = True
    else:
        cols, rows = plan["x1"] - plan["x0"] + 1, plan["y1"] - plan["y0"] + 1
        mosaic = np.zeros((rows * TILE, cols * TILE))
        try:
            for ty in range(plan["y0"], plan["y1"] + 1):
                for tx in range(plan["x0"], plan["x1"] + 1):
                    r = requests.get(URL.format(z=z, x=tx, y=ty), timeout=get_settings().http_timeout_s, headers={"User-Agent": "celestial-cartographers/0.2"})
                    r.raise_for_status()
                    img = np.array(Image.open(io.BytesIO(r.content)).convert("RGB"))
                    mosaic[(ty - plan["y0"]) * TILE:(ty - plan["y0"] + 1) * TILE, (tx - plan["x0"]) * TILE:(tx - plan["x0"] + 1) * TILE] = decode_terrarium(img)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"Elevation tiles unavailable: {type(e).__name__}: {e}"[:200]}
        west, north = tile_to_lonlat(plan["x0"], plan["y0"], z)
        east, south = tile_to_lonlat(plan["x1"] + 1, plan["y1"] + 1, z)
        covered = (west, south, east, north)
        np.savez_compressed(cache, dem=mosaic, bbox=np.array(covered))
        cached = False
    return {"ok": True, "dem": mosaic, "cell_m": meters_per_pixel(lat_c, z), "bbox": covered, "zoom": z, "cached": cached,
            "source": "AWS Terrain Tiles (Terrarium); blend of SRTM, 3DEP and other sources; nominal ~30 m", "crs": "EPSG:3857 tiles, elevation in metres",
            "provenance_class": "real"}
