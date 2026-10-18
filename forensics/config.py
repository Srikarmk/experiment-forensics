"""Analysis settings. These are the values frozen in ANALYSIS_PLAN.md."""

SEED = 20261018
ALPHA = 0.05
POWER = 0.80
MIN_ARM_IMPRESSIONS = 100

# Peeking simulation
N_SIMS = 20_000
MAX_LOOKS = 100
LOOKS = (1, 2, 5, 10, 20, 50, 100)
POWER_LIFTS = (0.10, 0.25, 0.50)

# mSPRT mixing scale on the absolute click-rate difference, set once from the
# exploratory release (normal empirical-Bayes prior SD, 0.362 pp, rounded to
# 0.36 pp) and then frozen.
MSPRT_TAU = 0.0036

# Hillstrom
HILLSTROM_ARMS = ["Mens E-Mail", "Womens E-Mail"]
HILLSTROM_CONTROL = "No E-Mail"
HILLSTROM_OUTCOMES = ["spend", "visit"]
