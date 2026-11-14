"""Rover and gravity-offload engineering estimates (blueprint Workspace 05).

Traverse planning: A* over a slope cost surface, energy and line-of-sight. Terramechanics (sinkage, slip, offload)
is in simulations/physics.py. Outputs are estimates for test planning, not validated hardware predictions.
"""
from __future__ import annotations

import heapq
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from simulations.physics import SOILS, Soil, gravity_offload, rolling_resistance_coeff  # noqa: F401  (terramechanics lives in physics.py)

# ---------------------------------------------------------------------------------------------
# Traverse planner: A* over a terrain cost surface, energy and line-of-sight estimates
# ---------------------------------------------------------------------------------------------
def astar(slope: np.ndarray, cell_m: float, start: Tuple[int, int], goal: Tuple[int, int], max_slope: float = 20.0):
    """8-connected A*. Cells steeper than max_slope are obstacles; cost grows with slope. Returns list of (row, col) or None."""
    n, m = slope.shape
    def h(a, b): return math.hypot(a[0] - b[0], a[1] - b[1]) * cell_m
    openq = [(h(start, goal), 0.0, start)]
    came: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g = {start: 0.0}
    while openq:
        _, gc, cur = heapq.heappop(openq)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]; path.append(cur)
            return path[::-1]
        if gc > g.get(cur, 1e18):
            continue
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nb = (cur[0] + dr, cur[1] + dc)
                if not (0 <= nb[0] < n and 0 <= nb[1] < m):
                    continue
                s = slope[nb]
                if s > max_slope:
                    continue
                step = math.hypot(dr, dc) * cell_m * (1 + (s / max_slope) ** 2)
                ng = gc + step
                if ng < g.get(nb, 1e18):
                    g[nb] = ng; came[nb] = cur
                    heapq.heappush(openq, (ng + h(nb, goal), ng, nb))
    return None


def path_stats(h: np.ndarray, cell_m: float, path: List[Tuple[int, int]], mass_kg: float, g: float,
               crr: float, efficiency: float = 0.5) -> Dict:
    dist, gain, energy = 0.0, 0.0, 0.0
    for a, b in zip(path[:-1], path[1:]):
        d = math.hypot(a[0] - b[0], a[1] - b[1]) * cell_m
        dz = h[b] - h[a]
        dist += d
        if dz > 0:
            gain += dz
        th = math.atan2(dz, d)
        force = mass_kg * g * (crr * math.cos(th) + math.sin(th))
        energy += max(force, 0.0) * math.hypot(d, dz) / efficiency   # no regeneration assumed
    return {"distance_m": dist, "elevation_gain_m": gain, "energy_Wh": energy / 3600.0,
            "avg_energy_Wh_per_km": (energy / 3600.0) / (dist / 1000.0) if dist > 0 else 0.0}


def line_of_sight(h: np.ndarray, cell_m: float, tx: Tuple[int, int], rx: Tuple[int, int],
                  tx_height_m: float = 3.0, rx_height_m: float = 1.5) -> bool:
    """Geometric LOS between antenna heights above the DEM; ignores curvature and diffraction."""
    steps = int(max(abs(tx[0] - rx[0]), abs(tx[1] - rx[1])) * 2) + 2
    zt, zr = h[tx] + tx_height_m, h[rx] + rx_height_m
    for i in range(1, steps):
        t = i / steps
        r = tx[0] + (rx[0] - tx[0]) * t; c = tx[1] + (rx[1] - tx[1]) * t
        ground = h[int(round(r)), int(round(c))]
        if ground > zt + (zr - zt) * t:
            return False
    return True


def comms_coverage(h: np.ndarray, cell_m: float, path: List[Tuple[int, int]], lander: Tuple[int, int]) -> float:
    ok = sum(line_of_sight(h, cell_m, lander, p) for p in path)
    return ok / max(len(path), 1)
