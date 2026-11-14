"""Working catalogue = built-in demonstration records + any user-supplied tables from the Data Source Manager.

Precedence: user rows with the same id override built-in rows. Every record carries provenance_class so the UI can
label demonstration vs local vs derived values. Nothing here fabricates measurements.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from data_sources import manager
from data_sources.seed_catalog import CANDIDATES as _SEED_C, TARGETS as _SEED_T


def _merge(base: List[dict], extra: List[dict]) -> List[dict]:
    by = {r["id"]: r for r in base}
    for r in extra:
        by[r["id"]] = r
    return list(by.values())


def load_catalog() -> Dict[str, List[dict]]:
    users = manager.user_records()
    ut = [r for r in users if r["role"] == "target"]
    uc = [r for r in users if r["role"] != "target"]
    for r in uc:
        r.setdefault("baseline", False); r.setdefault("water_basis", r.get("water_basis") or "proxy")
    for r in ut:
        r.setdefault("body", "Moon")
    return {"targets": _merge(_SEED_T, ut), "candidates": _merge(_SEED_C, uc), "user_rows": len(users)}


def targets_for(body: str) -> List[dict]:
    return [t for t in load_catalog()["targets"] if t["body"] == body]


def target_by_id(tid: str) -> Optional[dict]:
    return next((t for t in load_catalog()["targets"] if t["id"] == tid), None)
