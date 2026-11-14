import json

import numpy as np
import pytest

from data_sources import manager
from data_sources.planetary import registry
from geospatial import tiles
from scientific_engine import discovery, synthetic
from scientific_engine.similarity import rank_candidates
from config.mission_presets import PRESETS


def test_detector_finds_planted_features():
    ms = []
    for seed in (1, 2, 3):
        g, truth = synthetic.planted_dem(seed)
        ms.append(synthetic.match_detections(discovery.detect_landforms(g), truth))
    assert np.mean([m["recall"] for m in ms]) > 0.8
    assert np.mean([m["precision"] for m in ms]) > 0.5


def test_detection_is_deterministic():
    g, _ = synthetic.planted_dem(4)
    a = [(d["kind"], d["r"], d["c"]) for d in discovery.detect_landforms(g)]
    b = [(d["kind"], d["r"], d["c"]) for d in discovery.detect_landforms(g)]
    assert a == b


def test_discovery_keeps_unknowns_missing_and_scores_with_coverage():
    from data_sources.seed_catalog import TARGETS
    g, _ = synthetic.planted_dem(4)
    res = discovery.run_discovery(g, "Basalt Rover Traction Testing", "t")
    assert res["candidates"] and "regional scan" in res["coverage_note"]
    c = res["candidates"][0]
    assert c["water_ice"] is None and c["lithology"] is None and c["provenance_class"] == "derived"
    r = rank_candidates(TARGETS[0], res["candidates"], PRESETS["Basalt Rover Traction Testing"], "Basalt Rover Traction Testing")
    assert all(x["coverage"] < 1 for x in r)             # missing dims reduce coverage, they are not zero-filled
    assert all(x["dimension_scores"]["water_ice"] is None for x in r)


def test_mission_filters_reject_with_reason():
    g, _ = synthetic.planted_dem(4)
    res = discovery.run_discovery(g, "Lunar Base Site Identification", "t", user_filters={"max_slope_deg": 1.0})
    assert res["rejected"] and all(r["rejected_because"] for r in res["rejected"])


def test_terrarium_decode_and_tile_math():
    rgb = np.zeros((2, 2, 3)); rgb[..., 0] = 128      # R=128 -> 0 m
    assert np.allclose(tiles.decode_terrarium(rgb), 0.0)
    rgb[..., 1] = 100
    assert np.allclose(tiles.decode_terrarium(rgb), 100.0)
    x, y = tiles.lonlat_to_tile(0, 0, 1)
    assert abs(x - 1) < 1e-9 and abs(y - 1) < 1e-9
    lon, lat = tiles.tile_to_lonlat(x, y, 1)
    assert abs(lon) < 1e-9 and abs(lat) < 1e-9


def test_registry_missing_credentials_does_not_crash(monkeypatch):
    monkeypatch.delenv("COPERNICUS_CLIENT_ID", raising=False); monkeypatch.delenv("COPERNICUS_CLIENT_SECRET", raising=False)
    from config import settings
    pr = registry.PROVIDERS["copernicus"]
    assert pr.status() in ("awaiting_credentials", "connected")
    assert all(d["status"] for d in registry.datasets_for("Earth"))


def test_upload_validation_and_catalog_merge(tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "get_settings", lambda: settings.Settings(storage_dir=tmp_path, upload_dir=tmp_path, cache_dir=tmp_path))
    monkeypatch.setattr(manager, "get_settings", settings.get_settings)
    csv = manager.template_csv().encode()
    ok, _ = manager.register_upload("t.csv", csv, "Earth", "geology")
    assert ok
    assert not manager.register_upload("t.csv", csv, "Earth", "geology")[0]            # duplicate
    bad = b"name,lat,lon,roughness\nx,10,20,5\n"                                         # roughness out of 0-1
    ok, msg = manager.register_upload("bad.csv", bad, "Earth", "geology")
    assert not ok and manager.ingest_errors()
    assert not manager.register_upload("x.xyz", b"1", "Earth", "geology")[0]
    recs = manager.user_records()
    assert recs and recs[0]["provenance_class"] == "local" and recs[0]["water_ice"] == 0.1
    manager.remove_dataset(manager.list_datasets()[0]["id"])
    assert not manager.list_datasets()


def test_missing_values_stay_none():
    recs, probs = manager.validate_records([{"name": "a", "lat": 1, "lon": 2, "water_ice": None, "roughness": 0.5}])
    assert recs[0]["water_ice"] is None and not probs
