import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np
from config.mission_presets import DIMENSIONS, PRESETS
from data_sources.seed_catalog import CANDIDATES, TARGETS
from scientific_engine import dem, spectral
from scientific_engine.similarity import (normalise_weights, rank_candidates, score_candidate, sensitivity_analysis, weighted_score)
from simulations import rover, drilling

T = TARGETS[0]

def test_presets_sum_to_one():
    for name, w in PRESETS.items():
        assert abs(sum(w.values()) - 1) < 1e-9, name

def test_identical_site_scores_one_on_environment():
    twin = {**T, "id": "twin", "name": "twin", "operations": 1.0}
    r = score_candidate(T, twin, PRESETS["Polar Ice Drilling"], "Polar Ice Drilling")
    assert r["fidelity"] > 0.99

def test_missing_data_is_not_zero():
    c = {**CANDIDATES[0], "water_ice": None}
    r = score_candidate(T, c, PRESETS["Polar Ice Drilling"], "Polar Ice Drilling")
    assert r["dimension_scores"]["water_ice"] is None and "water_ice" in r["missing_dimensions"] and r["coverage"] < 1

def test_weights_renormalise():
    w = normalise_weights({d: 5 for d in DIMENSIONS})
    assert abs(sum(w.values()) - 1) < 1e-9

def test_scores_bounded_and_ranked():
    rows = rank_candidates(T, CANDIDATES, PRESETS["Lava Tube Exploration"], "Lava Tube Exploration")
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    for r in rows:
        assert 0 <= r["total"] <= 1 and 0 <= r["transferability"] <= r["fidelity"] + 1e-9

def test_lava_tube_objective_favours_cave_sites():
    m = next(t for t in TARGETS if t["id"] == "moon_marius")
    rows = rank_candidates(m, CANDIDATES, PRESETS["Lava Tube Exploration"], "Lava Tube Exploration")
    assert rows[0]["id"] in {"hawaii_tubes", "lanzarote"}

def test_sensitivity_is_deterministic():
    a = sensitivity_analysis(T, CANDIDATES, PRESETS["Polar Ice Drilling"], "Polar Ice Drilling", draws=50)
    b = sensitivity_analysis(T, CANDIDATES, PRESETS["Polar Ice Drilling"], "Polar Ice Drilling", draws=50)
    assert a == b

def test_dem_and_astar():
    h, cell = dem.synthetic_dem("valley", n=48)
    assert h.shape == (48, 48) and dem.terrain_metrics(h, cell)["relief_m"] > 0
    sl = dem.slope_deg(h, cell)
    path = rover.astar(sl, cell, (2, 2), (45, 45), 45)
    assert path and path[0] == (2, 2) and path[-1] == (45, 45)

def test_gravity_offload_physics():
    o = rover.gravity_offload(100, 4, 0.2, 0.1, 1.62, 0, list(rover.SOILS.values())[0])
    assert abs(o["offload_force_N"] - 100 * (9.80665 - 1.62)) < 1e-6
    assert o["sinkage_target_mm"] < o["sinkage_earth_mm"]

def test_drilling_scales_with_depth():
    a = drilling.drilling_estimate(1, 0.05, 0.5, "Dry regolith", 50)
    b = drilling.drilling_estimate(2, 0.05, 0.5, "Dry regolith", 50)
    assert abs(b["energy_Wh"] / a["energy_Wh"] - 2) < 1e-9

def test_spectral_self_match_and_identification():
    assert spectral.match("olivine", "olivine")["similarity"] > 0.999
    assert spectral.rank_against_library(spectral.noisy_unknown("gypsum", 50))[0][0] == "gypsum"
