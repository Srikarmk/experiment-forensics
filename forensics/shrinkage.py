"""Empirical-Bayes shrinkage of observed differences d_i ~ N(theta_i, s_i^2).

Two priors for theta:
- normal: theta ~ N(mu, tau^2), fit by maximum marginal likelihood;
- grid (NPMLE): theta takes values on a fixed grid with weights fit by EM
  (Kiefer-Wolfowitz / Koenker-Mizera style), which allows heavy tails.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize, stats


@dataclass
class NormalPrior:
    mu: float
    tau: float

    def posterior_mean(self, d, s):
        d, s = np.asarray(d, float), np.asarray(s, float)
        b = self.tau**2 / (self.tau**2 + s**2)
        return self.mu + b * (d - self.mu)

    def posterior_sd(self, d, s):
        s = np.asarray(s, float)
        return np.sqrt(self.tau**2 * s**2 / (self.tau**2 + s**2))

    def prob_positive(self, d, s):
        return stats.norm.sf(0, loc=self.posterior_mean(d, s), scale=self.posterior_sd(d, s))


def fit_normal_prior(d, s) -> NormalPrior:
    d, s = np.asarray(d, float), np.asarray(s, float)

    def nll(par):
        mu, log_tau = par
        v = np.exp(2 * log_tau) + s**2
        return 0.5 * np.sum(np.log(v) + (d - mu) ** 2 / v)

    tau0 = np.sqrt(max(np.var(d) - np.mean(s**2), 1e-12))
    res = optimize.minimize(nll, x0=[np.mean(d), np.log(tau0)], method="Nelder-Mead",
                            options={"xatol": 1e-10, "fatol": 1e-10, "maxiter": 5000})
    mu, log_tau = res.x
    return NormalPrior(mu=float(mu), tau=float(np.exp(log_tau)))


@dataclass
class GridPrior:
    grid: np.ndarray
    weights: np.ndarray

    def _post(self, d, s):
        d, s = np.asarray(d, float), np.asarray(s, float)
        lik = stats.norm.pdf(d[:, None], loc=self.grid[None, :], scale=s[:, None])
        post = lik * self.weights[None, :]
        post /= post.sum(axis=1, keepdims=True)
        return post

    def _chunked(self, d, s, f, size=20_000):
        d, s = np.atleast_1d(np.asarray(d, float)), np.atleast_1d(np.asarray(s, float))
        return np.concatenate([f(self._post(d[i:i + size], s[i:i + size])) for i in range(0, len(d), size)])

    def posterior_mean(self, d, s):
        return self._chunked(d, s, lambda post: post @ self.grid)

    def prob_positive(self, d, s):
        return self._chunked(d, s, lambda post: post[:, self.grid > 0].sum(axis=1))

    def mean(self):
        return float(self.weights @ self.grid)

    def sd(self):
        m = self.mean()
        return float(np.sqrt(self.weights @ (self.grid - m) ** 2))

    def quantile_abs(self, q):
        order = np.argsort(np.abs(self.grid))
        cw = np.cumsum(self.weights[order])
        return float(np.abs(self.grid[order])[np.searchsorted(cw, q)])


def fit_grid_prior(d, s, n_grid: int = 301, max_iter: int = 3000, tol: float = 1e-8) -> GridPrior:
    d, s = np.asarray(d, float), np.asarray(s, float)
    grid = np.linspace(d.min(), d.max(), n_grid)
    if not np.any(grid == 0):
        grid = np.sort(np.append(grid, 0.0))
    lik = stats.norm.pdf(d[:, None], loc=grid[None, :], scale=s[:, None])
    w = np.full(len(grid), 1.0 / len(grid))
    prev = -np.inf
    for _ in range(max_iter):
        m = lik @ w
        ll = np.sum(np.log(m))
        w = w * (lik.T @ (1.0 / m)) / len(d)
        if ll - prev < tol * abs(ll):
            break
        prev = ll
    return GridPrior(grid=grid, weights=w / w.sum())


def shrinkage_fraction(observed, posterior):
    """1 - posterior/observed: 0 means no shrinkage, 1 means shrunk to zero."""
    observed, posterior = np.asarray(observed, float), np.asarray(posterior, float)
    return 1 - posterior / observed
