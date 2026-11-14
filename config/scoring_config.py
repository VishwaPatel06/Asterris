"""Scoring configuration. Change here, not in page scripts."""

MODEL_VERSION = "cc-ranker-0.2"
DATA_VERSION = "curated-catalog-0.2"

# Normalisation ranges (physically meaningful scales, not min-max of the sample)
SLOPE_RANGE_DEG = 30.0
RELIEF_LOG_RANGE = 3.0        # log10 metres difference treated as maximally different
TEMP_MEAN_RANGE_C = 60.0      # |delta mean| at which the mean-temperature term reaches 0

# Terrain sub-score weights: slope, roughness, relief
TERRAIN_WEIGHTS = (0.4, 0.3, 0.3)

# Geology sub-score: mineral Jaccard vs lithology-class match
GEOLOGY_MINERAL_WEIGHT = 0.6
GEOLOGY_LITHOLOGY_WEIGHT = 0.4

# Temperature sub-score: range overlap vs mean difference
TEMP_OVERLAP_WEIGHT = 0.6
TEMP_MEAN_WEIGHT = 0.4

# Sensitivity analysis
SENSITIVITY_DRAWS = 300
SENSITIVITY_CONCENTRATION = 60.0   # Dirichlet concentration around preset weights (higher = smaller perturbation)

# Similarity-label thresholds (labels only; NOT probabilities)
HIGH = 0.75
MEDIUM = 0.50
