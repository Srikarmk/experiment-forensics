import pandas as pd
import pytest

from forensics import data
from forensics.data import (PROBLEM_END, PROBLEM_START, exclusion_summary, flag_problem_tests, load_upworthy,
                            pipeline_check)


def _df(times):
    rows = []
    for i, ts in enumerate(times):
        for a in range(2):
            rows.append({"clickability_test_id": f"t{i}", "created_ts": pd.Timestamp(ts) + pd.Timedelta(seconds=a),
                         "impressions": 1000, "clicks": 10})
    return pd.DataFrame(rows)


def test_window_bounds():
    assert PROBLEM_START == pd.Timestamp("2013-06-25")
    assert PROBLEM_END == pd.Timestamp("2014-01-11")
    df = _df(["2013-06-24 23:59:58", "2013-06-25 00:00:00", "2013-10-01", "2014-01-10 23:59:50",
              "2014-01-11 00:00:00", "2015-01-01"])
    flags = flag_problem_tests(df)["problem"]
    assert flags.to_dict() == {"t0": False, "t1": True, "t2": True, "t3": True, "t4": False, "t5": False}


def test_flag_uses_first_package():
    # A test that starts just before the window and adds an arm inside it is kept.
    df = pd.DataFrame({"clickability_test_id": ["a", "a"],
                       "created_ts": [pd.Timestamp("2013-06-24 23:59:00"), pd.Timestamp("2013-06-25 00:01:00")],
                       "impressions": [100, 100], "clicks": [1, 1]})
    t = flag_problem_tests(df)
    assert not t.loc["a", "problem"]
    assert t.loc["a", "any_in_window"]


def test_exclusion_drops_whole_tests():
    df = _df(["2013-03-01", "2013-07-01", "2014-02-01"])
    kept, summary = exclusion_summary(df)
    assert summary["tests_flagged"] == 1
    assert set(kept["clickability_test_id"]) == {"t0", "t2"}
    assert summary["packages_dropped"] == 2


def test_loader_parses_embedded_newlines(upworthy_csv):
    path = upworthy_csv("synthetic.csv", n_tests=20)
    df = load_upworthy("exploratory", path=path)
    assert len(df) == pd.read_csv(path).shape[0]
    assert df["lede"].str.contains("\n").all()
    assert "row" in df.columns


@pytest.mark.skipif(not (data.RAW_DIR / data.UPWORTHY_FILES["exploratory"]).is_file(), reason="raw data not present")
def test_exploratory_matches_paper_counts():
    df = load_upworthy("exploratory")
    check = pipeline_check(df, "exploratory")
    assert check["packages"] == 22_666 and check["tests"] == 4_873
    _, summary = exclusion_summary(df)
    assert summary["tests_flagged"] == 1_050


@pytest.mark.skipif(not (data.RAW_DIR / data.HILLSTROM_FILE).is_file(), reason="raw data not present")
def test_hillstrom_basic_numbers():
    df = data.load_hillstrom()
    c = data.hillstrom_check(df)
    assert c["rows"] == 64_000
    sizes = {k: v["n"] for k, v in c["by_segment"].items()}
    assert sizes == {"Mens E-Mail": 21_307, "Womens E-Mail": 21_387, "No E-Mail": 21_306}
    assert round(c["overall_visit"], 2) == 0.15
    assert round(c["overall_conversion"], 3) == 0.009
    assert c["spend_max"] == 499.0
    assert c["share_history_in_its_segment_bracket"] == 1.0
