import numpy as np
import pytest

from forensics.shrinkage import fit_grid_prior, fit_normal_prior, shrinkage_fraction


def _sim(rng, n=5000, mu=0.0, tau=1.0):
    theta = rng.normal(mu, tau, n)
    s = rng.uniform(0.5, 1.5, n)
    return theta, theta + rng.normal(0, s), s


def test_normal_prior_recovers_parameters():
    rng = np.random.default_rng(0)
    _, d, s = _sim(rng, mu=0.3, tau=0.8)
    prior = fit_normal_prior(d, s)
    assert prior.mu == pytest.approx(0.3, abs=0.06)
    assert prior.tau == pytest.approx(0.8, abs=0.06)


def test_posterior_means_beat_raw_estimates():
    rng = np.random.default_rng(1)
    theta, d, s = _sim(rng)
    for prior in (fit_normal_prior(d, s), fit_grid_prior(d, s)):
        post = prior.posterior_mean(d, s)
        assert np.mean((post - theta) ** 2) < 0.8 * np.mean((d - theta) ** 2)


def test_shrinkage_between_zero_and_one_for_centered_normal():
    rng = np.random.default_rng(2)
    _, d, s = _sim(rng)
    prior = fit_normal_prior(d, s)
    prior.mu = 0.0
    f = shrinkage_fraction(d, prior.posterior_mean(d, s))
    assert np.all((f >= 0) & (f <= 1))


def test_selected_winners_shrink_and_posterior_tracks_truth():
    # Winner's curse in miniature: among estimates that clear z > 1.96, the raw
    # mean overstates the truth, and the posterior mean is close to it.
    rng = np.random.default_rng(3)
    theta, d, s = _sim(rng, n=20000, tau=0.5)
    sel = d / s > 1.96
    prior = fit_grid_prior(d, s)
    post = prior.posterior_mean(d, s)
    assert d[sel].mean() > 1.5 * theta[sel].mean()
    assert post[sel].mean() == pytest.approx(theta[sel].mean(), abs=0.05)


def test_grid_prior_is_a_distribution_and_monotone():
    rng = np.random.default_rng(4)
    _, d, s = _sim(rng, n=2000)
    g = fit_grid_prior(d, s)
    assert g.weights.sum() == pytest.approx(1.0)
    assert np.all(g.weights >= 0)
    xs = np.linspace(-3, 3, 50)
    pm = g.posterior_mean(xs, np.ones_like(xs))
    assert np.all(np.diff(pm) >= -1e-9)
