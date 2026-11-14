# Celestial Cartographers

*Discover worlds within our world.* An AI-assisted platform for finding, characterising and comparing Earth analogues of lunar and Martian environments (NASA Space Apps Challenge 2026).

## Run (Windows CMD)
```
cd /d "D:\Asterris\celestial-cartographers (3)\celestial-cartographers"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```
Or double-click `scripts\run_windows.bat`. Tests: `python -m pytest -q`. Model verification: `python scripts\verify_models.py`.
Optional extras (rasterio for GeoTIFF metadata, etc.): `pip install -r requirements-optional.txt` (needs GDAL; Conda is easiest).

## Workspaces
Overview, Mission Control (world, region, objective, editable weights, mission dashboard, **Data sources** manager), Planetary Explorer (3D globe and terrain, layers, fingerprint), Analog Discovery Lab (discover, rank, atlas, subsurface), Scientific Comparison (candidate vs target, Earth/Moon/Mars, spectra, seasons), Mission Engineering (terramechanics and gravity offload, traverse, drilling, model accuracy), Field Campaign (plan and exports), Research Assistant.

## 3D view
Globe: Earth (Esri imagery), Moon (LROC WAC, NASA Moon Trek), Mars (Viking MDIM, NASA Mars Trek). Terrain: real Earth elevation (AWS Terrain Tiles) draped with satellite imagery, with elevation, slope, hillshade layers, sun control, vertical exaggeration, cursor readout and discovered-landform outlines. Imagery and elevation are fetched by your browser, so terrain needs internet. Moon/Mars terrain uses an uploaded DEM, otherwise a clearly labelled schematic surface. To view agency hardware models, put `.glb` files (NASA 3D Resources, etc.) in `assets/models/`.

## Adding hackathon data and keys later
1. Put credentials in `.env` (names in `.env.example`). Missing keys never break the app; providers show "Awaiting credentials".
2. Mission Control > Data sources: upload tables (CSV/GeoJSON/JSON, template provided) or rasters (GeoTIFF/ASC), choose body and layer. Tables with `role=target` or `role=candidate` merge into the working catalogue and override built-in demo rows with the same `id`.
3. New datasets or providers: add rows to `config/data_catalog.py` and `data_sources/planetary/registry.py`.

## Data integrity
Built-in site values are hand-compiled **demonstration estimates**, not NASA measurements. Each record carries a provenance class: real, local, demonstration, derived. Missing values stay missing. Similarity indices are not probabilities. See `docs/scientific_methodology.md` and `docs/IMPLEMENTATION_STATUS.md`.
