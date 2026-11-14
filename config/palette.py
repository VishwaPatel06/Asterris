"""Cosmic Earth palette: dark cosmic interface + semantic scientific map-layer colours.

Semantic colours must stay consistent across maps, legends, charts and layer controls.
"""
from __future__ import annotations

# Interface
DEEP_SPACE, NEBULA_NAVY, ORBIT_BLUE, STELLAR_SLATE = "#080F1E", "#101C32", "#192B46", "#263B59"
MOONLIGHT, STARLIGHT = "#A8B8CE", "#F1F5FA"

# Accents
COSMIC_CYAN, NEBULA_BLUE, GALAXY_PURPLE = "#48BFE3", "#788BFA", "#A78BFA"
COSMIC_LAVENDER, AURORA_TEAL, CELESTIAL_MINT = "#C4A1E8", "#45C4A1", "#8BD3A8"

# Scientific map layers (dark -> light)
WATER = ["#0B3C5D", "#146C94", "#2496C7", "#67C8E8", "#A5E5F5"]
VEGETATION = ["#183D2B", "#286847", "#3C9363", "#76B879", "#B4D99A"]
LAND = ["#493326", "#79543A", "#A8754B", "#C99A6B", "#E2C39A"]
VOLCANIC = ["#671F2B", "#A83232", "#DC4C36", "#F07832", "#FFB347"]
ELEVATION = ["#493C8C", "#7564B5", "#B18ACB", "#E0B9C9", "#F3D5A0"]
ICE = ["#D5EAF2", "#A9D4E5", "#7FB9D2", "#B5C9EA", "#E8F2FA"]

# Status
GOOD, MODERATE, LOW, CRITICAL, SELECTED, UNAVAILABLE = "#2E9D70", "#E6B84B", "#E66A4E", "#D64D62", "#788BFA", "#8493A8"

# Similarity gradient (normalised similarity only). Missing data uses a grey hatch, never the low colour.
SIMILARITY_SCALE = [[0.0, "#D64D62"], [0.25, "#E66A4E"], [0.5, "#E6B84B"], [0.75, "#76B879"], [1.0, "#2E9D70"]]

# Workspace identity
WORKSPACE_ACCENT = {
    "overview": NEBULA_BLUE, "mission_control": NEBULA_BLUE, "explorer": COSMIC_CYAN, "discovery": AURORA_TEAL,
    "comparison": GALAXY_PURPLE, "engineering": "#F07832", "campaign": "#C99A6B", "assistant": CELESTIAL_MINT,
}

# Chart series (categorical, colour-blind friendly ordering, distinct from the semantic layers)
SERIES = [COSMIC_CYAN, GALAXY_PURPLE, "#F07832", AURORA_TEAL, "#E6B84B", "#788BFA"]

# Per-body colours used wherever the three worlds are compared
BODY_COLOR = {"Earth": WATER[2], "Moon": MOONLIGHT, "Mars": VOLCANIC[2]}

# Terrain colour ramps used by the 3D viewer and 2D layer maps
LAYER_RAMPS = {
    "elevation": [[0, WATER[1]], [0.18, WATER[3]], [0.22, VEGETATION[2]], [0.45, VEGETATION[3]], [0.6, LAND[2]], [0.82, LAND[4]], [1, ICE[0]]],
    "slope": [[0, VEGETATION[1]], [0.35, VEGETATION[4]], [0.6, LAND[3]], [0.85, VOLCANIC[2]], [1, VOLCANIC[0]]],
    "roughness": [[0, ELEVATION[0]], [0.5, ELEVATION[2]], [1, ELEVATION[4]]],
    "thermal": [[0, ELEVATION[0]], [0.4, ELEVATION[2]], [0.7, VOLCANIC[3]], [1, VOLCANIC[4]]],
}
