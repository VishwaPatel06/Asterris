"""Seasonal deployment calendar (blueprint Workspace 04).

Produces a monthly suitability window and an uncertainty note, never a guaranteed forecast.
Uses real monthly data when the live archive is reachable, otherwise a sinusoidal estimate from the
catalogue's temp_mean/min/max (clearly flagged as an estimate).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def estimate_monthly(cand: dict) -> pd.DataFrame:
    """Sinusoidal monthly estimate from catalogue statistics. Northern-hemisphere peak in July."""
    mean, lo, hi = cand.get("temp_mean_c"), cand.get("temp_min_c"), cand.get("temp_max_c")
    if mean is None:
        return pd.DataFrame()
    amp = (hi - lo) / 4.0 if lo is not None and hi is not None else 5.0
    phase = 1 if cand["lat"] >= 0 else -1
    m = np.arange(1, 13)
    t = mean + phase * amp * np.sin(2 * np.pi * (m - 4) / 12)
    return pd.DataFrame({"month": m, "temp_mean_c": t, "temp_min_c": t - amp, "temp_max_c": t + amp, "precip_mm": np.nan})


def suitability_window(monthly: pd.DataFrame, comfort_min_c: float = -10.0, comfort_max_c: float = 30.0,
                       precip_limit_mm: float = 80.0) -> pd.DataFrame:
    """Score 0-1 per month: temperature within comfort band and (if known) low precipitation."""
    df = monthly.copy()
    mid = (comfort_min_c + comfort_max_c) / 2
    half = (comfort_max_c - comfort_min_c) / 2
    t_score = 1 - np.clip(np.abs(df["temp_mean_c"] - mid) / (half * 1.5), 0, 1)
    p = df["precip_mm"]
    p_score = np.where(p.isna(), 1.0, 1 - np.clip(p / (precip_limit_mm * 2), 0, 1))
    df["suitability"] = (0.7 * t_score + 0.3 * p_score).round(3)
    df["month_name"] = [MONTHS[m - 1] for m in df["month"]]
    return df
