# data/

Every NASA Giovanni CSV placed here is detected automatically (variable, units, region, duplicates).
Keep Giovanni's default units: the app converts them.

- `amazon_*.csv`: Amazon basin (Giovanni shape `watersheds/shp_8`), 2000-01 to 2026-01 (precipitation ends 2025-09):
  temperature (MERRA-2 T2M), precipitation (GPM IMERG), evapotranspiration and soil moisture 40-100 cm (GLDAS 2.1),
  organic carbon aerosol AOT 550 nm (MERRA-2, a smoke indicator).

Recognised variables: T2M, precipitation (GPM IMERG), Evap_tavg and SoilMoi* (GLDAS),
OCEXTTAU / BCEXTTAU / DUEXTTAU / TOTEXTTAU (MERRA-2 aerosols), QV2M, SWGDN, CLDTOT.
Regions are named from the Giovanni URL inside the CSV header (`REGION_LABELS` in `catalog.py`).
