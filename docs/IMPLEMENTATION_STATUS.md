# Implementation status
Legend: Done = works and tested here; Partial = works with stated limits; Not built = deferred.

| Feature | Status | Key files | Data / key dependency | Tests | Limitations / next step |
|---|---|---|---|---|---|
| Navigation, themes, palette | Done | app.py, components/theme.py, config/palette.py | none | page smoke tests | - |
| Mission Control (world, region, objective, weights, dashboard) | Done | views/01, components/context.py | none | smoke + workflow | Target search is name/coordinate lookup over catalogue |
| Data Source Manager (providers, status, upload, metadata, cache, errors) | Done | data_sources/planetary/registry.py, manager.py | Credentials in .env for Earthdata, Copernicus, ISRO | tests/test_discovery_data.py | Authenticated downloads not automated; manual ingestion documented per provider |
| Partner resources (Earthdata Search, Worldview, PDS, LRO/Diviner, CSA, Copernicus, ESA OSC, JAXA G-Portal) | Registered | config/data_catalog.py | Accounts/downloads | catalogue integrity | Portals were not reachable from the build sandbox; endpoints untested live |
| 3D globe and terrain viewer | Partial | components/viewer3d.py, viewer3d.js.txt | Internet for tiles | JS syntax check, HTML build | **Not exercised in a real browser/WebGL here.** Trek tile URL scheme (z/y/x) is from public examples and unverified; failures show a message and a schematic fallback |
| Earth real-elevation terrain | Partial | geospatial/tiles.py | AWS Terrain Tiles (no key) | decode and tile-math unit tests | Live fetch untested in sandbox |
| Moon/Mars local terrain | Partial | views/02 | Upload LOLA/MOLA DEM | smoke | Schematic surface when no DEM; CRS metadata not auto-used |
| Hardware models (.glb) | Partial | viewer3d.model_viewer_html | Files from NASA 3D Resources etc. | none | No models bundled (could not download); viewer is ready |
| Discovery engine | Done (regional) | scientific_engine/discovery.py | DEM: tiles, upload or synthetic | detector + filter + missing-data tests | Morphometric baseline, not deep learning; synthetic benchmark only; no lithology/water without data |
| 8D similarity, sensitivity, uncertainty | Done | scientific_engine/similarity.py | none | 6 verification checks + existing tests | No ground-truth labels |
| Scientific comparison incl. Earth/Moon/Mars | Done | views/04, config/planetary_constants.py | none | smoke | Constants are representative values |
| Spectral matcher | Partial | scientific_engine/spectral.py | USGS library spectra | smoke | Schematic curves |
| Seasonal calendar | Done | scientific_engine/seasonal.py | NASA POWER / Open-Meteo (live) | smoke | Falls back to labelled estimate offline |
| Physics engine + accuracy report | Done | simulations/physics.py, scientific_engine/validation.py | soil-bin data for validation | 11 physics checks | Verified, not validated |
| Traverse, drilling | Done | simulations/rover.py, drilling.py | real DEM optional | existing tests | Schematic terrain by default |
| Campaign and exports (PDF, MD, CSV, GeoJSON) | Done | views/06, reports/generators.py | none | smoke | - |
| Research assistant | Partial | ai/assistant.py | OPENAI_API_KEY (future) | smoke | Retrieval only |
| CesiumJS, FastAPI, PostGIS, PyTorch models, Docker rework | Not built | - | - | - | Three.js viewer used instead of Cesium |

## Update 2 (bug fixes and accuracy tooling)
| Item | Status | Files |
|---|---|---|
| Code printed in tabs (Streamlit magic on bare expressions) | Fixed; regression test fails if any page prints a help/DeltaGenerator panel | views/01, 03, 04, 06; tests/test_fixes.py |
| Fingerprint source selector (MOLA, CRISM, HiRISE/CTX, ...) updates profile and re-ranks Earth candidates | Done | views/02_Planetary_Explorer.py |
| Terrain derivatives: colour legends, no warning box | Done | views/02, components/charts.py |
| Physics: closed-form comparison, convergence, strength bound, uncertainty propagation, upload validation and calibration | Done | scientific_engine/validation.py, validation_data.py |
| Similarity: literature-pair agreement, ablation, upload labelled-pair scoring | Done (weak labels) | same |
| Detector: noise/resolution robustness, real-crater spot check (online), inventory scoring | Done (spot check untested live) | same |
