import numpy as np

from forensics.peeking import rejection_rates, sample_paths
from forensics.sequential import always_valid_p, log_mixture_lr


def test_msprt_aa_error_controlled_with_many_looks():
    rng = np.random.default_rng(1)
    n_sims = 6000
    edges, c0, c1 = sample_paths(np.array([0.015]), np.array([3000]), n_sims, rng, max_looks=100)
    r = rejection_rates(edges, c0, c1, looks=(1, 10, 100), tau=0.0036)
    se = np.sqrt(0.05 * 0.95 / n_sims)
    assert r["msprt"][100] <= 0.05 + 3 * se
    # Naive peeking in the same paths should be badly inflated.
    assert r["naive"][100] > 0.15
    assert abs(r["naive"][1] - 0.05) < 4 * se


def test_msprt_aa_error_controlled_near_continuous_monitoring():
    # Look after every 5 impressions per arm, across a range of rates and mixing scales.
    for p, tau in [(0.01, 0.002), (0.03, 0.01), (0.2, 0.05)]:
        rng = np.random.default_rng(int(p * 1000))
        edges, c0, c1 = sample_paths(np.array([p]), np.array([2000]), 3000, rng, max_looks=400)
        r = rejection_rates(edges, c0, c1, looks=(400,), tau=tau)
        assert r["msprt"][400] <= 0.05 + 3 * np.sqrt(0.05 * 0.95 / 3000), (p, tau, r)


def test_msprt_detects_large_effect():
    rng = np.random.default_rng(2)
    edges, c0, c1 = sample_paths(np.array([0.02]), np.array([20000]), 1000, rng, max_looks=50, lift=0.5)
    r = rejection_rates(edges, c0, c1, looks=(50,), tau=0.01)
    assert r["msprt"][50] > 0.9


def test_always_valid_p_is_monotone():
    path = np.array([0.0, 1.0, 0.5, 2.0, 1.5])
    p = always_valid_p(path)
    assert np.all(np.diff(p) <= 0)
    assert p[-1] == np.exp(-2.0)


def test_no_clicks_gives_no_evidence():
    assert log_mixture_lr(0, 100, 0, 100, 0.01) == 0.0
