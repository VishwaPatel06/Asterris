"""Model verification suite: the numbers behind "model accuracy" and "physics engine accuracy".

IMPORTANT distinction shown in the UI:
  VERIFICATION = does the code solve its equations correctly? (checked here against closed-form solutions and invariants)
  VALIDATION   = do the equations match reality? (needs hardware / field data, which this build does NOT have)
So: physics results below prove numerical correctness, not real-world predictive accuracy.
The similarity index has no ground-truth labels, so only internal consistency can be measured.
The detector is scored on SYNTHETIC planted features; its accuracy on real terrain is unknown until labelled data are supplied.
"""
from __future__ import annotations

import math
import time
from functools import lru_cache
from typing import Dict, List

import numpy as np
from scipy.stats import kendalltau

from config.mission_presets import DIMENSIONS, PRESETS
from simulations import physics as P

Row = Dict[str, object]


def _row(group: str, name: str, metric: str, value: float, tol: float, desc: str, higher_is_better: bool = False) -> Row:
    passed = (value >= tol) if higher_is_better else (value <= tol)
    return {"group": group, "check": name, "metric": metric, "value": value, "threshold": tol, "passed": bool(passed), "what it checks": desc}


# --------------------------------------------------------------------------------------------- physics
def physics_verification() -> List[Row]:
    rows: List[Row] = []
    # 1. wheel integrals vs closed form (n=1, no shear): W and DP
    soil = P.Soil("closed-form", 1.0, 1.4, 820.0, 0.0, 0.0, 0.02, "test")
    r, b, t1 = 0.2, 0.12, 0.35
    k = (soil.kc / b + soil.kphi) * 1000.0
    W_an = r * b * k * r * (t1 / 2 + math.sin(2 * t1) / 4 - math.sin(t1) * math.cos(t1))
    DP_an = -r * b * k * r * (math.sin(t1) ** 2 / 2 - math.cos(t1) * (1 - math.cos(t1)))
    W, DP, _ = P._integrals(soil, r, b, np.array(t1), np.array(0.0))
    rows.append(_row("Physics", "Normal-load integral vs closed form", "relative error", abs(float(W) - W_an) / W_an, 1e-3, "Bekker-Wong normal stress integral (n=1, tau=0) against its analytic solution"))
    rows.append(_row("Physics", "Drawbar-pull integral vs closed form", "relative error", abs(float(DP) - DP_an) / abs(DP_an), 1e-3, "Compaction-resistance integral against its analytic solution"))
    # 2. load equilibrium of the sinkage solver across all soils and bodies
    worst = 0.0
    for s in P.SOILS.values():
        for g in (1.62, 3.72, 9.80665):
            f = P.wheel_forces(s, 150 * g / 4, 0.2, 0.12, np.linspace(0, 0.8, 5))
            worst = max(worst, float(np.abs(f["W_residual"]).max()))
    rows.append(_row("Physics", "Sinkage solver load equilibrium", "max |W - load| / load", worst, 1e-6, "Integrated soil reaction equals applied wheel load for 3 soils x 3 gravities x 5 slips"))
    # 3. plate sinkage round trip
    z = 0.03
    p = k * z ** soil.n
    rows.append(_row("Physics", "Bekker plate pressure-sinkage law", "relative error", abs(P.plate_sinkage(soil, p, b) - z) / z, 1e-9, "Closed-form pressure-sinkage relation inverts exactly"))
    # 4. RK4 vs analytic (linear drag) and convergence order
    a_, kd = 2.0, 0.5
    f_ = lambda t, y: np.array([a_ - kd * y[0]])
    v_an = lambda t: a_ / kd * (1 - math.exp(-kd * t))
    errs = []
    for dt in (0.4, 0.2, 0.1):
        ts, ys = P.rk4(f_, np.array([0.0]), 0.0, 4.0, dt)
        errs.append(abs(ys[-1, 0] - v_an(4.0)))
    rows.append(_row("Physics", "RK4 integrator vs analytic solution", "abs error (dt=0.1)", errs[-1], 1e-6, "dv/dt = a - kv against v(t) = a/k (1 - e^-kt)"))
    order = math.log2(errs[0] / errs[1])
    rows.append(_row("Physics", "RK4 convergence order", "observed order (expect 4)", order, 3.5, "Error ratio when halving the step", higher_is_better=True))
    # 5. energy conservation: harmonic oscillator, 10 periods
    w = 2.0
    osc = lambda t, y: np.array([y[1], -w * w * y[0]])
    ts, ys = P.rk4(osc, np.array([1.0, 0.0]), 0.0, 10 * 2 * math.pi / w, 0.01)
    e0 = 0.5 * ys[0, 1] ** 2 + 0.5 * w * w * ys[0, 0] ** 2; e1 = 0.5 * ys[-1, 1] ** 2 + 0.5 * w * w * ys[-1, 0] ** 2
    rows.append(_row("Physics", "Energy conservation (10 periods)", "relative drift", abs(e1 - e0) / e0, 1e-6, "Conservative system under RK4"))
    # 6. quasi-static slope solution reproduces the required pull
    s = P.SOILS["Dry sand (Wong textbook values)"]
    cl = P.climb(s, 150, 3.72, 4, 0.2, 0.12, 12)
    f = P.wheel_forces(s, 150 * 3.72 * math.cos(math.radians(12)) / 4, 0.2, 0.12, cl["slip"])
    rows.append(_row("Physics", "Slope solver self-consistency", "relative pull error", abs(float(f["DP_N"]) - cl["required_pull_per_wheel_N"]) / cl["required_pull_per_wheel_N"], 0.01, "Re-evaluating the pull at the solved slip returns m g sin(slope)/n"))
    # 7. gravity offload exactness
    o = P.gravity_offload(100, 4, 0.2, 0.1, 1.62, 0, s)
    rows.append(_row("Physics", "Offload force = m (g_e - g_t)", "relative error", abs(o["offload_force_N"] - 100 * (P.G_EARTH - 1.62)) / (100 * (P.G_EARTH - 1.62)), 1e-12, "Weight removed by an ideal rig"))
    # 8. physical trends
    sk = P.gravity_sweep(s, 150, 4, 0.2, 0.12, 0, [1.62, 3.72, 9.80665])["sinkage_mm"]
    rows.append(_row("Physics", "Sinkage increases with gravity", "ordering holds (1 = yes)", float(sk[0] < sk[1] < sk[2]), 1.0, "Moon < Mars < Earth for identical vehicle and soil", higher_is_better=True))
    dp = P.wheel_forces(s, 150 * 3.72 / 4, 0.2, 0.12, P.SLIP_GRID)["DP_N"]
    rows.append(_row("Physics", "Drawbar pull rises with slip", "fraction of monotone steps", float((np.diff(dp) >= -1e-9).mean()), 1.0, "Traction curve is non-decreasing over 0-0.9 slip", higher_is_better=True))
    return rows


def physics_throughput() -> Dict[str, float]:
    s = P.SOILS["Dry sand (Wong textbook values)"]
    loads = np.linspace(20, 200, 100)[:, None]; slips = np.linspace(0, 0.8, 100)[None, :]
    t = time.perf_counter(); P.wheel_forces(s, loads, 0.2, 0.12, slips); dt = time.perf_counter() - t
    return {"evaluations": 10000, "seconds": dt, "evals_per_second": 10000 / dt}


# --------------------------------------------------------------------------------------------- similarity
def similarity_verification() -> List[Row]:
    from data_sources.seed_catalog import CANDIDATES, TARGETS
    from scientific_engine import similarity as S
    rows: List[Row] = []
    T = TARGETS[0]; w = PRESETS["Polar Ice Drilling"]
    twin = {**T, "id": "twin", "name": "twin", "operations": 1.0}
    rows.append(_row("Similarity", "Identical site scores 1.0", "1 - fidelity", 1 - S.score_candidate(T, twin, w, "Polar Ice Drilling")["fidelity"], 1e-9, "A site identical to the target reaches full environmental fidelity"))
    base = {**T, "id": "x", "name": "x", "operations": 0.5}
    vals = [S.score_candidate(T, {**base, "slope_deg": T["slope_deg"] + d}, w, "Polar Ice Drilling")["dimension_scores"]["terrain"] for d in range(0, 21, 2)]
    rows.append(_row("Similarity", "Terrain similarity monotone in slope gap", "fraction of non-increasing steps", float((np.diff(vals) <= 1e-12).mean()), 1.0, "Larger slope mismatch never raises the terrain score", higher_is_better=True))
    sc = S.score_candidate(T, {**CANDIDATES[0], "water_ice": None}, w, "Polar Ice Drilling")
    rows.append(_row("Similarity", "Missing data is not zero", "dimension score is None and coverage < 1", float(sc["dimension_scores"]["water_ice"] is None and sc["coverage"] < 1), 1.0, "Missing water/ice is excluded and reported, not scored as 0", higher_is_better=True))
    rows.append(_row("Similarity", "Weights normalise to 1", "|sum - 1|", abs(sum(S.normalise_weights({d: 7 for d in DIMENSIONS}).values()) - 1), 1e-12, "Any positive weights are renormalised"))
    a = [r["id"] for r in S.rank_candidates(T, CANDIDATES, w, "Polar Ice Drilling")]
    b = [r["id"] for r in S.rank_candidates(T, list(reversed(CANDIDATES)), w, "Polar Ice Drilling")]
    rows.append(_row("Similarity", "Ranking independent of input order", "identical ranking (1 = yes)", float(a == b), 1.0, "Permuting candidates does not change the ranking", higher_is_better=True))
    rng = np.random.default_rng(11); taus = []
    base_rank = {r["id"]: r["total"] for r in S.rank_candidates(T, CANDIDATES, w, "Polar Ice Drilling")}
    ids = list(base_rank)
    for _ in range(100):
        wp = {d: max(w[d] * (1 + rng.uniform(-0.1, 0.1)), 0) for d in DIMENSIONS}
        r2 = {r["id"]: r["total"] for r in S.rank_candidates(T, CANDIDATES, wp, "Polar Ice Drilling")}
        taus.append(kendalltau([base_rank[i] for i in ids], [r2[i] for i in ids])[0])
    rows.append(_row("Similarity", "Rank stability under +/-10% weight noise", "mean Kendall tau", float(np.mean(taus)), 0.9, "Rank correlation with the unperturbed ranking over 100 perturbations", higher_is_better=True))
    return rows


# --------------------------------------------------------------------------------------------- detector
def detector_benchmark(seeds=range(1, 6)) -> Dict:
    from scientific_engine import discovery, synthetic
    out = []
    for label, ratio in (("fresh features (depth/diameter 0.18)", 0.18), ("moderately degraded (0.12)", 0.12), ("heavily degraded (0.09)", 0.09)):
        ms = []
        for sd in seeds:
            g, truth = synthetic.planted_dem(sd, depth_ratio=ratio)
            ms.append(synthetic.match_detections(discovery.detect_landforms(g), truth))
        out.append({"scenario": label, "precision": float(np.mean([m["precision"] for m in ms])), "recall": float(np.mean([m["recall"] for m in ms])),
                    "f1": float(np.mean([m["f1"] for m in ms])), "false_positives_per_scene": float(np.mean([m["fp"] for m in ms])),
                    "center_error_px": float(np.nanmean([m["mean_center_error_px"] for m in ms])), "scenes": len(list(seeds))})
    return {"rows": out, "note": "Scored on SYNTHETIC planted craters, cones and a pit chain over fractal background terrain. Accuracy on real DEMs is unknown until labelled data are supplied."}


@lru_cache(maxsize=1)
def run_all() -> Dict:
    t = time.perf_counter()
    res = {"physics": physics_verification(), "similarity": similarity_verification(), "detector": detector_benchmark(), "throughput": physics_throughput()}
    res["elapsed_s"] = time.perf_counter() - t
    allrows = res["physics"] + res["similarity"]
    res["passed"] = sum(r["passed"] for r in allrows); res["total"] = len(allrows)
    res["physics_passed"] = sum(r["passed"] for r in res["physics"]); res["physics_total"] = len(res["physics"])
    return res


def _plain(o):
    if isinstance(o, dict):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def load_or_run(force: bool = False) -> Dict:
    """Verification results cached on disk (storage/cache/verification.json). Recomputed when forced or when the file is missing."""
    import json
    from config import scoring_config as cfg
    from config.settings import get_settings
    path = get_settings().cache_dir / "verification.json"
    if path.exists() and not force:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if d.get("model_version") == cfg.MODEL_VERSION:
                return d
        except Exception:  # noqa: BLE001
            pass
    run_all.cache_clear()
    d = _plain(run_all()); d["model_version"] = cfg.MODEL_VERSION
    d["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return d
