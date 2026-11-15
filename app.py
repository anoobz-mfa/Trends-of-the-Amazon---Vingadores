"""Trends of the Amazon: is the Amazon changing? (Streamlit, NASA Space Apps)"""
import hashlib
import re
from pathlib import Path

import pandas as pd
import streamlit as st

import plots
from icons import ASSETS, logo_uri, pin_img
from catalog import (CONVERSIONS, MONTH_NAMES, PRIMARY_REGION, REGION_HINT_BBOX, SEASONS, region_info, spec_for,
                     suggest)
from power_api import AMAZON_SPOTS, PARAMS, PRESETS, fetch_monthly
from trend_core import ALPHA, analyze_trend, fmt_p, read_giovanni_csv, remove_seasonality

st.set_page_config(page_title="Trends of the Amazon", page_icon=str(ASSETS / "favicon.png"), layout="wide")
DATA_DIR = Path(__file__).parent / "data"
LEGACY_PREFIXES = ("ref_montes_claros_",)

FRIENDLY = {  # class -> (title, subtitle, colour, short word for tables)
    "confirmed": ("Real trend", "The data back it up.", "#22c55e", "Real"),
    "indication": ("A hint", "Not strong enough to call it real yet.", "#f59e0b", "Hint"),
    "none": ("Nothing clear", "Looks like normal ups and downs.", "#94a3b8", "None"),
}

st.markdown("""
<style>
.hero{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;text-align:center;gap:20px;padding:10px 24px;border-radius:18px;margin-bottom:0;
  background:linear-gradient(120deg,#e4f2d2 0%,#cfe8b4 100%);color:#0f2d1a}
.hero img{height:82px;width:auto}
.hero h2{margin:0;font-size:1.5rem;color:#0f2d1a;padding:0}
.hero p{margin:2px 0 0 0;font-size:.98rem;color:#1c4429}
.vine{display:block;width:100%;height:34px;margin:2px 0 4px 0}
.askbar{display:flex;align-items:center;justify-content:center;gap:10px;font-weight:700;font-size:1.3rem;margin-bottom:4px}
.askbar .q{display:inline-flex;width:34px;height:34px;border-radius:10px;background:#5ce08a;color:#0b2a17;
  align-items:center;justify-content:center;font-size:1.2rem}
.pin .badge{display:inline-block;margin-left:6px;padding:0 8px;border-radius:999px;background:#5ce08a;color:#0b2a17;
  font-weight:700;font-size:.75rem}
.case{border-radius:16px;padding:16px 18px;margin-bottom:12px;background:rgba(255,255,255,.07);
  border:1px solid rgba(255,255,255,.14)}
.case .row{display:flex;align-items:center;gap:12px}
.case .top{font-size:1.05rem;font-weight:600}
.case .big{font-size:1.9rem;font-weight:700;margin:8px 0 0 0;line-height:1.1}
.case .sub{font-size:.85rem;opacity:.75;margin-bottom:8px}
.pill{display:inline-block;padding:3px 11px;border-radius:999px;font-weight:600;font-size:.82rem;color:#0b1511}
.tag{margin-top:8px;font-size:.8rem;color:#fbbf24}
.vcard{border-radius:16px;padding:14px 18px;margin:8px 0 14px 0;background:rgba(255,255,255,.05);
  border-left:7px solid #94a3b8}
.vcard .t{font-size:1.25rem;font-weight:700}
.vcard .s{opacity:.8;font-size:.95rem}
.vcard .h{margin-top:8px;font-size:1.05rem}
.pin{text-align:center;padding:10px 6px 6px 6px;border-radius:16px;border:2px solid transparent;
  background:rgba(255,255,255,.04);margin-bottom:6px;min-height:118px}
.pin.on{border-color:#4ade80;background:rgba(74,222,128,.13)}
.pin .pl{font-weight:600;font-size:.92rem;margin-top:4px}
.pin .pr{font-size:.72rem;opacity:.65}
.pin .noicon{width:52px;height:52px;margin:0 auto;border-radius:14px;background:rgba(255,255,255,.12);
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.1rem}
div.stButton > button{width:100%}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ data loading
@st.cache_data(show_spinner=False)
def _read_path(path, mtime):
    return read_giovanni_csv(path)


@st.cache_data(show_spinner=False)
def _read_bytes(name, data):
    return read_giovanni_csv(data)


@st.cache_data(show_spinner=False, ttl=86400)
def cached_power(lat, lon, params, y0, y1):
    return fetch_monthly(lat, lon, list(params), y0, y1)


@st.cache_data(show_spinner=False)
def cached_analysis(s, months, y0, y1):
    return analyze_trend(s, months=months, start_year=y0, end_year=y1)


@st.cache_data(show_spinner=False)
def quick_analysis(s, months, y0, y1):
    return analyze_trend(s, months=months, start_year=y0, end_year=y1, sensitivity=False)


def make_ds(source, s, meta, override=None):
    spec = spec_for(meta["variable"], meta.get("Title", ""))
    conv, unit = (override or (spec["conv"], spec["unit"]))
    rkey, rlabel, bbox = region_info(meta)
    s = CONVERSIONS[conv][1](s)
    sig = hashlib.md5(f"{meta['variable']}|{rkey}|{s.dropna().round(6).to_json(date_format='iso')}".encode()).hexdigest()
    return dict(id=sig[:10], source=source, series=s, meta=meta, spec=spec, name=spec["name"], short=spec["short"],
                unit=unit, ratio=spec["ratio"], about=spec["about"], caveat=spec["caveat"],
                key=spec["key"], origin="NASA Giovanni", region_key=rkey, region_label=rlabel, bbox=bbox, point=None,
                bbox_hint=REGION_HINT_BBOX.get(rlabel))


def load_datasets(uploads):
    out, seen, notes = [], set(), []
    for p in sorted(DATA_DIR.glob("*.csv")):
        if p.name.startswith(LEGACY_PREFIXES):  # old demo files that may linger after unzipping over an old copy
            continue
        try:
            s, meta = _read_path(str(p), p.stat().st_mtime)
            ds = make_ds(p.name, s, meta)
        except Exception as e:  # noqa: BLE001
            notes.append(f"Could not read {p.name}: {e}")
            continue
        if ds["id"] in seen:
            notes.append(f"Skipped duplicate file: {p.name}")
            continue
        seen.add(ds["id"])
        out.append(ds)
    for up in uploads or []:
        try:
            s, meta = _read_bytes(up.name, up.getvalue())
            spec = spec_for(meta["variable"], meta.get("Title", ""))
            override = None
            if spec["key"] == "custom":
                with st.sidebar.expander(f"Units for {up.name}"):
                    c = st.selectbox("Conversion", list(CONVERSIONS), format_func=lambda k: CONVERSIONS[k][0], key=f"c_{up.name}")
                    u = st.text_input("Unit name", spec["unit"], key=f"u_{up.name}")
                    override = (c, u)
            ds = make_ds(up.name, s, meta, override)
        except Exception as e:  # noqa: BLE001
            notes.append(f"Could not read {up.name}: {e}")
            continue
        if ds["id"] not in seen:
            seen.add(ds["id"])
            out.append(ds)
    out.sort(key=lambda d: (d["region_label"] != PRIMARY_REGION, d["region_label"], d["name"]))
    return out, notes


def label(ds):
    return f"{ds['name']} · {ds['region_label']}"


def pick(text, items, key, fmt=label):
    """Selectbox over dataset dicts, keyed by id (dicts holding Series are not valid widget options)."""
    by_id = {d["id"]: d for d in items}
    return by_id[st.selectbox(text, list(by_id), format_func=lambda i: fmt(by_id[i]), key=key)]


def pin_picker(items, key):
    """Row of custom pins used as a selector. Returns the chosen dataset."""
    ids = [d["id"] for d in items]
    sk = f"pinsel_{key}"
    cur = st.session_state.get(sk)
    if cur not in ids:
        cur = st.session_state[sk] = ids[0]
    for i in range(0, len(items), 6):
        chunk = items[i:i + 6]
        cols = st.columns(6 if len(items) > 5 else len(items))
        for col, d in zip(cols, chunk):
            on = d["id"] == cur
            img = pin_img(d["key"], 52) or f"<div class='noicon'>{d['short'][:2].upper()}</div>"
            with col:
                st.markdown(f"<div class='pin{' on' if on else ''}'>{img}<div class='pl'>{d['short']}</div>"
                            f"<div class='pr'>{d['region_label']}</div></div>", unsafe_allow_html=True)
                if st.button("Selected" if on else "Select", key=f"{key}_{d['id']}", disabled=on):
                    st.session_state[sk] = d["id"]
                    st.rerun()
    return next(d for d in items if d["id"] == cur)


def pin_multi(items, key, n=2):
    """Row of pins where exactly n can be chosen (shown as A, B). A new click replaces the older choice."""
    ids = [d["id"] for d in items]
    sk = f"multi_{key}"
    sel = [i for i in st.session_state.get(sk, []) if i in ids]
    sel = (sel + [i for i in ids if i not in sel])[:n]
    st.session_state[sk] = sel
    for i in range(0, len(items), 6):
        chunk = items[i:i + 6]
        cols = st.columns(6 if len(items) > 5 else len(items))
        for col, d in zip(cols, chunk):
            on = d["id"] in sel
            badge = f"<span class='badge'>{'AB'[sel.index(d['id'])]}</span>" if on else ""
            img = pin_img(d["key"], 52) or f"<div class='noicon'>{d['short'][:2].upper()}</div>"
            with col:
                st.markdown(f"<div class='pin{' on' if on else ''}'>{img}<div class='pl'>{d['short']}{badge}</div>"
                            f"<div class='pr'>{d['region_label']}</div></div>", unsafe_allow_html=True)
                if st.button("Chosen" if on else "Choose", key=f"{key}_{d['id']}", disabled=on):
                    st.session_state[sk] = sel[1:] + [d["id"]] if len(sel) >= n else sel + [d["id"]]
                    st.rerun()
    by_id = {d["id"]: d for d in items}
    return [by_id[i] for i in sel]


def common_years(items):
    ys = [d["series"].dropna().index.year for d in items]
    return int(max(y.min() for y in ys)), int(min(y.max() for y in ys))


def case_card_html(d, r):
    title, _, colr, _w = FRIENDLY[r["cls"]]
    arrow = "↗" if r["slope_dec"] > 0 else "↘"
    pct = f" · {r['pct_dec']:+.1f}%" if d["ratio"] and pd.notna(r["pct_dec"]) else ""
    tag = "<div class='tag'>Leans on recent years</div>" if r["fragile"] else ""
    big = f"{arrow} {r['slope_dec']:+.3g}" if r["cls"] != "none" else f"≈ {r['slope_dec']:+.2g}"
    return (f"<div class='case' style='border-top:5px solid {colr}'>"
            f"<div class='row'>{pin_img(d['key'], 44)}<div class='top'>{d['short']}</div></div><div class='big'>{big}</div>"
            f"<div class='sub'>{d['unit']} / decade{pct}</div>"
            f"<span class='pill' style='background:{colr}'>{title}</span>{tag}</div>")


# ------------------------------------------------------------------ small UI helpers
def season_label(months):
    if not months:
        return "all months"
    return ", ".join(MONTH_NAMES[m - 1] for m in months)


def luck(p):
    return "<0.01%" if p < 0.0001 else f"{p * 100:.2g}%"


def headline(ds, res):
    lo, hi = res["ci_dec"]
    d, u, nm = res["slope_dec"], ds["unit"], ds["short"]
    rng = f"likely between {lo:+.2g} and {hi:+.2g} {u}"
    if res["cls"] == "confirmed":
        return f"**{nm}** is **{'rising' if d > 0 else 'falling'}**: about **{d:+.3g} {u} per decade** ({rng})."
    if res["cls"] == "indication":
        return (f"**{nm}** might be {'rising' if d > 0 else 'falling'} ({d:+.2g} {u} per decade), "
                "but the data can't confirm it yet. More years could change this.")
    return f"**{nm}**: no clear change. The ups and downs look like normal variation."


def bold(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def verdict_card(ds, res):
    title, sub, col, _ = FRIENDLY[res["cls"]]
    tag = "<div class='tag'>Heads up: it leans on the last few years. Check “Go deeper”.</div>" if res["fragile"] else ""
    st.markdown(f"<div class='vcard' style='border-left-color:{col}'><div class='t'>{title}</div>"
                f"<div class='s'>{sub}</div><div class='h'>{bold(headline(ds, res))}</div>{tag}</div>",
                unsafe_allow_html=True)


def tiles(ds, res):
    lo, hi = res["ci_dec"]
    c1, c2, c3 = st.columns(3)
    pct = f"{res['pct_dec']:+.1f}% of the average per decade" if ds["ratio"] and pd.notna(res["pct_dec"]) else None
    c1.metric("How fast", f"{res['slope_dec']:+.3g} {ds['unit']}/decade", pct, delta_color="off")
    c2.metric("Likely range (95%)", f"{lo:.3g} to {hi:.3g}",
              help="We are 95% sure the true rate per decade lies in this range (already made wider to account for "
                   "neighbouring months being similar).")
    c3.metric("Odds it's just luck", luck(res["mk"]["p"]),
              help=f"p-value (Mann-Kendall, autocorrelation-corrected) {fmt_p(res['mk']['p'])}. If nothing were really changing, "
                   "a trend this strong would appear by pure chance about this often.")


def controls(ds, key):
    s = ds["series"].dropna()
    ymin, ymax = int(s.index.year.min()), int(s.index.year.max())
    c1, c2 = st.columns(2)
    y0, y1 = ymin, ymax
    if ymax > ymin:
        y0, y1 = c1.slider("Years", ymin, ymax, (ymin, ymax), key=f"{key}_per")
    season = c2.selectbox("Season", list(SEASONS), key=f"{key}_sea",
                          help="A season uses one average per year, which avoids the yearly cycle hiding or creating trends.")
    months = SEASONS[season]
    if months == "custom":
        picked = c2.multiselect("Months", MONTH_NAMES, default=["Jul", "Aug", "Sep"], key=f"{key}_mon")
        months = [MONTH_NAMES.index(m) + 1 for m in picked] or None
    return (tuple(months) if months else None), y0, y1


def analysis_panel(ds, key):
    """Condensed analysis: verdict, 3 numbers, one chart. Everything else sits under 'Go deeper'."""
    with st.expander("Filters: years and season"):
        months, y0, y1 = controls(ds, key)
    try:
        res = cached_analysis(ds["series"], months, y0, y1)
    except ValueError as e:
        st.warning(str(e))
        return None
    st.caption(f"{ds['name']} · {ds['region_label']} · {y0}–{y1} · {season_label(months)} · Source: {ds['origin']}")
    verdict_card(ds, res)
    tiles(ds, res)
    for w in res["warnings"]:
        st.warning(w)
    st.plotly_chart(plots.fig_anomalies(res, ds["unit"]), key=f"{key}_anom")
    unit = ds["unit"]
    with st.expander("Go deeper (for the curious)"):
        t1, t2, t3, t4, t5 = st.tabs(["In words", "Raw data", "Does the end year matter?", "The numbers", "Where and about"])
        with t1:
            st.markdown(f"> {res['text']}")
            if ds["about"]:
                st.markdown(f"**What is this?** {ds['about']}")
            if ds["caveat"]:
                st.info(f"**Detective's note:** {ds['caveat']}")
        with t2:
            st.plotly_chart(plots.fig_series(ds["series"].dropna(), unit), key=f"{key}_raw")
            if res["mode"] == "monthly":
                st.plotly_chart(plots.fig_season(ds["series"].dropna(), unit), key=f"{key}_cyc")
        with t3:
            if res["runs"]:
                st.plotly_chart(plots.fig_sensitivity(res, unit), key=f"{key}_sens")
                st.caption("Each dot repeats the whole analysis using data only up to that year. If the colour or sign "
                           "changes, the conclusion leans on a few recent years: report it with caution. The first dot is around 2014 "
                           "because each run needs at least 15 years of data; the data itself goes further.")
            else:
                st.caption("Not enough years to test this selection.")
        with t4:
            lo, hi = res["ci_dec"]
            st.dataframe(pd.DataFrame({
                "Method": ["Theil-Sen (robust)", "Linear regression, for comparison", "Mann-Kendall, corrected", "Mann-Kendall, uncorrected"],
                "Rate per decade": [f"{res['slope_dec']:+.4g}", f"{res['ols_dec']:+.4g}", "—", "—"],
                "95% range": [f"{lo:.3g} to {hi:.3g} (corrected)",
                              f"{res['ols_ci_dec'][0]:.3g} to {res['ols_ci_dec'][1]:.3g} (uncorrected)", "—", "—"],
                "p-value": ["—", f"{res['ols_p']:.2g}", f"{res['mk']['p']:.2g}", f"{res['mk_raw']['p']:.2g}"]}),
                hide_index=True)
            f = res["mk"]["autocorr_factor"]
            st.caption(f"Autocorrelation factor: {f:.2f} (1 = none). Neighbouring values are similar, so an uncorrected test is "
                       f"overconfident; the range above is widened by √factor = {f ** 0.5:.2f}×. "
                       f"Uncorrected Theil-Sen range: {res['ci_dec_raw'][0]:.3g} to {res['ci_dec_raw'][1]:.3g}. "
                       f"Samples used: {res['n']} ({'years' if res['mode'] == 'seasonal' else 'months'}).")
            st.download_button("Download the anomalies (CSV)", pd.DataFrame({"anomaly": res["y"]}).to_csv().encode(),
                               file_name="anomalies.csv", mime="text/csv", key=f"{key}_dl")
        with t5:
            if ds["meta"].get("resampled"):
                st.caption(ds["meta"]["resampled"])
            st.caption(f"Variable id: {ds['meta'].get('variable', '')} · Region: {ds['region_label']}")
            fig = plots.region_map(ds)
            if fig:
                st.plotly_chart(fig, key=f"{key}_reg")
                if ds.get("bbox_hint"):
                    st.caption("Approximate extent only; the exact basin outline is not stored in the CSV.")
    return res


# ------------------------------------------------------------------ sidebar + data
with st.sidebar:
    st.markdown("### Trends of the Amazon")
    st.caption("What is changing, where, how fast, and is it real?")
    with st.expander("Add your own data"):
        uploads = st.file_uploader("NASA Giovanni CSV files", type="csv", accept_multiple_files=True)
datasets, notes = load_datasets(uploads)
with st.sidebar:
    st.markdown(f"**Datasets loaded ({len(datasets)})**")
    for d in datasets:
        s_ = d["series"].dropna()
        st.caption(f"**{d['name']}** · {d['region_label']} · {s_.index[0].year}–{s_.index[-1].year} · {d['source']}")
    for n in notes:
        st.caption(n)
    st.markdown(f"Confidence level: **{int((1 - ALPHA) * 100)}%** (fixed)")
    st.caption("Data: NASA Giovanni (MERRA-2, GLDAS, GPM IMERG) and NASA POWER.")

regions = sorted({d["region_label"] for d in datasets})
VINE = """<svg class='vine' viewBox='0 0 1200 40' preserveAspectRatio='none' xmlns='http://www.w3.org/2000/svg'>
<path d='M0 20 C100 0,200 40,300 20 S500 0,600 20 S800 40,900 20 S1100 0,1200 20' stroke='#7be495' stroke-width='3' fill='none' stroke-linecap='round'/>
<path d='M0 20 C100 40,200 0,300 20 S500 40,600 20 S800 0,900 20 S1100 40,1200 20' stroke='#3f9b5c' stroke-width='3' fill='none' stroke-linecap='round'/>
<g stroke='#7be495' stroke-width='2.5' stroke-linecap='round'>
<path d='M300 20 L309 6'/><path d='M300 20 L291 34'/><path d='M600 20 L609 6'/><path d='M600 20 L591 34'/>
<path d='M900 20 L909 6'/><path d='M900 20 L891 34'/></g>
<g fill='#5ce08a'><ellipse cx='150' cy='11' rx='9' ry='4' transform='rotate(-30 150 11)'/>
<ellipse cx='450' cy='29' rx='9' ry='4' transform='rotate(30 450 29)'/>
<ellipse cx='750' cy='11' rx='9' ry='4' transform='rotate(-30 750 11)'/>
<ellipse cx='1050' cy='29' rx='9' ry='4' transform='rotate(30 1050 29)'/></g></svg>"""
EXAMPLES = ["Is it getting hotter?", "Is there less rain?", "Is there more smoke?", "Is the soil drying?"]
with st.container(border=True):
    st.markdown(f"""
<div class='hero'><img src='{logo_uri()}' alt='Trends of the Amazon'/>
<div><h2>Is the Amazon changing?</h2><p>Ask NASA data. Get an honest answer.</p></div></div>
{VINE}
""", unsafe_allow_html=True)
    st.markdown("<div class='askbar'><span class='q'>?</span> What would you like to know?</div>", unsafe_allow_html=True)
    query = st.pills("Pick a question", EXAMPLES, label_visibility="collapsed", key="ask_pill") or ""
    if query:
        hits = suggest(query)
        found = [d for v in hits for d in datasets if d["key"] == v["key"]][:3]
        if found:
            y0q, y1q = common_years(found)
            rs = []
            for d in found:
                try:
                    rs.append((d, cached_analysis(d["series"], None, y0q, y1q)))
                except ValueError:
                    pass
            cols = st.columns(len(rs)) if rs else []
            for col, (d, r) in zip(cols, rs):
                with col:
                    st.markdown(case_card_html(d, r), unsafe_allow_html=True)
                    st.markdown(bold(headline(d, r)))
            if rs:
                with st.expander(f"Open the full analysis: {rs[0][0]['short']}"):
                    analysis_panel(rs[0][0], "ask")


tab_ov, tab_inv, tab_cmp, tab_map, tab_learn = st.tabs(["Overview", "Investigate", "Compare", "Map", "Learn"])
st.session_state.setdefault("spots", {})

# ------------------------------------------------------------------ Map (runs first so Compare sees new spots)
with tab_map:
    st.markdown("### Pick a spot, ask the Earth a question")
    st.caption("Live data from NASA POWER for any point. Start with the Amazon, or type the coordinates of your own spot.")
    mode = st.segmented_control("Where?", ["Amazon spots", "My own spot"], default="Amazon spots", key="map_mode") \
        or "Amazon spots"
    spot = None
    if mode == "Amazon spots":
        sel = st.session_state.get("amz_sel")  # None until the user clicks a dot
        ev = st.plotly_chart(plots.spots_map(AMAZON_SPOTS, sel), key="amz_map", on_select="rerun", selection_mode="points")
        for p in ((ev or {}).get("selection", {}) or {}).get("points", []):
            idx = p.get("point_index", p.get("point_number"))
            if p.get("curve_number") == 1 and idx is not None and 0 <= idx < len(AMAZON_SPOTS):
                st.session_state["amz_sel"] = sel = int(idx)
        if sel is None:
            st.info("Click a dot on the map to see what NASA data says about that place.")
        else:
            nm, lat, lon, blurb = AMAZON_SPOTS[sel]
            st.markdown(f"**{nm}**: {blurb}  \n_Click another dot on the map to switch._")
            spot = (nm, lat, lon)
    else:
        cs = st.session_state.get("custom_spot")
        st.markdown("**Type the coordinates of your spot**")
        quick = st.selectbox("Quick picks", list(PRESETS), key="map_quick")
        lat0, lon0 = PRESETS[quick] or ((cs[1], cs[2]) if cs else (-3.12, -60.02))
        c1, c2 = st.columns(2)
        tlat = c1.number_input("Latitude", -90.0, 90.0, float(lat0), 0.01, key=f"clat_{quick}")
        tlon = c2.number_input("Longitude", -180.0, 180.0, float(lon0), 0.01, key=f"clon_{quick}")
        if st.button("Investigate this spot", type="primary"):
            nm_ = quick.split(" (")[0] if PRESETS[quick] else f"Pin {tlat:.2f}, {tlon:.2f}"
            st.session_state["custom_spot"] = (nm_, tlat, tlon)
            st.rerun()
        spot = st.session_state.get("custom_spot")
        if not spot:
            st.info("Set the coordinates and press the button.")
    if spot:
        nm, lat, lon = spot
        sid = "custom" if mode == "My own spot" else nm
        st.markdown(f"#### {nm} · {lat:.2f}°, {lon:.2f}°")
        data = None
        try:
            with st.spinner(f"Asking NASA POWER about {nm}…"):
                data = cached_power(round(lat, 4), round(lon, 4), tuple(PARAMS), 2000, 2025)
        except RuntimeError as e:
            st.error(str(e))
        if data:
            for k, s in data.items():
                pname, unit, ratio, about, short = PARAMS[k]
                st.session_state["spots"][f"spot:{sid}:{k}"] = dict(
                    id=f"spot:{sid}:{k}", series=s, unit=unit, name=pname, short=short, ratio=ratio, about=about,
                    caveat="NASA POWER blends satellite and MERRA-2 reanalysis data on a coarse grid: it describes the grid "
                           "cell around the point, not the exact spot.", key=k, meta={"variable": k}, spec={"key": k},
                    origin="NASA POWER (live)", region_label=f"{nm} (live)", region_key="point", bbox=None, point=(lat, lon), bbox_hint=None)
            st.markdown("**What do you want to know?**")
            chosen = pin_picker([st.session_state["spots"][f"spot:{sid}:{k}"] for k in data], f"map_{sid}")
            analysis_panel(chosen, f"map_{sid}_{chosen['key']}")
    with st.expander("About this map"):
        st.markdown("Dots are named places across the Amazon (approximate coordinates). Data comes from the NASA POWER API "
                    "(monthly, 2000–2025, no login). For averages over the whole basin, see **Overview**.")

all_ds = datasets  # Compare uses the Amazon-basin datasets only (map spots stay in the Map tab)

# ------------------------------------------------------------------ Overview
with tab_ov:
    if not datasets:
        st.info("No data loaded yet. Put Giovanni CSVs in the `data/` folder or add them in the sidebar.")
    else:
        reg = regions[0] if len(regions) == 1 else st.selectbox("Region", regions, key="ov_reg")
        items = [d for d in datasets if d["region_label"] == reg]
        st.markdown(f"### What is happening in the **{reg}**?")
        y0, y1 = common_years(items)
        st.caption(f"Source: NASA Giovanni (Amazon-basin averages). Every variable is analysed over the same years: {y0}–{y1}.")
        results = []
        for d in items:
            try:
                results.append((d, cached_analysis(d["series"], None, y0, y1)))
            except ValueError:
                pass
        n_conf = sum(r["cls"] == "confirmed" for _, r in results)
        n_frag = sum(r["cls"] == "confirmed" and r["fragile"] for _, r in results)
        st.markdown(f"**{n_conf} of {len(results)}** show a real trend" + (f", and **{n_frag}** of those lean on the last few years." if n_conf else "."))
        for i in range(0, len(results), 3):
            cols = st.columns(3)
            for col, (d, r) in zip(cols, results[i:i + 3]):
                col.markdown(case_card_html(d, r), unsafe_allow_html=True)
        with st.expander("Does it depend on the season?"):
            cols_s = [("All months", None), ("Dry season (Jul–Sep)", (7, 8, 9)),
                      ("Smoke peak (Aug–Oct)", (8, 9, 10)), ("Wet season (Feb–Apr)", (2, 3, 4))]
            rows = []
            for d, _ in results:
                row = {"Variable": d["short"]}
                for sname, mo in cols_s:
                    try:
                        q = quick_analysis(d["series"], mo, y0, y1)
                        row[sname] = f"{FRIENDLY[q['cls']][3]} {q['slope_dec']:+.3g}"
                    except ValueError:
                        row[sname] = "—"
                rows.append(row)
            st.dataframe(pd.DataFrame(rows), hide_index=True)
            st.caption("Rate per decade, with the verdict: Real trend, Hint, or None. A change can exist in one season and not in another.")
        with st.expander("Full table of numbers"):
            st.dataframe(pd.DataFrame([{
                "Variable": d["name"], "Rate per decade": f"{r['slope_dec']:+.3g} {d['unit']}",
                "% of average / decade": f"{r['pct_dec']:+.1f}%" if d["ratio"] else "—",
                "95% range": f"{r['ci_dec'][0]:.3g} to {r['ci_dec'][1]:.3g}", "p-value": fmt_p(r["mk"]["p"]).replace("= ", ""),
                "Verdict": FRIENDLY[r["cls"]][0],
                "Robust to the period?": "Sensitive" if r["fragile"] else "Robust"} for d, r in results]), hide_index=True)
        with st.expander("How to word these results honestly"):
            st.markdown("""
- **Real and robust**: say it, with the rate and its range.
- **Real but leans on recent years**: say "evidence of a trend that depends on the last few years".
- **A hint or nothing clear**: say "no confirmed trend yet". That does not prove nothing is happening.
- Model-based variables (MERRA-2, GLDAS) are not independent measurements and share inputs.
- Moving together (see **Compare**) suggests a hypothesis, not a cause.""")

# ------------------------------------------------------------------ Investigate
with tab_inv:
    if not datasets:
        st.info("No data loaded yet.")
    else:
        st.markdown("**Choose a variable**")
        analysis_panel(pin_picker(datasets, "inv"), "inv")

# ------------------------------------------------------------------ Compare
with tab_cmp:
    st.markdown("### Compare two things")
    if len(all_ds) < 2:
        st.info("Load at least two datasets to compare them.")
    else:
        st.caption("Source: NASA Giovanni. Compare any two Amazon-basin variables: do they move together, or against each other?")
        st.markdown("**Pick two** (the older choice is replaced when you pick a third)")
        a, b = pin_multi(all_ds, "cmp")
        season = st.selectbox("Season", list(SEASONS)[:-1], key="cmp_sea")
        months = SEASONS[season]
        ya0 = max(a["series"].dropna().index.year.min(), b["series"].dropna().index.year.min())
        ya1 = min(a["series"].dropna().index.year.max(), b["series"].dropna().index.year.max())
        st.caption(f"Compared over their shared years: {ya0}–{ya1}.")
        res = []
        cols = st.columns(2)
        for col, d in zip(cols, (a, b)):
            with col:
                try:
                    r = cached_analysis(d["series"], tuple(months) if months else None, int(ya0), int(ya1))
                except ValueError as e:
                    st.warning(f"{d['short']}: {e}")
                    r = None
                res.append(r)
                if r:
                    verdict_card(d, r)
        ra, rb = res
        if ra and rb:
            both = ra["cls"] == "confirmed" and rb["cls"] == "confirmed"
            if both and ra["slope_dec"] * rb["slope_dec"] < 0:
                st.success("**Opposite trends:** one is going up while the other goes down.")
            elif both:
                st.info("Both show a real trend, in the same direction.")
            elif ra["cls"] == "confirmed" or rb["cls"] == "confirmed":
                st.info("Only one of them shows a real trend.")
            else:
                st.info("Neither shows a real trend in this selection.")
            st.plotly_chart(plots.fig_overlay(ra["y"], rb["y"], f"{a['short']} · {a['region_label']}",
                                              f"{b['short']} · {b['region_label']}"), key="cmp_overlay")
            both_df = pd.concat([ra["y"], rb["y"]], axis=1, join="inner").dropna()
            if len(both_df) >= 8:
                rr = float(both_df.corr().iloc[0, 1])
                strength = ("barely related", "weakly", "moderately", "strongly", "very strongly")[
                    min(int(abs(rr) / 0.2), 4)]
                way = "move together" if rr > 0 else "move in opposite directions"
                st.metric("Do they move together?", f"r = {rr:+.2f}",
                          f"{strength} · {way}" if abs(rr) >= 0.2 else strength, delta_color="off")
                st.caption("Correlation is not causation. Models that share inputs can look related because of that.")
    groups = {}
    for d in datasets:
        groups.setdefault(d["region_label"], []).append(d)
    big = {k: v for k, v in groups.items() if len(v) >= 2}
    if big:
        with st.expander("Who moves with whom? (all pairs)"):
            reg = list(big)[0] if len(big) == 1 else st.selectbox("Region", list(big), key="con_reg")
            df = pd.DataFrame({d["short"]: remove_seasonality(d["series"].dropna()) for d in big[reg]}).dropna()
            if len(df) < 36:
                st.warning("Fewer than 36 shared months: too few for reliable correlations.")
            else:
                st.caption(f"Shared period: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} months).")
                st.plotly_chart(plots.fig_heatmap(df.corr()), key="cmp_heat")

# ------------------------------------------------------------------ Learn
with tab_learn:
    st.markdown("### How the detective works")
    with st.expander("The 4 steps", expanded=True):
        st.markdown("""
1. **Take out the yearly cycle.** Temperature and rain rise and fall every year. For each calendar month we subtract its long-term average, leaving **anomalies**: how far each month is above or below normal. For a *season* we use one average per year.
2. **Measure the speed (Theil-Sen).** The median of the slopes between all pairs of points. One extreme year can't drag it around.
3. **Test if it's real (Mann-Kendall).** Counts how often later values beat earlier ones. No bell-curve assumption needed.
4. **Correct for similar neighbours.** Months next to each other are alike, which makes a test overconfident. We correct it, and widen the confidence range by the same factor so range and p-value never disagree.""")
    with st.expander("What the verdicts mean"):
        st.markdown("""
- **Real trend**: p below 0.05 (95% confidence). **A hint**: p between 0.05 and 0.10. **Nothing clear**: p above 0.10.
- "Nothing clear" does **not** prove nothing is happening: sometimes the series is just too short.
- "Real" does **not** mean big: read the rate and its range.
- **Leans on recent years**: we re-run the analysis stopping 1 to many years earlier. If the verdict changes, a few extreme recent years are doing the work. Also flagged when a series changes direction midway.""")
    with st.expander("Words you'll meet"):
        st.markdown("""
- **Anomaly**: a value minus what is normal for that calendar month.
- **p-value / "odds it's just luck"**: how often a trend this strong would appear by chance if nothing were changing.
- **Confidence range (95%)**: the span where the true rate of change very likely sits.
- **Autocorrelation**: today's value resembles yesterday's, so the data points are not independent.
- **Reanalysis / model data (MERRA-2, GLDAS)**: physics models fed with observations. Useful, but not direct measurements.""")
    with st.expander("Limits"):
        st.markdown("""
- Only straight-line trends are estimated.
- Area averages describe a region, not a point; POWER describes a grid cell.
- Models share inputs, so agreement between them is weaker evidence than it looks.
- Correlation is not causation.""")
    with st.expander("Get your own data from NASA Giovanni"):
        st.markdown("""
1. Go to giovanni.gsfc.nasa.gov (free Earthdata account). 2. *Time Series, Area-Averaged*. 3. Pick dates and a region (box or shape).
4. Search the variable and tick **one monthly** variable. 5. **Plot Data**, then download the **CSV**. 6. Drop it in `data/` or add it in the sidebar.
Keep Giovanni's default units: the app converts them (K→°C, mm/hour→mm/day, kg m⁻² s⁻¹→mm/day). Use the same dates for variables you want to compare.""")
