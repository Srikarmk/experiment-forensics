"""Analyses 4-5 on the Hillstrom email test."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .cuped import covariate_balance, cuped, diff_in_means, lin_estimator, variance_reduction
from .data import PROJECT_ROOT, hillstrom_check, load_hillstrom
from .subgroups import add_recency_band, benjamini_hochberg, corrected_counts, holm, subgroup_table

# All measured before the emails went out (past-year purchase history).
BALANCE_COVARIATES = ["recency", "history", "mens", "womens", "newbie"]


def pre_covariates(df: pd.DataFrame) -> pd.DataFrame:
    x = df[["history", "recency", "mens", "womens", "newbie"]].astype(float)
    dummies = pd.get_dummies(df[["zip_code", "channel", "history_segment"]], drop_first=True, dtype=float)
    return pd.concat([x, dummies], axis=1)


def _r2_control(y, x):
    xc = np.column_stack([np.ones(len(y)), x])
    beta, *_ = np.linalg.lstsq(xc, y, rcond=None)
    resid = y - xc @ beta
    return float(1 - resid.var() / y.var())


def run_hillstrom(root: Path = PROJECT_ROOT, path: Path | None = None):
    df = load_hillstrom(root, path)
    res = {"check": hillstrom_check(df)}

    bal_df = df.copy()
    for lvl in sorted(df["zip_code"].unique()):
        bal_df[f"bal_zip_{lvl}"] = (df["zip_code"] == lvl).astype(int)
    for lvl in sorted(df["channel"].unique()):
        bal_df[f"bal_channel_{lvl}"] = (df["channel"] == lvl).astype(int)
    covs = BALANCE_COVARIATES + [c for c in bal_df.columns if c.startswith(("bal_zip_", "bal_channel_"))]
    res["balance"] = covariate_balance(bal_df, "segment", config.HILLSTROM_ARMS, config.HILLSTROM_CONTROL, covs)

    estimates = []
    for arm in config.HILLSTROM_ARMS:
        d = df[df["segment"].isin([arm, config.HILLSTROM_CONTROL])]
        t = (d["segment"] == arm).to_numpy()
        x_hist = d[["history"]].to_numpy(float)
        x_all = pre_covariates(d).to_numpy(float)
        for outcome in config.HILLSTROM_OUTCOMES:
            y = d[outcome].to_numpy(float)
            base = diff_in_means(y, t)
            ests = {
                "Difference in means": base,
                "CUPED (history)": cuped(y, t, x_hist),
                "CUPED (all pre-period)": cuped(y, t, x_all),
                "Lin (history)": lin_estimator(y, t, x_hist),
                "Lin (all pre-period)": lin_estimator(y, t, x_all),
            }
            r2_hist = _r2_control(y[~t], x_hist[~t])
            r2_all = _r2_control(y[~t], x_all[~t])
            for name, e in ests.items():
                row = {"treatment": arm, "outcome": outcome, "estimator": name, **e.as_dict(),
                       **variance_reduction(base, e), "r2_history_control": r2_hist, "r2_all_control": r2_all}
                estimates.append(row)
    res["estimates"] = estimates

    sdf = add_recency_band(df)
    tables = []
    for outcome in config.HILLSTROM_OUTCOMES:
        for arm in config.HILLSTROM_ARMS:
            tables.append(subgroup_table(sdf, outcome, arm, config.HILLSTROM_CONTROL))
    sub = pd.concat(tables, ignore_index=True)
    families = {}
    for outcome in config.HILLSTROM_OUTCOMES:
        s = sub[sub["outcome"] == outcome]
        families[outcome] = {
            "effect_nonzero": corrected_counts(s["p_effect"]),
            "differs_from_rest": corrected_counts(s.loc[s["hetero_test"], "p_hetero"]),
        }
    allh = sub[sub["hetero_test"]]
    families["all_heterogeneity_both_outcomes"] = corrected_counts(allh["p_hetero"])
    res["subgroups"] = {"families": families, "n_levels_per_arm": int(len(sub) / 4)}

    sub["p_effect_bh"] = np.nan
    sub["p_hetero_bh"] = np.nan
    sub["p_hetero_holm"] = np.nan
    for outcome in config.HILLSTROM_OUTCOMES:
        m = sub["outcome"] == outcome
        sub.loc[m, "p_effect_bh"] = benjamini_hochberg(sub.loc[m, "p_effect"])
        mh = m & sub["hetero_test"]
        sub.loc[mh, "p_hetero_bh"] = benjamini_hochberg(sub.loc[mh, "p_hetero"])
        sub.loc[mh, "p_hetero_holm"] = holm(sub.loc[mh, "p_hetero"])
    # Binary level 0 shares its level-1 test; copy the adjusted values for plotting.
    key = ["treatment", "outcome", "variable"]
    lvl1 = sub[sub["hetero_test"]].drop_duplicates(key).set_index(key)[["p_hetero_bh", "p_hetero_holm"]]
    mirror = ~sub["hetero_test"]
    idx = pd.MultiIndex.from_frame(sub.loc[mirror, key])
    sub.loc[mirror, ["p_hetero_bh", "p_hetero_holm"]] = lvl1.reindex(idx).to_numpy()
    naive_hetero = sub[sub["hetero_test"] & (sub["p_hetero"] < 0.05)]
    res["subgroups"]["naive_heterogeneity_findings"] = naive_hetero[
        ["treatment", "outcome", "variable", "level", "cate", "diff_vs_rest", "p_hetero", "p_hetero_holm",
         "p_hetero_bh"]].to_dict("records")
    return res, {"subgroups": sub, "estimates": pd.DataFrame(estimates)}
