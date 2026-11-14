"""Measured-data validation tools: score the models against evidence (uploaded or built-in literature pairs).

Everything here computes real error statistics from real inputs. Nothing is simulated to look like a measurement.
  * physics  : soil-bin / wheel test CSV  -> RMSE, MAE, MAPE, bias, R2 per quantity; optional parameter calibration
  * ranking  : labelled analogue pairs    -> precision@k, MRR, MAP, pooled AUC, Spearman
  * detector : labelled landform inventory -> precision, recall, F1, position error, diameter bias
  * real-terrain spot check on well-documented Earth impact craters (needs internet for elevation tiles)
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.stats import spearmanr

from config.mission_presets import PRESETS
from simulations import physics as P

PHYSICS_COLUMNS = ["wheel_load_N", "slip", "wheel_radius_m", "wheel_width_m", "drawbar_pull_N", "sinkage_mm", "torque_Nm"]


def regression_metrics(y: np.ndarray, yhat: np.ndarray) -> Dict[str, float]:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[m], yhat[m]
    if y.size == 0:
        return {"n": 0}
    err = yhat - y
    ss_res, ss_tot = float((err ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    nz = np.abs(y) > 1e-9
    return {"n": int(y.size), "RMSE": float(np.sqrt((err ** 2).mean())), "MAE": float(np.abs(err).mean()), "bias": float(err.mean()),
            "MAPE_pct": float(np.abs(err[nz] / y[nz]).mean() * 100) if nz.any() else float("nan"), "R2": float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")}


def physics_template() -> str:
    ex = pd.DataFrame([{"wheel_load_N": 60, "slip": 0.1, "wheel_radius_m": 0.2, "wheel_width_m": 0.12, "drawbar_pull_N": "", "sinkage_mm": "", "torque_Nm": ""}], columns=PHYSICS_COLUMNS)
    return ex.to_csv(index=False)


def _predict(df: pd.DataFrame, soil: P.Soil) -> pd.DataFrame:
    out = df.copy()
    sink, dp, tq = [], [], []
    for _, r in df.iterrows():
        res = P.wheel_forces(soil, float(r["wheel_load_N"]), float(r["wheel_radius_m"]), float(r["wheel_width_m"]), float(r["slip"]))
        sink.append(float(res["sinkage_m"]) * 1000); dp.append(float(res["DP_N"])); tq.append(float(res["T_Nm"]))
    out["pred_sinkage_mm"], out["pred_drawbar_pull_N"], out["pred_torque_Nm"] = sink, dp, tq
    return out


def evaluate_physics(df: pd.DataFrame, soil: P.Soil) -> Dict:
    need = {"wheel_load_N", "slip", "wheel_radius_m", "wheel_width_m"}
    if not need <= set(df.columns):
        return {"ok": False, "error": f"Missing columns: {sorted(need - set(df.columns))}"}
    df = df.copy()
    for c in PHYSICS_COLUMNS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=list(need))
    if df.empty:
        return {"ok": False, "error": "No valid rows."}
    pred = _predict(df, soil)
    metrics = {}
    for meas, p in (("drawbar_pull_N", "pred_drawbar_pull_N"), ("sinkage_mm", "pred_sinkage_mm"), ("torque_Nm", "pred_torque_Nm")):
        if meas in pred and pred[meas].notna().any():
            metrics[meas] = regression_metrics(pred[meas].to_numpy(), pred[p].to_numpy())
    if not metrics:
        return {"ok": False, "error": "Provide at least one measured column: drawbar_pull_N, sinkage_mm or torque_Nm."}
    return {"ok": True, "metrics": metrics, "table": pred}


def calibrate_soil(df: pd.DataFrame, soil: P.Soil) -> Dict:
    """Least-squares fit of Bekker-Wong parameters (relative residuals) to measured data. Needs >= 8 measured values."""
    ev0 = evaluate_physics(df, soil)
    if not ev0["ok"]:
        return ev0
    meas = [c for c in ("drawbar_pull_N", "sinkage_mm", "torque_Nm") if c in ev0["table"] and ev0["table"][c].notna().any()]
    n_meas = sum(int(ev0["table"][c].notna().sum()) for c in meas)
    if n_meas < 8:
        return {"ok": False, "error": f"Need at least 8 measured values to calibrate 6 parameters (have {n_meas})."}
    x0 = np.array([soil.n, soil.kc, soil.kphi, soil.c_kpa, soil.phi_deg, soil.K_m])
    lo = np.array([0.4, 0.01, 10, 0.0, 10, 0.002]); hi = np.array([1.6, 200, 20000, 50, 50, 0.1])
    pred_col = {"drawbar_pull_N": "pred_drawbar_pull_N", "sinkage_mm": "pred_sinkage_mm", "torque_Nm": "pred_torque_Nm"}

    def mk(x):
        return P.Soil(soil.name + " (calibrated)", *x, "calibrated to user data")

    def resid(x):
        pr = _predict(df_clean, mk(x))
        r = []
        for c in meas:
            y, yh = pr[c].to_numpy(float), pr[pred_col[c]].to_numpy(float)
            scale = np.maximum(np.abs(y), np.nanmax(np.abs(y)) * 0.05 + 1e-9)
            r.append(np.nan_to_num((yh - y) / scale))
        return np.concatenate(r)

    df_clean = ev0["table"][[c for c in PHYSICS_COLUMNS if c in ev0["table"]]]
    sol = least_squares(resid, np.clip(x0, lo * 1.0001, hi * 0.9999), bounds=(lo, hi), max_nfev=60)
    fitted = mk(sol.x)
    ev1 = evaluate_physics(df_clean, fitted)
    return {"ok": True, "before": ev0["metrics"], "after": ev1["metrics"], "soil": fitted, "params": dict(zip(["n", "kc", "kphi", "c_kpa", "phi_deg", "K_m"], map(float, sol.x))),
            "note": "Calibrated parameters describe THIS data set. Check on held-out tests before trusting them elsewhere."}


# ------------------------------------------------------------------------------------ ranking vs labels
# Weak labels compiled from widely documented analogue usage. They are NOT ground truth for "best analogue"; verify citations before publishing.
LITERATURE_PAIRS = [
    ("mars_jezero", "rio_tinto", 1), ("mars_jezero", "atacama", 1), ("mars_gale", "atacama", 1), ("mars_gale", "rio_tinto", 1), ("mars_gale", "dry_valleys", 1),
    ("mars_arsia", "hawaii_tubes", 1), ("mars_phoenix", "dry_valleys", 1), ("mars_phoenix", "haughton", 1), ("moon_shackleton", "mauna_kea", 1),
    ("moon_shackleton", "haughton", 1), ("moon_marius", "hawaii_tubes", 1), ("moon_taurus", "mauna_kea", 1), ("moon_taurus", "askja", 1)]


def _auc(pos: List[float], neg: List[float]) -> float:
    if not pos or not neg:
        return float("nan")
    return float(np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg]))


def evaluate_ranking(pairs: List[Tuple[str, str, float]], targets: List[dict], candidates: List[dict], objective: str = "Geological Exploration") -> Dict:
    """How well does the similarity ranking recover labelled analogue pairs? pairs = (target_id, candidate_id, relevance 0/1 or graded)."""
    from scientific_engine.similarity import rank_candidates
    tmap = {t["id"]: t for t in targets}; per, pooled_pos, pooled_neg, sc_all, rel_all = [], [], [], [], []
    for tid in sorted({p[0] for p in pairs}):
        if tid not in tmap:
            continue
        rows = rank_candidates(tmap[tid], candidates, PRESETS[objective], objective)
        rel = {c: r for t, c, r in pairs if t == tid}
        rel = {c: r for c, r in rel.items() if c in {x["id"] for x in rows}}
        if not rel or not any(v > 0 for v in rel.values()):
            continue
        ranks = {r["id"]: r["rank"] for r in rows}; score = {r["id"]: r["total"] for r in rows}
        rel_full = {r["id"]: rel.get(r["id"], 0) for r in rows}
        pos = [c for c, v in rel_full.items() if v > 0]
        order = [r["id"] for r in rows]
        hits = np.cumsum([1 if rel_full[c] > 0 else 0 for c in order])
        ap = float(np.mean([hits[i] / (i + 1) for i, c in enumerate(order) if rel_full[c] > 0]))
        mrr = 1.0 / min(ranks[c] for c in pos)
        per.append({"target": tmap[tid]["name"].split(" (")[0], "labelled analogues": len(pos), "best rank": min(ranks[c] for c in pos), "hit@3": int(any(ranks[c] <= 3 for c in pos)),
                    "precision@3": sum(1 for c in order[:3] if rel_full[c] > 0) / 3, "average precision": ap, "reciprocal rank": mrr})
        pooled_pos += [score[c] for c in pos if score[c] is not None]
        pooled_neg += [score[c] for c, v in rel_full.items() if v == 0 and score[c] is not None]
        for c in rel_full:
            if score[c] is not None:
                sc_all.append(score[c]); rel_all.append(rel_full[c])
    if not per:
        return {"ok": False, "error": "No labelled pair matched a known target and candidate id."}
    df = pd.DataFrame(per)
    rho = float(spearmanr(sc_all, rel_all)[0]) if len(set(rel_all)) > 1 else float("nan")
    random_hit3 = float(np.mean([min(1.0, 3 * l / len(candidates)) for l in df["labelled analogues"]]))
    return {"ok": True, "per_target": df, "hit_at_3": float(df["hit@3"].mean()), "mean_reciprocal_rank": float(df["reciprocal rank"].mean()), "map": float(df["average precision"].mean()),
            "auc": _auc(pooled_pos, pooled_neg), "spearman": rho, "random_hit_at_3_expected": random_hit3, "n_targets": len(df), "n_candidates": len(candidates), "objective": objective}


def parse_pairs(df: pd.DataFrame) -> Tuple[List[Tuple[str, str, float]], str]:
    need = {"target_id", "candidate_id", "relevance"}
    if not need <= set(df.columns):
        return [], f"Missing columns: {sorted(need - set(df.columns))}"
    return [(str(r.target_id), str(r.candidate_id), float(r.relevance)) for r in df.itertuples() if pd.notna(r.relevance)], ""


# ------------------------------------------------------------------------------------ detector vs inventory
def _hav_m(la1, lo1, la2, lo2):
    p1, p2 = math.radians(la1), math.radians(la2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def evaluate_inventory(cands: List[dict], inv: pd.DataFrame, kinds=("crater",), tol_factor: float = 0.5) -> Dict:
    """Match detections to a labelled inventory (lat, lon, diameter_m). A hit = centre within tol_factor x inventory diameter."""
    need = {"lat", "lon", "diameter_m"}
    if not need <= set(inv.columns):
        return {"ok": False, "error": f"Missing columns: {sorted(need - set(inv.columns))}"}
    dets = [c for c in cands if c.get("morphology") in kinds or not kinds]
    used, errs, derr, tp = set(), [], [], 0
    for r in inv.itertuples():
        best, bd = None, 1e18
        for i, c in enumerate(dets):
            if i in used:
                continue
            d = _hav_m(r.lat, r.lon, c["lat"], c["lon"])
            if d < bd:
                best, bd = i, d
        if best is not None and bd <= tol_factor * r.diameter_m:
            used.add(best); tp += 1; errs.append(bd); derr.append((dets[best]["diameter_m"] - r.diameter_m) / r.diameter_m * 100)
    fp = len(dets) - len(used); fn = len(inv) - tp
    prec, rec = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return {"ok": True, "tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": 2 * prec * rec / max(prec + rec, 1e-9),
            "mean_position_error_m": float(np.mean(errs)) if errs else float("nan"), "diameter_bias_pct": float(np.mean(derr)) if derr else float("nan"),
            "note": "Precision counts every detection of the chosen kinds inside the scanned area; inventories often omit small or degraded craters, which lowers precision."}


# Well-documented Earth impact structures (Earth Impact Database values, rounded)
KNOWN_CRATERS = [("Meteor Crater (Arizona)", 35.0275, -111.0225, 1186.0), ("Lonar Crater (India)", 19.9767, 76.5086, 1830.0), ("Tenoumer (Mauritania)", 22.9167, -10.4000, 1900.0)]


def real_crater_spot_check(half_size_deg: float = 0.05) -> Dict:
    """Run the detector on real elevation tiles around known craters. Needs internet. Returns per-site hit/miss, centre and diameter error."""
    from geospatial import tiles
    from scientific_engine import discovery
    rows = []
    for name, lat, lon, d in KNOWN_CRATERS:
        r = tiles.fetch_dem((lon - half_size_deg, lat - half_size_deg, lon + half_size_deg, lat + half_size_deg))
        if not r["ok"]:
            rows.append({"site": name, "status": "elevation tiles unavailable", "known diameter (m)": d}); continue
        g = discovery.Grid(r["dem"], r["cell_m"], r["bbox"], r["source"], "real")
        dets = discovery.detect_landforms(g, min_diameter_m=max(150.0, d * 0.25), max_diameter_m=d * 3)
        best = None
        for x in dets:
            if x["kind"] != "depression":
                continue
            lo, la = g.rc_to_lonlat(x["r"], x["c"]); dist = _hav_m(lat, lon, la, lo)
            if best is None or dist < best[0]:
                best = (dist, x["diameter_m"])
        hit = best is not None and best[0] <= 0.5 * d
        rows.append({"site": name, "status": "detected" if hit else "missed", "known diameter (m)": d, "detected diameter (m)": None if best is None else round(best[1]),
                     "centre error (m)": None if best is None else round(best[0]), "diameter error (%)": None if best is None else round((best[1] - d) / d * 100, 1), "cell size (m)": round(r["cell_m"], 1)})
    ok = [r for r in rows if r["status"] in ("detected", "missed")]
    return {"rows": rows, "recall": (sum(r["status"] == "detected" for r in ok) / len(ok)) if ok else float("nan"), "n_checked": len(ok),
            "note": "Recall over a handful of well-known craters. This is a spot check, not a statistical benchmark; precision cannot be judged from three sites."}
