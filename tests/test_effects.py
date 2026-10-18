import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.proportion import proportions_ztest

from forensics.effects import build_comparisons, mde, power_at, two_prop_ztest, winners


@pytest.mark.parametrize("c1,n1,c0,n0", [(30, 2000, 45, 2100), (120, 5000, 90, 4800), (0, 100, 3, 120),
                                         (500, 3000, 480, 3000)])
def test_ztest_matches_statsmodels(c1, n1, c0, n0):
    z, p = two_prop_ztest(c1, n1, c0, n0)
    z_sm, p_sm = proportions_ztest([c1, c0], [n1, n0])
    assert z == pytest.approx(z_sm, rel=1e-10)
    assert p == pytest.approx(p_sm, rel=1e-10)


def test_mde_gives_80_percent_power():
    p, n = 0.015, 3000
    d = mde(p, n, n)
    se = np.sqrt(2 * p * (1 - p) / n)
    assert power_at(d, se) == pytest.approx(0.80, abs=0.005)


def test_reference_is_first_created_arm():
    df = pd.DataFrame({
        "clickability_test_id": ["a"] * 3,
        "created_ts": pd.to_datetime(["2014-01-01 00:00:02", "2014-01-01 00:00:01", "2014-01-01 00:00:03"]),
        "impressions": [1000, 1000, 1000], "clicks": [20, 10, 30],
        "headline": ["second", "first", "third"], "eyecatcher_id": ["x"] * 3,
    })
    comp = build_comparisons(df)
    assert set(comp["headline0"]) == {"first"}
    assert sorted(comp["diff"].round(3)) == [0.01, 0.02]
    w = winners(comp)
    assert list(w["headline1"]) == ["third"]
