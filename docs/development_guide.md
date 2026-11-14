# Development guide
Setup: see README. Tests: `python -m pytest -q` (page smoke tests, physics, discovery, data manager). Verification report: `python scripts/verify_models.py`.
Add a dataset: row in `config/data_catalog.py`; add a provider in `data_sources/planetary/registry.py` if new. Add a scoring dimension: `scientific_engine/similarity.py` + `config/mission_presets.py`. Add soil: `simulations/physics.py::SOILS`. Add real spectra: `spectral.register_spectrum`.
Rules: algorithms in modules, not pages; never fill missing values with zero; label provenance; keep palette semantics (`config/palette.py`).
