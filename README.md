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
- **Question box (top of the page)**: four ready-made questions (hotter? less rain? more smoke? soil drying?) that open the matching variables
- **Overview** (NASA Giovanni): one card per variable (verdict, rate, "leans on recent years" flag), season table, honest wording guide
- **Investigate** (NASA Giovanni): verdict + 3 numbers + one chart; "Go deeper" holds raw data, period sensitivity, full statistics, region
- **Compare** (NASA Giovanni): pick two Amazon-basin variables; same-scale chart, correlation, opposite-trend detection
- **Map** (NASA POWER, live): click an Amazon spot, or type your own coordinates; the only tab that calls the API
- **Learn**: method, verdict meanings, glossary, limits, how to get Giovanni data

## Statistics
Monthly anomalies → Theil-Sen rate → Mann-Kendall with autocorrelation correction; the 95% CI is widened by the
same factor. A period-sensitivity check re-runs the analysis ending in earlier years; a non-linearity check flags
series that change direction. Confidence is fixed at 95%.

Icons: pins and logo live in `assets/`; `icons.py` maps each variable to its pin (replace a PNG to change it).

Files: `app.py` (UI), `trend_core.py` (statistics), `catalog.py` (variables, regions), `plots.py`, `power_api.py`,
`data/`, `tests/`, `.streamlit/config.toml` (dark theme).

## Use of AI (Claude)

This project was built with the help of **Claude**, an AI assistant made by Anthropic.

What Claude did:
- Wrote the code of the app (Streamlit interface, charts, map, data loading) and the statistical core
  (seasonal anomalies, Theil-Sen, Mann-Kendall with autocorrelation correction, period-sensitivity check).
- Ran the first analyses of the NASA data and wrote the plain-language explanations shown in the app.
- Wrote the automated tests (`tests/test_core.py`) and this documentation.

What the team did:
- Chose the challenge, the Amazon focus, the variables and the regions, and downloaded the NASA data.
- Designed the layout, the logo and the custom pins, and decided what the site says and shows.
- Reviewed and tested the app, and made the final decisions.

The results come from the code and data in this repository, not from Claude's memory. Anyone reusing the app
should check the statistics and the sources themselves.

## Data sources and credits

- NASA Giovanni (https://giovanni.gsfc.nasa.gov): MERRA-2 (temperature, organic carbon aerosol), GLDAS 2.1
  (evapotranspiration, soil moisture) and GPM IMERG (precipitation), Amazon basin averages, from 2000 on.
- NASA POWER API (https://power.larc.nasa.gov): live monthly data for the **Map** tab only.
- Logo and pins: created by the project team.

