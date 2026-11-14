"""Near-real-time Earth data feeds (no API keys needed).

"Live" means near-real-time: every feed has its own latency, shown in the UI. All calls have short
timeouts and return a result dict with `ok` and `error` so the app degrades gracefully offline.
The Moon and Mars have no live feeds here; their side of every comparison is a reference value.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Dict, List, Optional

import requests

TIMEOUT = 8
HEADERS = {"User-Agent": "celestial-cartographers/0.1 (research prototype)"}


def _get(url: str, params: dict = None) -> dict:
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT, headers=HEADERS)
        r.raise_for_status()
        return {"ok": True, "data": r.json(), "fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200], "data": None}


def open_meteo_current(lat: float, lon: float) -> dict:
    """Current conditions, hourly updates. Source: Open-Meteo (model-based, not a station)."""
    res = _get("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "UTC",
        "current": "temperature_2m,surface_pressure,wind_speed_10m,cloud_cover,relative_humidity_2m,shortwave_radiation",
    })
    if not res["ok"]:
        return res
    cur = res["data"].get("current", {})
    return {"ok": True, "fetched_utc": res["fetched_utc"], "observed_time": cur.get("time"),
            "temperature_c": cur.get("temperature_2m"),
            "pressure_kpa": (cur.get("surface_pressure") / 10.0) if cur.get("surface_pressure") is not None else None,
            "wind_ms": (cur.get("wind_speed_10m") / 3.6) if cur.get("wind_speed_10m") is not None else None,
            "cloud_pct": cur.get("cloud_cover"), "humidity_pct": cur.get("relative_humidity_2m"),
            "solar_wm2": cur.get("shortwave_radiation"),
            "source": "Open-Meteo forecast API (hourly model analysis)"}


def open_meteo_monthly(lat: float, lon: float, year: Optional[int] = None) -> dict:
    """Monthly mean temperature + total precipitation from the Open-Meteo archive (ERA5-based, days of lag)."""
    year = year or (dt.date.today().year - 1)
    res = _get("https://archive-api.open-meteo.com/v1/archive", {
        "latitude": lat, "longitude": lon, "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
        "daily": "temperature_2m_mean,temperature_2m_min,temperature_2m_max,precipitation_sum", "timezone": "UTC",
    })
    if not res["ok"]:
        return res
    d = res["data"]["daily"]
    import pandas as pd
    df = pd.DataFrame(d)
    df["time"] = pd.to_datetime(df["time"])
    df["month"] = df["time"].dt.month
    g = df.groupby("month").agg(temp_mean_c=("temperature_2m_mean", "mean"), temp_min_c=("temperature_2m_min", "min"),
                                temp_max_c=("temperature_2m_max", "max"), precip_mm=("precipitation_sum", "sum")).reset_index()
    return {"ok": True, "year": year, "monthly": g, "daily": df, "fetched_utc": res["fetched_utc"],
            "source": "Open-Meteo archive API (ERA5-derived reanalysis, not a station record)"}


def usgs_quakes_near(lat: float, lon: float, radius_km: float = 500.0, feed: str = "all_week") -> dict:
    """Recent earthquakes within radius (USGS GeoJSON feed, minute-level updates)."""
    res = _get(f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson")
    if not res["ok"]:
        return res
    out = []
    for f in res["data"].get("features", []):
        lo, la, _ = f["geometry"]["coordinates"]
        d = haversine_km(lat, lon, la, lo)
        if d <= radius_km:
            p = f["properties"]
            out.append({"time_utc": dt.datetime.fromtimestamp(p["time"] / 1000, dt.timezone.utc).isoformat(timespec="minutes"),
                        "mag": p.get("mag"), "place": p.get("place"), "distance_km": round(d, 1)})
    out.sort(key=lambda x: x["time_utc"], reverse=True)
    return {"ok": True, "events": out, "fetched_utc": res["fetched_utc"], "source": f"USGS Earthquake Hazards feed ({feed})"}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


GIBS_LAYERS = {
    "True colour (VIIRS SNPP)": ("VIIRS_SNPP_CorrectedReflectance_TrueColor", "jpg"),
    "True colour (MODIS Terra)": ("MODIS_Terra_CorrectedReflectance_TrueColor", "jpg"),
    "Land surface temp, day (MODIS Terra)": ("MODIS_Terra_Land_Surface_Temp_Day", "png"),
    "Snow cover (MODIS Terra)": ("MODIS_Terra_NDSI_Snow_Cover", "png"),
}


def gibs_tile_url(layer_name: str, days_back: int = 1) -> dict:
    """NASA GIBS WMTS (EPSG:3857) raster tile URL template for use as a map layer."""
    layer, ext = GIBS_LAYERS[layer_name]
    date = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_back)).date().isoformat()
    level = "GoogleMapsCompatible_Level9" if "TrueColor" in layer else "GoogleMapsCompatible_Level7"
    url = f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/{level}/{{z}}/{{y}}/{{x}}.{ext}"
    return {"url": url, "date": date, "layer": layer}


def nasa_power_climatology(lat: float, lon: float) -> dict:
    """Monthly climatology (1991-2020 style long-term means) from NASA POWER. Public, no key. Model/assimilation product at 0.5 deg."""
    res = _get("https://power.larc.nasa.gov/api/temporal/climatology/point", {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,WS10M", "community": "RE", "longitude": lon, "latitude": lat, "format": "JSON"})
    if not res["ok"]:
        return res
    try:
        par = res["data"]["properties"]["parameter"]
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        import pandas as pd
        df = pd.DataFrame({"month": range(1, 13), "temp_mean_c": [par["T2M"][m] for m in months], "temp_max_c": [par["T2M_MAX"][m] for m in months],
                           "temp_min_c": [par["T2M_MIN"][m] for m in months], "precip_mm": [par["PRECTOTCORR"][m] * 30.4 for m in months],
                           "wind_ms": [par["WS10M"][m] for m in months]})
        return {"ok": True, "monthly": df, "fetched_utc": res["fetched_utc"], "source": "NASA POWER monthly climatology (model-based, 0.5 deg)"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"unexpected POWER response: {e}"[:160], "data": None}
