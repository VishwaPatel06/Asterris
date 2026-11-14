"""DEM utilities: synthetic schematic terrain, terrain metrics, transects, GeoTIFF/ASCII loading.

Synthetic terrain is SCHEMATIC (blueprint Figure 3 style): it illustrates a morphology class
(crater, valley, lava tube, volcanic, flat). It is not measured Earth/Moon/Mars data. Upload a real
DEM (GeoTIFF or ESRI ASCII grid) in the app to replace it.
"""
from __future__ import annotations

import io
from typing import Dict, Optional, Tuple

import numpy as np


def _fbm(n: int, rng: np.random.Generator, octaves: int = 5, persistence: float = 0.5) -> np.ndarray:
    """Cheap fractal noise from upsampled random grids (no external deps)."""
    from scipy.ndimage import zoom
    out = np.zeros((n, n))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        k = 4 * (2 ** o)
        g = rng.standard_normal((k, k))
        out += amp * zoom(g, n / k, order=3)[:n, :n]
        total += amp
        amp *= persistence
    out /= total
    return (out - out.min()) / (out.max() - out.min() + 1e-12)


def synthetic_dem(kind: str = "crater", n: int = 96, size_m: float = 2000.0, relief_m: float = 200.0,
                  roughness: float = 0.3, seed: int = 3) -> Tuple[np.ndarray, float]:
    """Return (heights_m [n x n], cell_size_m)."""
    rng = np.random.default_rng(seed)
    x = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(x, x)
    R = np.sqrt(X ** 2 + Y ** 2)
    noise = _fbm(n, rng) - 0.5
    if kind == "crater":
        bowl = -np.exp(-(R / 0.45) ** 2)                      # depression
        rim = 0.35 * np.exp(-((R - 0.55) / 0.12) ** 2)         # raised rim
        ejecta = 0.08 * np.exp(-((R - 0.9) / 0.3) ** 2)
        h = bowl + rim + ejecta
    elif kind == "volcanic":
        cone = np.exp(-(R / 0.5) ** 2) - 0.25 * np.exp(-(R / 0.12) ** 2)  # cone with summit pit
        h = cone
    elif kind == "valley":
        h = (np.abs(X) ** 1.5) * 1.2 - 0.3 + 0.15 * np.sin(3 * Y)
        h -= h.min()
    elif kind == "lava_tube":
        # sinuous collapse trench with skylight pits
        centre = 0.25 * np.sin(2.5 * Y)
        trench = -0.6 * np.exp(-((X - centre) / 0.09) ** 2)
        pits = -0.5 * (np.exp(-(((X - centre) ** 2 + (Y + 0.3) ** 2) / 0.012)) + np.exp(-(((X - centre) ** 2 + (Y - 0.4) ** 2) / 0.015)))
        h = 0.15 * (_fbm(n, rng) - 0.5) + trench + pits
    else:  # flat
        h = 0.05 * (X + Y)
    h = h + noise * roughness * 0.6
    h = (h - h.min()) / (h.max() - h.min() + 1e-12)
    return h * relief_m, size_m / (n - 1)


def slope_deg(h: np.ndarray, cell: float) -> np.ndarray:
    gy, gx = np.gradient(h, cell)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def curvature(h: np.ndarray, cell: float) -> np.ndarray:
    gyy, _ = np.gradient(np.gradient(h, cell)[0], cell)
    _, gxx = np.gradient(np.gradient(h, cell)[1], cell)
    return gxx + gyy


def roughness_index(h: np.ndarray, cell: float, window: int = 3) -> np.ndarray:
    from scipy.ndimage import uniform_filter
    m = uniform_filter(h, window)
    return np.sqrt(np.maximum(uniform_filter(h ** 2, window) - m ** 2, 0))


def terrain_metrics(h: np.ndarray, cell: float) -> Dict[str, float]:
    s = slope_deg(h, cell)
    return {
        "elevation_min_m": float(h.min()), "elevation_max_m": float(h.max()),
        "relief_m": float(h.max() - h.min()),
        "mean_slope_deg": float(s.mean()), "max_slope_deg": float(s.max()),
        "steep_fraction_gt20": float((s > 20).mean()),
        "mean_roughness_m": float(roughness_index(h, cell).mean()),
        "cell_size_m": float(cell),
    }


def transect(h: np.ndarray, cell: float, a: Tuple[float, float], b: Tuple[float, float], samples: int = 120):
    """Sample the DEM along a line from a to b (fractions 0-1 of the grid). Returns distance_m, elevation_m, slope_deg."""
    from scipy.ndimage import map_coordinates
    n = h.shape[0]
    xs = np.linspace(a[0], b[0], samples) * (n - 1)
    ys = np.linspace(a[1], b[1], samples) * (n - 1)
    z = map_coordinates(h, [ys, xs], order=1)
    d = np.hypot(np.diff(xs), np.diff(ys)).cumsum() * cell
    d = np.concatenate([[0], d])
    ds = np.maximum(np.diff(d), 1e-9)
    sl = np.degrees(np.arctan(np.diff(z) / ds))
    sl = np.concatenate([[sl[0]], sl])
    return d, z, sl


def normalised_profile(z: np.ndarray) -> np.ndarray:
    return (z - z.min()) / (z.max() - z.min() + 1e-12)


def downsample(h: np.ndarray, n: int = 96) -> np.ndarray:
    from scipy.ndimage import zoom
    return zoom(h, (n / h.shape[0], n / h.shape[1]), order=1)


def load_uploaded_dem(name: str, data: bytes, n: int = 128) -> Tuple[Optional[np.ndarray], float, str]:
    """Read a user-supplied DEM. Supports GeoTIFF (needs rasterio) and ESRI ASCII grid (.asc/.txt).

    Returns (heights, cell_size_m, message). Records resampling in the message (blueprint 3.3).
    """
    lname = name.lower()
    try:
        if lname.endswith((".tif", ".tiff")):
            try:
                import rasterio
            except ImportError:
                return None, 0.0, "GeoTIFF support needs rasterio (pip install rasterio, requires GDAL)."
            with rasterio.MemoryFile(data) as mem, mem.open() as ds:
                arr = ds.read(1).astype(float)
                nod = ds.nodata
                if nod is not None:
                    arr[arr == nod] = np.nan
                res = abs(ds.res[0])
                crs = str(ds.crs) if ds.crs else "unknown CRS"
        elif lname.endswith((".asc", ".txt")):
            text = data.decode("utf-8", errors="ignore").splitlines()
            hdr = {}
            for i, line in enumerate(text[:6]):
                k, v = line.split()[:2]; hdr[k.lower()] = float(v)
            arr = np.loadtxt(io.StringIO("\n".join(text[6:])))
            arr[arr == hdr.get("nodata_value", -9999)] = np.nan
            res = hdr.get("cellsize", 1.0); crs = "ASCII grid (CRS not recorded)"
        else:
            return None, 0.0, "Unsupported file type. Use .tif/.tiff or .asc."
        if np.isnan(arr).all():
            return None, 0.0, "DEM contains only no-data cells."
        arr = np.where(np.isnan(arr), np.nanmedian(arr), arr)
        out = downsample(arr, n)
        cell = res * arr.shape[0] / n
        return out, float(cell), (f"Loaded {arr.shape[1]}x{arr.shape[0]} cells, {crs}; bilinear resampled to {n}x{n} "
                                  f"(effective cell ~{cell:.1f} map units). Units and vertical datum are NOT verified.")
    except Exception as e:  # noqa: BLE001
        return None, 0.0, f"Could not read DEM: {e}"
