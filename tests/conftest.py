import numpy as np
import pandas as pd
import pytest


def make_upworthy(n_tests=300, seed=0, start="2013-02-01", end="2015-04-01"):
    """Small synthetic file with the archive's columns."""
    rng = np.random.default_rng(seed)
    t0, t1 = pd.Timestamp(start).value, pd.Timestamp(end).value
    rows = []
    for t in range(n_tests):
        base = pd.Timestamp(rng.integers(t0, t1))
        k = int(rng.integers(2, 6))
        p0 = rng.uniform(0.005, 0.03)
        for a in range(k):
            p = p0 * (1 + rng.normal(0, 0.15)) if a else p0
            n = int(rng.integers(2000, 5000))
            same = a == 1 and t % 10 == 0
            rows.append({
                "created_at": str(base + pd.Timedelta(seconds=30 * a)),
                "updated_at": str(base + pd.Timedelta(days=1)),
                "clickability_test_id": f"t{t:05d}",
                "excerpt": "Things that matter.",
                "headline": f"headline {t}-0" if same else f"headline {t}-{a}",
                "lede": "<p>lede\nwith newline</p>",
                "slug": f"slug-{t}-{a}",
                "eyecatcher_id": f"img{t}",
                "impressions": n,
                "clicks": int(rng.binomial(n, min(max(p, 0.0005), 0.5))),
                "significance": 0.0,
                "first_place": a == 0,
                "winner": a == 0,
                "share_text": "",
                "square": "",
                "test_week": int(base.strftime("%Y%W")),
            })
    df = pd.DataFrame(rows)
    df.insert(0, "", range(len(df)))
    return df


@pytest.fixture
def upworthy_csv(tmp_path):
    def _write(name, **kw):
        path = tmp_path / name
        make_upworthy(**kw).to_csv(path, index=False)
        return path

    return _write
