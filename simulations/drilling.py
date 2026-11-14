"""Cryogenic drilling energy estimate (blueprint /api/simulation/drilling).

Specific-energy values are user-adjustable PLACEHOLDERS spanning broad ranges; they are not
calibrated for any real drill or material. Use for order-of-magnitude test planning only.
"""
import math
from typing import Dict

MEDIA = {  # specific energy MJ per m^3 of material removed (illustrative planning range)
    "Ice-cemented regolith": (40.0, 400.0),
    "Dry regolith": (10.0, 150.0),
    "Basaltic rock": (300.0, 1500.0),
}


def drilling_estimate(depth_m: float, diameter_m: float, rate_m_per_h: float, medium: str,
                      specific_energy_mj_m3: float, efficiency: float = 0.25) -> Dict:
    area = math.pi * (diameter_m / 2) ** 2
    volume = area * depth_m
    hours = depth_m / rate_m_per_h if rate_m_per_h > 0 else float("inf")
    energy_mj = volume * specific_energy_mj_m3 / max(efficiency, 1e-6)
    wh = energy_mj * 1e6 / 3600.0
    return {"volume_m3": volume, "duration_h": hours, "energy_Wh": wh,
            "mean_power_W": wh / hours if hours > 0 else float("nan"),
            "range_Wh": tuple(volume * s * 1e6 / 3600.0 / max(efficiency, 1e-6) for s in MEDIA[medium])}


# ---- Teale specific energy (rotary drilling) ----
def teale_specific_energy(wob_n: float, torque_nm: float, rpm: float, rop_m_per_h: float, diameter_m: float) -> dict:
    """SE = F/A + 2 pi N T / (A u)   (Teale 1965). N in rev/s, u in m/s. Returns MJ/m^3 and mechanical power."""
    area = math.pi * (diameter_m / 2) ** 2
    n = rpm / 60.0; u = rop_m_per_h / 3600.0
    se_pa = wob_n / area + (2 * math.pi * n * torque_nm) / (area * max(u, 1e-12))
    return {"specific_energy_MJ_m3": se_pa / 1e6, "rotary_power_W": 2 * math.pi * n * torque_nm, "thrust_term_MJ_m3": wob_n / area / 1e6}


ICE_SUBLIMATION_J_PER_KG = 2.83e6      # latent heat of sublimation of water ice (approx.)
ICE_CP_J_PER_KG_K = 1500.0             # representative specific heat of ice between ~100-270 K (varies strongly with temperature)
ICE_DENSITY = 917.0


def cryogenic_thermal_energy_wh(depth_m: float, diameter_m: float, ice_fraction: float, delta_t_k: float, sublimate: bool = False) -> float:
    """Energy to warm (and optionally sublimate) the ice contained in the removed volume: an UPPER-BOUND style estimate,
    ignoring heat shed to the surrounding ground. Conceptual, not a validated hardware prediction."""
    vol = math.pi * (diameter_m / 2) ** 2 * depth_m
    mass = vol * ice_fraction * ICE_DENSITY
    e = mass * (ICE_CP_J_PER_KG_K * delta_t_k + (ICE_SUBLIMATION_J_PER_KG if sublimate else 0.0))
    return e / 3600.0
