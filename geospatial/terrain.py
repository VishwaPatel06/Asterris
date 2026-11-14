"""Terrain derivatives from a DEM: slope, roughness, curvature, hillshade, and semantic layer colouring."""
from __future__ import annotations

from typing import Dict

import numpy as np

from config import palette
from scientific_engine import dem as demlib


def hillshade(h: np.ndarray, cell: float, azimuth_deg: float = 315.0, altitude_deg: float = 40.0, exag: float = 1.0) -> np.ndarray:
    gy, gx = np.gradient(h * exag, cell)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(360 - azimuth_deg + 90), np.radians(altitude_deg)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(hs, 0, 1)


def derivatives(h: np.ndarray, cell: float) -> Dict[str, np.ndarray]:
    return {"elevation": h, "slope": demlib.slope_deg(h, cell), "roughness": demlib.roughness_index(h, cell, 5),
            "curvature": demlib.curvature(h, cell), "hillshade": hillshade(h, cell)}


def _hex(c: str):
    return np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], dtype=float)


def colorize(values: np.ndarray, ramp_name: str, vmin=None, vmax=None) -> np.ndarray:
    """Map a 2D array to RGB (uint8) using a semantic ramp. NaN becomes transparent-grey (missing, not low)."""
    ramp = palette.LAYER_RAMPS[ramp_name]
    stops = np.array([s for s, _ in ramp]); cols = np.array([_hex(c) for _, c in ramp])
    lo = np.nanmin(values) if vmin is None else vmin; hi = np.nanmax(values) if vmax is None else vmax
    t = np.clip((values - lo) / max(hi - lo, 1e-12), 0, 1)
    out = np.stack([np.interp(t, stops, cols[:, i]) for i in range(3)], -1)
    out[np.isnan(values)] = _hex(palette.UNAVAILABLE)
    return out.astype(np.uint8)
