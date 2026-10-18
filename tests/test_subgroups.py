import numpy as np
import pytest
from statsmodels.stats.multitest import multipletests

from forensics.subgroups import benjamini_hochberg, corrected_counts, holm


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_corrections_match_statsmodels(seed):
    rng = np.random.default_rng(seed)
    p = np.concatenate([rng.uniform(size=40), rng.uniform(0, 0.01, size=5)])
    assert np.allclose(holm(p), multipletests(p, method="holm")[1])
    assert np.allclose(benjamini_hochberg(p), multipletests(p, method="fdr_bh")[1])


def test_counts_order():
    p = np.array([0.001, 0.01, 0.02, 0.04, 0.2, 0.5])
    c = corrected_counts(p)
    assert c["naive"] >= c["bh"] >= c["holm"]
    # Holm: 0.001*6 and 0.01*5 <= 0.05. BH: 0.02*6/3 = 0.04 <= 0.05.
    assert c == {"tests": 6, "naive": 4, "holm": 2, "bh": 3}
