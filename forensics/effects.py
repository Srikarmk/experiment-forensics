"""Arm-vs-reference comparisons, two-proportion z-tests, MDE and power.

Definition used throughout: in each test the reference arm is the package
created first (earliest created_at). Every other arm is compared with it.
Upworthy had no control arm; the first-written package is the closest thing
to an "original" headline and is fixed before any data come in, so the choice
cannot depend on the outcome.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .config import MIN_ARM_IMPRESSIONS


def two_prop_ztest(c1, n1, c0, n0):
    """Pooled two-proportion z-test of p1 - p0. Returns (z, two-sided p)."""
    c1, n1, c0, n0 = (np.asarray(a, dtype=float) for a in (c1, n1, c0, n0))
    p_pool = (c1 + c0) / (n1 + n0)
    se = np.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n0))
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (c1 / n1 - c0 / n0) / se
    z = np.where(se > 0, z, 0.0)
    return z, 2 * stats.norm.sf(np.abs(z))


def mde(p, n1, n0, alpha=0.05, power=0.8):
    """Smallest absolute difference detectable with the given power (two-sided)."""
    p, n1, n0 = (np.asarray(a, dtype=float) for a in (p, n1, n0))
    k = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return k * np.sqrt(p * (1 - p) * (1 / n1 + 1 / n0))


def power_at(delta, se, alpha=0.05):
    """Power of a two-sided z-test when the true difference is delta."""
    z = stats.norm.ppf(1 - alpha / 2)
    r = np.abs(np.asarray(delta, dtype=float)) / np.asarray(se, dtype=float)
    return stats.norm.cdf(r - z) + stats.norm.cdf(-r - z)


def build_comparisons(df: pd.DataFrame, min_impressions: int = MIN_ARM_IMPRESSIONS) -> pd.DataFrame:
    """One row per non-reference arm, compared with its test's reference arm."""
    d = df[df["impressions"] >= min_impressions].copy()
    sort_cols = ["clickability_test_id", "created_ts"] + (["row"] if "row" in d.columns else [])
    d = d.sort_values(sort_cols, kind="mergesort")
    d["arm_order"] = d.groupby("clickability_test_id").cumcount()
    ref = d[d["arm_order"] == 0].set_index("clickability_test_id")
    oth = d[d["arm_order"] > 0]
    r = ref.loc[oth["clickability_test_id"]]
    out = pd.DataFrame(
        {
            "test_id": oth["clickability_test_id"].to_numpy(),
            "arm_order": oth["arm_order"].to_numpy(),
            "n1": oth["impressions"].to_numpy(),
            "c1": oth["clicks"].to_numpy(),
            "n0": r["impressions"].to_numpy(),
            "c0": r["clicks"].to_numpy(),
            "headline1": oth["headline"].to_numpy(),
            "headline0": r["headline"].to_numpy(),
            "same_headline": (oth["headline"].fillna("").to_numpy() == r["headline"].fillna("").to_numpy()),
            "same_image": (oth["eyecatcher_id"].fillna("").to_numpy() == r["eyecatcher_id"].fillna("").to_numpy()),
        }
    )
    out["p1"] = out["c1"] / out["n1"]
    out["p0"] = out["c0"] / out["n0"]
    out["diff"] = out["p1"] - out["p0"]
    with np.errstate(divide="ignore", invalid="ignore"):
        out["rel"] = np.where(out["p0"] > 0, out["diff"] / out["p0"], np.nan)
    p_pool = (out["c1"] + out["c0"]) / (out["n1"] + out["n0"])
    out["se"] = np.sqrt(p_pool * (1 - p_pool) * (1 / out["n1"] + 1 / out["n0"]))
    out = out[out["se"] > 0].reset_index(drop=True)
    out["z"], out["p"] = two_prop_ztest(out["c1"], out["n1"], out["c0"], out["n0"])
    return out


def test_level_table(df: pd.DataFrame, min_impressions: int = MIN_ARM_IMPRESSIONS) -> pd.DataFrame:
    """Per test: arms, mean arm size, pooled click rate, and the 80%-power MDE."""
    d = df[df["impressions"] >= min_impressions]
    g = d.groupby("clickability_test_id")
    t = pd.DataFrame({"n_arms": g.size(), "impressions": g["impressions"].sum(), "clicks": g["clicks"].sum()})
    t = t[t["n_arms"] >= 2]
    t["n_per_arm"] = t["impressions"] / t["n_arms"]
    t["rate"] = t["clicks"] / t["impressions"]
    t["mde_abs"] = mde(t["rate"], t["n_per_arm"], t["n_per_arm"])
    t["mde_rel"] = t["mde_abs"] / t["rate"]
    return t


def identical_arm_pairs(df: pd.DataFrame, fields, min_impressions: int = MIN_ARM_IMPRESSIONS) -> pd.DataFrame:
    """Pairs of arms in the same test that showed viewers identical content.

    These are real A/A comparisons. One pair per duplicated group: the first
    two arms by creation time.
    """
    d = df[df["impressions"] >= min_impressions].copy()
    key = d[fields].fillna("").astype(str).agg("\x1f".join, axis=1)
    d["_key"] = key
    d = d.sort_values(["clickability_test_id", "created_ts"], kind="mergesort")
    dup = d[d.duplicated(["clickability_test_id", "_key"], keep=False)]
    dup = dup.assign(_pos=dup.groupby(["clickability_test_id", "_key"]).cumcount())
    a = dup[dup["_pos"] == 0].set_index(["clickability_test_id", "_key"])
    b = dup[dup["_pos"] == 1].set_index(["clickability_test_id", "_key"]).loc[a.index]
    pairs = pd.DataFrame({
        "test_id": a.index.get_level_values(0),
        "n0": a["impressions"].to_numpy(), "c0": a["clicks"].to_numpy(),
        "n1": b["impressions"].to_numpy(), "c1": b["clicks"].to_numpy(),
    })
    if len(pairs):
        pairs["z"], pairs["p"] = two_prop_ztest(pairs["c1"], pairs["n1"], pairs["c0"], pairs["n0"])
    return pairs


def winners(comp: pd.DataFrame) -> pd.DataFrame:
    """Per test, the non-reference arm with the highest observed click rate,
    kept only if it also beats the reference."""
    idx = comp.groupby("test_id")["p1"].idxmax()
    w = comp.loc[idx]
    return w[w["diff"] > 0]


def summarize_effects(comp: pd.DataFrame) -> dict:
    q = [0.05, 0.25, 0.5, 0.75, 0.95]
    absd = comp["diff"].abs()
    rel = comp["rel"].dropna()
    return {
        "n_comparisons": int(len(comp)),
        "n_tests": int(comp["test_id"].nunique()),
        "diff_quantiles_pp": {str(k): float(v * 100) for k, v in comp["diff"].quantile(q).items()},
        "abs_diff_median_pp": float(absd.median() * 100),
        "abs_diff_mean_pp": float(absd.mean() * 100),
        "rel_quantiles": {str(k): float(v) for k, v in rel.quantile(q).items()},
        "abs_rel_median": float(rel.abs().median()),
        "share_p_lt_05": float((comp["p"] < 0.05).mean()),
        "share_abs_rel_gt_10pct": float((rel.abs() > 0.10).mean()),
        "reference_rate_median": float(comp["p0"].median()),
        "n0_median": float(comp["n0"].median()),
        "n1_median": float(comp["n1"].median()),
    }
