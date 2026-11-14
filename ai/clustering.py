"""Exploratory environment clustering (blueprint A7 'Image clustering' analogue on feature vectors).

This clusters catalogue FEATURE VECTORS with k-means. It is an exploratory grouping to spot
recurring environment types; it is not computer-vision classification of imagery. CNN / U-Net
terrain classification needs labelled imagery and is not included in this build.
Cluster labels are not geological facts; check them against maps or expert review.
"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd

FEATURES = ["slope_deg", "roughness", "temp_mean_c", "water_ice", "dust", "biology", "caves", "relief_m"]


def cluster_environments(cands: List[dict], k: int = 4, seed: int = 0) -> pd.DataFrame:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    df = pd.DataFrame([{**{f: c.get(f) for f in FEATURES}, "id": c["id"], "name": c["name"]} for c in cands])
    df["relief_m"] = np.log10(df["relief_m"].clip(lower=1))
    X = df[FEATURES].copy()
    X = X.fillna(X.median(numeric_only=True))
    Z = StandardScaler().fit_transform(X)
    k = max(2, min(k, len(df)))
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(Z)
    df["cluster"] = km.labels_
    from sklearn.decomposition import PCA
    p = PCA(n_components=2, random_state=seed).fit_transform(Z)
    df["pc1"], df["pc2"] = p[:, 0], p[:, 1]
    return df
