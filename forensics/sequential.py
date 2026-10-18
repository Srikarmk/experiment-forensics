"""Mixture sequential probability ratio test (mSPRT) for a difference in click rates.

Normal-mixture mSPRT of Johari, Koomen, Pekelis and Walsh ("Always valid
inference", Operations Research 2022; arXiv:1512.04922). With the estimated
difference D_n, its variance V_n and a N(0, tau^2) mixing distribution over the
true difference, the mixture likelihood ratio is

    Lambda_n = sqrt(V_n / (V_n + tau^2)) * exp(tau^2 D_n^2 / (2 V_n (V_n + tau^2)))

and rejecting the first time Lambda_n >= 1/alpha keeps the type I error at or
below alpha however often one looks. V_n uses the pooled click rate, which is
the null variance.
"""

from __future__ import annotations

import numpy as np


def log_mixture_lr(c1, n1, c0, n0, tau: float):
    c1, n1, c0, n0 = (np.asarray(a, dtype=float) for a in (c1, n1, c0, n0))
    with np.errstate(divide="ignore", invalid="ignore"):
        p1 = np.where(n1 > 0, c1 / n1, 0.0)
        p0 = np.where(n0 > 0, c0 / n0, 0.0)
        pool = np.where(n1 + n0 > 0, (c1 + c0) / (n1 + n0), 0.0)
        v = pool * (1 - pool) * (1 / n1 + 1 / n0)
        t2 = tau**2
        out = 0.5 * np.log(v / (v + t2)) + t2 * (p1 - p0) ** 2 / (2 * v * (v + t2))
    # No clicks yet (or no data): no evidence either way.
    return np.where(v > 0, out, 0.0)


def msprt_reject(c1, n1, c0, n0, tau: float, alpha: float = 0.05):
    return log_mixture_lr(c1, n1, c0, n0, tau) >= np.log(1 / alpha)


def always_valid_p(log_lr_path):
    """Running always-valid p-value: min(1, 1 / max_k Lambda_k)."""
    running = np.maximum.accumulate(np.asarray(log_lr_path, float), axis=-1)
    return np.minimum(1.0, np.exp(-running))
