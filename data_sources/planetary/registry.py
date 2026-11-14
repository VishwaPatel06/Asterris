"""Provider registry: which data providers exist, whether they are usable now, and what they offer.

Status values
  public_ready          public endpoint, no credentials required
  connected             credentials present in the environment (validity is checked by "Test connection")
  awaiting_credentials  the provider needs credentials that are not configured yet
  manual_only           no practical live API: ingest via documented download + upload
  unavailable           last connection test failed
Missing credentials never raise: the provider simply reports its status and the app keeps working.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from config.data_catalog import DATASETS
from config.settings import get_settings

STATUS_LABEL = {"public_ready": "Public, ready", "connected": "Credentials set", "awaiting_credentials": "Awaiting credentials",
                "manual_only": "Manual ingestion", "unavailable": "Unavailable"}


@dataclass
class Provider:
    id: str
    name: str
    body: str                                   # Earth | Moon | Mars
    access: str                                 # public | credentials | manual
    env_vars: List[str] = field(default_factory=list)   # all must be non-empty
    ingestion: str = ""                         # documented procedure for manual / future integration
    probe_url: Optional[str] = None             # cheap GET used by "Test connection"
    homepage: str = ""

    def credentials_present(self) -> bool:
        s = get_settings()
        lookup = {"NASA_API_KEY": s.nasa_api_key, "NASA_EARTHDATA_USERNAME": s.earthdata_user, "NASA_EARTHDATA_PASSWORD": s.earthdata_password,
                  "COPERNICUS_CLIENT_ID": s.copernicus_id, "COPERNICUS_CLIENT_SECRET": s.copernicus_secret, "ISRO_API_KEY": s.isro_key}
        import os
        return all(lookup.get(v, os.getenv(v, "")) for v in self.env_vars) if self.env_vars else True

    def status(self, last_test: Optional[dict] = None) -> str:
        if last_test and last_test.get("ok") is False:
            return "unavailable"
        if self.access == "manual":
            return "manual_only"
        if self.access == "credentials":
            return "connected" if self.credentials_present() else "awaiting_credentials"
        return "public_ready"

    def datasets(self) -> List[dict]:
        return [d for d in DATASETS if d["provider"] == self.id]


PROVIDERS: Dict[str, Provider] = {p.id: p for p in [
    # Earth
    Provider("aws_terrain", "AWS Terrain Tiles", "Earth", "public", probe_url="https://s3.amazonaws.com/elevation-tiles-prod/terrarium/0/0/0.png", homepage="https://registry.opendata.aws/terrain-tiles/"),
    Provider("nasa_gibs", "NASA GIBS / Worldview", "Earth", "public", probe_url="https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml", homepage="https://worldview.earthdata.nasa.gov"),
    Provider("nasa_power", "NASA POWER", "Earth", "public", probe_url="https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=T2M&community=RE&longitude=0&latitude=0&format=JSON", homepage="https://power.larc.nasa.gov"),
    Provider("open_meteo", "Open-Meteo (ERA5-derived)", "Earth", "public", probe_url="https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m", homepage="https://open-meteo.com"),
    Provider("usgs_earthquakes", "USGS Earthquake Catalogue", "Earth", "public", probe_url="https://earthquake.usgs.gov/fdsnws/event/1/count?format=geojson&limit=1", homepage="https://earthquake.usgs.gov"),
    Provider("nasa_earthdata", "NASA Earthdata / LP DAAC (SRTM, ASTER, MODIS)", "Earth", "credentials", ["NASA_EARTHDATA_USERNAME", "NASA_EARTHDATA_PASSWORD"],
             ingestion="Create an Earthdata login, add credentials to .env, then download granules (earthaccess or LP DAAC AppEEARS) into storage/uploads or use the upload panel. Authentication: HTTP basic via Earthdata URS.", homepage="https://urs.earthdata.nasa.gov"),
    Provider("copernicus", "Copernicus Data Space (Sentinel-2, GLO-30)", "Earth", "credentials", ["COPERNICUS_CLIENT_ID", "COPERNICUS_CLIENT_SECRET"],
             ingestion="OAuth2 client-credentials against the Copernicus identity service; then query the OData/STAC catalogue. Add the client id/secret to .env.", homepage="https://dataspace.copernicus.eu"),
    Provider("usgs_landsat", "USGS Landsat (EROS)", "Earth", "manual", ingestion="Download Landsat Collection 2 Level-2 scenes from EarthExplorer or AWS and upload the thermal/surface-reflectance GeoTIFFs.", homepage="https://earthexplorer.usgs.gov"),
    Provider("era5", "ERA5 (Copernicus CDS)", "Earth", "manual", ingestion="Use the cdsapi client with a personal CDS key (~/.cdsapirc), export NetCDF, upload or place under storage/uploads.", homepage="https://cds.climate.copernicus.eu"),
    Provider("csa", "CSA open data (RADARSAT-1, RCM)", "Earth", "manual", ingestion="Open https://donnees-data.asc-csa.gc.ca, select RCM or RADARSAT-1, download GRD/GeoTIFF products (some need a free account) and upload with layer=water_ice or morphology. The CSA SAR tutorial (github.com/asc-csa/Synthetic_Aperture_Radar_Tutorial) shows Python/QGIS processing.", homepage="https://donnees-data.asc-csa.gc.ca"),
    Provider("esa_osc", "ESA Open Science Catalog", "Earth", "public", probe_url="https://opensciencedata.esa.int/", homepage="https://opensciencedata.esa.int", ingestion="Browse the STAC catalogue, follow dataset links, download and upload."),
    Provider("jaxa_gportal", "JAXA G-Portal", "Earth", "manual", ingestion="Create a free G-Portal account, search by variable (e.g. snow, vegetation, precipitation), download HDF5/GeoTIFF and upload.", homepage="https://www.gportal.jaxa.jp/?lang=en"),
    Provider("nasa_pds", "NASA Planetary Data System (all nodes)", "Moon", "public", probe_url="https://pds.nasa.gov/", homepage="https://pds.nasa.gov", ingestion="Use the PDS node for your instrument, download products, convert with GDAL to GeoTIFF, upload with body=Moon or Mars."),
    # Moon
    Provider("trek_moon", "NASA Moon Trek (WMTS imagery)", "Moon", "public", probe_url="https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/0/0/0.jpg", homepage="https://trek.nasa.gov/moon/"),
    Provider("pds_lro", "NASA PDS Geosciences: LRO (LOLA, Diviner, LROC)", "Moon", "manual", ingestion="Download LOLA DEM / Diviner GDR / LROC NAC DTM products from the PDS node, convert to GeoTIFF (GDAL), upload with body=Moon.", homepage="https://pds-geosciences.wustl.edu"),
    Provider("isro_pradan", "ISRO ISSDC / PRADAN (Chandrayaan)", "Moon", "credentials", ["ISRO_API_KEY"], ingestion="PRADAN requires registration; download PDS4 products manually and upload. Add a key to .env if a programmatic route is provided.", homepage="https://pradan.issdc.gov.in"),
    Provider("jaxa_selene", "JAXA SELENE / Kaguya archive", "Moon", "manual", ingestion="Download TC/LALT products from the JAXA DARTS archive, convert and upload.", homepage="https://darts.isas.jaxa.jp/planet/pdap/selene/"),
    Provider("esa_psa", "ESA Planetary Science Archive", "Moon", "manual", ingestion="Use the PSA interface or TAP service to fetch PDS4 products, then upload.", homepage="https://archives.esac.esa.int/psa/"),
    # Mars
    Provider("trek_mars", "NASA Mars Trek (WMTS imagery)", "Mars", "public", probe_url="https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/0/0/0.jpg", homepage="https://trek.nasa.gov/mars/"),
    Provider("pds_mars", "NASA PDS Geosciences: Mars (MOLA, HiRISE, CTX, THEMIS, CRISM)", "Mars", "manual", ingestion="Download MOLA/HiRISE DTM/CTX/THEMIS/CRISM products from PDS or the instrument portals, convert to GeoTIFF, upload with body=Mars.", homepage="https://pds-geosciences.wustl.edu"),
]}
PROVIDERS["esa_psa"].body = "Moon"   # shared ESA archive also serves Mars; datasets list both


def _test_cache_path():
    return get_settings().cache_dir / "provider_tests.json"


def load_tests() -> Dict[str, dict]:
    p = _test_cache_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def test_connection(provider_id: str) -> dict:
    """Cheap reachability check; stores the result. Providers without a probe URL report 'not testable'."""
    import requests
    pr = PROVIDERS[provider_id]
    res: dict = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not pr.probe_url:
        res.update(ok=None, detail="No programmatic endpoint to test; use manual ingestion.")
    else:
        try:
            r = requests.get(pr.probe_url, timeout=get_settings().http_timeout_s, headers={"User-Agent": "celestial-cartographers/0.2"})
            res.update(ok=r.status_code < 400, detail=f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            res.update(ok=False, detail=f"{type(e).__name__}: {e}"[:160])
    tests = load_tests(); tests[provider_id] = res
    _test_cache_path().write_text(json.dumps(tests, indent=1), encoding="utf-8")
    return res


def provider_table() -> List[dict]:
    tests = load_tests()
    rows = []
    for p in PROVIDERS.values():
        t = tests.get(p.id)
        rows.append({"id": p.id, "Provider": p.name, "Body": p.body, "Status": STATUS_LABEL[p.status(t)], "status_key": p.status(t),
                     "Datasets": len(p.datasets()), "Needs": ", ".join(p.env_vars) or "-", "Last test": (t or {}).get("detail", "not tested")})
    return rows


def datasets_for(body: Optional[str] = None, layer: Optional[str] = None) -> List[dict]:
    out = []
    for d in DATASETS:
        if body and d["body"] != body:
            continue
        if layer and d["layer"] != layer:
            continue
        pr = PROVIDERS.get(d["provider"])
        out.append({**d, "status": STATUS_LABEL[pr.status(load_tests().get(pr.id))] if pr else "unknown", "status_key": pr.status(load_tests().get(pr.id)) if pr else "unknown"})
    return out
