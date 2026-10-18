"""Loading, validation and exclusion logic for the Upworthy archive and the Hillstrom data."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

UPWORTHY_FILES = {
    "exploratory": "upworthy-archive-exploratory-packages-03.12.2020.csv",
    "confirmatory": "upworthy-archive-confirmatory-packages-03.12.2020.csv",
}
HILLSTROM_FILE = "hillstrom.csv"

PLAN_NAME = "ANALYSIS_PLAN.md"
LOCK_NAME = "ANALYSIS_PLAN.lock"

# Published counts (Matias et al. 2021, Usage Notes).
PUBLISHED_COUNTS = {
    "exploratory": {"packages": 22_666, "tests": 4_873},
    "confirmatory": {"packages": 105_551, "tests": 22_743},
}

# Author correction (Sci Data 11:765, 2024): omit experiments from June 25, 2013
# through the end of January 10, 2014. created_at has an unknown timezone.
PROBLEM_START = pd.Timestamp("2013-06-25 00:00:00")
PROBLEM_END = pd.Timestamp("2014-01-11 00:00:00")  # exclusive

# Stimulus fields that viewers actually saw in a test.
SHOWN_FIELDS = ["headline", "eyecatcher_id", "excerpt"]


class ConfirmatoryLocked(RuntimeError):
    """Raised when the confirmatory release is requested before the plan is frozen."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_confirmatory_allowed(root: Path = PROJECT_ROOT) -> None:
    """Refuse unless ANALYSIS_PLAN.lock exists next to ANALYSIS_PLAN.md.

    If the lock file contains a 64-character hex digest, it must match the
    sha256 of ANALYSIS_PLAN.md, so the plan cannot change after locking.
    """
    root = Path(root)
    lock = root / LOCK_NAME
    plan = root / PLAN_NAME
    if not lock.is_file():
        raise ConfirmatoryLocked(
            f"Refusing to touch the confirmatory release: {lock} does not exist. "
            f"Freeze {PLAN_NAME} first (commit it, then create {LOCK_NAME})."
        )
    if not plan.is_file():
        raise ConfirmatoryLocked(f"Refusing: {plan} is missing.")
    m = re.search(r"\b[0-9a-fA-F]{64}\b", lock.read_text())
    if m and m.group(0).lower() != sha256_file(plan):
        raise ConfirmatoryLocked(
            f"Refusing: the digest in {LOCK_NAME} does not match the current {PLAN_NAME}. "
            "The plan changed after it was locked."
        )


def upworthy_path(release: str, raw_dir: Path = RAW_DIR) -> Path:
    if release not in UPWORTHY_FILES:
        raise ValueError(f"unknown release {release!r}")
    return Path(raw_dir) / UPWORTHY_FILES[release]


def load_upworthy(release: str, root: Path = PROJECT_ROOT, path: Path | None = None) -> pd.DataFrame:
    """Read one Upworthy release, one row per package (arm)."""
    if release == "confirmatory":
        check_confirmatory_allowed(root)
    if path is None:
        path = upworthy_path(release, Path(root) / "data" / "raw")
    df = pd.read_csv(path, low_memory=False)
    first = df.columns[0]
    if first.startswith("Unnamed") or first == "":
        df = df.rename(columns={first: "row"})
    df["created_ts"] = pd.to_datetime(df["created_at"], format="mixed")
    df["impressions"] = df["impressions"].astype(np.int64)
    df["clicks"] = df["clicks"].astype(np.int64)
    return df


def flag_problem_tests(df: pd.DataFrame) -> pd.DataFrame:
    """Per test: start time and whether it falls in the correction's window.

    A test is flagged when its first package was created inside
    [2013-06-25, 2014-01-11). `any_in_window` and `all_in_window` are kept as
    a check that the choice of rule does not matter.
    """
    ts = df["created_ts"]
    inside = (ts >= PROBLEM_START) & (ts < PROBLEM_END)
    g = df.assign(_in=inside).groupby("clickability_test_id")
    out = pd.DataFrame(
        {
            "start": g["created_ts"].min(),
            "n_arms": g.size(),
            "any_in_window": g["_in"].any(),
            "all_in_window": g["_in"].all(),
        }
    )
    out["problem"] = (out["start"] >= PROBLEM_START) & (out["start"] < PROBLEM_END)
    return out


def window_sensitivity(tests: pd.DataFrame, shifts_hours=(-24, -12, 12, 24)) -> dict:
    """Flagged-test counts if the window edges move (timezone is unknown)."""
    res = {}
    for h in shifts_hours:
        d = pd.Timedelta(hours=h)
        flag = (tests["start"] >= PROBLEM_START + d) & (tests["start"] < PROBLEM_END + d)
        res[f"{h:+d}h"] = int(flag.sum())
    return res


def srm_pvalues(df: pd.DataFrame) -> pd.Series:
    """Chi-square test of equal allocation of impressions across a test's arms."""

    def one(x):
        x = np.asarray(x, dtype=float)
        if len(x) < 2 or x.sum() == 0:
            return np.nan
        return stats.chisquare(x).pvalue

    return df.groupby("clickability_test_id")["impressions"].apply(one)


def pipeline_check(df: pd.DataFrame, release: str) -> dict:
    tests = df["clickability_test_id"].nunique()
    out = {
        "packages": int(len(df)),
        "tests": int(tests),
        "impressions": int(df["impressions"].sum()),
        "clicks": int(df["clicks"].sum()),
        "clicks_exceed_impressions": int((df["clicks"] > df["impressions"]).sum()),
        "first_created": str(df["created_ts"].min()),
        "last_created": str(df["created_ts"].max()),
    }
    pub = PUBLISHED_COUNTS.get(release)
    if pub:
        out["published_packages"] = pub["packages"]
        out["published_tests"] = pub["tests"]
        out["matches_paper"] = bool(out["packages"] == pub["packages"] and out["tests"] == pub["tests"])
    return out


def exclusion_summary(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Apply the correction's exclusion and return (kept packages, summary)."""
    tests = flag_problem_tests(df)
    srm = srm_pvalues(df).reindex(tests.index)
    tests["srm_p"] = srm
    multi = tests["n_arms"] >= 2
    summary = {
        "tests_total": int(len(tests)),
        "tests_flagged": int(tests["problem"].sum()),
        "share_flagged": float(tests["problem"].mean()),
        "flagged_any_package_rule": int(tests["any_in_window"].sum()),
        "flagged_all_packages_rule": int(tests["all_in_window"].sum()),
        "window_shift_sensitivity": window_sensitivity(tests),
        "srm_share_p001_in_window": float((tests.loc[tests["problem"] & multi, "srm_p"] < 0.001).mean()),
        "srm_share_p001_outside": float((tests.loc[~tests["problem"] & multi, "srm_p"] < 0.001).mean()),
        "srm_median_p_in_window": float(tests.loc[tests["problem"] & multi, "srm_p"].median()),
        "srm_median_p_outside": float(tests.loc[~tests["problem"] & multi, "srm_p"].median()),
    }
    keep_ids = tests.index[~tests["problem"]]
    kept = df[df["clickability_test_id"].isin(keep_ids)].copy()
    summary["tests_kept"] = int(kept["clickability_test_id"].nunique())
    summary["packages_kept"] = int(len(kept))
    summary["packages_dropped"] = int(len(df) - len(kept))
    return kept, summary


def load_hillstrom(root: Path = PROJECT_ROOT, path: Path | None = None) -> pd.DataFrame:
    if path is None:
        path = Path(root) / "data" / "raw" / HILLSTROM_FILE
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _history_bracket_ok(row_seg: str, value: float) -> bool:
    nums = [float(x.replace(",", "")) for x in re.findall(r"\$([\d,]+(?:\.\d+)?)", row_seg)]
    if "+" in row_seg and len(nums) == 1:
        return value >= nums[0]
    if len(nums) == 2:
        return nums[0] <= value <= nums[1]
    return False


def hillstrom_check(df: pd.DataFrame) -> dict:
    by = df.groupby("segment")
    seg = by.agg(n=("visit", "size"), visit=("visit", "mean"), conversion=("conversion", "mean"),
                 spend=("spend", "mean"))
    hist_ok = np.mean([_history_bracket_ok(s, v) for s, v in zip(df["history_segment"], df["history"])])
    return {
        "rows": int(len(df)),
        "by_segment": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in seg.to_dict("index").items()},
        "overall_visit": float(df["visit"].mean()),
        "overall_conversion": float(df["conversion"].mean()),
        "spend_min": float(df["spend"].min()),
        "spend_max": float(df["spend"].max()),
        "share_spend_positive": float((df["spend"] > 0).mean()),
        "history_min": float(df["history"].min()),
        "history_max": float(df["history"].max()),
        "history_median": float(df["history"].median()),
        "share_history_in_its_segment_bracket": float(hist_ok),
        "recency_range": [int(df["recency"].min()), int(df["recency"].max())],
        "spend_positive_without_conversion": int(((df["spend"] > 0) & (df["conversion"] == 0)).sum()),
    }
