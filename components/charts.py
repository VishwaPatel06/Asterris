"""Plotly charts in the Cosmic Earth palette. One consistent style; similarity gradient only for normalised similarity."""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import plotly.graph_objects as go

from config import palette as P
from config.mission_presets import DIMENSION_LABELS, DIMENSIONS

SER = P.SERIES
GRID = "rgba(168,184,206,.14)"


def base(fig: go.Figure, height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=P.NEBULA_NAVY, font=dict(color=P.STARLIGHT, family="Inter, Segoe UI, sans-serif", size=12.5),
                      margin=dict(l=10, r=10, t=44, b=10), showlegend=legend, colorway=SER, title=dict(font=dict(size=15)),
                      legend=dict(orientation="h", yanchor="top", y=-0.16, x=0, bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor=P.ORBIT_BLUE, font_color=P.STARLIGHT, bordercolor=P.STELLAR_SLATE))
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=P.STELLAR_SLATE, linecolor=P.STELLAR_SLATE, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=P.STELLAR_SLATE, linecolor=P.STELLAR_SLATE, automargin=True)
    return fig


def sim_color(v: Optional[float]) -> str:
    if v is None:
        return P.UNAVAILABLE
    stops = P.SIMILARITY_SCALE
    for (a, ca), (b, cb) in zip(stops[:-1], stops[1:]):
        if v <= b:
            t = (v - a) / (b - a)
            ra = [int(ca[i:i + 2], 16) for i in (1, 3, 5)]; rb = [int(cb[i:i + 2], 16) for i in (1, 3, 5)]
            return "#" + "".join(f"{int(x + (y - x) * t):02x}" for x, y in zip(ra, rb))
    return stops[-1][1]


def _dims(row):
    return [row["dimension_scores"][d] for d in DIMENSIONS]


def dumbbell(rows: List[dict], target_name: str = "Target reference") -> go.Figure:
    """Horizontal dumbbell per dimension: target = 1.0 reference; dot = candidate similarity. Missing dimensions are greyed and labelled."""
    fig = go.Figure()
    labels = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    fig.add_trace(go.Scatter(x=[1] * len(labels), y=labels, mode="markers", name=target_name, marker=dict(symbol="diamond", size=11, color=P.STARLIGHT)))
    for i, r in enumerate(rows):
        v = _dims(r); col = SER[i % len(SER)]
        for lab, x in zip(labels, v):
            if x is not None:
                fig.add_trace(go.Scatter(x=[x, 1], y=[lab, lab], mode="lines", line=dict(color=col, width=2), opacity=.45, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=[x if x is not None else None for x in v], y=labels, mode="markers", name=r["name"].split(" (")[0],
                                 marker=dict(size=12, color=col, line=dict(color=P.DEEP_SPACE, width=1)), hovertemplate="%{y}: %{x:.2f}<extra>" + r["name"] + "</extra>"))
        miss = [lab for lab, x in zip(labels, v) if x is None]
        if miss:
            fig.add_trace(go.Scatter(x=[0.02] * len(miss), y=miss, mode="text", text=["no data"] * len(miss), textfont=dict(color=P.UNAVAILABLE, size=11), showlegend=False, hoverinfo="skip"))
    fig.update_layout(title="Dimension similarity: candidate vs target (target = 1.0)", xaxis=dict(range=[0, 1.05], title="similarity"), yaxis=dict(autorange="reversed"))
    return base(fig, 440)


def hbar(rows: List[dict]) -> go.Figure:
    fig = go.Figure()
    for i, r in enumerate(rows):
        v = _dims(r)
        fig.add_trace(go.Bar(y=[DIMENSION_LABELS[d] for d in DIMENSIONS], x=[x if x is not None else 0 for x in v], orientation="h", name=r["name"].split(" (")[0], marker_color=SER[i % len(SER)],
                             text=[f"{x:.2f}" if x is not None else "no data" for x in v], textposition="outside"))
    fig.update_layout(barmode="group", title="Dimension scores", xaxis=dict(range=[0, 1.2], title="similarity"), yaxis=dict(autorange="reversed"))
    return base(fig, 480)


def radar(rows: List[dict]) -> go.Figure:
    fig = go.Figure(); cats = [DIMENSION_LABELS[d] for d in DIMENSIONS]
    for i, r in enumerate(rows):
        v = [x if x is not None else 0 for x in _dims(r)]
        fig.add_trace(go.Scatterpolar(r=v + v[:1], theta=cats + cats[:1], name=r["name"].split(" (")[0], fill="toself", opacity=.55, line=dict(color=SER[i % len(SER)], width=2),
                                      hovertemplate="%{theta}: %{r:.2f}<extra></extra>"))
    fig.update_layout(title="Overview radar (missing dimensions plot at centre; see dumbbell for exact gaps)", polar=dict(bgcolor=P.NEBULA_NAVY, radialaxis=dict(range=[0, 1], gridcolor=GRID), angularaxis=dict(gridcolor=GRID)))
    return base(fig, 460)


def heatmap(rows: List[dict], dims: List[str]) -> go.Figure:
    z = [[r["dimension_scores"][d] for d in dims] for r in rows]
    zz = [[np.nan if v is None else v for v in row] for row in z]
    miss = [[1.0 if v is None else np.nan for v in row] for row in z]
    txt = [["n/a" if v is None else f"{v:.2f}" for v in row] for row in z]
    x = [DIMENSION_LABELS[d] for d in dims]; y = [r["name"].split(" (")[0] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Heatmap(z=miss, x=x, y=y, colorscale=[[0, P.UNAVAILABLE], [1, P.UNAVAILABLE]], showscale=False, hoverinfo="skip", opacity=.55, xgap=2, ygap=2))
    fig.add_trace(go.Heatmap(z=zz, x=x, y=y, zmin=0, zmax=1, colorscale=P.SIMILARITY_SCALE, text=txt, texttemplate="%{text}", xgap=2, ygap=2, hoverongaps=False,
                             colorbar=dict(title="similarity", tickvals=[0, .5, 1], ticktext=["low", "0.5", "high"])))
    fig.update_layout(title="Similarity heatmap (grey = missing data, not low similarity)", yaxis=dict(autorange="reversed"))
    return base(fig, 110 + 36 * len(rows), False)


def score_bars(rows: List[dict]) -> go.Figure:
    names = [r["name"].split(" (")[0] for r in rows]; fig = go.Figure()
    for key, lab, col in (("fidelity", "Analogue fidelity", P.COSMIC_CYAN), ("suitability", "Mission suitability", P.AURORA_TEAL), ("transferability", "Transferability (heuristic)", P.GALAXY_PURPLE)):
        fig.add_trace(go.Bar(x=names, y=[r[key] if r[key] is not None else None for r in rows], name=lab, marker_color=col))
    fig.update_layout(barmode="group", title="Three scores kept separate", yaxis=dict(range=[0, 1]), xaxis=dict(tickangle=-20))
    return base(fig, 400)


def difference_card(rows: List[dict]) -> go.Figure:
    """Signed gap to the target (score - 1) per dimension; larger bars = bigger difference."""
    fig = go.Figure()
    for i, r in enumerate(rows):
        v = _dims(r)
        fig.add_trace(go.Bar(x=[DIMENSION_LABELS[d] for d in DIMENSIONS], y=[(1 - x) if x is not None else None for x in v], name=r["name"].split(" (")[0], marker_color=SER[i % len(SER)]))
    fig.update_layout(barmode="group", title="Difference scorecard (1 - similarity; lower is closer)", yaxis=dict(range=[0, 1]))
    return base(fig, 380)


def candidate_map(cands: List[dict], values: Dict[str, Optional[float]], height: int = 520, center=None, zoom: float = 0.9, satellite: bool = False) -> go.Figure:
    fig = go.Figure()
    vals = [values.get(c["id"]) for c in cands]
    text = [f"<b>{c['name']}</b><br>{c['status']} - {c['scale']}<br>similarity index: " + ("n/a" if v is None else f"{v:.2f}") + f"<br>{c['lat']:.3f}, {c['lon']:.3f}" for c, v in zip(cands, vals)]
    fig.add_trace(go.Scattermap(lat=[c["lat"] for c in cands], lon=[c["lon"] for c in cands], mode="markers", hovertext=text, hoverinfo="text", customdata=[c["id"] for c in cands],
                                marker=dict(size=[11 + 16 * (v or 0.1) for v in vals], color=[v if v is not None else 0 for v in vals], colorscale=P.SIMILARITY_SCALE, cmin=0, cmax=1, opacity=.92,
                                            colorbar=dict(title="similarity", len=.55, thickness=12))))
    layers = []
    if satellite:
        layers.append(dict(sourcetype="raster", source=["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"], below="traces"))
    c = center or (18, 20)
    fig.update_layout(map=dict(style="carto-darkmatter", center=dict(lat=c[0], lon=c[1]), zoom=zoom, layers=layers), margin=dict(l=0, r=0, t=0, b=0), height=height,
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color=P.STARLIGHT), hoverlabel=dict(bgcolor=P.ORBIT_BLUE, font_color=P.STARLIGHT))
    return fig


def profiles(series: Dict[str, tuple], title: str, normalised: bool = True) -> go.Figure:
    fig = go.Figure()
    for i, (name, (d, z)) in enumerate(series.items()):
        fig.add_trace(go.Scatter(x=d / max(d.max(), 1e-9) if normalised else d, y=z, name=name, line=dict(color=SER[i % len(SER)], width=3), fill="tozeroy" if i == 0 else None, fillcolor="rgba(72,191,227,.10)"))
    fig.update_layout(title=title, xaxis_title="normalised distance" if normalised else "distance (m)", yaxis_title="normalised elevation" if normalised else "elevation (m)")
    return base(fig, 360)


def layer_image(rgb: np.ndarray, title: str) -> go.Figure:
    fig = go.Figure(go.Image(z=rgb)); fig.update_layout(title=title, xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"))
    return base(fig, 420, False)
