"""Seed catalogue of planetary targets and Earth candidates.

IMPORTANT - READ BEFORE USING:
These are hand-compiled, approximate, illustrative values drawn from general public knowledge of each
site. They are NOT measurements, NOT outputs of the data pipeline, and NOT validated. They exist so the
app can demonstrate the workflow end to end. Every value is tagged basis="demonstration_estimate". Replace with
pipeline-derived features (LOLA/MOLA/SRTM/MODIS/...) before drawing any scientific conclusion.
(Blueprint 11.1: "Do not present hardcoded example scores as real measurements.")

Feature schema (all optional; None / missing = unknown, never zero):
  lithology (str), minerals (list[str]), slope_deg, roughness (0-1), relief_m,
  temp_mean_c, temp_min_c, temp_max_c, water_ice (0-1), water_basis ("observed"|"proxy"|"inferred"),
  dust (0-1), biology (0-1), caves (0-1), operations (0-1, Earth candidates only)
"""

BASIS = "demonstration_estimate"

# ----------------------------------------------------------------------------------------------
# Planetary targets
# ----------------------------------------------------------------------------------------------
TARGETS = [
    {
        "id": "moon_shackleton", "body": "Moon", "name": "Shackleton Crater rim (south pole)",
        "lat": -89.9, "lon": 0.0, "scale": "crater", "morphology": "crater",
        "lithology": "anorthosite", "minerals": ["plagioclase", "pyroxene", "regolith", "ice"],
        "slope_deg": 15, "roughness": 0.55, "relief_m": 4200,
        "temp_mean_c": -150, "temp_min_c": -240, "temp_max_c": -50,
        "water_ice": 0.7, "water_basis": "proxy", "dust": 0.9, "biology": 0.0, "caves": 0.1,
        "sources": ["LOLA (topography, resolution varies)", "LRO Diviner (thermal)", "LCROSS/LEND (hydrogen proxy)"],
        "resolution_m": 20, "data_quality": 0.7,
    },
    {
        "id": "moon_marius", "body": "Moon", "name": "Marius Hills pit (lava-tube skylight)",
        "lat": 14.09, "lon": -56.77, "scale": "cave", "morphology": "lava_tube",
        "lithology": "basalt", "minerals": ["pyroxene", "plagioclase", "ilmenite", "olivine"],
        "slope_deg": 8, "roughness": 0.40, "relief_m": 50,
        "temp_mean_c": -20, "temp_min_c": -30, "temp_max_c": -10,
        "water_ice": 0.05, "water_basis": "inferred", "dust": 0.85, "biology": 0.0, "caves": 0.9,
        "sources": ["LROC (pit imagery)", "GRAIL (gravity, tube inference)", "LRO Diviner (pit thermal)"],
        "resolution_m": 1, "data_quality": 0.6,
    },
    {
        "id": "moon_taurus", "body": "Moon", "name": "Taurus-Littrow Valley",
        "lat": 20.19, "lon": 30.77, "scale": "valley", "morphology": "valley",
        "lithology": "basalt", "minerals": ["pyroxene", "ilmenite", "plagioclase", "olivine"],
        "slope_deg": 10, "roughness": 0.45, "relief_m": 2000,
        "temp_mean_c": -20, "temp_min_c": -170, "temp_max_c": 110,
        "water_ice": 0.05, "water_basis": "inferred", "dust": 0.9, "biology": 0.0, "caves": 0.05,
        "sources": ["LOLA", "LROC", "Apollo 17 sample context"],
        "resolution_m": 10, "data_quality": 0.8,
    },
    {
        "id": "mars_jezero", "body": "Mars", "name": "Jezero Crater delta",
        "lat": 18.38, "lon": 77.58, "scale": "crater", "morphology": "crater",
        "lithology": "basalt", "minerals": ["olivine", "pyroxene", "carbonate", "clay"],
        "slope_deg": 10, "roughness": 0.40, "relief_m": 500,
        "temp_mean_c": -60, "temp_min_c": -90, "temp_max_c": 0,
        "water_ice": 0.5, "water_basis": "inferred", "dust": 0.8, "biology": 0.05, "caves": 0.05,
        "sources": ["MOLA", "CRISM (hydrated minerals)", "HiRISE/CTX"],
        "resolution_m": 1, "data_quality": 0.85,
    },
    {
        "id": "mars_arsia", "body": "Mars", "name": "Arsia Mons pits (lava-tube candidates)",
        "lat": -8.35, "lon": -121.1, "scale": "cave", "morphology": "lava_tube",
        "lithology": "basalt", "minerals": ["pyroxene", "olivine", "plagioclase"],
        "slope_deg": 6, "roughness": 0.35, "relief_m": 180,
        "temp_mean_c": -55, "temp_min_c": -110, "temp_max_c": 0,
        "water_ice": 0.1, "water_basis": "inferred", "dust": 0.85, "biology": 0.0, "caves": 0.8,
        "sources": ["MOLA", "THEMIS", "HiRISE/CTX (skylight imagery)"],
        "resolution_m": 6, "data_quality": 0.55,
    },
    {
        "id": "mars_gale", "body": "Mars", "name": "Gale Crater / Mount Sharp",
        "lat": -5.4, "lon": 137.8, "scale": "crater", "morphology": "crater",
        "lithology": "sedimentary", "minerals": ["clay", "sulfate", "hematite", "gypsum", "olivine"],
        "slope_deg": 12, "roughness": 0.45, "relief_m": 5000,
        "temp_mean_c": -55, "temp_min_c": -90, "temp_max_c": 0,
        "water_ice": 0.45, "water_basis": "inferred", "dust": 0.8, "biology": 0.05, "caves": 0.0,
        "sources": ["MOLA", "CRISM", "MSL rover observations"],
        "resolution_m": 1, "data_quality": 0.9,
    },
    {
        "id": "mars_phoenix", "body": "Mars", "name": "Vastitas Borealis (Phoenix region, shallow ice)",
        "lat": 68.2, "lon": -125.7, "scale": "regional", "morphology": "flat",
        "lithology": "regolith", "minerals": ["ice", "perchlorate", "basalt_regolith"],
        "slope_deg": 2, "roughness": 0.15, "relief_m": 20,
        "temp_mean_c": -75, "temp_min_c": -130, "temp_max_c": -20,
        "water_ice": 0.9, "water_basis": "observed", "dust": 0.8, "biology": 0.0, "caves": 0.0,
        "sources": ["Phoenix lander (in situ ice)", "MOLA", "Mars Odyssey GRS (hydrogen)"],
        "resolution_m": 10, "data_quality": 0.9,
    },
]

# ----------------------------------------------------------------------------------------------
# Earth candidates. baseline=True marks famous, well-known analogue regions; others are
# lesser-characterised "proposed candidates" (blueprint 6.3: proposed != validated).
# ----------------------------------------------------------------------------------------------
CANDIDATES = [
    {
        "id": "lonar", "name": "Lonar Crater", "country": "India", "lat": 19.976, "lon": 76.508,
        "scale": "crater", "morphology": "crater", "baseline": False, "status": "proposed candidate",
        "lithology": "basalt", "minerals": ["plagioclase", "pyroxene", "clay", "olivine"],
        "slope_deg": 20, "roughness": 0.40, "relief_m": 150,
        "temp_mean_c": 26, "temp_min_c": 12, "temp_max_c": 42,
        "water_ice": 0.6, "water_basis": "observed", "dust": 0.4, "biology": 0.6, "caves": 0.05, "operations": 0.9,
        "sources": ["NASA Earth Observatory (Lonar Crater)", "SRTM DEM", "Deccan basalt geology"],
        "resolution_m": 30, "data_quality": 0.6,
    },
    {
        "id": "tso_kar", "name": "Tso Kar Valley (Ladakh)", "country": "India", "lat": 33.2, "lon": 78.0,
        "scale": "valley", "morphology": "valley", "baseline": False, "status": "proposed candidate",
        "lithology": "evaporite", "minerals": ["gypsum", "halite", "carbonate", "clay"],
        "slope_deg": 6, "roughness": 0.25, "relief_m": 600,
        "temp_mean_c": 1, "temp_min_c": -30, "temp_max_c": 25,
        "water_ice": 0.5, "water_basis": "proxy", "dust": 0.5, "biology": 0.15, "caves": 0.05, "operations": 0.6,
        "sources": ["SRTM DEM", "MODIS LST (regional)", "Published high-altitude Mars-analogue context"],
        "resolution_m": 30, "data_quality": 0.45,
    },
    {
        "id": "atacama", "name": "Atacama Desert (Yungay)", "country": "Chile", "lat": -24.1, "lon": -69.9,
        "scale": "regional", "morphology": "flat", "baseline": True, "status": "published analogue",
        "lithology": "evaporite", "minerals": ["gypsum", "halite", "perchlorate", "clay"],
        "slope_deg": 3, "roughness": 0.20, "relief_m": 100,
        "temp_mean_c": 17, "temp_min_c": 0, "temp_max_c": 32,
        "water_ice": 0.02, "water_basis": "observed", "dust": 0.7, "biology": 0.02, "caves": 0.0, "operations": 0.8,
        "sources": ["SRTM DEM", "MODIS LST", "Published hyper-arid analogue literature"],
        "resolution_m": 30, "data_quality": 0.8,
    },
    {
        "id": "haughton", "name": "Haughton Crater (Devon Island)", "country": "Canada", "lat": 75.37, "lon": -89.68,
        "scale": "crater", "morphology": "crater", "baseline": True, "status": "published analogue",
        "lithology": "impact_breccia", "minerals": ["carbonate", "plagioclase", "gypsum", "ice"],
        "slope_deg": 12, "roughness": 0.45, "relief_m": 200,
        "temp_mean_c": -16, "temp_min_c": -45, "temp_max_c": 15,
        "water_ice": 0.3, "water_basis": "observed", "dust": 0.4, "biology": 0.1, "caves": 0.0, "operations": 0.4,
        "sources": ["ArcticDEM (where available)", "Published polar-desert analogue literature"],
        "resolution_m": 10, "data_quality": 0.75,
    },
    {
        "id": "dry_valleys", "name": "McMurdo Dry Valleys", "country": "Antarctica", "lat": -77.5, "lon": 162.5,
        "scale": "valley", "morphology": "valley", "baseline": True, "status": "published analogue",
        "lithology": "basalt", "minerals": ["pyroxene", "plagioclase", "ice", "perchlorate"],
        "slope_deg": 14, "roughness": 0.40, "relief_m": 1500,
        "temp_mean_c": -20, "temp_min_c": -50, "temp_max_c": 5,
        "water_ice": 0.35, "water_basis": "observed", "dust": 0.5, "biology": 0.05, "caves": 0.02, "operations": 0.2,
        "sources": ["REMA DEM", "Landsat/Sentinel-2", "Published cold-desert analogue literature"],
        "resolution_m": 8, "data_quality": 0.75,
    },
    {
        "id": "askja", "name": "Askja / Holuhraun (Iceland)", "country": "Iceland", "lat": 65.03, "lon": -16.75,
        "scale": "formation", "morphology": "volcanic", "baseline": True, "status": "published analogue",
        "lithology": "basalt", "minerals": ["olivine", "pyroxene", "plagioclase", "glass"],
        "slope_deg": 10, "roughness": 0.60, "relief_m": 400,
        "temp_mean_c": 2, "temp_min_c": -15, "temp_max_c": 15,
        "water_ice": 0.6, "water_basis": "observed", "dust": 0.5, "biology": 0.2, "caves": 0.3, "operations": 0.7,
        "sources": ["ArcticDEM / ISN DEM", "Sentinel-2", "Published volcanic-analogue literature"],
        "resolution_m": 10, "data_quality": 0.8,
    },
    {
        "id": "hawaii_tubes", "name": "Hawaiian lava tubes (Kilauea-Mauna Loa)", "country": "USA", "lat": 19.42, "lon": -155.28,
        "scale": "cave", "morphology": "lava_tube", "baseline": True, "status": "published analogue",
        "lithology": "basalt", "minerals": ["olivine", "pyroxene", "plagioclase", "glass"],
        "slope_deg": 8, "roughness": 0.45, "relief_m": 30,
        "temp_mean_c": 20, "temp_min_c": 12, "temp_max_c": 28,
        "water_ice": 0.2, "water_basis": "proxy", "dust": 0.3, "biology": 0.5, "caves": 0.9, "operations": 0.6,
        "sources": ["USGS 3DEP", "Cave survey records", "Published lava-tube analogue literature"],
        "resolution_m": 10, "data_quality": 0.7,
    },
    {
        "id": "lanzarote", "name": "Cueva de los Verdes (Lanzarote)", "country": "Spain", "lat": 29.157, "lon": -13.43,
        "scale": "cave", "morphology": "lava_tube", "baseline": False, "status": "proposed candidate",
        "lithology": "basalt", "minerals": ["olivine", "pyroxene", "plagioclase"],
        "slope_deg": 5, "roughness": 0.35, "relief_m": 20,
        "temp_mean_c": 20, "temp_min_c": 14, "temp_max_c": 28,
        "water_ice": 0.05, "water_basis": "proxy", "dust": 0.3, "biology": 0.15, "caves": 0.85, "operations": 0.8,
        "sources": ["Spanish national DEM", "Published cave survey context"],
        "resolution_m": 5, "data_quality": 0.5,
    },
    {
        "id": "uyuni", "name": "Salar de Uyuni", "country": "Bolivia", "lat": -20.13, "lon": -67.49,
        "scale": "formation", "morphology": "flat", "baseline": False, "status": "proposed candidate",
        "lithology": "evaporite", "minerals": ["halite", "gypsum", "clay", "carbonate"],
        "slope_deg": 0.3, "roughness": 0.05, "relief_m": 10,
        "temp_mean_c": 8, "temp_min_c": -15, "temp_max_c": 25,
        "water_ice": 0.5, "water_basis": "observed", "dust": 0.4, "biology": 0.1, "caves": 0.0, "operations": 0.6,
        "sources": ["SRTM DEM", "Sentinel-2", "MODIS LST"],
        "resolution_m": 30, "data_quality": 0.6,
    },
    {
        "id": "dallol", "name": "Dallol hydrothermal field (Danakil)", "country": "Ethiopia", "lat": 14.24, "lon": 40.30,
        "scale": "formation", "morphology": "flat", "baseline": False, "status": "proposed candidate",
        "lithology": "evaporite", "minerals": ["jarosite", "gypsum", "halite", "sulfate"],
        "slope_deg": 3, "roughness": 0.30, "relief_m": 50,
        "temp_mean_c": 35, "temp_min_c": 25, "temp_max_c": 48,
        "water_ice": 0.7, "water_basis": "observed", "dust": 0.5, "biology": 0.3, "caves": 0.0, "operations": 0.2,
        "sources": ["SRTM DEM", "ASTER", "Published hydrothermal-analogue literature"],
        "resolution_m": 30, "data_quality": 0.5,
    },
    {
        "id": "rio_tinto", "name": "Rio Tinto", "country": "Spain", "lat": 37.72, "lon": -6.55,
        "scale": "regional", "morphology": "valley", "baseline": True, "status": "published analogue",
        "lithology": "sedimentary", "minerals": ["jarosite", "hematite", "sulfate", "clay"],
        "slope_deg": 9, "roughness": 0.35, "relief_m": 200,
        "temp_mean_c": 17, "temp_min_c": 3, "temp_max_c": 35,
        "water_ice": 0.8, "water_basis": "observed", "dust": 0.3, "biology": 0.6, "caves": 0.05, "operations": 0.8,
        "sources": ["Spanish national DEM", "Landsat/Sentinel-2", "Published Mars-analogue literature"],
        "resolution_m": 10, "data_quality": 0.8,
    },
    {
        "id": "mauna_kea", "name": "Mauna Kea summit region", "country": "USA", "lat": 19.82, "lon": -155.47,
        "scale": "formation", "morphology": "volcanic", "baseline": True, "status": "published analogue",
        "lithology": "basalt", "minerals": ["olivine", "pyroxene", "plagioclase", "palagonite", "glass"],
        "slope_deg": 14, "roughness": 0.50, "relief_m": 300,
        "temp_mean_c": 0, "temp_min_c": -10, "temp_max_c": 12,
        "water_ice": 0.1, "water_basis": "proxy", "dust": 0.6, "biology": 0.02, "caves": 0.1, "operations": 0.5,
        "sources": ["USGS 3DEP", "Published ISRU / regolith-simulant literature"],
        "resolution_m": 10, "data_quality": 0.75,
    },
]

for _r in TARGETS + CANDIDATES:
    _r["basis"] = BASIS
    _r["provenance_class"] = "demonstration"


def get_targets(body: str):
    return [t for t in TARGETS if t["body"] == body]


def get_target(target_id: str):
    return next(t for t in TARGETS if t["id"] == target_id)


def get_candidate(candidate_id: str):
    return next(c for c in CANDIDATES if c["id"] == candidate_id)
