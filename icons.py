"""Single place that maps variables to the custom pin images.
To change an icon, replace the PNG in assets/pins (same file name) or edit PIN_FILES below."""
import base64
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
# variable key (Giovanni catalog key or NASA POWER code) -> file name in assets/pins (without .png)
PIN_FILES = {
    "t2m": "temperature", "T2M": "temperature",
    "precip": "rain", "PRECTOTCORR": "rain",
    "evap": "evaporation",
    "soil": "soil",
    "oc": "smoke",
    "qv2m": "humidity", "RH2M": "humidity",
    "sw": "sunlight", "ALLSKY_SFC_SW_DWN": "sunlight",
    "WS2M": "wind",
}


@lru_cache(maxsize=None)
def _uri(path):
    p = Path(path)
    if not p.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def pin_uri(key):
    name = PIN_FILES.get(key)
    return _uri(str(ASSETS / "pins" / f"{name}.png")) if name else None


def pin_img(key, size=52):
    """<img> tag for a variable's pin, or '' when it has none."""
    uri = pin_uri(key)
    return f"<img class='pinimg' src='{uri}' width='{size}' height='{size}'/>" if uri else ""


def logo_uri():
    return _uri(str(ASSETS / "logo.png"))
