"""Cosmic Earth theme: layered navy surfaces, restrained accents, workspace identity colours."""
from __future__ import annotations

import streamlit as st

from config import palette as P

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap');
:root {{ --accent:{P.NEBULA_BLUE}; }}
html, body, .stApp {{ font-family:'Inter','Segoe UI',system-ui,sans-serif; }}
h1,h2,h3,h4 {{ font-family:'Space Grotesk','Inter',sans-serif; letter-spacing:-.01em; color:{P.STARLIGHT}; }}
.stApp {{ background: radial-gradient(1000px 520px at 85% -10%, rgba(120,139,250,.14), transparent 60%),
          radial-gradient(800px 480px at -5% 8%, rgba(72,191,227,.09), transparent 60%), {P.DEEP_SPACE}; }}
[data-testid="stHeader"] {{ background: rgba(8,15,30,.85); backdrop-filter: blur(8px); }}
.block-container {{ padding-top: 2.6rem; max-width: 1320px; }}
section[data-testid="stSidebar"] {{ background:{P.NEBULA_NAVY}; border-right:1px solid {P.STELLAR_SLATE}; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ background:{P.ORBIT_BLUE}; border:1px solid {P.STELLAR_SLATE} !important; border-radius:14px !important; }}
[data-testid="stMetric"] {{ background:{P.ORBIT_BLUE}; border:1px solid {P.STELLAR_SLATE}; border-radius:12px; padding:.7rem .9rem; }}
[data-testid="stMetricLabel"] p {{ color:{P.MOONLIGHT}; font-size:.74rem; letter-spacing:.07em; text-transform:uppercase; }}
[data-testid="stMetricValue"] {{ font-family:'Space Grotesk',sans-serif; font-size:1.55rem; }}
[data-testid="stMetricValue"] > div {{ white-space:normal !important; line-height:1.15; }}
.stTabs [data-baseweb="tab-list"] {{ gap:.25rem; border-bottom:1px solid {P.STELLAR_SLATE}; }}
.stTabs [data-baseweb="tab"] {{ color:{P.MOONLIGHT}; padding:.45rem .9rem; }}
.stTabs [aria-selected="true"] {{ color:{P.STARLIGHT}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:var(--accent) !important; height:3px; }}
.stButton > button, .stDownloadButton > button {{ border-radius:10px; border:1px solid {P.STELLAR_SLATE}; background:{P.ORBIT_BLUE}; color:{P.STARLIGHT}; font-weight:500; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color:{P.COSMIC_CYAN}; color:{P.COSMIC_CYAN}; }}
.stButton > button[kind="primary"] {{ background:{P.NEBULA_BLUE}; border-color:{P.NEBULA_BLUE}; color:#fff; }}
[data-baseweb="select"] > div, .stTextInput input, .stNumberInput input {{ background:{P.NEBULA_NAVY} !important; border-color:{P.STELLAR_SLATE} !important; border-radius:10px !important; }}
[data-testid="stDataFrame"] {{ border:1px solid {P.STELLAR_SLATE}; border-radius:12px; overflow:hidden; }}
.ws-head {{ border-left:4px solid var(--accent); padding:.2rem 0 .2rem 1rem; margin:.2rem 0 1.1rem 0; }}
.ws-head .eyebrow {{ color:var(--accent); text-transform:uppercase; letter-spacing:.2em; font-size:.7rem; font-weight:600; }}
.ws-head h1 {{ margin:.1rem 0 .2rem 0; font-size:2rem; }} .ws-head p {{ margin:0; color:{P.MOONLIGHT}; max-width:62rem; }}
.badge {{ display:inline-block; padding:.12rem .6rem; border-radius:999px; font-size:.72rem; margin-right:.35rem; border:1px solid {P.STELLAR_SLATE}; color:{P.MOONLIGHT}; background:{P.NEBULA_NAVY}; }}
.badge.real {{ border-color:{P.GOOD}; color:{P.GOOD}; }} .badge.local {{ border-color:{P.COSMIC_CYAN}; color:{P.COSMIC_CYAN}; }}
.badge.demonstration {{ border-color:{P.MODERATE}; color:{P.MODERATE}; }} .badge.derived {{ border-color:{P.GALAXY_PURPLE}; color:{P.GALAXY_PURPLE}; }}
.badge.warn {{ border-color:{P.LOW}; color:{P.LOW}; }}
.note {{ border-left:3px solid {P.MODERATE}; background:{P.NEBULA_NAVY}; padding:.55rem .9rem; border-radius:0 10px 10px 0; color:{P.MOONLIGHT}; font-size:.86rem; margin:.4rem 0 1rem 0; }}
.tiny {{ font-size:.78rem; color:{P.MOONLIGHT}; }}
.pcard {{ border-radius:14px; border:1px solid {P.STELLAR_SLATE}; padding:1rem 1.1rem; background:{P.ORBIT_BLUE}; }}
.pcard h3 {{ margin:.1rem 0; }} .pcard.sel {{ border-color:{P.NEBULA_BLUE}; box-shadow:0 0 0 1px {P.NEBULA_BLUE}; }}
.dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:.4rem; }}
"""
ACCENT_KEY = {"overview": "overview", "mission_control": "mission_control", "explorer": "explorer", "discovery": "discovery", "comparison": "comparison",
              "engineering": "engineering", "campaign": "campaign", "assistant": "assistant"}
CLASS_LABEL = {"real": "Real data", "local": "Local data", "demonstration": "Demonstration values", "derived": "Derived"}


def apply_theme(accent: str = "overview") -> None:
    col = P.WORKSPACE_ACCENT.get(accent, P.NEBULA_BLUE)
    st.markdown(f"<style>{CSS}:root{{--accent:{col};}}</style>", unsafe_allow_html=True)


def header(title: str, subtitle: str, eyebrow: str, accent: str) -> None:
    apply_theme(accent)
    st.markdown(f"<div class='ws-head'><div class='eyebrow'>{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>", unsafe_allow_html=True)


def badge(kind: str, text: str = "") -> str:
    return f"<span class='badge {kind}'>{text or CLASS_LABEL.get(kind, kind)}</span>"


def note(text: str) -> None:
    st.markdown(f"<div class='note'>{text}</div>", unsafe_allow_html=True)


def demo_note() -> None:
    note("Built-in site values are hand-compiled demonstration estimates, not pipeline measurements, and scores are similarity indices, not probabilities. "
         "Hackathon data added in Mission Control > Data sources replaces them without code changes.")
