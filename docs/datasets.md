# Datasets
Catalogued in `config/data_catalog.py`; status per provider in Mission Control > Data sources.
Used live without keys: Open-Meteo, NASA POWER, USGS earthquakes, AWS Terrain Tiles, Esri World Imagery, NASA Moon/Mars Trek tiles (browser-side), NASA GIBS (listed).
Hackathon-listed resources registered: NASA Earthdata Search, Worldview, PDS, LRO, Diviner (polar), CSA RCM and RADARSAT-1 (+ SAR tutorial), Copernicus Data Space, ESA Open Science Catalog, JAXA G-Portal. Most require a download step; each provider lists its ingestion procedure.
Provenance classes: real, local, demonstration, derived. Nominal resolutions are product-level figures; confirm against each product's metadata.
Candidate/target table columns: see the template in the Data sources panel (`id, name, role, body, lat, lon, scale, morphology, status, lithology, minerals, slope_deg, roughness, relief_m, temp_*, water_ice, dust, biology, caves, operations, resolution_m, data_quality, sources`). Ranges: 0-1 for indices.
