"""Data Source Manager backend: manual uploads, dataset metadata, cache control, ingestion errors.

Everything the UI shows in the Data Sources panel comes from here. Uploaded files are stored under
storage/uploads with a JSON manifest. Candidate/target tables (CSV, GeoJSON, JSON) are validated and
merged into the working catalogue; rasters are registered with whatever metadata can be read.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.settings import get_settings

TABLE_EXT = {".csv", ".geojson", ".json"}
RASTER_EXT = {".tif", ".tiff", ".asc", ".txt"}
SUPPORTED = sorted(TABLE_EXT | RASTER_EXT)

# Columns understood when a table is used as a candidate/target catalogue
RECORD_FIELDS = ["id", "name", "role", "body", "lat", "lon", "scale", "morphology", "status", "lithology", "minerals", "slope_deg", "roughness",
                 "relief_m", "temp_mean_c", "temp_min_c", "temp_max_c", "water_ice", "water_basis", "dust", "biology", "caves", "operations",
                 "resolution_m", "data_quality", "sources", "country"]
NUMERIC = ["lat", "lon", "slope_deg", "roughness", "relief_m", "temp_mean_c", "temp_min_c", "temp_max_c", "water_ice", "dust", "biology", "caves",
           "operations", "resolution_m", "data_quality"]
UNIT_RANGE = ["roughness", "water_ice", "dust", "biology", "caves", "operations", "data_quality"]


def _manifest_path() -> Path:
    return get_settings().storage_dir / "manifest.json"


def _errors_path() -> Path:
    return get_settings().storage_dir / "ingest_errors.json"


def _read(path: Path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return []
    return []


def list_datasets() -> List[dict]:
    return _read(_manifest_path())


def ingest_errors() -> List[dict]:
    return _read(_errors_path())


def _log_error(filename: str, message: str) -> None:
    errs = ingest_errors()
    errs.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "file": filename, "error": message})
    _errors_path().write_text(json.dumps(errs[-50:], indent=1), encoding="utf-8")


def clear_errors() -> None:
    _errors_path().write_text("[]", encoding="utf-8")


def _records_from(name: str, raw: bytes) -> Tuple[Optional[List[dict]], str]:
    ext = Path(name).suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(io.BytesIO(raw))
            recs = df.where(pd.notna(df), None).to_dict("records")
        else:
            obj = json.loads(raw.decode("utf-8"))
            if isinstance(obj, dict) and obj.get("type") == "FeatureCollection":
                recs = []
                for f in obj.get("features", []):
                    props = dict(f.get("properties") or {})
                    g = f.get("geometry") or {}
                    if g.get("type") == "Point":
                        props.setdefault("lon", g["coordinates"][0]); props.setdefault("lat", g["coordinates"][1])
                    recs.append(props)
            elif isinstance(obj, list):
                recs = obj
            else:
                return None, "JSON must be a list of records or a GeoJSON FeatureCollection"
    except Exception as e:  # noqa: BLE001
        return None, f"Could not parse {ext}: {e}"
    return recs, ""


def validate_records(recs: List[dict]) -> Tuple[List[dict], List[str]]:
    """Validate and normalise candidate/target records. Missing values stay None (never 0)."""
    good, problems = [], []
    for i, r in enumerate(recs):
        r = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in r.items()}
        if r.get("name") in (None, "") or r.get("lat") is None or r.get("lon") is None:
            problems.append(f"row {i + 1}: name, lat and lon are required"); continue
        try:
            for k in NUMERIC:
                if r.get(k) not in (None, ""):
                    r[k] = float(r[k])
                else:
                    r[k] = None
        except (TypeError, ValueError):
            problems.append(f"row {i + 1}: non-numeric value in a numeric column"); continue
        if not (-90 <= r["lat"] <= 90 and -360 <= r["lon"] <= 360):
            problems.append(f"row {i + 1}: coordinates out of range"); continue
        bad = [k for k in UNIT_RANGE if r.get(k) is not None and not 0 <= r[k] <= 1]
        if bad:
            problems.append(f"row {i + 1}: {', '.join(bad)} must be within 0-1"); continue
        if isinstance(r.get("minerals"), str):
            r["minerals"] = [m.strip() for m in r["minerals"].replace(";", ",").split(",") if m.strip()]
        if isinstance(r.get("sources"), str):
            r["sources"] = [m.strip() for m in r["sources"].split(";") if m.strip()]
        r["minerals"] = r.get("minerals") or []
        r["sources"] = r.get("sources") or ["user-supplied table"]
        r["role"] = (r.get("role") or "candidate").lower()
        r["id"] = str(r.get("id") or "usr_" + hashlib.sha1(f"{r['name']}{r['lat']}{r['lon']}".encode()).hexdigest()[:8])
        r["scale"] = r.get("scale") or "formation"; r["morphology"] = r.get("morphology") or "flat"
        r["status"] = r.get("status") or "proposed (user-supplied)"
        r["basis"] = "local"; r["provenance_class"] = "local"
        good.append(r)
    return good, problems


def _raster_meta(path: Path) -> dict:
    meta: dict = {}
    try:
        import rasterio  # optional
        with rasterio.open(path) as ds:
            meta.update(shape=[ds.height, ds.width], crs=str(ds.crs), bounds=list(ds.bounds), res=list(ds.res), nodata=ds.nodata, dtype=ds.dtypes[0])
    except ImportError:
        meta["note"] = "rasterio not installed: CRS and bounds could not be read. Install rasterio for full metadata."
    except Exception as e:  # noqa: BLE001
        meta["note"] = f"metadata unreadable: {e}"[:160]
    return meta


def register_upload(name: str, raw: bytes, body: str, layer: str, notes: str = "") -> Tuple[bool, str]:
    """Store an uploaded file and register it. Returns (ok, message)."""
    s = get_settings()
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED:
        msg = f"Unsupported format {ext or '(none)'}. Supported: {', '.join(SUPPORTED)}"
        _log_error(name, msg); return False, msg
    sha = hashlib.sha256(raw).hexdigest()
    if any(d["sha256"] == sha for d in list_datasets()):
        return False, "This exact file is already registered."
    entry = {"id": f"upl_{sha[:10]}", "file": f"{sha[:10]}_{Path(name).name}", "original_name": name, "kind": "table" if ext in TABLE_EXT else "raster",
             "body": body, "layer": layer, "bytes": len(raw), "sha256": sha, "uploaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "provenance_class": "local", "notes": notes, "meta": {}}
    path = s.upload_dir / entry["file"]
    if ext in TABLE_EXT:
        recs, err = _records_from(name, raw)
        if recs is None:
            _log_error(name, err); return False, err
        good, problems = validate_records(recs)
        if not good:
            msg = "No valid rows. " + "; ".join(problems[:4]); _log_error(name, msg); return False, msg
        for p in problems:
            _log_error(name, p)
        entry["meta"] = {"rows_total": len(recs), "rows_valid": len(good), "rows_rejected": len(problems)}
    else:
        path.write_bytes(raw)
        entry["meta"] = _raster_meta(path)
    path.write_bytes(raw)
    m = list_datasets(); m.append(entry)
    _manifest_path().write_text(json.dumps(m, indent=1), encoding="utf-8")
    return True, f"Registered {name} ({entry['kind']})."


def remove_dataset(dataset_id: str) -> None:
    s = get_settings(); keep = []
    for d in list_datasets():
        if d["id"] == dataset_id:
            (s.upload_dir / d["file"]).unlink(missing_ok=True)
        else:
            keep.append(d)
    _manifest_path().write_text(json.dumps(keep, indent=1), encoding="utf-8")


def clear_cache() -> int:
    s = get_settings(); n = 0
    for p in s.cache_dir.glob("*"):
        if p.is_file():
            p.unlink(); n += 1
    return n


def user_records() -> List[dict]:
    """All validated candidate/target rows from uploaded tables."""
    out: List[dict] = []
    s = get_settings()
    for d in list_datasets():
        if d["kind"] != "table":
            continue
        p = s.upload_dir / d["file"]
        if not p.exists():
            continue
        recs, _ = _records_from(d["original_name"], p.read_bytes())
        good, _ = validate_records(recs or [])
        for r in good:
            r["body"] = r.get("body") or d["body"]
            r["source_dataset"] = d["id"]
        out.extend(good)
    return out


def user_rasters(body: Optional[str] = None) -> List[dict]:
    return [d for d in list_datasets() if d["kind"] == "raster" and (body is None or d["body"] == body)]


def raster_bytes(dataset_id: str) -> Optional[Tuple[str, bytes]]:
    s = get_settings()
    for d in list_datasets():
        if d["id"] == dataset_id:
            return d["original_name"], (s.upload_dir / d["file"]).read_bytes()
    return None


def template_csv() -> str:
    row = {"id": "my_site_1", "name": "Example site", "role": "candidate", "body": "Earth", "lat": 37.0, "lon": -110.0, "scale": "formation",
           "morphology": "volcanic", "status": "proposed (user-supplied)", "lithology": "basalt", "minerals": "olivine;pyroxene", "slope_deg": 12,
           "roughness": 0.4, "relief_m": 150, "temp_mean_c": 10, "temp_min_c": -10, "temp_max_c": 35, "water_ice": 0.1, "water_basis": "proxy",
           "dust": 0.5, "biology": 0.1, "caves": 0.0, "operations": 0.7, "resolution_m": 30, "data_quality": 0.7, "sources": "SRTM;Landsat", "country": ""}
    return pd.DataFrame([row], columns=RECORD_FIELDS).to_csv(index=False)
