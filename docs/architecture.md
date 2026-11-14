# Architecture
Streamlit multipage UI (`views/`) over reusable modules; no scientific logic lives in page scripts.
- `config/` settings (.env), palette, mission presets, planetary constants, dataset catalogue.
- `data_sources/` provider registry (`planetary/registry.py`), manager (uploads, errors, cache), catalogue merge, live feeds, built-in demonstration records.
- `geospatial/` tile maths and elevation-tile fetch, terrain derivatives and semantic colouring.
- `scientific_engine/` similarity (8D), discovery (landform detector + mission filters), synthetic benchmark terrain, validation suite, spectral, seasonal, explanations.
- `simulations/` physics (Bekker-Wong terramechanics, RK4 dynamics, gravity offload), rover traverse (A*), drilling.
- `optimization/`, `reports/`, `ai/` campaign selection, exports, retrieval assistant.
- `components/` theme, charts, Three.js viewer (`viewer3d.py` + `viewer3d.js.txt`), shared context.
Flow: Mission Control state (session) -> `components/context.py` builds the ranked pool (catalogue + uploads + discovered) -> pages render it.
Deferred (not built): FastAPI service, PostGIS, CesiumJS (the Three.js viewer covers 3D now), PyTorch models, background jobs.
