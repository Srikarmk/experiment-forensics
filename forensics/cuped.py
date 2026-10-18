"""Average treatment effect estimators for a two-arm comparison.

- difference in means with a Welch (unequal variance) standard error;
- CUPED (Deng, Xu, Kohavi and Walker, WSDM 2013): subtract theta * (X - mean X)
  with theta estimated on both arms pooled, then take the difference in means;
- Lin (2013) regression adjustment: OLS of Y on T, centred covariates and their
  interactions with T, HC2 robust standard errors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import statsmodels.api as sm
from scipy import stats


@dataclass
class Estimate:
    est: float
    se: float
    n_treat: int
    n_ctrl: int

    @property
    def ci(self):
        h = stats.norm.ppf(0.975) * self.se
        return self.est - h, self.est + h

    @property
    def ci_width(self):
        return 2 * stats.norm.ppf(0.975) * self.se

    def as_dict(self):
        d = asdict(self)
        d["ci_low"], d["ci_high"] = self.ci
        d["ci_width"] = self.ci_width
        return d


def _as2d(x):
    x = np.asarray(x, float)
    return x[:, None] if x.ndim == 1 else x


def diff_in_means(y, t) -> Estimate:
    y, t = np.asarray(y, float), np.asarray(t).astype(bool)
    y1, y0 = y[t], y[~t]
    se = np.sqrt(y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0))
    return Estimate(float(y1.mean() - y0.mean()), float(se), int(t.sum()), int((~t).sum()))


def cuped_theta(y, x):
    """Pooled regression coefficients of Y on X (one per covariate column)."""
    y, x = np.asarray(y, float), _as2d(x)
    xc = x - x.mean(axis=0)
    beta, *_ = np.linalg.lstsq(xc, y - y.mean(), rcond=None)
    return beta


def cuped(y, t, x) -> Estimate:
    y, x = np.asarray(y, float), _as2d(x)
    theta = cuped_theta(y, x)
    y_adj = y - (x - x.mean(axis=0)) @ theta
    return diff_in_means(y_adj, t)


def lin_estimator(y, t, x) -> Estimate:
    y, t, x = np.asarray(y, float), np.asarray(t).astype(float), _as2d(x)
    xc = x - x.mean(axis=0)
    design = np.column_stack([np.ones(len(y)), t, xc, xc * t[:, None]])
    fit = sm.OLS(y, design).fit(cov_type="HC2")
    return Estimate(float(fit.params[1]), float(fit.bse[1]), int(t.sum()), int((1 - t).sum()))


def variance_reduction(base: Estimate, other: Estimate) -> dict:
    ratio = other.se**2 / base.se**2
    return {
        "variance_reduction": float(1 - ratio),
        "ci_width_change": float(other.ci_width / base.ci_width - 1),
        "equivalent_sample_multiplier": float(1 / ratio),
    }


def covariate_balance(df, treat_col, arms, control, covariates):
    """Standardized mean differences (each arm vs control) and an omnibus test across all arms."""
    rows = []
    for cov in covariates:
        x = df[cov].astype(float)
        groups = [x[df[treat_col] == a] for a in arms + [control]]
        if set(np.unique(x)) <= {0.0, 1.0}:
            table = np.array([[g.sum(), len(g) - g.sum()] for g in groups])
            p = stats.chi2_contingency(table)[1]
        else:
            p = stats.f_oneway(*groups).pvalue
        c = x[df[treat_col] == control]
        row = {"covariate": cov, "omnibus_p": float(p), "mean_control": float(c.mean())}
        for a in arms:
            g = x[df[treat_col] == a]
            sd = np.sqrt((g.var(ddof=1) + c.var(ddof=1)) / 2)
            row[f"smd_{a}"] = float((g.mean() - c.mean()) / sd) if sd > 0 else 0.0
            row[f"mean_{a}"] = float(g.mean())
        rows.append(row)
    return rows
