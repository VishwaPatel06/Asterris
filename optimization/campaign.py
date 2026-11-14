"""Multi-site campaign optimisation (blueprint /api/campaign/optimize).

Greedy selection of complementary Earth sites: each pick should add the most *new* weighted
dimension coverage, discounted by logistics difficulty, so the campaign does not repeat the same
strengths at three sites. Greedy submodular selection, not a proven global optimum.
"""
from __future__ import annotations

from typing import Dict, List

from config.mission_presets import DIMENSIONS
from data_sources.live_earth import haversine_km
from scientific_engine.similarity import normalise_weights


def select_campaign(rows: List[dict], cands: Dict[str, dict], weights: Dict[str, float], k: int = 3,
                    logistics_weight: float = 0.25) -> List[dict]:
    w = normalise_weights(weights)
    best = {d: 0.0 for d in DIMENSIONS}
    chosen, remaining = [], {r["id"]: r for r in rows if r["total"] is not None}
    for step in range(min(k, len(remaining))):
        gains = {}
        for cid, r in remaining.items():
            gain = 0.0
            for d in DIMENSIONS:
                s = r["dimension_scores"].get(d)
                if s is not None and d != "operations":
                    gain += w[d] * max(0.0, s - best[d])
            ops = cands[cid].get("operations")
            ops = 0.5 if ops is None else ops
            gains[cid] = gain * (1 - logistics_weight) + logistics_weight * ops * 0.2 + 0.02 * (r["total"] or 0)
        cid = max(gains, key=gains.get)
        r = remaining.pop(cid)
        added = {d: max(0.0, (r["dimension_scores"].get(d) or 0) - best[d]) for d in DIMENSIONS if d != "operations"}
        for d in DIMENSIONS:
            s = r["dimension_scores"].get(d)
            if s is not None:
                best[d] = max(best[d], s)
        chosen.append({"order": step + 1, "id": cid, "name": r["name"], "marginal_gain": gains[cid],
                       "new_coverage": [d for d, v in added.items() if v > 0.15]})
    return chosen


def route_length_km(ids: List[str], cands: Dict[str, dict]) -> float:
    total = 0.0
    for a, b in zip(ids[:-1], ids[1:]):
        total += haversine_km(cands[a]["lat"], cands[a]["lon"], cands[b]["lat"], cands[b]["lon"])
    return total


def campaign_coverage(chosen: List[dict], rows: List[dict]) -> Dict[str, float]:
    by = {r["id"]: r for r in rows}
    out = {}
    for d in DIMENSIONS:
        vals = [by[c["id"]]["dimension_scores"].get(d) for c in chosen]
        vals = [v for v in vals if v is not None]
        out[d] = max(vals) if vals else None
    return out
