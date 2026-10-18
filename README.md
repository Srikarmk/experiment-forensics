# experiment-forensics

How much does the *analysis* of an A/B test change its answer, when the data and the test are fixed?
This project looks at three choices: when you look at the results, how you control variance, and how many
subgroups you check. It uses two public experiment datasets.

- **Upworthy Research Archive**: thousands of real headline A/B tests run by Upworthy from 2013 to 2015.
  Used for effect sizes and power, peeking, and the winner's curse.
- **Hillstrom MineThatData email test**: 64,000 customers randomized to a men's email, a women's email or
  no email. Used for variance reduction (CUPED, regression adjustment) and subgroup analysis.

Results: [`reports/exploratory.md`](reports/exploratory.md) (Upworthy exploratory release and Hillstrom)
and [`reports/confirmatory.md`](reports/confirmatory.md) (the single pre-registered run on the Upworthy
confirmatory release). All 13 replication criteria in the plan were met.

## Data and sources

**Upworthy.** Matias, J. N., Munger, K., Aubin Le Quere, M. and Ebersole, C. (2021). The Upworthy
Research Archive, a time series of 32,487 experiments in U.S. media. *Scientific Data* 8, 195.
[doi:10.1038/s41597-021-00934-7](https://doi.org/10.1038/s41597-021-00934-7)
([PMC8329003](https://pmc.ncbi.nlm.nih.gov/articles/PMC8329003/)). Data on the
[Open Science Framework](https://osf.io/jd64p/) and at [upworthy.natematias.com](https://upworthy.natematias.com),
licensed CC BY 4.0. Files used (release of 03.12.2020):

- exploratory packages: <https://osf.io/download/3vqmp/> (22,666 packages in 4,873 tests)
- confirmatory packages: <https://osf.io/download/vy8mj/> (105,551 packages in 22,743 tests)

Each row is one arm ("package"): a headline, an image ID, an excerpt, and its impressions and clicks.
Arms in the same experiment share `clickability_test_id`. There is no control arm.

**Correction.** Matias, J. N., Munger, K., Aubin Le Quere, M. and Ebersole, C. (2024). Author Correction:
The Upworthy Research Archive, a time series of 32,487 experiments in U.S. media. *Scientific Data* 11, 765.
[doi:10.1038/s41597-024-03600-w](https://doi.org/10.1038/s41597-024-03600-w)
([PMC11239857](https://pmc.ncbi.nlm.nih.gov/articles/PMC11239857/)).

**Hillstrom.** Hillstrom, K. (2008). The MineThatData E-Mail Analytics And Data Mining Challenge.
[Blog post, 20 March 2008](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html);
[CSV](http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv).
`history` is the actual dollar value spent in the past year, and `mens` / `womens` flag past-year purchases
of men's or women's merchandise; all of these are measured before the campaign. `segment` is the treatment,
and `visit`, `conversion` and `spend` cover the two weeks after it.

## The randomization caveat

After the archive was published, the authors found evidence that randomization likely failed for tests
run between 25 June 2013 and 10 January 2014: 7,004 tests, 22% of the archive. They believe a web cache
was serving one arm at a time. They encourage researchers to treat these tests as not randomized, and to
omit all experiments from 25 June 2013 through the end of 10 January 2014 from causal analysis.

The 03.12.2020 files predate the correction and do not have the `problem` column it added, so this project
rebuilds the exclusion from `created_at`. A test is dropped when its first package was created inside that
window. In the exploratory release that drops 1,050 of 4,873 tests (21.5%). As a check, unequal
allocation of impressions across arms (p < 0.001) shows up in 70.0% of multi-arm tests inside the window and
0.5% outside it. `created_at` has an unknown timezone; moving the window edges by up to a day changes the
count by at most 6 tests.

## Explore, then confirm

The archive ships as separate exploratory and confirmatory releases so that analysts can explore on one
and test on the other. This project uses them that way:

1. All Upworthy analysis was developed on the exploratory release only, before the confirmatory file
   was read by anything here.
2. [`ANALYSIS_PLAN.md`](ANALYSIS_PLAN.md) freezes the definitions, exclusion, seeds, frozen parameters and
   the list of numbers to compare, each with the criterion it has to meet to count as replicating.
3. The plan was committed, then the lock file in a separate commit, then the confirmatory analysis ran
   once (see the git history).
   `forensics` refuses to load the confirmatory file unless `ANALYSIS_PLAN.lock` exists, and if the lock
   holds a sha256 digest it must match the plan.

Hillstrom is a single experiment, so its results stay exploratory.

## Reproduce

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```
uv sync
scripts/fetch_data.sh                          # downloads into data/raw/ and checks sha256
uv run pytest
uv run forensics run --release exploratory     # writes reports/exploratory.md, figures, results JSON
```

Confirmatory run, once the plan is frozen:

```
shasum -a 256 ANALYSIS_PLAN.md > ANALYSIS_PLAN.lock
uv run forensics run --release confirmatory    # writes reports/confirmatory.md
```

All simulations are seeded, so reruns give identical numbers.

## Layout

```
forensics/
  data.py         loading, paper-count checks, correction exclusion, confirmatory guard
  effects.py      arm-vs-reference comparisons, z-test, MDE, power
  peeking.py      A/A and A/B simulations with interim looks
  sequential.py   mixture SPRT (always-valid test)
  shrinkage.py    empirical-Bayes priors (normal and grid NPMLE)
  cuped.py        difference in means, CUPED, Lin regression adjustment, balance
  subgroups.py    subgroup effects, Holm and Benjamini-Hochberg
  upworthy.py     analyses 1-3
  hillstrom.py    analyses 4-5
  report.py       markdown reports
  plots.py        figures
  cli.py          `forensics run --release ...`
tests/            pytest suite
scripts/          data download
reports/          generated reports and figures
```

## Methods referenced

- Deng, A., Xu, Y., Kohavi, R. and Walker, T. (2013). Improving the sensitivity of online controlled
  experiments by utilizing pre-experiment data. *WSDM 2013*. (CUPED)
- Lin, W. (2013). Agnostic notes on regression adjustments to experimental data: reexamining Freedman's
  critique. *Annals of Applied Statistics* 7(1).
- Johari, R., Koomen, P., Pekelis, L. and Walsh, D. (2022). Always valid inference: continuous monitoring of
  A/B tests. *Operations Research* 70(3). (mSPRT)
- Koenker, R. and Mizera, I. (2014). Convex optimization, shape constraints, compound decisions, and
  empirical Bayes rules. *Journal of the American Statistical Association* 109(506). (grid NPMLE)
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of
  Statistics* 6(2).
- Benjamini, Y. and Hochberg, Y. (1995). Controlling the false discovery rate. *Journal of the Royal
  Statistical Society, Series B* 57(1).

## License

Code: MIT (see `LICENSE`). The Upworthy data are CC BY 4.0 from their authors; the Hillstrom data are
distributed by MineThatData.
