"""Global Earth Analog Discovery Engine: candidate DISCOVERY (this module) is separate from SCORING (similarity.py).

Pipeline (blueprint Workspace 03 B):
  1 scan DEM  2 find signatures  3 detect landforms  4 generate boundaries  5 extract features
  6 apply mission filters  -> hand over to similarity.rank_candidates (7-10)  11 explain.

Detector = transparent morphometric baseline, NOT a trained deep-learning model:
  * multi-scale Laplacian-of-Gaussian blob search on a smoothed DEM,
  * depression / mound classification with measured depth-to-diameter and rim checks,
  * pit-chain and valley detection from linear negative-curvature structures.
Its accuracy is reported against synthetic ground truth in scientific_engine/validation.py. It has not been
validated against a labelled real-world crater/volcano inventory, so detections are CANDIDATES that need
imagery or field confirmation.
Features that no input dataset provides (lithology, water, dust, biology, temperature, access) stay None.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage as ndi

from config.mission_presets import MISSION_FILTERS
from geospatial import terrain

DETECTOR_VERSION = "cc-morphometric-0.2"
MIN_RATIO = 0.09          # minimum depth (or height) to diameter ratio; more degraded landforms are NOT detected (documented limitation)


@dataclass
class Grid:
    """A DEM plus its georeference. bbox = (west, south, east, north) in degrees (equirectangular, small-area approximation)."""
    h: np.ndarray
    cell_m: float
    bbox: Tuple[float, float, float, float]
    source: str = "unspecified"
    provenance_class: str = "local"
    crs: str = "EPSG:4326 (assumed)"

    def rc_to_lonlat(self, r: float, c: float) -> Tuple[float, float]:
        w, s, e, n = self.bbox
        ny, nx = self.h.shape
        return w + (c + 0.5) / nx * (e - w), n - (r + 0.5) / ny * (n - s)


def _detect_blobs(h_s: np.ndarray, cell: float, sigmas: List[float], sign: int, thr: float) -> List[Tuple[int, int, float, float]]:
    """LoG blob maxima. sign=+1 finds depressions (positive Laplacian), -1 finds mounds. Returns (r, c, sigma_px, response)."""
    stack = np.stack([ndi.gaussian_laplace(h_s, s) * s * s * sign for s in sigmas])
    mx = ndi.maximum_filter(stack, size=(3, 9, 9))
    peaks = (stack == mx) & (stack > thr)
    out = []
    for k, r, c in zip(*np.nonzero(peaks)):
        out.append((int(r), int(c), sigmas[k], float(stack[k, r, c])))
    out.sort(key=lambda t: -t[3])
    kept: List[Tuple[int, int, float, float]] = []
    for r, c, s, v in out:           # non-maximum suppression across scales
        if all(math.hypot(r - r2, c - c2) > 1.5 * max(s, s2) * 1.414 for r2, c2, s2, _ in kept):
            kept.append((r, c, s, v))
    return kept


def _ring_stats(h: np.ndarray, r: int, c: int, rad: float) -> Tuple[float, float, float, np.ndarray]:
    """(rim_median, interior_min, interior_median, ring_values) around a blob of radius rad (px)."""
    yy, xx = np.ogrid[:h.shape[0], :h.shape[1]]
    d = np.hypot(yy - r, xx - c)
    inner = h[d <= rad * 0.8]
    ring = h[(d >= rad * 0.95) & (d <= rad * 1.35)]
    if inner.size < 4 or ring.size < 8:
        return np.nan, np.nan, np.nan, ring
    return float(np.median(ring)), float(inner.min()), float(np.median(inner)), ring


def _sector_closure(h: np.ndarray, r: int, c: int, rad: float, level: float, above: bool) -> float:
    """Fraction of 12 angular sectors whose ring median lies above (depression) / below (mound) `level`: 1.0 = closed rim."""
    ok = 0
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        vals = []
        for rr in np.linspace(rad * 1.0, rad * 1.3, 4):
            y, x = int(round(r + rr * math.sin(a))), int(round(c + rr * math.cos(a)))
            if 0 <= y < h.shape[0] and 0 <= x < h.shape[1]:
                vals.append(h[y, x])
        if not vals:
            continue
        m = float(np.median(vals))
        ok += (m >= level) if above else (m <= level)
    return ok / 12.0


def detect_landforms(grid: Grid, min_diameter_m: float = 150.0, max_diameter_m: float = 8000.0, sensitivity: float = 1.0) -> List[dict]:
    """Return raw detections: dicts with type, row/col centre, diameter, depth/height, confidence. Deterministic."""
    h, cell = grid.h.astype(float), grid.cell_m
    h_s = ndi.gaussian_filter(h, 1.0)
    rmin, rmax = min_diameter_m / (2 * cell) / 1.414, max_diameter_m / (2 * cell) / 1.414
    sigmas = list(np.geomspace(max(rmin, 1.5), max(rmax, 3.0), 8))
    noise = float(np.median(np.abs(ndi.gaussian_laplace(h_s, 1.5)))) + 1e-6
    thr = max(noise * 4.0 / sensitivity, 0.02 * (np.ptp(h) + 1e-6) / 10)
    dets: List[dict] = []
    for sign, kind in ((+1, "depression"), (-1, "mound")):
        for r, c, s, v in _detect_blobs(h_s, cell, sigmas, sign, thr):
            rad = s * 1.414
            rim, fmin, fmed, _ring = _ring_stats(h_s, r, c, rad)
            if np.isnan(rim):
                continue
            diam = 2 * rad * cell
            if kind == "depression":
                depth = rim - fmin
                ratio = depth / diam
                if not (MIN_RATIO <= ratio <= 0.40) or depth < 6.0:
                    continue
                closure = _sector_closure(h_s, r, c, rad, fmin + 0.5 * depth, True)
                if closure < 0.75 / sensitivity ** 0.5:
                    continue
                conf = float(np.clip((ratio - MIN_RATIO) / 0.10, 0, 1) * 0.4 + closure * 0.4 + np.clip(v / (thr * 4), 0, 1) * 0.2)
                dets.append({"kind": "depression", "r": r, "c": c, "diameter_m": diam, "depth_m": depth, "ratio": ratio, "confidence": conf})
            else:
                height = fmed - rim
                ratio = height / diam
                if not (MIN_RATIO <= ratio <= 0.45) or height < 8.0:
                    continue
                closure = _sector_closure(h_s, r, c, rad, rim + 0.5 * height, False)
                if closure < 0.75 / sensitivity ** 0.5:
                    continue
                conf = float(np.clip((ratio - MIN_RATIO) / 0.10, 0, 1) * 0.4 + closure * 0.4 + np.clip(v / (thr * 4), 0, 1) * 0.2)
                dets.append({"kind": "mound", "r": r, "c": c, "diameter_m": diam, "depth_m": height, "ratio": ratio, "confidence": conf})
    dets += _linear_features(h_s, cell, dets)
    return dets


def _linear_features(h_s: np.ndarray, cell: float, blobs: List[dict]) -> List[dict]:
    """Valleys / trenches from strong negative curvature that is elongated; pit chains when >=2 depressions lie along them."""
    gy, gx = np.gradient(h_s, cell)
    gyy, gyx = np.gradient(gy, cell); gxy, gxx = np.gradient(gx, cell)
    tr, det = gxx + gyy, gxx * gyy - gxy * gyx
    lam_min = tr / 2 - np.sqrt(np.maximum(tr * tr / 4 - det, 0))      # most negative curvature -> ridges; we want valleys = largest positive
    lam_max = tr / 2 + np.sqrt(np.maximum(tr * tr / 4 - det, 0))
    valley = (lam_max > 0) & (np.abs(lam_min) < 0.35 * lam_max)       # strong curvature in one direction only
    thr = np.percentile(lam_max[valley], 90) if valley.any() else 0
    mask = ndi.binary_opening(valley & (lam_max > thr), iterations=1)
    lab, n = ndi.label(mask, structure=np.ones((3, 3)))
    out = []
    for i in range(1, n + 1):
        rr, cc = np.nonzero(lab == i)
        if rr.size < 12:
            continue
        pts = np.stack([rr, cc], 1).astype(float); pts -= pts.mean(0)
        ev = np.linalg.eigvalsh(np.cov(pts.T) + 1e-9 * np.eye(2))
        length_px, width_px = 4 * math.sqrt(ev[1]), 4 * math.sqrt(max(ev[0], 1e-6))
        if length_px / max(width_px, 1.0) < 4.0 or length_px * cell < 400:
            continue
        r0, c0 = rr.mean(), cc.mean()
        z = h_s[rr, cc]
        near = [b for b in blobs if b["kind"] == "depression" and np.min(np.hypot(rr - b["r"], cc - b["c"])) < 4]
        kind = "pit_chain" if len(near) >= 2 else "valley"
        out.append({"kind": kind, "r": int(r0), "c": int(c0), "diameter_m": length_px * cell, "width_m": width_px * cell, "depth_m": float(np.ptp(z)),
                    "ratio": width_px / length_px, "pits": len(near), "confidence": float(np.clip(0.35 + 0.1 * len(near) + 0.2 * min(length_px * cell / 2000, 1), 0, 0.9)),
                    "pixels": (int(rr.min()), int(rr.max()), int(cc.min()), int(cc.max()))})
    return out


MORPH = {"depression": "crater", "mound": "volcanic", "pit_chain": "lava_tube", "valley": "valley"}
LABEL = {"depression": "Circular depression (crater/pit candidate)", "mound": "Positive-relief mound (cone/dome candidate)",
         "pit_chain": "Aligned pit chain (lava-tube candidate)", "valley": "Linear valley or channel"}


def _scale(det: dict) -> str:
    d = det["diameter_m"]
    if det["kind"] == "pit_chain":
        return "cave"
    if det["kind"] == "valley":
        return "valley"
    return "crater" if d < 3000 and det["kind"] == "depression" else "formation"


def build_candidates(grid: Grid, dets: List[dict], region_name: str = "region", climate: Optional[dict] = None) -> List[dict]:
    """Turn detections into candidate records using the shared schema. Unknown features remain None."""
    h, cell = grid.h, grid.cell_m
    der = terrain.derivatives(h, cell)
    cands = []
    for i, d in enumerate(sorted(dets, key=lambda x: -x["confidence"])):
        rad = max(d["diameter_m"] / (2 * cell), 3.0)
        r0, c0 = d["r"], d["c"]
        r1, r2, c1, c2 = max(int(r0 - rad), 0), min(int(r0 + rad) + 1, h.shape[0]), max(int(c0 - rad), 0), min(int(c0 + rad) + 1, h.shape[1])
        if "pixels" in d:
            r1, r2, c1, c2 = d["pixels"][0], d["pixels"][1] + 1, d["pixels"][2], d["pixels"][3] + 1
        patch = der["slope"][r1:r2, c1:c2]; elev = h[r1:r2, c1:c2]; rough = der["roughness"][r1:r2, c1:c2]
        lon, lat = grid.rc_to_lonlat(r0, c0)
        w, n = grid.rc_to_lonlat(r1, c1); e, s = grid.rc_to_lonlat(r2, c2)
        cid = "DISC-" + hashlib.sha1(f"{lat:.5f}{lon:.5f}{d['kind']}{grid.source}".encode()).hexdigest()[:8].upper()
        c = {
            "id": cid, "name": f"{LABEL[d['kind']].split(' (')[0]} {cid[-4:]} ({region_name})", "lat": float(lat), "lon": float(lon), "scale": _scale(d),
            "morphology": MORPH[d["kind"]], "status": "data-screened candidate", "baseline": False, "country": "", "body": "Earth",
            "bbox": [float(min(w, e)), float(min(s, n)), float(max(w, e)), float(max(s, n))],
            "lithology": None, "minerals": [], "slope_deg": float(np.mean(patch)), "roughness": float(np.clip(np.mean(rough) / 15.0, 0, 1)),
            "relief_m": float(max(np.ptp(elev), d.get("depth_m", 0))), "elevation_m": float(np.mean(elev)),
            "temp_mean_c": None, "temp_min_c": None, "temp_max_c": None, "water_ice": None, "water_basis": None, "dust": None, "biology": None,
            "caves": float(np.clip(d.get("pits", 0) / 3.0, 0, 1)) if d["kind"] in ("pit_chain",) else 0.0, "operations": None,
            "sources": [grid.source, f"detector {DETECTOR_VERSION}"], "resolution_m": float(cell), "data_quality": float(np.clip(0.3 + 0.5 * d["confidence"], 0, 0.8)),
            "basis": "derived", "provenance_class": "derived", "detector_kind": d["kind"], "detector_confidence": d["confidence"],
            "diameter_m": d["diameter_m"], "depth_m": d.get("depth_m"), "grid_rc": [int(r0), int(c0)], "dem_provenance": grid.provenance_class,
            "feature_sigma": {"slope_deg": 0.15, "roughness": 0.15, "relief_m": 0.2},
            "caves_basis": "DEM-derived pit evidence at this resolution only; 0 means none detected, not none present",
        }
        if climate and climate.get("temp_mean_c") is not None:
            c.update(temp_mean_c=climate["temp_mean_c"], temp_min_c=climate["temp_min_c"], temp_max_c=climate["temp_max_c"])
            c["sources"].append(climate.get("source", "climatology"))
        cands.append(c)
    return cands


def apply_mission_filters(cands: List[dict], objective: str, user: Optional[dict] = None) -> Tuple[List[dict], List[dict]]:
    """Step 6: constraints applied BEFORE similarity. Returns (kept, rejected_with_reason)."""
    f = {**MISSION_FILTERS.get(objective, {}), **(user or {})}
    kept, rej = [], []
    for c in cands:
        why = None
        if f.get("morphologies") and c["morphology"] not in f["morphologies"]:
            why = f"morphology '{c['morphology']}' not in {sorted(f['morphologies'])}"
        elif f.get("max_slope_deg") is not None and c["slope_deg"] is not None and c["slope_deg"] > f["max_slope_deg"]:
            why = f"mean slope {c['slope_deg']:.1f} deg exceeds {f['max_slope_deg']} deg"
        elif f.get("min_confidence") is not None and c["detector_confidence"] < f["min_confidence"]:
            why = f"detector confidence {c['detector_confidence']:.2f} below {f['min_confidence']}"
        elif f.get("min_diameter_m") is not None and c["diameter_m"] < f["min_diameter_m"]:
            why = f"size {c['diameter_m']:.0f} m below {f['min_diameter_m']} m"
        (rej.append({**c, "rejected_because": why}) if why else kept.append(c))
    return kept, rej


def run_discovery(grid: Grid, objective: str, region_name: str = "region", climate: Optional[dict] = None, sensitivity: float = 1.0,
                  user_filters: Optional[dict] = None, min_diameter_m: float = 150.0) -> Dict:
    dets = detect_landforms(grid, min_diameter_m=min_diameter_m, sensitivity=sensitivity)
    cands = build_candidates(grid, dets, region_name, climate)
    kept, rejected = apply_mission_filters(cands, objective, user_filters)
    area_km2 = grid.h.shape[0] * grid.h.shape[1] * (grid.cell_m / 1000) ** 2
    return {"detections": len(dets), "candidates": kept, "rejected": rejected, "area_km2": area_km2, "cell_m": grid.cell_m, "detector": DETECTOR_VERSION,
            "coverage_note": f"Scanned {area_km2:,.0f} km2 at {grid.cell_m:.0f} m/px from '{grid.source}'. This is a regional scan, not a global search."}
