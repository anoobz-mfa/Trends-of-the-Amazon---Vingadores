"""Live access to the NASA POWER monthly API for any point on Earth (no login needed)."""
import json
import urllib.error
import urllib.parse
import urllib.request

import pandas as pd

URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
# parameter -> (name, unit, ratio-scale?, plain definition, short name). Only codes confirmed in NASA/POWER-client docs.
PARAMS = {
    "T2M": ("Air temperature (2 m)", "°C", False, "Air temperature 2 m above the ground.", "Temperature"),
    "PRECTOTCORR": ("Precipitation", "mm/day", True, "Bias-corrected rainfall, in mm per day.", "Rain"),
    "RH2M": ("Relative humidity (2 m)", "%", True, "How saturated the air is with water vapour.", "Humidity"),
    "ALLSKY_SFC_SW_DWN": ("Sunlight at the surface", "kWh/m²/day", True,
                          "Solar energy reaching the ground (satellite-based, starts around 2001).", "Sunlight"),
    "WS2M": ("Wind speed (2 m)", "m/s", True, "Wind speed 2 m above the ground.", "Wind"),
}
# Named places across the Amazon (approximate coordinates): (name, lat, lon, one-line story)
AMAZON_SPOTS = [
    ("Manaus", -3.12, -60.02, "Heart of the basin, where the Negro and Solimões rivers meet."),
    ("Belém", -1.46, -48.50, "Eastern edge, near the Amazon river mouth."),
    ("Santarém", -2.44, -54.71, "Lower Amazon, at the Tapajós river."),
    ("Altamira", -3.20, -52.21, "Xingu river region, east-central Amazon."),
    ("Marabá", -5.37, -49.12, "Southeast, close to the Cerrado transition."),
    ("Sinop", -11.86, -55.50, "Southern edge, where the Amazon meets the Cerrado."),
    ("Porto Velho", -8.76, -63.90, "Southwest Amazon, Rondônia."),
    ("Rio Branco", -9.97, -67.81, "Southwestern Amazon, Acre."),
    ("Cruzeiro do Sul", -7.63, -72.67, "Far west, near the Peruvian border."),
    ("Iquitos", -3.75, -73.25, "Peruvian Amazon, upper river."),
    ("São Gabriel da Cachoeira", 0.13, -67.09, "Northwest, among the wettest parts of the basin."),
    ("Tefé", -3.35, -64.71, "Western-central Amazon, on the Solimões."),
    ("Boa Vista", 2.82, -60.67, "North edge, Roraima."),
    ("Macapá", 0.03, -51.07, "Northeast, on the equator."),
]
PRESETS = {
    "Type coordinates…": None,
    "Brasília (Cerrado)": (-15.79, -47.88),
    "São Paulo (large city)": (-23.55, -46.63),
    "Petrolina (semi-arid)": (-9.39, -40.50),
    "Rio de Janeiro": (-22.91, -43.17),
    "New York": (40.71, -74.01),
}


def parse_power_json(js):
    """POWER JSON -> {parameter: monthly Series}. Month '13' is the annual mean and is dropped; -999 is missing."""
    out = {}
    for name, vals in js["properties"]["parameter"].items():
        rows = {}
        for ym, v in vals.items():
            if len(ym) == 6 and ym[4:] != "13":
                rows[pd.Timestamp(int(ym[:4]), int(ym[4:]), 1)] = float("nan") if v <= -998 else float(v)
        out[name] = pd.Series(rows).sort_index().asfreq("MS")
    return out


def fetch_monthly(lat, lon, params, start, end, timeout=90):
    q = urllib.parse.urlencode(dict(parameters=",".join(params), community="AG", longitude=f"{lon:.4f}",
                                    latitude=f"{lat:.4f}", start=start, end=end, format="JSON"))
    try:
        with urllib.request.urlopen(f"{URL}?{q}", timeout=timeout) as r:
            return parse_power_json(json.load(r))
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"Could not reach NASA POWER ({e}). Check your internet connection and try again.") from e
    except (KeyError, ValueError) as e:
        raise RuntimeError("NASA POWER returned an unexpected response for this request.") from e
