import math

import numpy as np
import pytest

from simulations import physics as P


def test_verification_suite_all_pass():
    from scientific_engine import validation as V
    rows = V.physics_verification() + V.similarity_verification()
    failed = [r["check"] for r in rows if not r["passed"]]
    assert not failed, failed


def test_sinkage_ordering_by_gravity():
    s = P.SOILS["Dry sand (Wong textbook values)"]
    sk = P.gravity_sweep(s, 150, 4, 0.2, 0.12, 0, [1.62, 3.72, 9.80665])["sinkage_mm"]
    assert sk[0] < sk[1] < sk[2]


def test_load_equilibrium():
    s = P.SOILS["Lunar regolith (commonly cited Apollo-era values)"]
    f = P.wheel_forces(s, 60.0, 0.2, 0.12, 0.2)
    assert abs(float(f["W_residual"])) < 1e-6


def test_climb_infeasible_on_steep_slope():
    s = P.SOILS["Dry sand (Wong textbook values)"]
    assert not P.climb(s, 150, 9.80665, 4, 0.2, 0.12, 40)["feasible"]


def test_rk4_exponential():
    ts, ys = P.rk4(lambda t, y: np.array([-y[0]]), np.array([1.0]), 0, 2, 0.05)
    assert abs(ys[-1, 0] - math.exp(-2)) < 1e-6
