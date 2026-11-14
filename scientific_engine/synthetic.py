"""Synthetic terrain with PLANTED features and known ground truth.

Purpose: (1) a working discovery demonstration when no real DEM is available offline, and
(2) an honest benchmark for the detector (precision/recall against truth we control).
This is synthetic demonstration data, never Earth observations.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

from scientific_engine import dem
from scientific_engine.discovery import Grid


def planted_dem(seed: int = 4, n: int = 320, cell_m: float = 30.0, n_craters: int = 6, n_cones: int = 4, with_pit_chain: bool = True, depth_ratio: float = 0.18,
                bbox=(-113.62, 43.10, -113.30, 43.32)) -> Tuple[Grid, List[dict]]:
    rng = np.random.default_rng(seed)
    base = dem._fbm(n, rng, octaves=6, persistence=0.55) * 220.0           # gentle regional relief (m)
    yy, xx = np.mgrid[:n, :n].astype(float)
    truth: List[dict] = []
    z = base.copy()
    used: List[Tuple[float, float, float]] = []

    def free(r, c, rad):
        return all(math.hypot(r - r2, c - c2) > (rad + rad2) * 1.6 for r2, c2, rad2 in used)

    def place(kind):
        for _ in range(200):
            rad = rng.uniform(9, 26)
            r, c = rng.uniform(rad * 2, n - rad * 2, 2)
            if free(r, c, rad):
                used.append((r, c, rad)); return r, c, rad
        return None

    for _ in range(n_craters):
        p = place("crater")
        if p is None:
            continue
        r, c, rad = p
        d = np.hypot(yy - r, xx - c) / rad
        depth = depth_ratio * 2 * rad * cell_m
        bowl = -depth * np.clip(1 - d ** 2, 0, None) ** 1.5 * (d < 1)
        rim = 0.25 * depth * np.exp(-((d - 1.1) / 0.18) ** 2)
        z += bowl + rim
        truth.append({"kind": "depression", "r": r, "c": c, "diameter_m": 2 * rad * cell_m})
    for _ in range(n_cones):
        p = place("cone")
        if p is None:
            continue
        r, c, rad = p
        d = np.hypot(yy - r, xx - c) / rad
        h = (depth_ratio + 0.04) * 2 * rad * cell_m
        z += h * np.clip(1 - d, 0, None) ** 1.3 * (d < 1)
        truth.append({"kind": "mound", "r": r, "c": c, "diameter_m": 2 * rad * cell_m})
    if with_pit_chain:
        r0, c0 = n * 0.78, n * 0.12
        ang = math.radians(25)
        for k, t in enumerate(np.linspace(0, 120, 60)):
            r, c = r0 - t * math.sin(ang), c0 + t * math.cos(ang)
            d2 = (yy - r) ** 2 + (xx - c) ** 2
            z -= 10.0 * np.exp(-d2 / (2 * 2.2 ** 2))                         # shallow collapse trench
        for t in (25, 60, 95):
            r, c = r0 - t * math.sin(ang), c0 + t * math.cos(ang)
            d2 = (yy - r) ** 2 + (xx - c) ** 2
            z -= 38.0 * np.exp(-d2 / (2 * 3.5 ** 2))                         # skylight pits
        truth.append({"kind": "pit_chain", "r": r0 - 60 * math.sin(ang), "c": c0 + 60 * math.cos(ang), "diameter_m": 120 * cell_m})
    g = Grid(h=z, cell_m=cell_m, bbox=bbox, source="Synthetic demonstration terrain (planted features, not Earth data)", provenance_class="demonstration",
             crs="synthetic")
    return g, truth


def match_detections(dets: List[dict], truth: List[dict], tol_factor: float = 0.6) -> Dict[str, float]:
    """Greedy matching: a detection hits a truth feature of the same kind when the centres are within tol_factor x diameter."""
    used, tp = set(), 0
    errs = []
    for t in truth:
        best, bd = None, 1e9
        for i, d in enumerate(dets):
            if i in used or d["kind"] != t["kind"]:
                continue
            dist = math.hypot(d["r"] - t["r"], d["c"] - t["c"])
            if dist < bd:
                best, bd = i, dist
        tol = tol_factor * t["diameter_m"] / 30.0 if t["kind"] != "pit_chain" else 0.5 * t["diameter_m"] / 30.0
        if best is not None and bd <= tol:
            used.add(best); tp += 1; errs.append(bd)
    fp = sum(1 for i, d in enumerate(dets) if i not in used and d["kind"] in {t["kind"] for t in truth})
    prec = tp / max(tp + fp, 1); rec = tp / max(len(truth), 1)
    return {"tp": tp, "fp": fp, "fn": len(truth) - tp, "precision": prec, "recall": rec, "f1": 2 * prec * rec / max(prec + rec, 1e-9),
            "mean_center_error_px": float(np.mean(errs)) if errs else float("nan")}
