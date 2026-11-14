"""Spectral reflectance curve matcher (blueprint Workspace 04).

The reference curves below are SCHEMATIC: Gaussian absorption features placed at commonly cited
band centres on a sloped continuum. They are NOT the USGS Spectral Library. Swap in real library
spectra (resampled to a common grid) by calling `register_spectrum`. Spectral resemblance is not
definitive mineral identification (grain size, mixtures, illumination and calibration all matter).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

WAVELENGTHS = np.arange(400, 2501, 10, dtype=float)  # nm

# mineral: (continuum_slope, [(centre_nm, width_nm, depth), ...])
_SCHEMATIC = {
    "olivine": (0.10, [(1050, 220, 0.45)]),
    "pyroxene": (0.05, [(930, 120, 0.30), (1900, 250, 0.35)]),
    "jarosite": (0.15, [(430, 60, 0.35), (910, 90, 0.25), (1470, 40, 0.20), (2265, 40, 0.30)]),
    "gypsum": (0.02, [(1450, 40, 0.30), (1750, 40, 0.20), (1940, 50, 0.45), (2215, 30, 0.20)]),
    "clay": (0.05, [(1410, 40, 0.25), (1910, 50, 0.30), (2200, 40, 0.35)]),
    "hematite": (0.20, [(530, 70, 0.30), (860, 100, 0.30)]),
}

_REGISTRY: Dict[str, np.ndarray] = {}


def _build(slope: float, feats: List[Tuple[float, float, float]]) -> np.ndarray:
    base = 0.25 + slope * (WAVELENGTHS - 400) / 2100
    r = base.copy()
    for c, w, d in feats:
        r -= d * base * np.exp(-0.5 * ((WAVELENGTHS - c) / w) ** 2)
    return np.clip(r, 0.01, 1.0)


for _name, (_s, _f) in _SCHEMATIC.items():
    _REGISTRY[_name] = _build(_s, _f)


def register_spectrum(name: str, wavelengths_nm: np.ndarray, reflectance: np.ndarray) -> None:
    _REGISTRY[name] = np.interp(WAVELENGTHS, wavelengths_nm, reflectance)


def minerals() -> List[str]:
    return sorted(_REGISTRY)


def spectrum(name: str) -> np.ndarray:
    return _REGISTRY[name]


def continuum_removed(r: np.ndarray) -> np.ndarray:
    """Divide by the upper convex hull so absorption features are comparable across slopes/brightness."""
    pts = list(zip(WAVELENGTHS, r))
    hull: List[Tuple[float, float]] = []
    for p in pts:
        while len(hull) >= 2 and (hull[-1][0] - hull[-2][0]) * (p[1] - hull[-2][1]) - (hull[-1][1] - hull[-2][1]) * (p[0] - hull[-2][0]) >= 0:
            hull.pop()
        hull.append(p)
    hx, hy = zip(*hull)
    cont = np.interp(WAVELENGTHS, hx, hy)
    return r / np.maximum(cont, 1e-9)


def spectral_angle(a: np.ndarray, b: np.ndarray) -> float:
    """Spectral angle mapper in radians (0 = identical shape)."""
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    return float(np.arccos(np.clip(cos, -1, 1)))


def absorption_bands(r: np.ndarray, min_depth: float = 0.08) -> List[Tuple[float, float]]:
    """Local minima of the continuum-removed curve deeper than min_depth: [(centre_nm, depth)]."""
    cr = continuum_removed(r)
    out = []
    for i in range(1, len(cr) - 1):
        if cr[i] < cr[i - 1] and cr[i] <= cr[i + 1] and 1 - cr[i] >= min_depth:
            out.append((float(WAVELENGTHS[i]), float(1 - cr[i])))
    return out


def match(name_a: str, name_b: str) -> Dict[str, float]:
    a, b = continuum_removed(_REGISTRY[name_a]), continuum_removed(_REGISTRY[name_b])
    ang = spectral_angle(a, b)
    return {"angle_rad": ang, "similarity": float(1 - ang / (np.pi / 2))}


def noisy_unknown(name: str, snr: float = 40.0, seed: int = 1) -> np.ndarray:
    """Utility for demos/tests: a mineral spectrum with noise (simulates a measured spectrum)."""
    rng = np.random.default_rng(seed)
    r = _REGISTRY[name]
    return np.clip(r + rng.normal(0, r.mean() / snr, r.shape), 0.01, 1.0)


def rank_against_library(measured: np.ndarray) -> List[Tuple[str, float]]:
    cm = continuum_removed(measured)
    res = []
    for k, v in _REGISTRY.items():
        ang = spectral_angle(cm, continuum_removed(v))
        res.append((k, float(1 - ang / (np.pi / 2))))
    res.sort(key=lambda x: -x[1])
    return res
