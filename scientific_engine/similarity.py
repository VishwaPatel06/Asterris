"""Eight-dimension similarity ranker (blueprint Workspace 03 + Section 3).

UI-independent. Pure functions over plain dicts so Streamlit, tests, notebooks or a future FastAPI
layer can all call the same code.

Key rules implemented:
* S_total = sum(w_i * S_i) over *available* dimensions, weights renormalised, coverage reported.
* Missing data is None, never 0. Missing != dissimilar.
* Three scores kept separate: analogue fidelity, mission suitability, transferability.
* Scores are similarity indices, NOT probabilities.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from config import scoring_config as cfg
from config.mission_presets import DIMENSIONS, PHYSICS_SENSITIVITY, PRESETS
from config.planetary_constants import mismatch

ENV_DIMENSIONS = [d for d in DIMENSIONS if d != "operations"]


def _present(*vals) -> bool:
    return all(v is not None for v in vals)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ----------------------------------------------------------------------------------------------
# Dimension scorers: return (score in [0,1]) or None when data are insufficient
# ----------------------------------------------------------------------------------------------
def geology_similarity(t: dict, c: dict) -> Optional[float]:
    parts, weights = [], []
    mt, mc = set(t.get("minerals") or []), set(c.get("minerals") or [])
    if mt and mc:
        parts.append(len(mt & mc) / len(mt | mc))
        weights.append(cfg.GEOLOGY_MINERAL_WEIGHT)
    if t.get("lithology") and c.get("lithology"):
        parts.append(1.0 if t["lithology"] == c["lithology"] else 0.0)
        weights.append(cfg.GEOLOGY_LITHOLOGY_WEIGHT)
    if not parts:
        return None
    return float(np.average(parts, weights=weights))


def terrain_similarity(t: dict, c: dict) -> Optional[float]:
    comps, weights = [], []
    ws, wr, wl = cfg.TERRAIN_WEIGHTS
    if _present(t.get("slope_deg"), c.get("slope_deg")):
        comps.append(abs(t["slope_deg"] - c["slope_deg"]) / cfg.SLOPE_RANGE_DEG); weights.append(ws)
    if _present(t.get("roughness"), c.get("roughness")):
        comps.append(abs(t["roughness"] - c["roughness"])); weights.append(wr)
    if _present(t.get("relief_m"), c.get("relief_m")):
        d = abs(math.log10(max(t["relief_m"], 1)) - math.log10(max(c["relief_m"], 1))) / cfg.RELIEF_LOG_RANGE
        comps.append(d); weights.append(wl)
    if not comps:
        return None
    return _clip01(1.0 - float(np.average(comps, weights=weights)))


def temperature_similarity(t: dict, c: dict) -> Optional[float]:
    if not _present(t.get("temp_mean_c"), c.get("temp_mean_c")):
        return None
    mean_term = _clip01(1.0 - abs(t["temp_mean_c"] - c["temp_mean_c"]) / cfg.TEMP_MEAN_RANGE_C)
    if _present(t.get("temp_min_c"), t.get("temp_max_c"), c.get("temp_min_c"), c.get("temp_max_c")):
        lo = max(t["temp_min_c"], c["temp_min_c"]); hi = min(t["temp_max_c"], c["temp_max_c"])
        inter = max(0.0, hi - lo)
        union = max(t["temp_max_c"], c["temp_max_c"]) - min(t["temp_min_c"], c["temp_min_c"])
        iou = inter / union if union > 0 else 0.0
        return cfg.TEMP_OVERLAP_WEIGHT * iou + cfg.TEMP_MEAN_WEIGHT * mean_term
    return mean_term


def _abs_diff_sim(key: str):
    def f(t: dict, c: dict) -> Optional[float]:
        if not _present(t.get(key), c.get(key)):
            return None
        return _clip01(1.0 - abs(t[key] - c[key]))
    return f


def operations_score(t: dict, c: dict) -> Optional[float]:
    """Operations is candidate feasibility (access, logistics), not environmental similarity."""
    v = c.get("operations")
    return None if v is None else _clip01(v)


SCORERS = {
    "geology": geology_similarity,
    "terrain": terrain_similarity,
    "temperature": temperature_similarity,
    "water_ice": _abs_diff_sim("water_ice"),
    "dust": _abs_diff_sim("dust"),
    "biology": _abs_diff_sim("biology"),
    "caves": _abs_diff_sim("caves"),
    "operations": operations_score,
}


def dimension_scores(target: dict, cand: dict) -> Dict[str, Optional[float]]:
    return {d: SCORERS[d](target, cand) for d in DIMENSIONS}


def normalise_weights(w: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, v) for v in w.values())
    if s <= 0:
        return {d: 1.0 / len(DIMENSIONS) for d in DIMENSIONS}
    return {d: max(0.0, w.get(d, 0.0)) / s for d in DIMENSIONS}


def weighted_score(scores: Dict[str, Optional[float]], weights: Dict[str, float], dims: List[str] = None):
    """Return (score, coverage). coverage = share of weight mass backed by real data."""
    dims = dims or DIMENSIONS
    wsum = sum(weights.get(d, 0.0) for d in dims)
    if wsum <= 0:
        return None, 0.0
    avail = [d for d in dims if scores.get(d) is not None and weights.get(d, 0.0) > 0]
    mass = sum(weights[d] for d in avail)
    if mass <= 0:
        return None, 0.0
    total = sum(weights[d] * scores[d] for d in avail) / mass
    return float(total), float(mass / wsum)


def label(score: Optional[float]) -> str:
    if score is None:
        return "no data"
    return "high" if score >= cfg.HIGH else "medium" if score >= cfg.MEDIUM else "low"


def transferability(fidelity: Optional[float], body: str, objective: str) -> Optional[float]:
    """Heuristic: fidelity discounted by unavoidable physical mismatches weighted by objective sensitivity."""
    if fidelity is None:
        return None
    sens = PHYSICS_SENSITIVITY.get(objective, {})
    penalty = sum(s * mismatch(body, f) for f, s in sens.items())
    return _clip01(fidelity * (1.0 - penalty))


def mission_suitability(cand: dict) -> Optional[float]:
    """Access/logistics (operations) combined with slope-based terrain safety. Independent of target similarity.

    With no access data the score falls back to terrain safety alone (flagged by suitability_basis) rather than guessing logistics."""
    ops = cand.get("operations")
    slope = cand.get("slope_deg")
    safety = None if slope is None else _clip01(1.0 - slope / 35.0)
    if ops is None:
        return safety
    return 0.7 * ops + 0.3 * (1.0 if safety is None else safety)


def score_uncertainty(target: dict, cand: dict, weights: Dict[str, float], draws: int = 120, seed: int = 5) -> Optional[tuple]:
    """5th-95th percentile of the similarity index when measured features are perturbed by their relative measurement error.

    Uses cand["feature_sigma"] (relative sigma per feature) or a default of 10% for measured numeric features. Reflects measurement
    noise only; it does NOT include model-form error or the effect of missing dimensions (see coverage for that)."""
    base, _ = weighted_score(dimension_scores(target, cand), normalise_weights(weights))
    if base is None:
        return None
    rng = np.random.default_rng(seed)
    sig = {"slope_deg": 0.10, "roughness": 0.10, "relief_m": 0.15, "temp_mean_c": 0.05, "water_ice": 0.15, "dust": 0.10, "biology": 0.15, "caves": 0.15}
    sig.update(cand.get("feature_sigma") or {})
    w = normalise_weights(weights); vals = []
    for _ in range(draws):
        c2 = dict(cand)
        for k, s_ in sig.items():
            v = cand.get(k)
            if v is not None and isinstance(v, (int, float)):
                nv = v * (1 + rng.normal(0, s_)) if k != "temp_mean_c" else v + rng.normal(0, max(abs(v), 10) * s_)
                c2[k] = float(np.clip(nv, 0, 1)) if k in ("roughness", "water_ice", "dust", "biology", "caves") else float(nv)
        t, _ = weighted_score(dimension_scores(target, c2), w)
        if t is not None:
            vals.append(t)
    return (float(np.percentile(vals, 5)), float(np.percentile(vals, 95))) if vals else None


def score_candidate(target: dict, cand: dict, weights: Dict[str, float], objective: str) -> dict:
    w = normalise_weights(weights)
    ds = dimension_scores(target, cand)
    total, coverage = weighted_score(ds, w)
    env_w = {d: w[d] for d in ENV_DIMENSIONS}
    fidelity, fid_cov = weighted_score(ds, env_w, ENV_DIMENSIONS)
    missing = [d for d in DIMENSIONS if ds[d] is None and w[d] > 0]
    return {
        "id": cand["id"], "name": cand["name"], "dimension_scores": ds,
        "total": total, "coverage": coverage, "missing_dimensions": missing,
        "fidelity": fidelity, "fidelity_coverage": fid_cov,
        "suitability": mission_suitability(cand),
        "suitability_basis": "access + terrain" if cand.get("operations") is not None else ("terrain safety only (no access data)" if cand.get("slope_deg") is not None else "no data"),
        "interval": score_uncertainty(target, cand, w),
        "transferability": transferability(fidelity, target["body"], objective),
        "data_quality": cand.get("data_quality"),
        "label": label(total),
    }


def rank_candidates(target: dict, candidates: List[dict], weights: Dict[str, float], objective: str) -> List[dict]:
    rows = [score_candidate(target, c, weights, objective) for c in candidates]
    rows.sort(key=lambda r: (-1 if r["total"] is None else -r["total"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def sensitivity_analysis(target: dict, candidates: List[dict], weights: Dict[str, float], objective: str,
                         draws: int = cfg.SENSITIVITY_DRAWS, seed: int = 7) -> List[dict]:
    """Perturb weights (Dirichlet around the preset) and report rank stability.

    A candidate that stays top-3 across perturbations is robust to the weight choice.
    """
    rng = np.random.default_rng(seed)
    base = normalise_weights(weights)
    alpha = np.array([base[d] * cfg.SENSITIVITY_CONCENTRATION + 0.05 for d in DIMENSIONS])
    dscores = {c["id"]: dimension_scores(target, c) for c in candidates}
    ranks = {c["id"]: [] for c in candidates}
    for _ in range(draws):
        wv = rng.dirichlet(alpha)
        w = dict(zip(DIMENSIONS, wv))
        tot = {cid: (weighted_score(ds, w)[0] if weighted_score(ds, w)[0] is not None else -1) for cid, ds in dscores.items()}
        order = sorted(tot, key=lambda k: -tot[k])
        for r, cid in enumerate(order, 1):
            ranks[cid].append(r)
    out = []
    for c in candidates:
        r = np.array(ranks[c["id"]])
        out.append({"id": c["id"], "name": c["name"], "mean_rank": float(r.mean()), "rank_std": float(r.std()),
                    "best_rank": int(r.min()), "worst_rank": int(r.max()), "p_top3": float((r <= 3).mean())})
    out.sort(key=lambda x: x["mean_rank"])
    return out


def rank_all_objectives(target: dict, cand: dict) -> Dict[str, Optional[float]]:
    """Why a candidate ranks differently under alternative objectives (blueprint A21)."""
    return {obj: score_candidate(target, cand, w, obj)["total"] for obj, w in PRESETS.items()}
