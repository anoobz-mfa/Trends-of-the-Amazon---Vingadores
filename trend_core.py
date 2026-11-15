"""Statistical core: Giovanni CSV reader + trend analysis.

Pipeline: monthly anomalies (seasonality removed) -> Theil-Sen slope -> Mann-Kendall test with
autocorrelation correction (Hamed & Rao, simplified) -> confidence interval widened by the same
correction -> sensitivity to the period -> plain-language text.
The confidence level is fixed at 95%.
"""
import io
import math

import numpy as np
import pandas as pd
from scipy import stats

ALPHA = 0.05  # fixed: 95% confidence
VERDICTS = {
    "confirmed": ("", "Trend confirmed"),
    "indication": ("", "Hint of a trend"),
    "none": ("", "No evidence of a trend"),
}


# --------------------------------------------------------------------------- reading
def read_giovanni_csv(source):
    """Read a Giovanni area-averaged time-series CSV (path, file object or bytes).
    Returns (monthly Series, metadata dict). Daily data become monthly means."""
    if isinstance(source, (bytes, bytearray)):
        text = bytes(source).decode("utf-8-sig")
    elif hasattr(source, "read"):
        raw = source.read()
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    else:
        with open(source, encoding="utf-8-sig") as f:
            text = f.read()
    lines = text.splitlines()
    meta, start = {}, None
    for i, line in enumerate(lines):
        if line.lower().startswith("time,"):
            start = i
            break
        if ":," in line:
            k, v = line.split(":,", 1)
            meta[k.strip()] = v.strip().strip('"')
    if start is None:
        raise ValueError("Could not find the 'time,' header: this does not look like a Giovanni time-series CSV.")
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), skipinitialspace=True)
    varname = df.columns[1].strip()
    meta["variable"] = varname
    df.columns = ["time", "value"]
    df["time"] = pd.to_datetime(df["time"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    for k, v in meta.items():
        if k.startswith("Fill Value"):
            try:
                df.loc[np.isclose(df["value"], float(v)), "value"] = np.nan
            except ValueError:
                pass
    df.loc[df["value"].abs() >= 1e14, "value"] = np.nan
    s = df.set_index("time")["value"].sort_index()
    if len(s) > 2 and s.index.to_series().diff().median() < pd.Timedelta(days=20):
        s = s.resample("MS").mean()
        meta["resampled"] = "daily/sub-monthly data were converted to monthly means"
    else:
        s = s.asfreq("MS")
    return s, meta


# --------------------------------------------------------------------------- statistics
def remove_seasonality(s):
    """Monthly anomalies: value minus the climatological mean of the same calendar month."""
    return s - s.groupby(s.index.month).transform("mean")


def theil_sen(x, t=None, alpha=ALPHA):
    """Theil-Sen slope (units per unit of t) with scipy's confidence interval."""
    x = np.asarray(x, float)
    t = np.arange(len(x), dtype=float) if t is None else np.asarray(t, float)
    res = stats.theilslopes(x, t, alpha=1 - alpha)
    return float(res[0]), float(res[2]), float(res[3])


def mann_kendall(x, t=None, alpha=ALPHA, correct_autocorr=True):
    """Mann-Kendall test with optional autocorrelation correction (Hamed & Rao, simplified)."""
    x = np.asarray(x, float)
    n = len(x)
    t = np.arange(n, dtype=float) if t is None else np.asarray(t, float)
    if n < 4:
        return dict(S=0, z=0.0, p=1.0, significant=False, autocorr_factor=1.0)
    S = np.triu(np.sign(x[None, :] - x[:, None]), 1).sum()
    _, counts = np.unique(x, return_counts=True)
    var_s = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18
    factor = 1.0
    if correct_autocorr:
        slope0 = theil_sen(x, t)[0]
        ranks = stats.rankdata(x - slope0 * t)
        ranks = ranks - ranks.mean()
        denom = np.sum(ranks ** 2)
        if denom > 0:
            k = np.arange(1, n)
            acf = np.array([np.sum(ranks[:n - j] * ranks[j:]) / denom for j in k])
            sig = np.abs(acf) > 1.96 / np.sqrt(n)
            corr = np.sum((n - k[sig]) * (n - k[sig] - 1) * (n - k[sig] - 2) * acf[sig])
            factor = max(1 + 2 / (n * (n - 1) * (n - 2)) * corr, 1.0)
    var_s *= factor
    z = (S - np.sign(S)) / np.sqrt(var_s) if S != 0 else 0.0
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    return dict(S=int(S), z=float(z), p=float(p), significant=bool(p < alpha), autocorr_factor=float(factor))


def classify(p, alpha=ALPHA):
    if p < alpha:
        return "confirmed"
    return "indication" if p < 0.10 else "none"


def fit_trend(y, t, alpha=ALPHA):
    """All trend statistics for samples y observed at times t (decimal years)."""
    y, t = np.asarray(y, float), np.asarray(t, float)
    sl, lo, hi = theil_sen(y, t, alpha)
    mk = mann_kendall(y, t, alpha)
    mk_raw = mann_kendall(y, t, alpha, correct_autocorr=False)
    w = math.sqrt(mk["autocorr_factor"])  # widen the CI by the same correction used in the test
    lo_c, hi_c = sl - (sl - lo) * w, sl + (hi - sl) * w
    lr = stats.linregress(t, y)
    ci = stats.t.ppf(1 - alpha / 2, len(y) - 2) * lr.stderr
    return dict(n=len(y), slope_yr=sl, ci_yr=(lo_c, hi_c), slope_dec=sl * 10, ci_dec=(lo_c * 10, hi_c * 10),
                ci_dec_raw=(lo * 10, hi * 10), intercept=float(np.median(y - sl * t)), mk=mk, mk_raw=mk_raw,
                ols_dec=lr.slope * 10, ols_ci_dec=((lr.slope - ci) * 10, (lr.slope + ci) * 10), ols_p=lr.pvalue,
                cls=classify(mk["p"], alpha))


def make_samples(s, months=None, start_year=None, end_year=None):
    """Return (samples Series, t in decimal years, mode, base values).
    All months -> monthly anomalies. A season -> one mean anomaly per year (avoids gaps/autocorrelation tricks)."""
    s = s.dropna()
    if start_year is not None:
        s = s[s.index.year >= start_year]
    if end_year is not None:
        s = s[s.index.year <= end_year]
    if len(s) == 0:
        raise ValueError("No data in the selected period.")
    anom = remove_seasonality(s)
    if not months or len(set(months)) >= 12:
        t = (anom.index.year + (anom.index.month - 1) / 12).values.astype(float)
        return anom, t, "monthly", s
    sel = anom[anom.index.month.isin(months)]
    g = sel.groupby(sel.index.year)
    y = g.mean()[g.count() >= math.ceil(len(months) / 2)]
    idx = pd.to_datetime([f"{yr}-07-01" for yr in y.index])
    return pd.Series(y.values, index=idx), np.array(y.index, float) + 0.5, "seasonal", s[s.index.month.isin(months)]


def trend_band(res):
    """Trend line and 95% band (pivoting on the median time) for plotting."""
    t = res["t"]
    tm = np.median(t)
    sl, (lo, hi), b = res["slope_yr"], res["ci_yr"], res["intercept"]
    c = sl * tm + b
    line = sl * t + b
    a, d = c + lo * (t - tm), c + hi * (t - tm)
    return line, np.minimum(a, d), np.maximum(a, d)


def analyze_trend(s, months=None, start_year=None, end_year=None, sensitivity=True, alpha=ALPHA):
    y, t, mode, base = make_samples(s, months, start_year, end_year)
    if len(y) < (36 if mode == "monthly" else 8):
        raise ValueError("Too little data in this selection for a reliable trend "
                         "(need 3+ years of months, or 8+ years for a season).")
    res = fit_trend(y.values, t, alpha)
    mean_level = float(base.mean())
    res.update(mode=mode, y=y, t=t, months=list(months) if months else None, n_months=int(len(base)),
               start=str(base.index[0].date()), end=str(base.index[-1].date()), mean_level=mean_level,
               pct_dec=(res["slope_dec"] / mean_level * 100) if mean_level else float("nan"),
               anomalies=y, warnings=[], runs=[], fragile=False)
    last_year, first_year = int(base.index.year.max()), int(base.index.year.min())
    if sensitivity:
        for e in range(first_year + 14, last_year):
            try:
                r = analyze_trend(s, months, start_year, e, sensitivity=False, alpha=alpha)
            except ValueError:
                continue
            res["runs"].append(dict(end_year=e, slope_dec=r["slope_dec"], ci_dec=r["ci_dec"], p=r["mk"]["p"], cls=r["cls"]))
        _assess_sensitivity(res, last_year)
    _check_nonlinear(res)
    res["text"] = explain(res)
    return res


def _assess_sensitivity(res, last_year):
    recent = [r for r in res["runs"] if r["end_year"] >= last_year - 4]
    changed = [r for r in recent if r["cls"] != res["cls"]]
    big = []
    if res["cls"] != "none":
        big = [r for r in recent if r["cls"] == res["cls"] and
               (np.sign(r["slope_dec"]) != np.sign(res["slope_dec"]) or
                abs(r["slope_dec"] - res["slope_dec"]) > 0.5 * abs(res["slope_dec"]))]
    if changed:
        ends = ", ".join(str(r["end_year"]) for r in changed)
        what = ", ".join(sorted({VERDICTS[r["cls"]][1].lower() for r in changed}))
        res["warnings"].append(f"Sensitive to the period: if the series ended in {ends}, the verdict would be "
                               f"'{what}' instead of '{VERDICTS[res['cls']][1].lower()}'.")
    elif big:
        ends = ", ".join(str(r["end_year"]) for r in big)
        res["warnings"].append(f"Sensitive to the period: the rate changes by more than 50% if the series ended in {ends}.")
    res["fragile"] = bool(changed or big)


def _check_nonlinear(res):
    t, y = res["t"], res["y"].values
    if len(y) < 16:
        return
    m = np.median(t)
    a, b = t <= m, t > m
    if a.sum() < 8 or b.sum() < 8:
        return
    sa, sb = theil_sen(y[a], t[a])[0], theil_sen(y[b], t[b])[0]
    pa = mann_kendall(y[a], t[a], correct_autocorr=False)["p"]
    pb = mann_kendall(y[b], t[b], correct_autocorr=False)["p"]
    if np.sign(sa) != np.sign(sb) and pa < 0.10 and pb < 0.10:
        res["warnings"].append(f"The direction changes around {int(m)} (first half {'rises' if sa > 0 else 'falls'}, "
                               f"second half {'rises' if sb > 0 else 'falls'}): a straight line may be a poor summary.")


# --------------------------------------------------------------------------- text
def _fmt(v):
    d = 2 if abs(v) >= 0.01 else 3
    return f"{v:.{d}f}"


def fmt_p(p):
    return "< 0.0001" if p < 0.0001 else f"= {p:.4f}"


def explain(r, unit=None):
    unit = unit or "units"
    sl, (lo, hi), mk = r["slope_dec"], r["ci_dec"], r["mk"]
    how = ("the mean anomaly of each year's selected months" if r["mode"] == "seasonal"
           else f"{r['n_months']} monthly anomalies")
    base = (f"Between {r['start'][:4]} and {r['end'][:4]} (based on {how}), the estimated rate of change is "
            f"{'+' if sl > 0 else '−'}{_fmt(abs(sl))} per decade (95% confidence interval: "
            f"{_fmt(lo)} to {_fmt(hi)}, widened for autocorrelation).")
    p = fmt_p(mk["p"])
    if mk["significant"]:
        return base + f" The trend is statistically significant (p {p}, Mann-Kendall with autocorrelation correction)."
    if mk["p"] < 0.10:
        return base + f" There is a hint of a trend, but it is not significant at 95% (p {p}). More years of data could change this."
    return base + f" There is no statistical evidence of a trend (p {p}): the observed variation is compatible with natural noise."
