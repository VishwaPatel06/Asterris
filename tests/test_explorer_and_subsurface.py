"""Automated Test Suite for Asterris Workspace 02 (Planetary Explorer) & Workspace 03 (Subsurface Tab).

Place in: `tests/test_explorer_and_subsurface.py`
Run via: `pytest tests/test_explorer_and_subsurface.py` or `python3 tests/test_explorer_and_subsurface.py`
"""

from __future__ import annotations

import json
import py_compile
from pathlib import Path

from data_sources.global_earth_analogs import (
    GLOBAL_EARTH_ANALOGS,
    PLANETARY_INSTRUMENT_SOURCES,
    get_merged_global_earth_catalog,
)
from data_sources.subsurface_catalog import (
    EVIDENCE_CLASSES,
    PLANETARY_SUBSURFACE_REFERENCES,
    SUBSURFACE_CATEGORIES,
    SUBSURFACE_DATASET_REGISTRY,
    SUBSURFACE_MISSION_OBJECTIVES,
    TERRESTRIAL_SUBSURFACE_SITES,
    build_subsurface_catalog,
    get_provider_adapter_status,
)
from scientific_engine.planetary_ml import (
    build_instrument_fingerprint,
    run_global_ml_analog_search,
)
from scientific_engine.subsurface_engine import (
    build_earth_moon_mars_comparison,
    evaluate_site_for_objective,
    evidence_badge_html,
    flatten_site_properties_table,
    format_property_value,
    generate_subsurface_assessment_report_md,
    generate_subsurface_geojson,
    plot_cross_section_scale_diagram,
    subsurface_3d_viewer_html,
)


def test_global_earth_catalog_and_ml_search():
    """Verifies that Global ML Analog search evaluates 30+ global locations and respects coordinate bounding boxes."""
    mock_target = {
        "id": "MARS-JEZERO",
        "body": "Mars",
        "name": "Jezero Crater",
        "lat": 18.38,
        "lon": 77.58,
        "morphology": "crater",
        "lithology": "basalt",
        "minerals": ["olivine", "pyroxene", "phyllosilicates", "sulfates"],
        "slope_deg": 6.5,
        "roughness": 0.42,
        "relief_m": 250.0,
        "temp_mean_c": -60.0,
        "temp_min_c": -110.0,
        "temp_max_c": 5.0,
        "water_ice": 0.35,
        "dust": 0.65,
        "caves": 0.25,
        "resolution_m": 18,
        "data_quality": 0.94,
    }
    seed_cands = [
        {
            "id": "SEED-TEST-01",
            "name": "Seed Test Volcanic Site (Iceland)",
            "lat": 64.2,
            "lon": -18.1,
            "morphology": "volcanic",
            "lithology": "basalt",
            "minerals": ["basalt", "olivine"],
            "slope_deg": 7.0,
            "roughness": 0.50,
            "relief_m": 200.0,
            "temp_mean_c": 2.0,
            "water_ice": 0.5,
            "dust": 0.4,
            "caves": 0.6,
            "operations": 0.8,
            "data_quality": 0.9,
            "sources": ["Seed Catalog"],
        }
    ]

    merged = get_merged_global_earth_catalog(seed_cands)
    assert len(merged) >= 31, f"Expected >= 31 global locations, got {len(merged)}"

    # 1. Global search
    params_global = {
        "terrain": "All / Any",
        "weather": "All / Any",
        "soil": "All / Any",
        "materials": ["basalt", "olivine", "sulfates"],
        "temp_range_c": (-30.0, 35.0),
        "target_temp_c": -60.0,
        "max_slope_deg": 25.0,
        "target_roughness": 0.45,
        "target_relief_m": 250.0,
        "water_ice_target": 0.35,
        "subsurface_priority": 0.25,
        "area_mode": "Global (All Over Earth)",
        "lat_bounds": (-90.0, 90.0),
        "lon_bounds": (-180.0, 180.0),
    }
    res_global = run_global_ml_analog_search(mock_target, seed_cands, params_global)
    assert len(res_global) == len(merged)
    assert res_global[0]["ml_similarity"] >= res_global[-1]["ml_similarity"]
    assert "similarities_text" in res_global[0]
    assert "dissimilarities_text" in res_global[0]
    assert "other_factors_text" in res_global[0]

    # 2. Custom coordinate bounding box search (e.g., India: Lat 15..36, Lon 65..85)
    params_bbox = dict(params_global)
    params_bbox["area_mode"] = "Custom Coordinate Bounding Box"
    params_bbox["lat_bounds"] = (15.0, 36.0)
    params_bbox["lon_bounds"] = (65.0, 85.0)
    res_bbox = run_global_ml_analog_search(mock_target, seed_cands, params_bbox)
    assert len(res_bbox) >= 3  # Lonar, Ladakh, Kachchh
    for r in res_bbox:
        assert 15.0 <= r["lat"] <= 36.0 and 65.0 <= r["lon"] <= 85.0


def test_clickable_instrument_reference_fingerprints():
    """Verifies that selecting each planetary instrument updates the Environmental Fingerprint profile."""
    mock_target = {
        "id": "MOON-SHACKLETON",
        "body": "Moon",
        "name": "Shackleton Crater Rim",
        "lithology": "anorthosite",
        "minerals": ["plagioclase", "pyroxene", "water_ice"],
        "dust": 0.45,
        "slope_deg": 14.5,
        "roughness": 0.52,
        "relief_m": 4200.0,
        "caves": 0.20,
        "temp_mean_c": -185.0,
        "temp_min_c": -230.0,
        "temp_max_c": -90.0,
        "water_ice": 0.85,
        "water_basis": "LEND/M3",
        "resolution_m": 20,
        "data_quality": 0.95,
    }
    earth_site = GLOBAL_EARTH_ANALOGS[0]
    resolutions = set()
    for ikey in PLANETARY_INSTRUMENT_SOURCES:
        rows, meta = build_instrument_fingerprint(mock_target, ikey, earth_site)
        assert len(rows) >= 12
        assert meta["instrument_key"] == ikey
        assert meta["url"].startswith("https://")
        resolutions.add(meta["resolution_m"])
    assert len(resolutions) >= 4, "Different instruments must update reference spatial resolution & datum"


def test_subsurface_catalog_and_evidence_integrity():
    """Verifies all 6 categories, 10 mission objectives, and strict Evidence Classification rules."""
    extra_cands = [
        {
            "id": "DISC-PIT-01",
            "name": "Discovered Pit Chain 01 (Idaho)",
            "lat": 43.25,
            "lon": -113.48,
            "morphology": "lava_tube",
            "scale": "cave",
            "lithology": "basalt",
            "caves": 0.78,
            "diameter_m": 310.0,
            "depth_m": 18.0,
            "slope_deg": 6.4,
            "roughness": 0.55,
            "relief_m": 24.0,
            "provenance_class": "derived",
            "detector_confidence": 0.82,
            "sources": ["AWS Terrain Tiles LoG Detector"],
        }
    ]
    sites = build_subsurface_catalog(extra_cands)
    assert len(sites) >= 16

    # Verify all 6 required subsurface environment categories are present
    present_cats = {s["category"] for s in sites}
    for req_cat in SUBSURFACE_CATEGORIES:
        assert req_cat in present_cats, f"Missing category: {req_cat}"

    # Verify missing values are represented as 'Unknown / Not measured' and never 0
    disc_site = next(s for s in sites if s["id"] == "DISC-PIT-01")
    assert disc_site["geometry"]["max_width_m"]["value"] is None
    assert format_property_value(disc_site["geometry"]["max_width_m"]) == "Unknown / Not measured"
    assert disc_site["geometry"]["internal_volume_m3"]["evidence"] == "UNKNOWN"

    # Verify all 10 mission objectives produce separate Fidelity, Suitability, and Transferability scores
    for obj in SUBSURFACE_MISSION_OBJECTIVES:
        ev = evaluate_site_for_objective(TERRESTRIAL_SUBSURFACE_SITES[0], obj, "Moon")
        assert 0.0 <= ev["analogue_fidelity"] <= 1.0
        assert 0.0 <= ev["mission_suitability"] <= 1.0
        assert 0.0 <= ev["transferability"] <= 1.0
        assert ev["analogue_fidelity"] != ev["mission_suitability"] or ev["analogue_fidelity"] != ev["transferability"]

    # Verify 3D viewer HTML generation, Earth-Moon-Mars comparison, and exports
    html_3d = subsurface_3d_viewer_html(TERRESTRIAL_SUBSURFACE_SITES[0])
    assert "THREE.Scene" in html_3d and "Valentine Cave" in html_3d

    moon_ref = PLANETARY_SUBSURFACE_REFERENCES["Moon"][0]
    mars_ref = PLANETARY_SUBSURFACE_REFERENCES["Mars"][0]
    cmp_rows, cmp_summary = build_earth_moon_mars_comparison(TERRESTRIAL_SUBSURFACE_SITES[0], moon_ref, mars_ref)
    assert len(cmp_rows) == 10
    fig_cs = plot_cross_section_scale_diagram(TERRESTRIAL_SUBSURFACE_SITES[0], moon_ref, mars_ref)
    assert len(fig_cs.data) == 3

    ev0 = evaluate_site_for_objective(TERRESTRIAL_SUBSURFACE_SITES[0], SUBSURFACE_MISSION_OBJECTIVES[1], "Moon")
    rep_md = generate_subsurface_assessment_report_md(TERRESTRIAL_SUBSURFACE_SITES[0], ev0, moon_ref, mars_ref)
    assert "Not an official NASA" in rep_md or "not** an official NASA" in rep_md

    gj = json.loads(generate_subsurface_geojson(sites, SUBSURFACE_MISSION_OBJECTIVES[0], "Mars"))
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == len(sites)

    assert len(SUBSURFACE_DATASET_REGISTRY) >= 5
    assert len(get_provider_adapter_status()) >= 4
    assert "MEASURED" in evidence_badge_html("MEASURED")


if __name__ == "__main__":
    test_global_earth_catalog_and_ml_search()
    test_clickable_instrument_reference_fingerprints()
    test_subsurface_catalog_and_evidence_integrity()
    print("ALL TESTS PASSED SUCCESSFULLY!")