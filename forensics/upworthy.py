"""Analyses 1-3 on one Upworthy release."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from . import config
from .data import PROJECT_ROOT, SHOWN_FIELDS, exclusion_summary, load_upworthy, pipeline_check
from .effects import (build_comparisons, identical_arm_pairs, power_at, summarize_effects,
                      test_level_table, winners)
from .peeking import mc_se, rejection_rates, sample_paths
from .shrinkage import fit_grid_prior, fit_normal_prior, shrinkage_fraction


def _median_abs_normal(mu, tau, n=200_000, seed=0):
    rng = np.random.default_rng(seed)
    return float(np.median(np.abs(rng.normal(mu, tau, n))))


def run_upworthy(release: str, root: Path = PROJECT_ROOT, path: Path | None = None,
                 n_sims: int = config.N_SIMS, tau: float | None = None):
    """Return (results dict, frames dict for figures)."""
    df = load_upworthy(release, root=root, path=path)
    res = {"release": release, "pipeline_check": pipeline_check(df, release)}
    kept, excl = exclusion_summary(df)
    res["exclusion"] = excl

    # Real A/A pairs: arms that showed identical content, kept vs flagged tests.
    flagged = df[~df["clickability_test_id"].isin(kept["clickability_test_id"].unique())]
    aa = {}
    for name, part in (("kept", kept), ("flagged", flagged)):
        pairs = identical_arm_pairs(part, SHOWN_FIELDS, config.MIN_ARM_IMPRESSIONS)
        aa[name] = {"pairs": int(len(pairs)),
                    "share_p_lt_05": float((pairs["p"] < 0.05).mean()) if len(pairs) else None,
                    "mean_z_squared": float((pairs["z"] ** 2).mean()) if len(pairs) else None,
                    "binom_p_vs_5pct": float(stats.binomtest(int((pairs["p"] < 0.05).sum()), len(pairs), 0.05).pvalue)
                    if len(pairs) else None}
    res["identical_arm_pairs"] = aa

    # 1. Effect sizes and power
    comp = build_comparisons(kept, config.MIN_ARM_IMPRESSIONS)
    tests = test_level_table(kept, config.MIN_ARM_IMPRESSIONS)
    res["effects"] = summarize_effects(comp)
    res["effects"]["arms_dropped_small"] = int((kept["impressions"] < config.MIN_ARM_IMPRESSIONS).sum())

    normal = fit_normal_prior(comp["diff"], comp["se"])
    grid = fit_grid_prior(comp["diff"], comp["se"])
    typical_grid = grid.quantile_abs(0.5)
    typical_normal = _median_abs_normal(normal.mu, normal.tau)
    typical_obs = float(comp["diff"].abs().median())
    se_test = np.sqrt(2 * tests["rate"] * (1 - tests["rate"]) / tests["n_per_arm"])
    res["power"] = {
        "n_tests": int(len(tests)),
        "mde_abs_median_pp": float(tests["mde_abs"].median() * 100),
        "mde_abs_quartiles_pp": [float(tests["mde_abs"].quantile(q) * 100) for q in (0.25, 0.75)],
        "mde_rel_median": float(tests["mde_rel"].median()),
        "mde_rel_quartiles": [float(tests["mde_rel"].quantile(q)) for q in (0.25, 0.75)],
        "n_per_arm_median": float(tests["n_per_arm"].median()),
        "rate_median": float(tests["rate"].median()),
        "typical_true_abs_effect_pp_grid": typical_grid * 100,
        "typical_true_abs_effect_pp_normal": typical_normal * 100,
        "typical_observed_abs_effect_pp": typical_obs * 100,
        "share_tests_mde_le_typical_grid": float((tests["mde_abs"] <= typical_grid).mean()),
        "share_tests_mde_le_typical_observed": float((tests["mde_abs"] <= typical_obs).mean()),
        "mean_power_at_typical_grid": float(power_at(typical_grid, se_test).mean()),
        "median_power_at_typical_grid": float(np.median(power_at(typical_grid, se_test))),
    }
    res["prior"] = {
        "normal_mu_pp": normal.mu * 100, "normal_tau_pp": normal.tau * 100,
        "grid_mean_pp": grid.mean() * 100, "grid_sd_pp": grid.sd() * 100,
        "grid_abs_quantiles_pp": {str(q): grid.quantile_abs(q) * 100 for q in (0.5, 0.9, 0.99)},
        "grid_share_mass_within_0_1pp": float(grid.weights[np.abs(grid.grid) <= 0.001].sum()),
    }

    # 2. Peeking
    tau = tau if tau is not None else (config.MSPRT_TAU if config.MSPRT_TAU is not None else normal.tau)
    rng = np.random.default_rng([config.SEED, 1])
    edges, c0, c1 = sample_paths(tests["rate"].to_numpy(), tests["n_per_arm"].to_numpy(), n_sims, rng,
                                 config.MAX_LOOKS)
    aa_rates = rejection_rates(edges, c0, c1, config.LOOKS, config.ALPHA, tau)
    res["peeking"] = {"n_sims": n_sims, "msprt_tau_pp": tau * 100, "aa": aa_rates,
                      "mc_se_at_5pct": mc_se(0.05, n_sims)}
    power_rows = {}
    for i, lift in enumerate(config.POWER_LIFTS):
        rng = np.random.default_rng([config.SEED, 2, i])
        e, a0, a1 = sample_paths(tests["rate"].to_numpy(), tests["n_per_arm"].to_numpy(), n_sims, rng,
                                 config.MAX_LOOKS, lift=lift)
        r = rejection_rates(e, a0, a1, (1, 10, 100), config.ALPHA, tau)
        power_rows[str(lift)] = {"fixed_single_look": r["naive"][1], "msprt_10_looks": r["msprt"][10],
                                 "msprt_100_looks": r["msprt"][100]}
    res["peeking"]["power"] = power_rows

    # 3. Winner's curse
    comp["post_grid"] = grid.posterior_mean(comp["diff"], comp["se"])
    comp["post_normal"] = normal.posterior_mean(comp["diff"], comp["se"])
    w = winners(comp)
    sig = w[w["p"] < config.ALPHA].copy()
    sig["shrink_grid"] = shrinkage_fraction(sig["diff"], sig["post_grid"])
    sig["shrink_normal"] = shrinkage_fraction(sig["diff"], sig["post_normal"])
    sig["prob_pos_grid"] = grid.prob_positive(sig["diff"], sig["se"])
    res["winners"] = {
        "tests_with_winner_beating_reference": int(len(w)),
        "significant_winners": int(len(sig)),
        "share_of_tests_significant": float(len(sig) / comp["test_id"].nunique()),
        "median_observed_lift_pp": float(sig["diff"].median() * 100),
        "median_observed_rel_lift": float(sig["rel"].median()),
        "median_shrinkage_grid": float(sig["shrink_grid"].median()),
        "median_shrinkage_normal": float(sig["shrink_normal"].median()),
        "median_posterior_lift_pp_grid": float(sig["post_grid"].median() * 100),
        "median_posterior_lift_pp_normal": float(sig["post_normal"].median() * 100),
        "share_prob_positive_ge_95_grid": float((sig["prob_pos_grid"] >= 0.95).mean()),
    }

    # Sensitivity: identical-content arm pairs vary more than binomial sampling
    # allows. Inflate every SE by sqrt(phi), phi = mean z^2 over those pairs.
    phi = aa["kept"]["mean_z_squared"]
    if phi and phi > 1:
        s_inf = comp["se"] * np.sqrt(phi)
        grid_inf = fit_grid_prior(comp["diff"], s_inf)
        post_inf = grid_inf.posterior_mean(sig["diff"], sig["se"] * np.sqrt(phi))
        res["winners"]["overdispersion_phi"] = phi
        res["winners"]["median_shrinkage_grid_inflated_se"] = float(
            np.median(shrinkage_fraction(sig["diff"], post_inf)))
        res["winners"]["share_significant_inflated_se"] = float(
            (np.abs(sig["z"]) / np.sqrt(phi) > 1.959964).mean())

    sig["shrink_pp"] = (sig["diff"] - sig["post_grid"]) * 100
    typical = (sig["shrink_grid"] - sig["shrink_grid"].median()).abs().idxmin()
    examples = pd.concat([sig.nlargest(1, "shrink_pp"), sig.loc[[typical]]])
    res["winners"]["examples"] = [
        {"test_id": r.test_id, "reference_headline": r.headline0, "winner_headline": r.headline1,
         "same_headline": bool(r.same_headline), "same_image": bool(r.same_image),
         "n0": int(r.n0), "c0": int(r.c0), "n1": int(r.n1), "c1": int(r.c1),
         "observed_pp": r.diff * 100, "observed_rel": r.rel, "p": r.p,
         "posterior_grid_pp": r.post_grid * 100, "posterior_normal_pp": r.post_normal * 100,
         "shrinkage_grid": r.shrink_grid, "prob_positive_grid": r.prob_pos_grid}
        for r in examples.itertuples()
    ]
    frames = {"comp": comp, "tests": tests, "sig": sig, "grid": grid, "normal": normal}
    return res, frames
