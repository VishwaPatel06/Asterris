"""AI Planetary Research Assistant (blueprint A22) - dataset-grounded, retrieval-based.

This version deliberately uses NO language model: answers are assembled from the candidate
records and computed scores, cite the recorded datasets, separate fact from interpretation, and say
when information is unavailable. That makes it incapable of inventing scientific explanations.
`answer()` is the single integration point: to add an LLM later, pass the same retrieved
`evidence` list to it as its only allowed context.
"""
from __future__ import annotations

import re
from typing import Dict, List

from config.mission_presets import DIMENSION_LABELS, PRESETS
from scientific_engine.explain import explain, physical_scorecard, processes_for
from scientific_engine.similarity import rank_candidates

SUPPORTED = ["why a site was selected", "which sites suit rover testing", "what resembles the target terrain",
             "limitations of an analogue", "water/ice indicators", "caves and lava tubes", "missing or unavailable data"]


def _find_candidate(q: str, cands: List[dict]):
    ql = q.lower()
    for c in cands:
        names = [c["name"].lower(), c["id"].replace("_", " ")] + [w for w in re.split(r"[ ()/,-]+", c["name"].lower()) if len(w) > 4]
        if any(n in ql for n in names[:2]) or any(n in ql for n in names[2:3]):
            return c
    return None


def answer(question: str, target: dict, cands: List[dict], rows: List[dict], objective: str) -> Dict:
    q = question.lower()
    by_row = {r["id"]: r for r in rows}
    by_c = {c["id"]: c for c in cands}
    evidence: List[str] = []
    facts: List[str] = []
    interp: List[str] = []

    c = _find_candidate(q, cands)

    if c and any(k in q for k in ("why", "selected", "identified", "chosen")):
        ex = explain(target, c, by_row[c["id"]], objective)
        facts += ex["Why was this location selected?"] + ex["Which planetary characteristics does it resemble?"]
        interp += ex["What geological processes are comparable?"]
        facts += [f"Limitation: {x}" for x in ex["Where does the analogy break down?"][:4]]
        evidence += c.get("sources", [])
    elif c and any(k in q for k in ("limit", "break", "differ", "weak")):
        ex = explain(target, c, by_row[c["id"]], objective)
        facts += ex["Where does the analogy break down?"]
        evidence += c.get("sources", [])
    elif any(k in q for k in ("rover", "traction", "mobility", "wheel")):
        preset = "Basalt Rover Traction" if target["body"] == "Moon" else "Mars Rover Mobility"
        rr = rank_candidates(target, cands, PRESETS[preset], preset)[:3]
        facts.append(f"Ranked with the '{preset}' preset (terrain and operations weighted heavily) against {target['name']}:")
        for r in rr:
            cc = by_c[r["id"]]
            facts.append(f"{r['rank']}. {r['name']} - index {r['total']:.2f}; slope {cc.get('slope_deg')}°, roughness {cc.get('roughness')}, operations {cc.get('operations')}.")
            evidence += cc.get("sources", [])[:2]
        interp.append("Rover tests also depend on soil mechanics and gravity, which a similarity index does not capture.")
    elif any(k in q for k in ("resemble", "similar", "look like", "terrain", "lunar", "martian")):
        top = sorted(rows, key=lambda r: -(r["dimension_scores"].get("terrain") or 0))[:3]
        facts.append(f"Closest terrain similarity to {target['name']}:")
        for r in top:
            facts.append(f"{r['name']}: terrain {r['dimension_scores']['terrain']:.2f}, geology "
                         f"{(r['dimension_scores']['geology'] or 0):.2f}.")
            evidence += by_c[r["id"]].get("sources", [])[:2]
    elif any(k in q for k in ("ice", "water", "wet", "brine")):
        top = sorted([c2 for c2 in cands if c2.get("water_ice") is not None], key=lambda x: -x["water_ice"])[:4]
        facts.append("Water/ice indicator (0-1) with how it was established:")
        for c2 in top:
            facts.append(f"{c2['name']}: {c2['water_ice']} ({c2.get('water_basis', 'basis unknown')}).")
            evidence += c2.get("sources", [])[:1]
        interp.append("Proxies and inferences are not direct measurements of ice.")
    elif any(k in q for k in ("cave", "lava tube", "tube", "subsurface", "underground")):
        top = sorted([c2 for c2 in cands if (c2.get("caves") or 0) >= 0.5], key=lambda x: -x["caves"])
        facts.append("Candidates with strong cave/lava-tube evidence:")
        for c2 in top:
            facts.append(f"{c2['name']}: cave evidence {c2['caves']}, stable temp range {c2.get('temp_min_c')} to {c2.get('temp_max_c')} °C.")
            evidence += c2.get("sources", [])[:1]
        interp.append("Unknown cave evidence is not absence; subsurface properties are mostly inferred.")
    elif any(k in q for k in ("missing", "unavailable", "unknown", "no data", "gap")):
        for r in rows:
            if r["missing_dimensions"]:
                facts.append(f"{r['name']}: missing {', '.join(DIMENSION_LABELS[d] for d in r['missing_dimensions'])}.")
        facts = facts or ["No candidate has a missing weighted dimension in the current catalogue."]
    elif any(k in q for k in ("limitation", "limit", "gravity", "radiation", "pressure")):
        for r in physical_scorecard(target["body"]):
            facts.append(f"{r['Factor']}: Earth {r['Earth']} vs {target['body']} {r['Target body']} - {r['Earth site can...']}.")
    else:
        return {"text": "I can only answer from the loaded catalogue and computed scores, and I could not match your question to "
                        "available evidence. I can help with: " + "; ".join(SUPPORTED) + ".", "evidence": [], "grounded": False}

    seen, ev = set(), []
    for e in evidence:
        if e not in seen:
            seen.add(e); ev.append(e)
    text = "**Facts from the catalogue and scores**\n" + "\n".join(f"- {f}" for f in facts)
    if interp:
        text += "\n\n**Interpretation (not a measurement)**\n" + "\n".join(f"- {i}" for i in interp)
    text += "\n\n_Catalogue values are seed estimates, not validated measurements._"
    return {"text": text, "evidence": ev, "grounded": True}
