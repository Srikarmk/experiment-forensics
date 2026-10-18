"""Subgroup effects for Hillstrom and multiple-comparison corrections."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .cuped import diff_in_means

RECENCY_BANDS = [(1, 3), (4, 6), (7, 9), (10, 12)]
BINARY_VARS = ["newbie", "mens", "womens"]
CATEGORICAL_VARS = ["history_segment", "channel", "zip_code"]


def holm(p):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


def benjamini_hochberg(p):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, p[i] * m / (rank + 1))
        adj[i] = running
    return adj


def add_recency_band(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    band = pd.Series(index=df.index, dtype=object)
    for lo, hi in RECENCY_BANDS:
        band[(df["recency"] >= lo) & (df["recency"] <= hi)] = f"{lo}-{hi} months"
    df["recency_band"] = band
    return df


def subgroup_levels(df: pd.DataFrame):
    """(variable, level, mask). Binary variables appear with both levels."""
    out = []
    for lo, hi in RECENCY_BANDS:
        lvl = f"{lo}-{hi} months"
        out.append(("recency_band", lvl, df["recency_band"] == lvl))
    for v in CATEGORICAL_VARS:
        for lvl in sorted(df[v].unique()):
            out.append((v, str(lvl), df[v] == lvl))
    for v in BINARY_VARS:
        for lvl in (1, 0):
            out.append((v, str(lvl), df[v] == lvl))
    return out


def subgroup_table(df, outcome, treat_arm, control="No E-Mail", seg_col="segment"):
    """CATE per subgroup level, plus a test of whether it differs from the rest.

    For binary variables the level-vs-rest test is the same for both levels,
    so it is kept only on level 1 (`hetero_test` False on level 0).
    """
    d = df[df[seg_col].isin([treat_arm, control])]
    t = (d[seg_col] == treat_arm).to_numpy()
    y = d[outcome].to_numpy(float)
    rows = []
    for var, lvl, mask in subgroup_levels(d):
        m = mask.to_numpy()
        inside = diff_in_means(y[m], t[m])
        rest = diff_in_means(y[~m], t[~m])
        z_eff = inside.est / inside.se
        diff = inside.est - rest.est
        se_diff = np.sqrt(inside.se**2 + rest.se**2)
        lo, hi = inside.ci
        rows.append({
            "treatment": treat_arm, "outcome": outcome, "variable": var, "level": lvl,
            "n": int(m.sum()), "cate": inside.est, "se": inside.se, "ci_low": lo, "ci_high": hi,
            "p_effect": float(2 * stats.norm.sf(abs(z_eff))),
            "diff_vs_rest": diff, "p_hetero": float(2 * stats.norm.sf(abs(diff / se_diff))),
            "hetero_test": not (var in BINARY_VARS and lvl == "0"),
        })
    return pd.DataFrame(rows)


def corrected_counts(p, alpha=0.05):
    p = np.asarray(p, float)
    return {
        "tests": int(len(p)),
        "naive": int((p < alpha).sum()),
        "holm": int((holm(p) <= alpha).sum()),
        "bh": int((benjamini_hochberg(p) <= alpha).sum()),
    }
