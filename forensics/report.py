"""Markdown reports built from the results dictionaries. Every number is filled in from code output."""

from __future__ import annotations

import pandas as pd


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


def num(x, d=2):
    return "n/a" if x is None else f"{x:,.{d}f}"


def _k(d, k):
    return d[k] if k in d else d[str(k)]


def _table(rows, header):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _md_escape(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def upworthy_sections(up: dict, fig_prefix: str = "") -> list[str]:
    pc, ex, aa = up["pipeline_check"], up["exclusion"], up["identical_arm_pairs"]
    ef, pw, pr, pk, wn = up["effects"], up["power"], up["prior"], up["peeking"], up["winners"]
    s = []
    s.append("## Upworthy pipeline checks\n")
    match = "match" if pc.get("matches_paper") else "DO NOT match"
    s.append(
        f"The {up['release']} file has {pc['packages']:,} packages in {pc['tests']:,} tests. The archive paper "
        f"reports {pc.get('published_packages', 'n/a'):,} packages within {pc.get('published_tests', 'n/a'):,} tests "
        f"for this release, so the counts {match}. Clicks never exceed impressions "
        f"({pc['clicks_exceed_impressions']} violations). Packages were created between {pc['first_created']} and "
        f"{pc['last_created']} (timezone unknown, per the paper). Total impressions: {pc['impressions']:,}; clicks: "
        f"{pc['clicks']:,}. The paper does not give per-release impression or click totals, so those are not checked.\n"
    )
    s.append("### The randomization correction\n")
    s.append(
        f"Tests whose first package was created from 25 June 2013 through the end of 10 January 2014 are dropped, as "
        f"the authors' correction recommends. That removes **{ex['tests_flagged']:,} of {ex['tests_total']:,} tests "
        f"({pct(ex['share_flagged'])})** and {ex['packages_dropped']:,} packages, leaving {ex['tests_kept']:,} tests. "
        f"The correction reports 7,004 affected tests, or 22% of the full archive"
        + (", so the share here is in line. " if abs(ex["share_flagged"] - 7004 / 32487) <= 0.02 else
           ", so the share here is noticeably different. ")
        + f""
        f"Flagging a test when any of its packages falls in the window gives {ex['flagged_any_package_rule']:,}; "
        f"requiring all of them gives {ex['flagged_all_packages_rule']:,}. Shifting both window edges to allow for "
        f"the unknown timezone gives: "
        + ", ".join(f"{k}: {v:,}" for k, v in ex["window_shift_sensitivity"].items()) + ".\n"
    )
    s.append(
        f"A sample-ratio check backs the correction up. Within each test, a chi-square test of equal impressions "
        f"across arms gives p < 0.001 in {pct(ex['srm_share_p001_in_window'])} of multi-arm tests inside the window "
        f"and in {pct(ex['srm_share_p001_outside'])} outside it (median p {ex['srm_median_p_in_window']:.2g} vs "
        f"{ex['srm_median_p_outside']:.2f}).\n"
    )
    k = aa["kept"]
    s.append(
        f"**A real A/A check.** Some tests contain two arms that showed viewers exactly the same headline, image ID "
        f"and excerpt. In the kept tests there are {k['pairs']} such pairs. If those arms were fairly randomized and "
        f"clicks were independent, about 5% of them would differ at p < 0.05. {pct(k['share_p_lt_05'])} do "
        f"(binomial test against 5%: p = {k['binom_p_vs_5pct']:.2g}), and the mean squared z-statistic is "
        f"{num(k['mean_z_squared'])} where 1 is expected.\n"
    )
    if k["binom_p_vs_5pct"] < 0.01 and k["share_p_lt_05"] > 0.05:
        s.append(
            "So click counts vary more between identical arms than binomial sampling allows. The data cannot say "
            "why (possible reasons: something about the arms not recorded in the archive, or traffic that was not "
            "served evenly over time). It means the naive z-tests below, and the simulations that assume binomial "
            "noise, are if anything too optimistic. Section 3 includes a sensitivity check that inflates standard "
            "errors by this factor.\n"
        )
    else:
        s.append("That is consistent with binomial noise.\n")
    s.append("## 1. Effect sizes and power\n")
    s.append(
        "**Definition.** In each test the *reference* arm is the package created first (earliest `created_at`, "
        "among arms with at least 100 impressions). Every other arm is compared with it: difference in click rate "
        "(arm minus reference) and relative difference (divided by the reference rate). Upworthy had no control "
        "arm, and the first-written package is the nearest thing to an original headline. Its identity is fixed "
        "before any traffic arrives, so it cannot be chosen by the outcome. Best-vs-rest would build the winner's "
        "curse into the definition.\n"
    )
    q = ef["diff_quantiles_pp"]
    rq = ef["rel_quantiles"]
    s.append(
        f"There are {ef['n_comparisons']:,} comparisons in {ef['n_tests']:,} tests ({ef['arms_dropped_small']} arms "
        f"with under 100 impressions dropped). The median reference click rate is {pct(ef['reference_rate_median'], 2)}"
        f" and the median arm has {ef['n1_median']:,.0f} impressions.\n"
    )
    s.append(_table([
        ["Absolute difference (pp)"] + [num(q[k]) for k in ("0.05", "0.25", "0.5", "0.75", "0.95")],
        ["Relative difference"] + [pct(rq[k]) for k in ("0.05", "0.25", "0.5", "0.75", "0.95")],
    ], ["Observed, arm minus reference", "5th", "25th", "median", "75th", "95th"]) + "\n")
    s.append(
        f"The median observed absolute difference is {num(ef['abs_diff_median_pp'])} pp, or "
        f"{pct(ef['abs_rel_median'])} in relative terms. {pct(ef['share_p_lt_05'])} of comparisons are significant "
        f"at p < 0.05. The median difference is "
        + ("negative: later arms tend to do slightly worse than the first one.\n" if q["0.5"] < 0 else
           "non-negative: later arms do not do worse than the first one.\n")
    )
    s.append(
        f"Observed differences include sampling noise, so they overstate how big true effects are. The empirical-"
        f"Bayes fits in section 3 deconvolve that noise. The normal prior has mean {num(pr['normal_mu_pp'], 3)} pp "
        f"and SD {num(pr['normal_tau_pp'], 3)} pp. The nonparametric (grid) prior puts a median absolute true effect "
        f"of **{num(pw['typical_true_abs_effect_pp_grid'], 3)} pp** ({pct(pr['grid_share_mass_within_0_1pp'])} of "
        f"its mass is within 0.1 pp of zero; 90th percentile {num(pr['grid_abs_quantiles_pp']['0.9'], 3)} pp).\n"
    )
    s.append(
        f"**Power.** For each test, using its average arm size and pooled click rate, the minimum detectable "
        f"difference at 80% power and two-sided alpha 0.05 has median **{num(pw['mde_abs_median_pp'], 3)} pp** "
        f"(interquartile range {num(pw['mde_abs_quartiles_pp'][0], 3)} to {num(pw['mde_abs_quartiles_pp'][1], 3)}), "
        f"or **{pct(pw['mde_rel_median'], 0)} relative**. Only {pct(pw['share_tests_mde_le_typical_grid'], 2)} of "
        f"{pw['n_tests']:,} tests could detect the typical true effect from the grid prior, and "
        f"{pct(pw['share_tests_mde_le_typical_observed'], 1)} could detect the (inflated) median observed difference "
        f"of {num(pw['typical_observed_abs_effect_pp'], 3)} pp. Average power against the typical true effect is "
        f"{pct(pw['mean_power_at_typical_grid'])}.\n"
    )
    s.append(f"![Effect sizes]({fig_prefix}effect_distribution.png)\n")
    s.append(f"![MDE]({fig_prefix}power_mde.png)\n")

    s.append("## 2. Peeking\n")
    aa_ = pk["aa"]
    looks = sorted(int(x) for x in aa_["naive"])
    s.append(
        f"Each of {pk['n_sims']:,} simulated A/A tests draws a real kept test (with replacement), uses its pooled "
        f"click rate for both arms and its average arm size, and delivers impressions in 100 equal batches. An "
        f"analyst who checks K times runs a pooled two-proportion z-test after every 100/K batches and stops at the "
        f"first p < 0.05. The mSPRT (normal mixture, mixing SD {num(pk['msprt_tau_pp'], 2)} pp, "
        f"threshold 1/alpha = 20) "
        f"looks at the same points. Monte Carlo SE near 5% is {num(pk['mc_se_at_5pct'] * 100, 2)} pp.\n"
    )
    s.append(_table([[str(L), pct(_k(aa_["naive"], L)), pct(_k(aa_["msprt"], L), 2)] for L in looks],
                    ["Looks", "z-test false-positive rate", "mSPRT false-positive rate"]) + "\n")
    s.append(f"![Peeking]({fig_prefix}peeking_false_positive.png)\n")
    pwr = pk["power"]
    s.append(
        "The same simulation with a true relative lift in the second arm shows how much power each approach keeps:\n"
    )
    s.append(_table([[pct(float(lift), 0), pct(v["fixed_single_look"]), pct(v["msprt_10_looks"]),
                      pct(v["msprt_100_looks"])] for lift, v in pwr.items()],
                    ["True lift", "z-test, one look at the end", "mSPRT, 10 looks", "mSPRT, 100 looks"]) + "\n")
    top = pwr[max(pwr, key=float)]
    if top["msprt_100_looks"] < top["fixed_single_look"]:
        s.append(
            "At these sample sizes the always-valid test gives up a lot of power compared with a single look at the "
            "planned end; it buys honest error rates with power the tests did not have to spare.\n"
        )

    s.append("## 3. Winner's curse\n")
    s.append(
        f"Per test, the *winner* is the non-reference arm with the highest observed click rate, kept when it beats "
        f"the reference. {wn['tests_with_winner_beating_reference']:,} tests have one, and "
        f"**{wn['significant_winners']:,} ({pct(wn['share_of_tests_significant'])} of tests)** beat the reference at "
        f"p < 0.05. Their median observed lift is {num(wn['median_observed_lift_pp'], 3)} pp "
        f"({pct(wn['median_observed_rel_lift'], 0)} relative).\n"
    )
    s.append(
        "Two priors are fit to all comparisons (not just winners), each observed difference treated as normal "
        "around its true value with its own standard error: a normal prior by maximum marginal likelihood, and a "
        "nonparametric prior on a 301-point grid fit by EM (an NPMLE). The posterior mean is the best guess for "
        "what a re-run would show. Shrinkage is 1 minus posterior mean over observed lift.\n"
    )
    rows = [["Median shrinkage", pct(wn["median_shrinkage_grid"]), pct(wn["median_shrinkage_normal"])],
            ["Median posterior lift (pp)", num(wn["median_posterior_lift_pp_grid"], 3),
             num(wn["median_posterior_lift_pp_normal"], 3)]]
    s.append(_table(rows, ["Among significant winners", "Grid prior", "Normal prior"]) + "\n")
    s.append(
        f"Under the grid prior, {pct(wn['share_prob_positive_ge_95_grid'])} of significant winners have at least a "
        f"95% posterior probability of truly beating the reference.\n"
    )
    if "overdispersion_phi" in wn:
        s.append(
            f"Sensitivity: inflating every standard error by the square root of {num(wn['overdispersion_phi'])} (the "
            f"identical-arm variance ratio) raises median shrinkage to {pct(wn['median_shrinkage_grid_inflated_se'])}, "
            f"and only {pct(wn['share_significant_inflated_se'])} of the significant winners would still clear "
            f"p < 0.05.\n"
        )
    s.append(f"![Shrinkage]({fig_prefix}shrinkage.png)\n")
    labels = ["The winner that shrinks most (in percentage points)", "A typical significant winner (median shrinkage)"]
    for lab, e in zip(labels, wn["examples"]):
        s.append(f"**{lab}.** Test `{e['test_id']}`.\n")
        s.append(
            f"- Reference: \"{_md_escape(e['reference_headline'])}\" ({e['c0']:,} clicks / {e['n0']:,})\n"
            f"- Winner: \"{_md_escape(e['winner_headline'])}\" ({e['c1']:,} clicks / {e['n1']:,})"
            + (" (same headline, different image ID)" if e["same_headline"] and not e["same_image"] else
               " (same headline and image ID)" if e["same_headline"] else "")
            + "\n"
            f"- Observed lift {num(e['observed_pp'], 2)} pp ({pct(e['observed_rel'], 0)} relative), p = "
            f"{e['p']:.2g}. Posterior mean {num(e['posterior_grid_pp'], 2)} pp (grid) or "
            f"{num(e['posterior_normal_pp'], 2)} pp (normal); shrinkage {pct(e['shrinkage_grid'])} under the grid "
            f"prior.\n"
        )
    return s


def hillstrom_sections(hs: dict, fig_prefix: str = "") -> list[str]:
    c = hs["check"]
    s = ["## Hillstrom pipeline checks\n"]
    seg = c["by_segment"]
    s.append(_table([[k, f"{int(v['n']):,}", pct(v["visit"], 2), pct(v["conversion"], 2), f"${v['spend']:.3f}"]
                     for k, v in seg.items()], ["Segment", "Customers", "Visit", "Conversion", "Mean spend"]) + "\n")
    s.append(
        f"{c['rows']:,} rows, split into three groups of about 21.3k each, as the challenge describes (one third "
        f"each). The scikit-uplift documentation lists an average visit rate of .15 and conversion rate of .009 and "
        f"spend from 0 to 499; here they are {c['overall_visit']:.4f}, {c['overall_conversion']:.5f} and "
        f"{c['spend_min']:.0f} to {c['spend_max']:.0f}.\n"
    )
    s.append(
        f"**Units of `history`.** Hillstrom's description: actual dollar value spent in the past year. Values run "
        f"from ${c['history_min']:.2f} to ${c['history_max']:,.2f} (median ${c['history_median']:.2f}), and "
        f"{pct(c['share_history_in_its_segment_bracket'])} fall inside their own `history_segment` dollar bracket, "
        f"so it is dollars, measured before the campaign. Spend is positive for only "
        f"{pct(c['share_spend_positive'], 2)} of customers (exactly the converters; "
        f"{c['spend_positive_without_conversion']} customers have spend without a conversion).\n"
    )
    bal = hs["balance"]
    smds = [abs(v) for r in bal for k, v in r.items() if k.startswith("smd_")]
    ps = [r["omnibus_p"] for r in bal]
    s.append(
        f"**Balance.** Across {len(bal)} pre-treatment covariates (recency, history, mens, womens, newbie, and "
        f"indicators for each zip_code and channel level), the largest standardized mean difference between an email "
        f"arm and the control is {max(smds):.3f} and the smallest omnibus p-value across the three arms is "
        f"{min(ps):.2f}."
        + (" Randomization looks fine.\n" if max(smds) < 0.05 and min(ps) > 0.01 else
           " Some imbalance is present; treat the adjusted estimates with care.\n")
    )
    s.append("## 4. Variance reduction on Hillstrom\n")
    s.append(
        "Estimators, each for one email vs no email: difference in means (Welch SE); CUPED with pre-period `history`, "
        "theta estimated on both arms pooled; CUPED with all pre-period covariates; Lin's regression adjustment "
        "(treatment, centred covariates and their interactions, HC2 robust SE) with `history` only and with all "
        "pre-period covariates. \"All pre-period\" means history, recency, mens, womens, newbie and dummies for "
        "zip_code, channel and history_segment. Nothing measured after the email is used.\n"
    )
    est = pd.DataFrame(hs["estimates"])
    rows = []
    for _, r in est.iterrows():
        scale, unit = (1, "$") if r["outcome"] == "spend" else (100, "pp")
        rows.append([r["treatment"], r["outcome"], r["estimator"], f"{r['est'] * scale:.3f} {unit}",
                     f"[{r['ci_low'] * scale:.3f}, {r['ci_high'] * scale:.3f}]", f"{r['ci_width'] * scale:.4f}",
                     pct(r["variance_reduction"], 2), f"{r['equivalent_sample_multiplier']:.4f}"])
    s.append(_table(rows, ["Email", "Outcome", "Estimator", "Effect", "95% CI", "CI width", "Variance reduction",
                           "Equivalent sample multiplier"]) + "\n")
    r2 = est.groupby("outcome")[["r2_history_control", "r2_all_control"]].first()
    s.append(
        f"The gains are small, and the reason is visible in the control group: `history` explains "
        f"{pct(r2.loc['spend', 'r2_history_control'], 3)} of the variance in spend and "
        f"{pct(r2.loc['visit', 'r2_history_control'], 2)} of the variance in visits; all pre-period covariates "
        f"together explain {pct(r2.loc['spend', 'r2_all_control'], 2)} and {pct(r2.loc['visit', 'r2_all_control'], 2)}."
        f" CUPED's variance reduction is roughly that R-squared, so here it is close to nothing. Spend is zero for "
        f"almost everyone and a few large orders dominate its variance, and a past-year dollar total does not predict "
        f"which customers place them. The \"equivalent sample multiplier\" is the factor by which the plain "
        f"difference in means would need more customers to match each estimator's precision. A multiplier slightly "
        f"below 1 means the robust SE of the fuller model came out marginally wider.\n"
    )
    s.append(f"![Hillstrom CIs]({fig_prefix}hillstrom_ci.png)\n")
    s.append("## 5. Subgroups on Hillstrom\n")
    sg = hs["subgroups"]
    s.append(
        f"Each email is compared with no email inside {sg['n_levels_per_arm']} subgroup levels: four recency bands "
        f"(1-3, 4-6, 7-9, 10-12 months), seven history segments, three channels, three zip_code types, and both "
        f"levels of newbie, mens and womens (the last two are past-year purchase flags, not the treatment). Two "
        f"questions get separate families, per outcome:\n\n"
        f"- *Does the email work in this subgroup?* (CATE differs from zero; "
        f"2 emails x {sg['n_levels_per_arm']} levels)\n"
        f"- *Does it work differently here than in everyone else?* (subgroup CATE minus the CATE in the complement; "
        f"binary variables counted once)\n"
    )
    rows = []
    for outcome in ("spend", "visit"):
        for fam, label in (("effect_nonzero", "effect differs from 0"), ("differs_from_rest", "differs from the rest")):
            f = sg["families"][outcome][fam]
            rows.append([outcome, label, f["tests"], f["naive"], f["holm"], f["bh"]])
    f = sg["families"]["all_heterogeneity_both_outcomes"]
    rows.append(["both", "differs from the rest (pooled family)", f["tests"], f["naive"], f["holm"], f["bh"]])
    s.append(_table(rows, ["Outcome", "Question", "Tests", "p < 0.05", "Holm", "Benjamini-Hochberg"]) + "\n")
    s.append("The naive \"who responds differently\" findings, with their corrected p-values:\n")
    rows = []
    for r in sg["naive_heterogeneity_findings"]:
        scale = 1 if r["outcome"] == "spend" else 100
        unit = "$" if r["outcome"] == "spend" else "pp"
        rows.append([r["treatment"], r["outcome"], f"{r['variable']} = {r['level']}",
                     f"{r['diff_vs_rest'] * scale:+.3f} {unit}", f"{r['p_hetero']:.2g}", f"{r['p_hetero_holm']:.2g}",
                     f"{r['p_hetero_bh']:.2g}"])
    s.append(_table(rows, ["Email", "Outcome", "Subgroup", "CATE minus rest", "p", "Holm p", "BH p"]) + "\n")
    surv = [r for r in sg["naive_heterogeneity_findings"] if r["p_hetero_bh"] <= 0.05]
    if surv:
        s.append(
            "Survivors after Benjamini-Hochberg: "
            + "; ".join(f"{r['treatment']} on {r['outcome']} where {r['variable']} = {r['level']}" for r in surv)
            + ". Everything else that looked like a segment story at p < 0.05 does not survive.\n"
        )
    else:
        s.append("No heterogeneity finding survives Benjamini-Hochberg.\n")
    s.append(f"![Subgroups, spend]({fig_prefix}subgroup_forest_spend.png)\n")
    s.append(f"![Subgroups, visit]({fig_prefix}subgroup_forest_visit.png)\n")
    return s


# Metrics compared between releases, with the criteria fixed in ANALYSIS_PLAN.md.
def comparison_rows(expl: dict, conf: dict) -> list[list[str]]:
    def g(r, path):
        cur = r
        for p in path:
            if p in cur:
                cur = cur[p]
            elif str(p) in cur:
                cur = cur[str(p)]
            else:
                return None
        return cur

    specs = [
        ("Share of tests in the correction window", ("exclusion", "share_flagged"), pct,
         lambda e, c: abs(c - 7004 / 32487) <= 0.02, "within 2 pp of 21.6%"),
        ("SRM p<0.001, inside window", ("exclusion", "srm_share_p001_in_window"), pct,
         lambda e, c: c > 0.25, "> 25%"),
        ("SRM p<0.001, outside window", ("exclusion", "srm_share_p001_outside"), pct,
         lambda e, c: c < 0.02, "< 2%"),
        ("Identical-arm pairs with p<0.05", ("identical_arm_pairs", "kept", "share_p_lt_05"), pct,
         lambda e, c: c > 0.05, "> 5%"),
        ("Identical-arm pairs, binomial test vs 5%", ("identical_arm_pairs", "kept", "binom_p_vs_5pct"),
         lambda x: f"{x:.2g}", lambda e, c: c < 0.01, "p < 0.01"),
        ("Median |difference| (pp)", ("effects", "abs_diff_median_pp"), lambda x: num(x, 3), None, "descriptive"),
        ("Median |relative difference|", ("effects", "abs_rel_median"), pct, None, "descriptive"),
        ("Normal prior SD (pp)", ("prior", "normal_tau_pp"), lambda x: num(x, 3), None, "descriptive"),
        ("Typical true |effect|, grid (pp)", ("power", "typical_true_abs_effect_pp_grid"), lambda x: num(x, 3), None,
         "descriptive"),
        ("Median relative MDE", ("power", "mde_rel_median"), pct, None, "descriptive"),
        ("Tests powered for the typical effect", ("power", "share_tests_mde_le_typical_grid"), lambda x: pct(x, 2),
         lambda e, c: c < 0.05, "< 5%"),
        ("Mean power at the typical effect", ("power", "mean_power_at_typical_grid"), pct,
         lambda e, c: c < 0.2, "< 20%"),
        ("A/A false positives, 1 look", ("peeking", "aa", "naive", 1), pct,
         lambda e, c: abs(c - 0.05) <= 0.01, "within 1 pp of 5%"),
        ("A/A false positives, 10 looks", ("peeking", "aa", "naive", 10), pct,
         lambda e, c: c >= 0.10, ">= 10%"),
        ("A/A false positives, 100 looks", ("peeking", "aa", "naive", 100), pct,
         lambda e, c: c >= 0.20, ">= 20%"),
        ("mSPRT false positives, 100 looks", ("peeking", "aa", "msprt", 100), lambda x: pct(x, 2),
         lambda e, c: c <= 0.055, "<= 5.5%"),
        ("Significant winners (share of tests)", ("winners", "share_of_tests_significant"), pct, None, "descriptive"),
        ("Median shrinkage, grid prior", ("winners", "median_shrinkage_grid"), pct,
         lambda e, c: abs(c - e) <= 0.10, "within 10 pp of exploratory"),
        ("Median shrinkage, normal prior", ("winners", "median_shrinkage_normal"), pct,
         lambda e, c: abs(c - e) <= 0.10, "within 10 pp of exploratory"),
        ("Winners with P(true lift > 0) >= 95%", ("winners", "share_prob_positive_ge_95_grid"), pct, None,
         "descriptive"),
        ("Median shrinkage, grid prior, inflated SEs", ("winners", "median_shrinkage_grid_inflated_se"), pct, None,
         "descriptive"),
    ]
    rows = []
    for label, path, fmt, crit, crit_text in specs:
        e, c = g(expl, path), g(conf, path)
        met = "" if crit is None or c is None else ("yes" if crit(e, c) else "no")
        rows.append([label, "n/a" if e is None else fmt(e), "n/a" if c is None else fmt(c), crit_text, met])
    return rows


def exploratory_markdown(up: dict, hs: dict) -> str:
    head = [
        "# Exploratory results\n",
        "Upworthy exploratory release (after the randomization exclusion) and the Hillstrom email test. Every "
        "number here is written by `uv run forensics run --release exploratory`; the raw values are in "
        "`reports/results_exploratory.json`. The analysis choices for the confirmatory run are frozen in "
        "`ANALYSIS_PLAN.md`.\n",
    ]
    body = upworthy_sections(up, "figures/") + hillstrom_sections(hs, "figures/")
    tail = [
        "## Caveats\n",
        "- Upworthy arms were never compared with a control; \"effect\" here always means relative to the "
        "first-created package.\n"
        "- Comparisons within a test share the reference arm, so they are not independent. The prior fits ignore "
        "that dependence.\n"
        "- Identical-content arms disagree more often than chance allows (see the A/A check), so the binomial "
        "standard errors used throughout are probably too small.\n"
        "- The peeking simulation assumes binomial noise and a constant click rate within each test. Neither "
        "drift over time nor the extra variance seen between identical arms is modelled.\n"
        "- Hillstrom is a single experiment, so its numbers are not part of the confirmatory comparison.\n",
    ]
    return "\n".join(head + body + tail)


def confirmatory_markdown(conf: dict, expl: dict) -> str:
    s = [
        "# Confirmatory results\n",
        "This is the single pre-registered run on the Upworthy confirmatory release, using the definitions, "
        "exclusions, seeds and criteria in `ANALYSIS_PLAN.md`. Every number is written by "
        "`uv run forensics run --release confirmatory`.\n",
        "## Exploratory vs confirmatory\n",
        _table(comparison_rows(expl, conf), ["Metric", "Exploratory", "Confirmatory", "Criterion", "Met"]) + "\n",
    ]
    s += upworthy_sections(conf, "figures/confirmatory_")
    return "\n".join(s)
