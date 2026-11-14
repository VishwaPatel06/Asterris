"""Explanation engine, process comparison, condition comparison (blueprint A8, A12, A13, A14).

Every statement is built from fields in the candidate/target records and the computed scores, so
explanations are grounded and cite the contributing datasets. Nothing here invents science.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from config.mission_presets import DIMENSION_LABELS, EXPERIMENTS
from config.planetary_constants import PHYSICAL_FACTORS, PLANETS

# lithology / mineral tags -> processes (blueprint A8)
PROCESS_MAP = {
    "basalt": ("Volcanic activity", "Basaltic landforms, lava flows, vents (lunar maria, Martian volcanic provinces)"),
    "glass": ("Volcanic activity", "Quenched volcanic glass; rapid-cooling textures"),
    "olivine": ("Volcanic activity", "Primitive mafic mineralogy common to Moon and Mars basalts"),
    "impact_breccia": ("Impact cratering", "Crater shape, rim/ejecta morphology, shock features"),
    "evaporite": ("Salt deposition", "Evaporitic mineral environments; ancient water-related processes on Mars"),
    "halite": ("Salt deposition", "Chloride salts as indicators of ancient brines"),
    "gypsum": ("Chemical weathering / evaporation", "Hydrated sulfates detected on Mars"),
    "jarosite": ("Chemical weathering", "Acidic-water alteration; reported at Meridiani on Mars"),
    "sulfate": ("Chemical weathering", "Sulfate-bearing sedimentary units"),
    "clay": ("Water-driven alteration", "Phyllosilicates indicate past water-rock interaction"),
    "carbonate": ("Water-driven alteration", "Carbonates reported at Jezero and in Martian meteorites"),
    "ice": ("Glacial / periglacial processes", "Ground ice, permafrost and ice-rich regolith"),
    "perchlorate": ("Hyper-arid surface chemistry", "Perchlorate salts detected on Mars (Phoenix)"),
    "palagonite": ("Chemical weathering", "Altered basaltic glass; regolith-simulant relevance"),
    "sedimentary": ("Water-driven erosion", "Channels, deltas, layered sedimentary landforms"),
}
CAVE_PROCESS = ("Lava tube formation", "Tube morphology, roof/collapse features and skylight openings")

CONDITION_ROWS = [
    ("Temperature mean (°C)", "temp_mean_c", 20.0),
    ("Temperature min (°C)", "temp_min_c", 40.0),
    ("Temperature max (°C)", "temp_max_c", 40.0),
    ("Slope (°)", "slope_deg", 8.0),
    ("Roughness (0-1)", "roughness", 0.2),
    ("Relief (m)", "relief_m", None),
    ("Water/ice indicator (0-1)", "water_ice", 0.2),
    ("Dust (0-1)", "dust", 0.2),
    ("Biology (0-1)", "biology", 0.2),
    ("Cave evidence (0-1)", "caves", 0.2),
]


def compare_conditions(target: dict, cand: dict) -> List[dict]:
    """Per-parameter match / partial / mismatch / unknown rows (the 'where it works vs breaks down' table)."""
    rows = []
    for label, key, tol in CONDITION_ROWS:
        tv, cv = target.get(key), cand.get(key)
        if tv is None or cv is None:
            status = "unknown"
        elif key == "relief_m":
            import math
            r = abs(math.log10(max(tv, 1)) - math.log10(max(cv, 1)))
            status = "match" if r < 0.3 else "partial" if r < 0.8 else "mismatch"
        else:
            d = abs(tv - cv)
            status = "match" if d <= tol else "partial" if d <= 2 * tol else "mismatch"
        rows.append({"Parameter": label, "Earth site": cv, "Target": tv, "Status": status})
    return rows


def physical_scorecard(body: str) -> List[dict]:
    """What the Earth site reproduces / partially / cannot (blueprint scorecard)."""
    e, b = PLANETS["Earth"], PLANETS[body]
    out = []
    for key, label, unit, handling in PHYSICAL_FACTORS:
        if key in ("gravity", "pressure_kpa", "radiation_msv_day"):
            ev, bv = e[key], b[key]
        elif key == "temperature":
            ev, bv = f"{e['temp_min_c']:.0f} to {e['temp_max_c']:.0f}", f"{b['temp_min_c']:.0f} to {b['temp_max_c']:.0f}"
        elif key == "atmosphere":
            ev, bv = e["atmosphere"], b["atmosphere"]
        else:
            ev, bv = "Earth-specific minerals/weathering", "Planet-specific chemistry/alteration"
        status = "cannot reproduce" if handling == "no" else "partial"
        out.append({"Factor": label, "Unit": unit, "Earth": ev, "Target body": bv, "Earth site can...": status})
    return out


def processes_for(cand: dict) -> List[dict]:
    seen, out = set(), []
    tags = [cand.get("lithology")] + list(cand.get("minerals") or [])
    for t in tags:
        if t in PROCESS_MAP and PROCESS_MAP[t][0] not in seen:
            seen.add(PROCESS_MAP[t][0]); out.append({"Process": PROCESS_MAP[t][0], "Evidence tag": t, "What to compare": PROCESS_MAP[t][1]})
    if (cand.get("caves") or 0) >= 0.5 and CAVE_PROCESS[0] not in seen:
        out.append({"Process": CAVE_PROCESS[0], "Evidence tag": f"caves={cand['caves']}", "What to compare": CAVE_PROCESS[1]})
    return out


def explain(target: dict, cand: dict, result: dict, objective: str) -> Dict[str, List[str]]:
    """Answer the five blueprint questions (A13) from the record + scores."""
    ds = result["dimension_scores"]
    ranked = sorted([(d, s) for d, s in ds.items() if s is not None and d != "operations"], key=lambda x: -x[1])
    top = ranked[:3]
    src = "; ".join(cand.get("sources", [])[:3]) or "no sources recorded"

    why = [f"Ranked #{result['rank']} for '{objective}' vs {target['name']} with similarity index "
           f"{result['total']:.2f} ({result['label']}) over {result['coverage']*100:.0f}% of the weighted dimensions."
           if result["total"] is not None else "Insufficient data to score."]
    why += [f"Strongest dimension: {DIMENSION_LABELS[d]} ({s:.2f})." for d, s in top[:2]]
    why.append(f"Contributing datasets (as recorded): {src}.")

    resembles = []
    if "geology" in ds and ds["geology"] is not None:
        shared = sorted(set(target.get("minerals") or []) & set(cand.get("minerals") or []))
        if shared:
            resembles.append(f"Shared mineral/rock indicators: {', '.join(shared)}.")
        if target.get("lithology") == cand.get("lithology"):
            resembles.append(f"Both are {cand['lithology']}-dominated.")
    for d, s in ranked:
        if s >= 0.75 and d != "geology":
            resembles.append(f"{DIMENSION_LABELS[d]} similarity is high ({s:.2f}).")
    resembles = resembles or ["No dimension reaches the 'high' similarity band."]

    procs = [f"{p['Process']}: {p['What to compare']}" for p in processes_for(cand)] or ["No process tags recorded."]

    exps = EXPERIMENTS.get(objective, ["No experiment template for this objective."])

    breaks = [f"{r['Factor']}: Earth {r['Earth']} vs {target['body']} {r['Target body']} ({r['Earth site can...']})."
              for r in physical_scorecard(target["body"]) if r["Earth site can..."] == "cannot reproduce"]
    weak = [f"{DIMENSION_LABELS[d]} similarity is low ({s:.2f})." for d, s in ranked if s < 0.5]
    miss = [f"No data for {DIMENSION_LABELS[d]} (unknown, not absent)." for d in result["missing_dimensions"]]
    proxies = []
    if cand.get("water_basis") in ("proxy", "inferred"):
        proxies.append(f"Water/ice indicator is a {cand['water_basis']}, not a direct observation.")
    proxies.append("Catalogue values are hand-compiled demonstration estimates, not pipeline measurements." if cand.get("basis") == "demonstration_estimate" else "")
    return {"Why was this location selected?": why,
            "Which planetary characteristics does it resemble?": resembles,
            "What geological processes are comparable?": procs,
            "What experiments could be conducted there?": exps,
            "Where does the analogy break down?": breaks + weak + miss + [p for p in proxies if p]}
