"""Representative planetary reference values for Earth, Moon and Mars.

Values are representative; local and temporal variation applies (especially Mars pressure and
radiation, and all temperatures). Each row carries a source note. Verify against the cited
mission product before any quantitative use. These are reference constants, not live measurements.
"""
from __future__ import annotations

PLANETS = {
    "Earth": {"gravity": 9.807, "pressure_kpa": 101.3, "atmosphere": "N2 78%, O2 21%", "radiation_msv_day": 0.007,
              "temp_mean_c": 15.0, "temp_min_c": -89.0, "temp_max_c": 57.0, "radius_km": 6371.0, "solar_day_h": 24.0,
              "escape_kms": 11.19, "solar_flux_wm2": 1361.0, "axial_tilt_deg": 23.44, "magnetic_field": "Global dipole, ~25-65 uT",
              "density_gcc": 5.51, "liquid_water": "Stable at surface"},
    "Moon": {"gravity": 1.62, "pressure_kpa": 3e-13, "atmosphere": "Surface exosphere, effectively vacuum", "radiation_msv_day": 1.37,
             "temp_mean_c": -53.0, "temp_min_c": -248.0, "temp_max_c": 127.0, "radius_km": 1737.4, "solar_day_h": 708.7,
             "escape_kms": 2.38, "solar_flux_wm2": 1361.0, "axial_tilt_deg": 1.54, "magnetic_field": "No global field; crustal anomalies",
             "density_gcc": 3.34, "liquid_water": "None at surface; polar cold-trap ice"},
    "Mars": {"gravity": 3.72, "pressure_kpa": 0.6, "atmosphere": "CO2 95%, N2 2.8%, Ar 2%", "radiation_msv_day": 0.67,
             "temp_mean_c": -63.0, "temp_min_c": -140.0, "temp_max_c": 35.0, "radius_km": 3389.5, "solar_day_h": 24.66,
             "escape_kms": 5.03, "solar_flux_wm2": 590.0, "axial_tilt_deg": 25.19, "magnetic_field": "No global field; crustal anomalies",
             "density_gcc": 3.93, "liquid_water": "Not stable at surface; subsurface ice"},
}

SOURCE_NOTES = {
    "gravity": "Standard values from NASA planetary fact sheets (NSSDCA).",
    "pressure_kpa": "Earth: sea level. Moon: ~1e-10 Pa exosphere. Mars: mean ~600 Pa, varies ~30% seasonally.",
    "radiation_msv_day": "Earth: ~2.4 mSv/yr natural background. Moon: Chang'e-4 LND, ~1.37 mSv/day. Mars: MSL RAD, ~0.67 mSv/day (GCR dominated).",
    "temp_min_c": "Moon min from LRO Diviner permanently shadowed regions; Mars/Earth extremes are regional records.",
    "solar_flux_wm2": "Top-of-atmosphere/solar constant; Mars value is the orbit average at ~1.52 AU.",
}

# (key, label, unit, can an Earth site reproduce it?)  "no" | "partial"
PHYSICAL_FACTORS = [
    ("gravity", "Surface gravity", "m/s2", "no"),
    ("pressure_kpa", "Atmospheric pressure", "kPa", "no"),
    ("radiation_msv_day", "Surface radiation dose", "mSv/day", "no"),
    ("temperature", "Temperature range", "deg C", "partial"),
    ("atmosphere", "Atmospheric composition", "-", "no"),
    ("surface_chemistry", "Surface chemistry (perchlorates, oxidants, regolith)", "-", "partial"),
]

# Rows for the Earth / Moon / Mars comparison table and charts
COMPARISON_ROWS = [
    ("Surface gravity", "gravity", "m/s2", "{:.2f}"),
    ("Radius", "radius_km", "km", "{:,.0f}"),
    ("Mean density", "density_gcc", "g/cm3", "{:.2f}"),
    ("Escape velocity", "escape_kms", "km/s", "{:.2f}"),
    ("Surface pressure", "pressure_kpa", "kPa", "{:.3g}"),
    ("Mean temperature", "temp_mean_c", "deg C", "{:.0f}"),
    ("Minimum temperature", "temp_min_c", "deg C", "{:.0f}"),
    ("Maximum temperature", "temp_max_c", "deg C", "{:.0f}"),
    ("Surface radiation dose", "radiation_msv_day", "mSv/day", "{:.3g}"),
    ("Solar flux at body", "solar_flux_wm2", "W/m2", "{:,.0f}"),
    ("Solar day", "solar_day_h", "hours", "{:,.1f}"),
    ("Axial tilt", "axial_tilt_deg", "deg", "{:.2f}"),
    ("Atmosphere", "atmosphere", "", "{}"),
    ("Magnetic field", "magnetic_field", "", "{}"),
    ("Liquid water", "liquid_water", "", "{}"),
]


def mismatch(body: str, factor: str) -> float:
    """Mismatch magnitude in [0, 1] for the heuristic transferability score only."""
    e, b = PLANETS["Earth"], PLANETS[body]
    if factor == "gravity":
        return min(1.0, abs(e["gravity"] - b["gravity"]) / e["gravity"])
    if factor == "pressure_kpa":
        return min(1.0, abs(e["pressure_kpa"] - b["pressure_kpa"]) / e["pressure_kpa"])
    if factor == "radiation_msv_day":
        return 1.0 if b["radiation_msv_day"] > 20 * e["radiation_msv_day"] else 0.5
    return 0.0
