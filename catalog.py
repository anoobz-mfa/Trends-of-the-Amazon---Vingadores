"""Variable catalog (units, plain-language definitions, caveats), regions and season presets."""
import re
from urllib.parse import unquote

CONVERSIONS = {
    "none": ("No conversion", lambda s: s),
    "K_to_C": ("Kelvin → °C", lambda s: s - 273.15),
    "mmhr_to_mmday": ("mm/hour → mm/day", lambda s: s * 24),
    "flux_to_mmday": ("kg m⁻² s⁻¹ → mm/day", lambda s: s * 86400),
    "kgkg_to_gkg": ("kg/kg → g/kg", lambda s: s * 1000),
}

SEASONS = {
    "All months": None,
    "Jul–Sep (dry season in the Amazon / Cerrado)": [7, 8, 9],
    "Aug–Oct (peak fire/smoke season in the Amazon)": [8, 9, 10],
    "Feb–Apr (wet season in the Amazon)": [2, 3, 4],
    "Dec–Feb (DJF)": [12, 1, 2],
    "Jun–Aug (JJA)": [6, 7, 8],
    "Custom months…": "custom",
}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# pattern: regex on the Giovanni variable id. ratio: True if "% of the mean" makes sense.
VARIABLES = [
    dict(pattern=r"T2M", key="t2m", short="Temperature", name="Air temperature (2 m)", unit="°C", conv="K_to_C", ratio=False,
         about="Air temperature 2 metres above the ground, like a weather-station thermometer.",
         caveat="MERRA-2 is a reanalysis (a model constrained by observations), not a direct thermometer reading.",
         keywords=["temperature", "temperatura", "warming", "heat", "hot", "calor", "aquec", "climate"]),
    dict(pattern=r"precipitation", key="precip", short="Rain", name="Precipitation", unit="mm/day", conv="mmhr_to_mmday", ratio=True,
         about="How much rain (and snow) falls on an area. Very variable from one year to the next.",
         caveat="Rainfall is noisy year to year, so a few extreme years can swing the trend. Check the period-sensitivity panel.",
         keywords=["rain", "precip", "chuva", "rainfall", "drought", "seca", "dry", "wet", "storm"]),
    dict(pattern=r"Evap", key="evap", short="Evapotranspiration", name="Evapotranspiration", unit="mm/day", conv="flux_to_mmday", ratio=True,
         about="Water returning to the air from soil, lakes and plants (evaporation + plant transpiration).",
         caveat="Modelled (GLDAS), not measured. In humid forests it may depend more on sunlight than on water supply. "
                "Rising and falling segments make a straight line a poor summary.",
         keywords=["evapo", "transpiration", "evaporation", "water loss", "plants"]),
    dict(pattern=r"SoilMoi(\d+)_(\d+)cm", key="soil", short="Soil moisture", name="Soil moisture", unit="mm of water", conv="none", ratio=True,
         about="Amount of water held in a layer of soil (kg/m² of water equals mm of water).",
         caveat="GLDAS is a land model driven by rainfall and other inputs, so it is not an independent measurement "
                "from precipitation. Changes in input sources over time can create artificial jumps.",
         keywords=["soil", "solo", "moisture", "umidade do solo", "drought", "seca", "groundwater"]),
    dict(pattern=r"OCEXTTAU", key="oc", short="Smoke", name="Organic carbon aerosol (smoke) AOT 550 nm", unit="AOT (unitless)", conv="none",
         ratio=True, about="How much sunlight is blocked by organic-carbon particles at 550 nm, mostly from burning "
                           "vegetation: a smoke indicator. 0 = clear air.",
         caveat="MERRA-2 aerosols are model-based and rely on fire-emission inventories. Smoke peaks in the dry season: "
                "compare the full series with the Aug–Oct peak before claiming that fires are increasing.",
         keywords=["smoke", "fumaça", "fumaca", "fire", "queimada", "burn", "aerosol", "organic carbon", "haze", "wildfire"]),
    dict(pattern=r"BCEXTTAU", key="bc", short="Soot", name="Black carbon aerosol AOT 550 nm", unit="AOT (unitless)", conv="none", ratio=True,
         about="Sunlight blocked by soot (black carbon) particles, from combustion and fires.",
         caveat="Model-based (MERRA-2), tied to emission inventories.",
         keywords=["black carbon", "soot", "fuligem", "fire", "smoke", "pollution"]),
    dict(pattern=r"DUEXTTAU", key="dust", short="Dust", name="Dust aerosol AOT 550 nm", unit="AOT (unitless)", conv="none", ratio=True,
         about="Sunlight blocked by mineral dust, e.g. dust crossing the Atlantic from Africa.",
         caveat="Model-based (MERRA-2).", keywords=["dust", "poeira", "sahara"]),
    dict(pattern=r"TOTEXTTAU|AODANA", key="aod", short="Aerosols", name="Total aerosol AOT 550 nm", unit="AOT (unitless)", conv="none", ratio=True,
         about="Total sunlight blocked by all aerosols (smoke, dust, sea salt, sulfate).",
         caveat="Model-based (MERRA-2).", keywords=["aerosol", "aot", "optical", "haze", "air quality"]),
    dict(pattern=r"QV2M", key="qv2m", short="Humidity", name="Specific humidity (2 m)", unit="g/kg", conv="kgkg_to_gkg", ratio=True,
         about="Grams of water vapour per kilogram of air at 2 m.", caveat="Reanalysis (MERRA-2).",
         keywords=["humidity", "umidade", "moist air", "vapor", "vapour"]),
    dict(pattern=r"SWGDN", key="sw", short="Sunlight", name="Sunlight reaching the surface", unit="W/m²", conv="none", ratio=True,
         about="Shortwave solar radiation arriving at the ground.", caveat="Reanalysis (MERRA-2).",
         keywords=["sun", "radiation", "solar", "radiação", "light"]),
    dict(pattern=r"CLDTOT", key="cloud", short="Clouds", name="Cloud fraction", unit="fraction", conv="none", ratio=True,
         about="Fraction of the sky covered by clouds (0 to 1).", caveat="Reanalysis (MERRA-2).",
         keywords=["cloud", "nuvem", "nuvens", "cloudiness"]),
]
CUSTOM = dict(key="custom", short="Data", name=None, unit="units", conv="none", ratio=False, about="", caveat="", keywords=[])

# Giovanni "shape" ids / bounding boxes -> readable names. Confirm shapes on the Giovanni map!
REGION_LABELS = {
    "watersheds/shp_8": "Amazon basin",
}


PRIMARY_REGION = "Amazon basin"  # shown first everywhere
# Rough extent for the map preview only (the exact Giovanni shape outline is not in the CSV).
REGION_HINT_BBOX = {"Amazon basin": (-79.0, -20.0, -49.0, 5.5)}


def spec_for(varid, title=""):
    for v in VARIABLES:
        m = re.search(v["pattern"], varid)
        if m:
            spec = dict(v)
            if v["key"] == "soil":
                spec["name"] = f"Soil moisture ({m.group(1)}–{m.group(2)} cm)"
            return spec
    spec = dict(CUSTOM)
    spec["name"] = (title or varid).replace("Time Series, Area-Averaged of ", "")[:80]
    spec["short"] = spec["name"][:24]
    return spec


def region_info(meta):
    """(key, label, bbox or None) from a Giovanni CSV header."""
    url = unquote(meta.get("URL to Reproduce Results", ""))
    shape = re.search(r"shape=([^&]+)", url)
    box = re.search(r"bbox=([^&]+)", url)
    bbox_s = (box.group(1) if box else meta.get("User Bounding Box", "")).replace(" ", "")
    bbox = None
    try:
        w, s, e, n = (float(x) for x in bbox_s.split(","))
        bbox = (w, s, e, n)
    except ValueError:
        pass
    if shape:
        key = shape.group(1)
        return key, REGION_LABELS.get(key, f"Custom shape ({key})"), None
    return bbox_s, REGION_LABELS.get(bbox_s, f"Box {bbox_s}"), bbox


def suggest(question):
    """Rule-based 'ask the detective': rank catalog variables by keyword hits (English or Portuguese)."""
    q = question.lower()
    scored = [(sum(k in q for k in v["keywords"]), v) for v in VARIABLES]
    return [v for sc, v in sorted(scored, key=lambda x: -x[0]) if sc > 0][:4]
