"""Vectorised physics engine for rover-soil interaction and slope dynamics.

Models
  * Bekker-Wong rigid-wheel terramechanics: normal stress  sigma = k r^n (cos t - cos t1)^n,  k = kc/b + kphi,
    shear stress  tau = (c + sigma tan(phi)) (1 - exp(-j/K)),  j = r[(t1 - t) - (1 - s)(sin t1 - sin t)].
    Load W, drawbar pull DP and torque T are integrals over the contact arc, solved for sinkage by vectorised bisection.
  * Quasi-static slope climbing: slip s* such that n_wheels * DP(s*) = m g sin(slope).
  * Transient 1-D longitudinal dynamics integrated with RK4.
Assumptions (all of them matter): rigid wheel, flat soil surface, exit angle = 0, soil parameters independent of gravity,
constant slip along the contact arc, no grousers, no suspension compliance, no thermal/dust effects.
Soil parameter sets are literature-cited or illustrative and are NOT calibrated to any specific vehicle or regolith.
This engine is VERIFIED against analytic solutions (see scientific_engine/validation.py) but NOT VALIDATED against hardware tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional

import numpy as np

_trapz = getattr(np, "trapezoid", None) or np.trapz
G_EARTH = 9.80665
N_THETA = 64
SLIP_GRID = np.linspace(0.0, 0.9, 46)


@dataclass(frozen=True)
class Soil:
    name: str
    n: float            # sinkage exponent
    kc: float           # kN/m^(n+1)
    kphi: float         # kN/m^(n+2)
    c_kpa: float        # cohesion
    phi_deg: float      # internal friction angle
    K_m: float          # shear deformation modulus
    status: str         # provenance of the parameters


SOILS: Dict[str, Soil] = {s.name: s for s in [
    Soil("Dry sand (Wong textbook values)", 1.1, 0.99, 1528.43, 1.04, 28.0, 0.010, "literature-cited (Wong, Terramechanics and Off-Road Vehicle Engineering); verify before use"),
    Soil("Lunar regolith (commonly cited Apollo-era values)", 1.0, 1.4, 820.0, 0.17, 35.0, 0.018, "literature-cited approximation; regolith varies strongly with depth and compaction"),
    Soil("Compacted basaltic soil (illustrative)", 0.9, 5.0, 2500.0, 5.0, 33.0, 0.015, "ILLUSTRATIVE placeholder; calibrate with a soil-bin or in-situ test"),
]}


def _hs(soil: Soil) -> tuple:
    return soil.n, (soil.kc, soil.kphi), soil.c_kpa * 1000.0, math.tan(math.radians(soil.phi_deg)), soil.K_m


def _integrals(soil: Soil, r: float, b: float, theta1: np.ndarray, s: np.ndarray):
    """W, DP, T per contact angle theta1 and slip s (broadcast arrays). Returns arrays in N, N, N*m."""
    n, (kc, kphi), c, tanphi, K = _hs(soil)
    k = (kc / b + kphi) * 1000.0
    u = np.linspace(0.0, 1.0, N_THETA)
    th = theta1[..., None] * u                                   # (..., N_THETA)
    cos1 = np.cos(theta1)[..., None]
    sig = k * r ** n * np.clip(np.cos(th) - cos1, 0.0, None) ** n
    j = r * ((theta1[..., None] - th) - (1.0 - s[..., None]) * (np.sin(theta1)[..., None] - np.sin(th)))
    tau = (c + sig * tanphi) * (1.0 - np.exp(-np.clip(j, 0.0, None) / K))
    dth = theta1
    W = r * b * _trapz(sig * np.cos(th) + tau * np.sin(th), u, axis=-1) * dth
    DP = r * b * _trapz(tau * np.cos(th) - sig * np.sin(th), u, axis=-1) * dth
    T = r * r * b * _trapz(tau, u, axis=-1) * dth
    return W, DP, T


def wheel_forces(soil: Soil, load_n, r: float, b: float, slip) -> Dict[str, np.ndarray]:
    """Solve sinkage for a given wheel load and evaluate drawbar pull and torque. `load_n` and `slip` broadcast."""
    load = np.asarray(load_n, dtype=float); s = np.asarray(slip, dtype=float)
    load, s = np.broadcast_arrays(load, s)
    lo = np.full(load.shape, 1e-5); hi = np.full(load.shape, math.acos(0.1))      # sinkage up to 0.9 r
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        W, _, _ = _integrals(soil, r, b, mid, s)
        over = W > load
        hi = np.where(over, mid, hi); lo = np.where(over, lo, mid)
    t1 = 0.5 * (lo + hi)
    W, DP, T = _integrals(soil, r, b, t1, s)
    return {"theta1": t1, "sinkage_m": r * (1 - np.cos(t1)), "W_N": W, "W_residual": (W - load) / np.maximum(load, 1e-9), "DP_N": DP, "T_Nm": T,
            "saturated": t1 >= math.acos(0.1) - 1e-6}


def plate_sinkage(soil: Soil, pressure_pa: float, b: float) -> float:
    """Closed-form Bekker plate sinkage z = (p / k)^(1/n). Used as an analytic check of the pressure-sinkage law."""
    n, (kc, kphi), *_ = _hs(soil)
    return (pressure_pa / ((kc / b + kphi) * 1000.0)) ** (1.0 / n)


@lru_cache(maxsize=512)
def _climb_cached(soil_name: str, mass: float, g: float, wheels: int, r: float, b: float, slope_deg: float) -> tuple:
    soil = SOILS[soil_name]
    th = math.radians(slope_deg)
    load = mass * g * math.cos(th) / wheels
    need = mass * g * math.sin(th) / wheels
    f = wheel_forces(soil, load, r, b, SLIP_GRID)
    dp = f["DP_N"]
    if f["saturated"].any() and f["saturated"][0]:
        return (False, float("nan"), float(f["sinkage_m"][0]), float("nan"), float(dp.max()), need, "wheel sinks beyond 0.9 r under this load")
    if dp.max() < need:
        return (False, float("nan"), float(f["sinkage_m"][int(np.argmax(dp))]), float("nan"), float(dp.max()), need, "insufficient drawbar pull at any slip up to 0.9")
    i = int(np.argmax(dp >= need))
    if i == 0:
        s_star, z, T = 0.0, float(f["sinkage_m"][0]), float(f["T_Nm"][0])
    else:
        w = (need - dp[i - 1]) / max(dp[i] - dp[i - 1], 1e-12)
        s_star = float(SLIP_GRID[i - 1] + w * (SLIP_GRID[i] - SLIP_GRID[i - 1]))
        z = float(f["sinkage_m"][i - 1] + w * (f["sinkage_m"][i] - f["sinkage_m"][i - 1])); T = float(f["T_Nm"][i - 1] + w * (f["T_Nm"][i] - f["T_Nm"][i - 1]))
    return (True, s_star, z, T, float(dp.max()), need, "ok")


def climb(soil: Soil, mass_kg: float, g: float, wheels: int, r: float, b: float, slope_deg: float) -> Dict:
    ok, s, z, T, dpmax, need, note = _climb_cached(soil.name, round(mass_kg, 6), round(g, 6), wheels, round(r, 6), round(b, 6), round(slope_deg, 4))
    out = {"feasible": ok, "slip": s, "sinkage_mm": z * 1000, "torque_per_wheel_Nm": T, "max_pull_per_wheel_N": dpmax, "required_pull_per_wheel_N": need, "note": note}
    if ok:
        out["energy_J_per_m"] = wheels * T / (r * max(1 - s, 1e-3))      # mechanical energy per metre travelled
    return out


def max_climbable_slope(soil: Soil, mass_kg: float, g: float, wheels: int, r: float, b: float, hi_deg: float = 45.0) -> float:
    lo, hi = 0.0, hi_deg
    if climb(soil, mass_kg, g, wheels, r, b, hi)["feasible"]:
        return hi
    for _ in range(18):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if climb(soil, mass_kg, g, wheels, r, b, mid)["feasible"] else (lo, mid)
    return lo


def gravity_sweep(soil: Soil, mass_kg: float, wheels: int, r: float, b: float, slope_deg: float, gravities) -> Dict[str, np.ndarray]:
    """Sinkage and slip across gravity levels (Moon 1.62, Mars 3.72, Earth 9.81 ...). Vectorised in one pass."""
    g = np.asarray(gravities, dtype=float)
    load = mass_kg * g * math.cos(math.radians(slope_deg)) / wheels
    f = wheel_forces(soil, load, r, b, np.zeros_like(g))
    return {"g": g, "sinkage_mm": f["sinkage_m"] * 1000, "load_N": load, "resistance_N": -f["DP_N"]}


def rolling_resistance_coeff(soil: Soil, mass_kg: float, g: float, wheels: int, r: float, b: float) -> float:
    """Motion-resistance coefficient R/W at small slip, from the terramechanics model (floored at 0.01)."""
    load = mass_kg * g / wheels
    f = wheel_forces(soil, load, r, b, 0.02)
    return float(max(-float(f["DP_N"]) / load, 0.01))


def gravity_offload(mass_kg: float, wheels: int, r: float, b: float, g_target: float, slope_deg: float, soil: Soil,
                    offload_efficiency: float = 1.0) -> Dict:
    """What a gravity-offload rig must supply, and what the soil interaction looks like on Earth vs under the target gravity.

    N = m g cos(slope) (normal load), T = F r (wheel torque from the pull force F). Offload rig mass-equivalent = removed weight / g_earth.
    `offload_efficiency` < 1 models an imperfect rig that only removes that share of the excess weight.
    """
    th = math.radians(slope_deg)
    N_e, N_t = mass_kg * G_EARTH * math.cos(th), mass_kg * g_target * math.cos(th)
    removed = (N_e - N_t) * offload_efficiency
    N_eff = N_e - removed
    out = {"normal_load_earth_N": N_e, "normal_load_target_N": N_t, "offload_force_N": removed, "offload_mass_equiv_kg": removed / G_EARTH,
           "normal_load_with_rig_N": N_eff, "residual_gravity_error_pct": (N_eff - N_t) / max(N_t, 1e-9) * 100.0}
    for tag, load in (("earth", N_e), ("target", N_t), ("rig", N_eff)):
        f = wheel_forces(soil, load / wheels, r, b, 0.0)
        out[f"sinkage_{tag}_mm"] = float(f["sinkage_m"]) * 1000
    cl_t = climb(soil, mass_kg, g_target, wheels, r, b, slope_deg); cl_e = climb(soil, mass_kg, G_EARTH, wheels, r, b, slope_deg)
    out["climb_target"], out["climb_earth"] = cl_t, cl_e
    out["torque_per_wheel_target_Nm"] = (cl_t["torque_per_wheel_Nm"] if cl_t["feasible"] else float("nan"))
    out["torque_per_wheel_earth_Nm"] = (cl_e["torque_per_wheel_Nm"] if cl_e["feasible"] else float("nan"))
    out["max_slope_target_deg"] = max_climbable_slope(soil, mass_kg, g_target, wheels, r, b)
    out["max_slope_earth_deg"] = max_climbable_slope(soil, mass_kg, G_EARTH, wheels, r, b)
    return out


# ---------------------------------------------------------------------------------------------
# Transient dynamics (RK4)
# ---------------------------------------------------------------------------------------------
def rk4(f, y0: np.ndarray, t0: float, t1: float, dt: float) -> tuple:
    n = max(int(round((t1 - t0) / dt)), 1); h = (t1 - t0) / n
    y = np.array(y0, dtype=float); ts, ys = [t0], [y.copy()]
    t = t0
    for _ in range(n):
        k1 = f(t, y); k2 = f(t + h / 2, y + h / 2 * k1); k3 = f(t + h / 2, y + h / 2 * k2); k4 = f(t + h, y + h * k3)
        y = y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4); t += h
        ts.append(t); ys.append(y.copy())
    return np.array(ts), np.array(ys)


def accelerate_on_slope(soil: Soil, mass_kg: float, g: float, wheels: int, r: float, b: float, slope_deg: float, wheel_speed_rad_s: float,
                        duration_s: float = 20.0, dt: float = 0.05) -> Dict:
    """Rover accelerating up a slope with constant wheel angular speed. Slip s = 1 - v/(w r); pull from the terramechanics table.
    State = [v, x]. Illustrates inertial effects the quasi-static solver ignores."""
    th = math.radians(slope_deg)
    load = mass_kg * g * math.cos(th) / wheels
    f = wheel_forces(soil, load, r, b, SLIP_GRID)
    dp_tab = f["DP_N"]; vmax = wheel_speed_rad_s * r

    def rhs(t, y):
        v = min(max(y[0], 0.0), vmax)
        s = 1.0 - v / vmax
        pull = np.interp(min(s, SLIP_GRID[-1]), SLIP_GRID, dp_tab) * wheels
        a = (pull - mass_kg * g * math.sin(th)) / mass_kg
        return np.array([a if not (y[0] <= 0 and a < 0) else 0.0, y[0]])

    ts, ys = rk4(rhs, np.array([0.0, 0.0]), 0.0, duration_s, dt)
    return {"t": ts, "v": ys[:, 0], "x": ys[:, 1], "v_final": float(ys[-1, 0]), "distance_m": float(ys[-1, 1])}
