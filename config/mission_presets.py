"""Mission-objective presets (blueprint Workspace 01 / Appendix A2).

Weights are STARTING PLACEHOLDERS, not validated universal weights. The user can edit them in the UI.
Only 'Polar Ice Drilling' and 'Lava Tube Exploration' weights come from the blueprint's table;
the others are placeholders in the same spirit.
"""

DIMENSIONS = ["geology", "terrain", "temperature", "water_ice", "dust", "biology", "caves", "operations"]

DIMENSION_LABELS = {
    "geology": "Geology",
    "terrain": "Terrain",
    "temperature": "Temperature",
    "water_ice": "Water/Ice",
    "dust": "Dust",
    "biology": "Biology",
    "caves": "Caves",
    "operations": "Operations",
}

# order: geology, terrain, temperature, water_ice, dust, biology, caves, operations
_W = lambda *v: dict(zip(DIMENSIONS, v))

PRESETS = {
    "Polar Ice Drilling": _W(0.15, 0.10, 0.20, 0.25, 0.05, 0.05, 0.05, 0.15),            # blueprint
    "Lava Tube Exploration": _W(0.20, 0.15, 0.05, 0.05, 0.05, 0.05, 0.35, 0.10),         # blueprint
    "Astrobiology Sampling": _W(0.20, 0.05, 0.10, 0.20, 0.05, 0.25, 0.05, 0.10),
    "Basalt Rover Traction Testing": _W(0.25, 0.30, 0.05, 0.00, 0.15, 0.00, 0.00, 0.25),
    "Lunar Base Site Identification": _W(0.10, 0.20, 0.20, 0.10, 0.10, 0.00, 0.10, 0.20),
    "Mars Habitat Site Identification": _W(0.10, 0.20, 0.15, 0.15, 0.10, 0.05, 0.10, 0.15),
    "Instrument and Equipment Testing": _W(0.10, 0.15, 0.20, 0.05, 0.15, 0.00, 0.05, 0.30),
    "Mars Rover Mobility": _W(0.15, 0.30, 0.05, 0.00, 0.20, 0.00, 0.00, 0.30),
    "Geological Exploration": _W(0.35, 0.20, 0.05, 0.05, 0.05, 0.05, 0.10, 0.15),
    "Astronaut EVA Training": _W(0.15, 0.25, 0.10, 0.00, 0.10, 0.00, 0.10, 0.30),
    "Resource Prospecting": _W(0.25, 0.10, 0.10, 0.30, 0.05, 0.00, 0.05, 0.15),
}

# How strongly each objective depends on physical conditions Earth cannot reproduce.
# Used only by the heuristic transferability score (sum <= 0.6). Placeholders.
PHYSICS_SENSITIVITY = {
    "Polar Ice Drilling": {"gravity": 0.15, "pressure_kpa": 0.15, "radiation_msv_day": 0.05},
    "Lava Tube Exploration": {"gravity": 0.10, "pressure_kpa": 0.10, "radiation_msv_day": 0.10},
    "Astrobiology Sampling": {"gravity": 0.05, "pressure_kpa": 0.15, "radiation_msv_day": 0.25},
    "Basalt Rover Traction Testing": {"gravity": 0.35, "pressure_kpa": 0.05, "radiation_msv_day": 0.00},
    "Lunar Base Site Identification": {"gravity": 0.15, "pressure_kpa": 0.20, "radiation_msv_day": 0.25},
    "Mars Habitat Site Identification": {"gravity": 0.15, "pressure_kpa": 0.10, "radiation_msv_day": 0.20},
    "Instrument and Equipment Testing": {"gravity": 0.10, "pressure_kpa": 0.20, "radiation_msv_day": 0.10},
    "Mars Rover Mobility": {"gravity": 0.35, "pressure_kpa": 0.05, "radiation_msv_day": 0.00},
    "Geological Exploration": {"gravity": 0.05, "pressure_kpa": 0.05, "radiation_msv_day": 0.05},
    "Astronaut EVA Training": {"gravity": 0.30, "pressure_kpa": 0.15, "radiation_msv_day": 0.10},
    "Resource Prospecting": {"gravity": 0.10, "pressure_kpa": 0.15, "radiation_msv_day": 0.05},
}

# Experiments suggested per objective (used by the explanation engine)
EXPERIMENTS = {
    "Polar Ice Drilling": ["Cryogenic drill-string trials in ice-cemented ground", "Ground-ice sampling and core handling", "Thermal-stability tests of drill hardware"],
    "Lava Tube Exploration": ["Cave/tube mapping with LiDAR or SLAM rovers", "Skylight descent and tether tests", "Subsurface comms and radio propagation tests"],
    "Astrobiology Sampling": ["Contamination-controlled sampling protocols", "Biosignature detection instrument trials", "Evaporite/brine microbial community sampling"],
    "Basalt Rover Traction Testing": ["Wheel-soil traction and slip trials on basaltic terrain", "Suspension and slope-climb tests", "Obstacle-field navigation"],
    "Lunar Base Site Identification": ["Site survey and slope/roughness mapping", "Foundation and regolith handling trials", "Thermal management tests"],
    "Mars Rover Mobility": ["Rover mobility on loose sand/duricrust analog", "Slope traverse and energy-use logging", "Autonomous navigation trials"],
    "Geological Exploration": ["Field mapping and stratigraphic logging", "Hand-lens and portable spectrometer campaigns", "Sample caching rehearsals"],
    "Mars Habitat Site Identification": ["Foundation, shielding and ISRU rehearsals on candidate terrain", "Dust and wind-exposure monitoring", "Site slope and hazard mapping"],
    "Instrument and Equipment Testing": ["Instrument calibration against known targets", "Thermal-cycle and dust-exposure trials", "Field comms and power logging"],
    "Astronaut EVA Training": ["EVA traverse rehearsals with suit-mass offload", "Sample collection timeline drills", "Navigation and comms-loss procedures"],
    "Resource Prospecting": ["Ground-penetrating radar and neutron-style survey rehearsals", "Hydrated-mineral spectral surveys", "Core sampling and volatile assay"],
}


# Step-6 candidate filters per objective (applied before similarity scoring). Placeholders to be tuned by the team.
MISSION_FILTERS = {
    "Polar Ice Drilling": {"max_slope_deg": 20, "min_confidence": 0.3},
    "Lava Tube Exploration": {"morphologies": ["lava_tube", "crater", "valley"], "min_confidence": 0.3},
    "Astrobiology Sampling": {"min_confidence": 0.3},
    "Basalt Rover Traction Testing": {"max_slope_deg": 25, "min_confidence": 0.3, "min_diameter_m": 300},
    "Lunar Base Site Identification": {"max_slope_deg": 15, "min_confidence": 0.3},
    "Mars Habitat Site Identification": {"max_slope_deg": 15, "min_confidence": 0.3},
    "Mars Rover Mobility": {"max_slope_deg": 25, "min_confidence": 0.3},
    "Geological Exploration": {"min_confidence": 0.25},
    "Astronaut EVA Training": {"max_slope_deg": 25, "min_confidence": 0.3},
    "Resource Prospecting": {"min_confidence": 0.3},
    "Instrument and Equipment Testing": {"max_slope_deg": 20, "min_confidence": 0.3},
}
