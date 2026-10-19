"""Figures for the reports."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def peeking_curve(aa: dict, path: Path, alpha=0.05, title_suffix=""):
    looks = sorted(int(k) for k in aa["naive"])
    naive = [aa["naive"][k] if k in aa["naive"] else aa["naive"][str(k)] for k in looks]
    ms = [aa["msprt"][k] if k in aa["msprt"] else aa["msprt"][str(k)] for k in looks]
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.plot(looks, np.array(naive) * 100, color=BLUE, lw=2, marker="o", ms=6, label="z-test at every look")
    ax.plot(looks, np.array(ms) * 100, color=ORANGE, lw=2, marker="o", ms=6, label="mSPRT (always valid)")
    ax.axhline(alpha * 100, color=MUTED, lw=1, ls="--")
    ax.text(looks[-1], alpha * 100 + 0.6, "nominal 5%", ha="right", color=MUTED, fontsize=9)
    ax.set_xscale("log")
    ax.set_xticks(looks, [str(k) for k in looks])
    ax.set_xlabel("Number of looks", color=INK)
    ax.set_ylabel("A/A tests declared significant (%)", color=INK)
    ax.set_title(f"A/A false-positive rate by number of looks{title_suffix}", color=INK, fontsize=11, loc="left")
    ax.text(looks[-1], naive[-1] * 100 - 2.5, "z-test", color=BLUE, ha="right", fontsize=9)
    ax.text(looks[-1], ms[-1] * 100 + 1.2, "mSPRT", color=ORANGE, ha="right", fontsize=9)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    _style(ax)
    _save(fig, path)


def effect_distribution(comp, path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    d = comp["diff"] * 100
    lo, hi = d.quantile([0.005, 0.995])
    axes[0].hist(d.clip(lo, hi), bins=80, color=BLUE, edgecolor="white", linewidth=0.3)
    axes[0].set_xlabel("Click-rate difference vs first arm (percentage points)", color=INK)
    axes[0].set_ylabel("Arm comparisons", color=INK)
    axes[0].set_title("Absolute differences", color=INK, fontsize=11, loc="left")
    r = comp["rel"].dropna() * 100
    lo, hi = r.quantile([0.005, 0.99])
    axes[1].hist(r.clip(lo, hi), bins=80, color=BLUE, edgecolor="white", linewidth=0.3)
    axes[1].set_xlabel("Relative difference vs first arm (%)", color=INK)
    axes[1].set_title("Relative differences", color=INK, fontsize=11, loc="left")
    for ax in axes:
        ax.axvline(0, color=MUTED, lw=1)
        _style(ax)
    fig.text(0.01, -0.04, "Observed differences include sampling noise; tails clipped at the 0.5th and 99.5th "
             "(relative: 99th) percentiles.", fontsize=8, color=MUTED)
    _save(fig, path)


def mde_plot(tests, typical_pp, path: Path):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    m = tests["mde_abs"] * 100
    ax.hist(m.clip(upper=m.quantile(0.99)), bins=60, color=BLUE, edgecolor="white", linewidth=0.3)
    ax.axvline(typical_pp, color=ORANGE, lw=2)
    ax.text(typical_pp * 1.05, ax.get_ylim()[1] * 0.9, f"typical true effect\n{typical_pp:.2f} pp",
            color=INK, fontsize=9)
    ax.set_xlabel("Minimum detectable effect at 80% power (percentage points)", color=INK)
    ax.set_ylabel("Tests", color=INK)
    ax.set_title("Minimum detectable effect per test", color=INK, fontsize=11, loc="left")
    fig.text(0.01, -0.03, "Two-sided alpha 0.05, each test's average arm size and pooled click rate; clipped at the "
             "99th percentile.", fontsize=8, color=MUTED)
    _style(ax)
    _save(fig, path)


def shrinkage_plot(comp, sig, examples, path: Path):
    fig, ax = plt.subplots(figsize=(6.4, 5))
    ax.scatter(comp["diff"] * 100, comp["post_grid"] * 100, s=6, color="#b7b6b0", alpha=0.5,
               linewidths=0, label="all arm comparisons")
    ax.scatter(sig["diff"] * 100, sig["post_grid"] * 100, s=12, color=BLUE, alpha=0.8, linewidths=0,
               label="significant winners (p < 0.05)")
    ex_max = max((abs(e["observed_pp"]) for e in examples), default=0)
    lim = max(abs(comp["diff"]).quantile(0.999) * 100, abs(sig["diff"]).quantile(0.995) * 100, ex_max) * 1.1
    clipped = int(((abs(comp["diff"]) * 100 > lim) | (abs(comp["post_grid"]) * 100 > lim)).sum())
    ax.plot([-lim, lim], [-lim, lim], color=MUTED, lw=1, ls="--")
    ax.text(lim * 0.95, lim * 0.82, "no shrinkage", color=MUTED, fontsize=9, ha="right")
    for e in examples:
        ax.scatter([e["observed_pp"]], [e["posterior_grid_pp"]], s=60, facecolor="none", edgecolor=ORANGE, lw=2)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel("Observed difference vs first arm (pp)", color=INK)
    ax.set_ylabel("Empirical-Bayes posterior mean (pp)", color=INK)
    ax.set_title("Observed vs empirical-Bayes differences", color=INK, fontsize=11, loc="left")
    if clipped:
        fig.text(0.5, 0.005, f"{clipped} comparison{'s' if clipped != 1 else ''} beyond the axes not shown.", ha="center", color=MUTED, fontsize=8)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    _style(ax)
    _save(fig, path)


def hillstrom_ci(est, path: Path):
    combos = [(t, o) for o in ("spend", "visit") for t in ("Mens E-Mail", "Womens E-Mail")]
    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    order = list(dict.fromkeys(est["estimator"]))
    for ax, (t, o) in zip(axes.flat, combos):
        e = est[(est["treatment"] == t) & (est["outcome"] == o)].set_index("estimator").loc[order]
        scale = 1 if o == "spend" else 100
        y = np.arange(len(order))[::-1]
        ax.hlines(y, e["ci_low"] * scale, e["ci_high"] * scale, color=BLUE, lw=2)
        ax.scatter(e["est"] * scale, y, color=BLUE, s=36, zorder=3)
        for yi, (_, r) in zip(y, e.iterrows()):
            ax.text(r["ci_high"] * scale, yi + 0.18, f"width {r['ci_width'] * scale:.3f}", fontsize=8,
                    color=MUTED, ha="right")
        ax.set_yticks(y, order, fontsize=9)
        unit = "dollars per customer" if o == "spend" else "percentage points"
        ax.set_xlabel(f"Effect on {o} ({unit})", color=INK, fontsize=9)
        ax.set_title(f"{t} vs no email: {o}", color=INK, fontsize=10, loc="left")
        _style(ax)
    fig.tight_layout()
    _save(fig, path)


def subgroup_forest(sub, outcome, path: Path):
    s = sub[sub["outcome"] == outcome]
    arms = ["Mens E-Mail", "Womens E-Mail"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 7.5), sharey=True)
    scale = 1 if outcome == "spend" else 100
    for ax, arm in zip(axes, arms):
        a = s[s["treatment"] == arm].reset_index(drop=True)
        y = np.arange(len(a))[::-1]
        survives = a["p_hetero_bh"] <= 0.05
        naive = (a["p_hetero"] < 0.05) & ~survives
        colors = np.where(survives, ORANGE, np.where(naive, AQUA, BLUE))
        ax.hlines(y, a["ci_low"] * scale, a["ci_high"] * scale, color=colors, lw=1.6)
        ax.scatter(a["cate"] * scale, y, color=colors, s=24, zorder=3)
        ax.axvline(0, color=MUTED, lw=1)
        labels = [f"{v}: {lv}".replace("$", r"\$") for v, lv in zip(a["variable"], a["level"])]
        ax.set_yticks(y, labels, fontsize=8)
        unit = r"\$" if outcome == "spend" else "pp"
        ax.set_xlabel(f"Effect on {outcome} ({unit}), 95% CI", color=INK, fontsize=9)
        ax.set_title(f"{arm} vs no email", color=INK, fontsize=10, loc="left")
        _style(ax)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=BLUE, lw=2, label="no evidence it differs from the rest"),
               Line2D([], [], color=AQUA, lw=2, label="differs from rest at p < 0.05, not after BH"),
               Line2D([], [], color=ORANGE, lw=2, label="differs from rest after BH")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle(f"Subgroup effects on {outcome}", x=0.01, ha="left", color=INK, fontsize=11)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    _save(fig, path)
