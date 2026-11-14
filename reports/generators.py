"""Discovery report generator: Markdown, CSV, GeoJSON and PDF (blueprint Workspace 06 / A23).

Every export carries a timestamp, model/data versions, assumptions and missing-data notes, and the
clear label: proposed field campaign brief, not an official NASA protocol.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
from typing import Dict, List

from config import scoring_config as cfg
from config.mission_presets import DIMENSION_LABELS, DIMENSIONS
from scientific_engine.explain import explain

TITLE = "Proposed Field Campaign Brief - Not an Official NASA Protocol"
DISCLAIMER = ("Proposed Field Campaign Brief - Not an Official NASA Protocol. Similarity indices are not probabilities. "
              "Built-in catalogue values are hand-compiled demonstration estimates, not validated measurements. Earth cannot reproduce "
              "extraterrestrial gravity, vacuum, radiation or atmospheric conditions.")


def _meta(target: dict, objective: str, weights: Dict[str, float]) -> dict:
    return {"generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "model_version": cfg.MODEL_VERSION,
            "data_version": cfg.DATA_VERSION, "target": target["name"], "body": target["body"], "objective": objective,
            "weights": {d: round(weights.get(d, 0), 3) for d in DIMENSIONS}}


def candidate_table(rows: List[dict], cands: Dict[str, dict]) -> List[dict]:
    out = []
    for r in rows:
        c = cands[r["id"]]
        rec = {"rank": r["rank"], "name": r["name"], "lat": c["lat"], "lon": c["lon"], "scale": c["scale"], "status": c["status"],
               "similarity_index": None if r["total"] is None else round(r["total"], 3),
               "analogue_fidelity": None if r["fidelity"] is None else round(r["fidelity"], 3),
               "mission_suitability": None if r["suitability"] is None else round(r["suitability"], 3),
               "transferability_heuristic": None if r["transferability"] is None else round(r["transferability"], 3),
               "coverage": round(r["coverage"], 2), "missing": ";".join(r["missing_dimensions"]),
               "score_interval_low": None if not r.get("interval") else round(r["interval"][0], 3),
               "score_interval_high": None if not r.get("interval") else round(r["interval"][1], 3),
               "suitability_basis": r.get("suitability_basis"), "provenance_class": c.get("provenance_class", "demonstration"),
               "resolution_m": c.get("resolution_m"), "data_quality": c.get("data_quality")}
        for d in DIMENSIONS:
            v = r["dimension_scores"][d]
            rec[f"dim_{d}"] = None if v is None else round(v, 3)
        rec["sources"] = " | ".join(c.get("sources", []))
        out.append(rec)
    return out


def to_csv(rows, cands) -> str:
    tab = candidate_table(rows, cands)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(tab[0].keys()))
    w.writeheader(); w.writerows(tab)
    return buf.getvalue()


def to_geojson(rows, cands, target, objective, weights) -> str:
    feats = []
    for rec in candidate_table(rows, cands):
        props = {k: v for k, v in rec.items() if k not in ("lat", "lon")}
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [rec["lon"], rec["lat"]]}, "properties": props})
    return json.dumps({"type": "FeatureCollection", "properties": {**_meta(target, objective, weights), "disclaimer": DISCLAIMER},
                       "features": feats}, indent=2)


def to_markdown(rows, cands, target, objective, weights, top_n: int = 3, extras: str = "") -> str:
    m = _meta(target, objective, weights)
    L = [f"# {TITLE}", f"_{DISCLAIMER}_", "",
         f"- Generated (UTC): {m['generated_utc']}", f"- Model / data version: {m['model_version']} / {m['data_version']}",
         f"- Target: {target['name']} ({target['body']}); coordinates {target['lat']}, {target['lon']}",
         f"- Mission objective: {objective}",
         f"- Weights: " + ", ".join(f"{DIMENSION_LABELS[d]} {v:.0%}" for d, v in m["weights"].items()),
         "- Scoring: weighted mean of available dimension similarities (weights renormalised over available dimensions); intervals are 5-95% over feature measurement noise only", "",
         "## Ranking", "", "| Rank | Site | Similarity (5-95%) | Fidelity | Suitability | Transferability* | Coverage |", "|---|---|---|---|---|---|---|"]
    f = lambda v: "n/a" if v is None else f"{v:.2f}"
    for r in rows:
        L.append(f"| {r['rank']} | {r['name']} | {f(r['total'])}{'' if not r.get('interval') else ' (' + format(r['interval'][0], '.2f') + '-' + format(r['interval'][1], '.2f') + ')'} | {f(r['fidelity'])} | {f(r['suitability'])} | {f(r['transferability'])} | {r['coverage']:.0%} |")
    L += ["", "*Transferability is a heuristic discount for unavoidable physical mismatches, not a validated model.", ""]
    for r in rows[:top_n]:
        c = cands[r["id"]]
        L += [f"## {r['rank']}. {r['name']}", f"Coordinates: {c['lat']}, {c['lon']} - scale: {c['scale']} - status: {c['status']}", ""]
        for q, items in explain(target, c, r, objective).items():
            L.append(f"**{q}**")
            L += [f"- {i}" for i in items]
            L.append("")
        L.append("Dimension scores: " + ", ".join(f"{DIMENSION_LABELS[d]} {('n/a' if r['dimension_scores'][d] is None else format(r['dimension_scores'][d], '.2f'))}" for d in DIMENSIONS))
        L.append("Sources: " + "; ".join(c.get("sources", [])) + f" | provenance: {c.get('provenance_class', 'demonstration')} | resolution {c.get('resolution_m')} m")
        L.append("")
    if extras:
        L += [extras, ""]
    L += ["## Assumptions and missing data",
          "- Dimension weights are editable presets, not validated universal weights.",
          "- Missing measurements are treated as unknown (excluded and weights renormalised), never as zero similarity.",
          "- Coordinates, CRS, datum and resolution of source layers must be verified per dataset before field use."]
    return "\n".join(L)


def to_pdf(rows, cands, target, objective, weights, top_n: int = 3, extras: str = "") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    m = _meta(target, objective, weights)
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=colors.HexColor("#101C32"))
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#4B5FD0"))
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=ss["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#101C32"))
    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title="Proposed field campaign brief", author="Celestial Cartographers")
    S = [Paragraph(esc(TITLE), h1), Paragraph(esc(DISCLAIMER), small), Spacer(1, 6),
         Paragraph(f"<b>Target:</b> {esc(target['name'])} ({target['body']}) &nbsp; <b>Objective:</b> {esc(objective)}", body),
         Paragraph(f"<b>Generated (UTC):</b> {m['generated_utc']} &nbsp; <b>Model/data:</b> {m['model_version']} / {m['data_version']}", body),
         Paragraph("<b>Weights:</b> " + ", ".join(f"{DIMENSION_LABELS[d]} {v:.0%}" for d, v in m["weights"].items()), body), Spacer(1, 8),
         Paragraph("Ranking", h2)]
    f = lambda v: "n/a" if v is None else f"{v:.2f}"
    data = [["#", "Site", "Sim.", "Fid.", "Suit.", "Transf.*", "Cov."]]
    for r in rows:
        data.append([r["rank"], Paragraph(esc(r["name"]), body), f(r["total"]), f(r["fidelity"]), f(r["suitability"]), f(r["transferability"]), f"{r['coverage']:.0%}"])
    t = Table(data, colWidths=[8 * mm, 70 * mm, 15 * mm, 15 * mm, 15 * mm, 18 * mm, 15 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#101C32")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#E8F2FA")),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#A8B8CE")), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E8F2FA")])]))
    S += [t, Paragraph("*Transferability is a heuristic discount for physical mismatches, not a validated model.", small), Spacer(1, 8)]
    for r in rows[:top_n]:
        c = cands[r["id"]]
        S += [Paragraph(f"{r['rank']}. {esc(r['name'])}", h2),
              Paragraph(f"Coordinates {c['lat']}, {c['lon']} - scale {c['scale']} - status {c['status']}", body)]
        for q, items in explain(target, c, r, objective).items():
            S.append(Paragraph(f"<b>{esc(q)}</b>", body))
            for i in items:
                S.append(Paragraph("&bull; " + esc(i), body))
        S += [Paragraph("<b>Sources:</b> " + esc("; ".join(c.get("sources", []))), small), Spacer(1, 8)]
    if extras:
        for line in extras.split("\n"):
            if line.strip():
                S.append(Paragraph(esc(line.lstrip("#- ").strip()) if not line.startswith("#") else f"<b>{esc(line.lstrip('# '))}</b>", body))
        S.append(Spacer(1, 6))
    S += [Paragraph("Assumptions and missing data", h2),
          Paragraph("Weights are editable presets. Missing measurements are unknown, not zero. Verify CRS, datum and resolution of each "
                    "source layer before field use.", body)]
    doc.build(S)
    return buf.getvalue()
