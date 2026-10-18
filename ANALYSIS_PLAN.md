# Analysis plan for the confirmatory run

Status: written after exploring the Upworthy exploratory release, before the confirmatory release has been
opened. Nothing in this repository has read, counted or hashed the confirmatory file. (When it was
downloaded, its sha256 and raw line count were printed to confirm the download; no rows were parsed.) Once this plan and
the code are committed, `ANALYSIS_PLAN.lock` is created and the confirmatory analysis is run once:

```
shasum -a 256 ANALYSIS_PLAN.md > ANALYSIS_PLAN.lock
uv run forensics run --release confirmatory
```

The code refuses to load the confirmatory file unless `ANALYSIS_PLAN.lock` exists. If the lock contains a
sha256 digest, it must match this file. The results go to `reports/confirmatory.md` and
`reports/results_confirmatory.json`, and are reported whatever they show.

## Data

- File: `data/raw/upworthy-archive-confirmatory-packages-03.12.2020.csv`, expected sha256
  `b2a88288c88f2b67d40413c9bdbebe79a1c0b5d9a9354180549f59f3bfff685f` (checked by `scripts/fetch_data.sh`).
- Read with `pandas.read_csv` (fields contain embedded newlines and HTML). One row per package (arm); arms
  are grouped by `clickability_test_id`. `created_at` is parsed as a naive timestamp (the archive says its
  timezone is unknown).
- Pipeline check: count packages and tests and compare with the paper's 105,551 packages within 22,743
  tests. A mismatch is reported, and the analysis still runs.

## Exclusion (Matias et al. 2024 correction)

- A test is excluded when its first package (earliest `created_at`) was created on or after
  2013-06-25 00:00:00 and before 2014-01-11 00:00:00, i.e. "from June 25, 2013 through the end of
  January 10, 2014".
- Reported alongside: counts under the any-package and all-packages rules, and with both window edges
  shifted by -24, -12, +12 and +24 hours.
- Sample-ratio check: per multi-arm test, chi-square test of equal impressions across arms; share with
  p < 0.001 inside and outside the window.

## Definitions

- Arms with fewer than 100 impressions are dropped before anything else.
- Reference arm: the arm in a test with the earliest `created_at` (ties broken by file row order).
- Comparison: every other arm vs the reference. Difference `d = p_arm - p_ref`; relative difference
  `d / p_ref` (undefined when `p_ref = 0`). Standard error from the pooled rate,
  `s = sqrt(p_pool (1 - p_pool) (1/n_arm + 1/n_ref))`; comparisons with `s = 0` are dropped. Two-sided
  pooled two-proportion z-test.
- Identical-arm pairs: within a kept test, arms with identical `headline`, `eyecatcher_id` and `excerpt`
  (missing values treated as empty strings); the first two such arms by creation time form one pair.
  Reported: number of pairs, share with p < 0.05, binomial test of that share against 5%, mean z squared
  (phi).

## Analysis 1: effect sizes and power

- Quantiles (5, 25, 50, 75, 95) of `d` and of the relative difference; median |d|, median |relative d|,
  share of comparisons with p < 0.05.
- Per test: average arm size `n` (total impressions over arms) and pooled click rate `p`. MDE at 80% power,
  two-sided alpha 0.05: `(z_0.975 + z_0.80) sqrt(2 p (1 - p) / n)`; relative MDE = MDE / p.
- Typical true effect: median |theta| under the grid prior of analysis 3. Reported: share of tests with
  MDE <= typical true effect, share with MDE <= median observed |d|, mean and median power at the typical
  true effect.

## Analysis 2: peeking

- 20,000 simulated A/A tests. Each draws a kept test uniformly with replacement and uses its pooled rate
  for both arms and its average arm size (rounded) for each arm. Impressions arrive in 100 equal batches
  (batch edges `floor(n k / 100)`), with binomial clicks per batch.
- Looks K in {1, 2, 5, 10, 20, 50, 100}: check after every 100/K batches. Naive: pooled z-test, reject at
  the first |z| > 1.96. mSPRT: normal-mixture likelihood ratio of Johari et al. with pooled-variance
  plug-in, mixing SD tau = 0.0036 (0.36 pp, the exploratory normal prior SD rounded, frozen), reject at the
  first look with ratio >= 20.
- Power: the same with a relative lift of 10%, 25% and 50% in the second arm; reported for a single final
  z-test and for mSPRT with 10 and 100 looks.
- Seeds: `numpy.random.default_rng([20261018, 1])` for A/A, `default_rng([20261018, 2, i])` for the i-th
  lift.

## Analysis 3: winner's curse

- Priors are fit to all comparisons (`d`, `s`): normal prior N(mu, tau^2) by maximum marginal likelihood
  (Nelder-Mead), and a grid NPMLE with 301 equally spaced points from min(d) to max(d), plus 0, fit by EM
  (up to 3,000 iterations, stopping when the log-likelihood gain is below 1e-8 of its size).
- Winner per test: the non-reference arm with the highest observed rate, kept if `d > 0`. Significant
  winner: two-sided p < 0.05.
- Reported: number of significant winners and share of tests; median observed lift; median shrinkage
  `1 - posterior mean / d` under each prior; median posterior lift; share of significant winners with grid
  posterior P(theta > 0) >= 0.95.
- Sensitivity: multiply every `s` by sqrt(phi) from the identical-arm pairs (when phi > 1), refit the grid
  prior, and report median shrinkage and the share of significant winners still clearing
  |z| / sqrt(phi) > 1.96.
- Examples: the significant winner with the largest shrinkage in percentage points, and the one whose
  shrinkage is closest to the median.

## What gets compared, and what counts as replicating

The confirmatory report prints these side by side with the exploratory values. Criteria were set before
looking at the confirmatory data.

| Metric | Exploratory | Replicates if the confirmatory value is |
|---|---|---|
| Share of tests in the correction window | 21.5% | within 2 pp of 21.6% (7,004 / 32,487) |
| SRM p < 0.001, inside window | 70.0% | > 25% |
| SRM p < 0.001, outside window | 0.5% | < 2% |
| Identical-arm pairs with p < 0.05 | 13.3% | > 5%, with binomial test p < 0.01 |
| Tests powered (MDE <= typical true effect) | 0.03% | < 5% |
| Mean power at the typical true effect | 10.3% | < 20% |
| A/A false positives, 1 look | 5.2% | within 1 pp of 5% |
| A/A false positives, 10 looks | 18.9% | >= 10% |
| A/A false positives, 100 looks | 30.4% | >= 20% |
| mSPRT false positives, 100 looks | 0.32% | <= 5.5% |
| Median shrinkage of significant winners, grid prior | 40.5% | within 10 pp of exploratory |
| Median shrinkage of significant winners, normal prior | 41.8% | within 10 pp of exploratory |

Reported as descriptive, with no criterion: median |d|, median |relative d|, normal prior SD, typical true
effect, median relative MDE, share of tests with a significant winner, share of winners with
P(theta > 0) >= 0.95, inflated-SE shrinkage.

## Not part of the confirmatory run

- The Hillstrom analyses (variance reduction, subgroups). Hillstrom is one experiment with no second
  release, so its results are exploratory only.
- The Upworthy hold-out release, which is not used here.

## Deviations

Any change after the lock is created will be listed here with the reason, and the confirmatory report will
say which results it affects.
