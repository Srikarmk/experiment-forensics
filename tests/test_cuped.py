import numpy as np
import pytest

from forensics.cuped import cuped, cuped_theta, diff_in_means, lin_estimator


def _sim(rng, n=4000, effect=0.5, beta=3.0):
    x = rng.normal(10, 2, n)
    t = rng.random(n) < 0.5
    y = 1 + beta * x + effect * t + rng.normal(0, 2, n)
    return y, t, x


def test_cuped_unbiased_and_lower_variance():
    rng = np.random.default_rng(0)
    est_dim, est_cuped, est_lin, se_dim, se_cuped = [], [], [], [], []
    for _ in range(400):
        y, t, x = _sim(rng)
        a, b, c = diff_in_means(y, t), cuped(y, t, x), lin_estimator(y, t, x)
        est_dim.append(a.est)
        est_cuped.append(b.est)
        est_lin.append(c.est)
        se_dim.append(a.se)
        se_cuped.append(b.se)
    for est in (est_dim, est_cuped, est_lin):
        assert np.mean(est) == pytest.approx(0.5, abs=3 * np.std(est) / np.sqrt(len(est)) + 1e-3)
    # Var(Y|X) = 4 vs Var(Y) = 9*4 + 4 = 40, so the variance should drop by about 90%.
    assert np.var(est_cuped) < 0.15 * np.var(est_dim)
    assert np.mean(se_cuped) < 0.4 * np.mean(se_dim)
    # Reported SEs should match the spread of the estimates.
    assert np.mean(se_cuped) == pytest.approx(np.std(est_cuped), rel=0.15)


def test_theta_recovers_slope():
    rng = np.random.default_rng(1)
    y, t, x = _sim(rng, n=20000)
    assert cuped_theta(y, x)[0] == pytest.approx(3.0, abs=0.05)


def test_cuped_with_useless_covariate_changes_little():
    rng = np.random.default_rng(2)
    y, t, _ = _sim(rng)
    noise = rng.normal(size=len(y))
    assert cuped(y, t, noise).se == pytest.approx(diff_in_means(y, t).se, rel=0.01)
