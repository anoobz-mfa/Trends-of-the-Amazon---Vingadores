"""Run: python tests/test_core.py  (no pytest needed)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trend_core import analyze_trend, mann_kendall  # noqa: E402

rng = np.random.default_rng(0)
idx = pd.date_range("2000-01-01", periods=312, freq="MS")
season = 2 * np.sin(idx.month / 12 * 2 * np.pi)

# 1) known trend (+0.5/decade) hidden under a strong seasonal cycle must be recovered and be significant
s = pd.Series(season + 0.05 * np.arange(312) / 12 * 10 / 10 + rng.normal(0, 0.3, 312), index=idx)
r = analyze_trend(s)
assert r["cls"] == "confirmed" and abs(r["slope_dec"] - 0.5) < 0.15, r["slope_dec"]
assert r["ci_dec"][0] <= r["slope_dec"] <= r["ci_dec"][1]

# 2) pure noise + seasonality must not be flagged
n = pd.Series(season + rng.normal(0, 0.3, 312), index=idx)
assert analyze_trend(n)["cls"] in ("none", "indication")

# 3) a trend created only by the last 3 years must trigger the sensitivity warning
y = pd.Series(season + rng.normal(0, 0.3, 312), index=idx)
y[y.index.year >= 2023] += 3.0
r = analyze_trend(y)
assert r["fragile"], r["warnings"]

# 4) autocorrelation correction widens the CI and never shrinks it
walk = pd.Series(season + np.cumsum(rng.normal(0, 0.1, 312)), index=idx)
r = analyze_trend(walk)
assert r["mk"]["autocorr_factor"] >= 1
assert (r["ci_dec"][1] - r["ci_dec"][0]) >= (r["ci_dec_raw"][1] - r["ci_dec_raw"][0]) - 1e-12

# 5) seasonal mode returns one value per year
r = analyze_trend(s, months=(7, 8, 9))
assert r["mode"] == "seasonal" and r["n"] == 26
print("all core tests passed")
