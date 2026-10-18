"""A/A (and A/B) simulations with interim looks.

Each simulated experiment takes a real test's pooled click rate and average arm
size. Both arms share the same true rate (A/A) or the treatment arm gets a
relative lift (A/B). Impressions arrive in `max_looks` equal batches; a policy
with K looks checks after every (max_looks / K)-th batch, so all K share the
same sample paths and the curves are nested.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from .effects import two_prop_ztest
from .sequential import msprt_reject

DEFAULT_LOOKS = (1, 2, 5, 10, 20, 50, 100)


def sample_paths(rates, n_per_arm, n_sims, rng, max_looks=100, lift=0.0):
    """Cumulative (n, clicks) for both arms at each of max_looks batch ends."""
    idx = rng.integers(0, len(rates), size=n_sims)
    p0 = np.asarray(rates, float)[idx]
    p1 = np.clip(p0 * (1 + lift), 0, 1)
    n = np.asarray(n_per_arm, float)[idx].round().astype(np.int64)
    edges = np.floor(n[:, None] * np.arange(1, max_looks + 1)[None, :] / max_looks).astype(np.int64)
    batch = np.diff(np.concatenate([np.zeros((n_sims, 1), np.int64), edges], axis=1), axis=1)
    c0 = np.cumsum(rng.binomial(batch, p0[:, None]), axis=1)
    c1 = np.cumsum(rng.binomial(batch, p1[:, None]), axis=1)
    return edges, c0, c1


def rejection_rates(edges, c0, c1, looks=DEFAULT_LOOKS, alpha=0.05, tau=None):
    """Share of simulations that ever reject, per number of looks."""
    max_looks = edges.shape[1]
    zcrit = stats.norm.ppf(1 - alpha / 2)
    out = {"naive": {}, "msprt": {}}
    with np.errstate(divide="ignore", invalid="ignore"):
        z, _ = two_prop_ztest(c1, edges, c0, edges)
        z = np.where(edges > 0, z, 0.0)
        naive_rej = np.abs(z) > zcrit
        ms_rej = msprt_reject(c1, edges, c0, edges, tau, alpha) & (edges > 0) if tau else None
    for k in looks:
        if max_looks % k:
            raise ValueError(f"{k} looks does not divide {max_looks}")
        cols = np.arange(max_looks // k - 1, max_looks, max_looks // k)
        out["naive"][k] = float(naive_rej[:, cols].any(axis=1).mean())
        if ms_rej is not None:
            out["msprt"][k] = float(ms_rej[:, cols].any(axis=1).mean())
    return out


def mc_se(p, n):
    return float(np.sqrt(p * (1 - p) / n))
