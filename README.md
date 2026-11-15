# Trends of the Amazon

Is the Amazon changing? Streamlit app that turns NASA Giovanni / POWER time series into answers:
**what** is changing, **where**, **how fast**, and **is it real?**

## Run
```
pip install -r requirements.txt
py -m streamlit run app.py        # (python -m streamlit run app.py on Mac/Linux)
python tests/test_core.py         # statistical self-tests
```

## Tabs
- **Overview**: one card per variable (verdict, rate, "leans on recent years" flag), season table, honest wording guide
- **Investigate**: verdict + 3 numbers + one chart; "Go deeper" holds raw data, period sensitivity, full statistics, region
- **Compare**: any two variables or places on the same scale, with correlation and opposite-trend detection
- **Map**: clickable Amazon spots (NASA POWER, live) or your own pin; opened spots feed the Compare tab
- **Learn**: method, verdict meanings, glossary, limits, how to get Giovanni data

## Statistics
Monthly anomalies → Theil-Sen rate → Mann-Kendall with autocorrelation correction; the 95% CI is widened by the
same factor. A period-sensitivity check re-runs the analysis ending in earlier years; a non-linearity check flags
series that change direction. Confidence is fixed at 95%.

Icons: pins and logo live in `assets/`; `icons.py` maps each variable to its pin (replace a PNG to change it).

Files: `app.py` (UI), `trend_core.py` (statistics), `catalog.py` (variables, regions), `plots.py`, `power_api.py`,
`data/`, `tests/`, `.streamlit/config.toml` (dark theme).
