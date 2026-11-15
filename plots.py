"""Plotly figures (styled for a dark, colourful look)."""
import numpy as np
import plotly.graph_objects as go

from catalog import MONTH_NAMES
from trend_core import trend_band

RED = "#ff6b6b"
GREEN = "#4ade80"
COLORWAY = [GREEN, "#38bdf8", "#fbbf24", "#f472b6", "#a78bfa"]
COLORS = {"confirmed": "#22c55e", "indication": "#f59e0b", "none": "#94a3b8"}


def _style(fig, title=None, height=380, **kw):
    layout = dict(title=dict(text=title, font=dict(size=16)) if title else None, colorway=COLORWAY, height=height,
                  margin=dict(t=50 if title else 20, b=10, l=10, r=10), legend=dict(orientation="h", y=-0.18),
                  hovermode="x unified")
    layout.update(kw)  # callers may override e.g. hovermode
    fig.update_layout(**layout)
    return fig


def fig_series(s, unit, title="The raw data"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name="Monthly", line=dict(width=1), opacity=0.5))
    fig.add_trace(go.Scatter(x=s.index, y=s.rolling(12, center=True).mean(), mode="lines",
                             name="12-month average", line=dict(width=3)))
    fig.update_yaxes(title_text=unit)
    return _style(fig, title)


def fig_anomalies(res, unit, show_trend=True, title=None):
    y = res["y"]
    seasonal = res["mode"] == "seasonal"
    title = title or ("How each year compares with normal" if seasonal else "How each month compares with normal")
    fig = go.Figure()
    if show_trend:
        line, lo, hi = trend_band(res)
        fig.add_trace(go.Scatter(x=y.index, y=hi, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=y.index, y=lo, mode="lines", line=dict(width=0), fill="tonexty",
                                 name="95% range of the trend", fillcolor="rgba(255,107,107,0.22)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=y.index, y=y.values, mode="lines+markers" if seasonal else "lines", name="Difference from normal",
                             line=dict(width=1.5 if seasonal else 1), opacity=0.75))
    if show_trend:
        fig.add_trace(go.Scatter(x=y.index, y=line, mode="lines", name="Trend", line=dict(width=3.5, color=RED)))
    fig.add_hline(y=0, line_dash="dot", opacity=0.4)
    fig.update_yaxes(title_text=f"Above / below normal ({unit})")
    return _style(fig, title)


def fig_season(s, unit):
    clim = s.groupby(s.index.month).mean().reindex(range(1, 13))
    fig = go.Figure(go.Bar(x=MONTH_NAMES, y=clim.values))
    fig.update_yaxes(title_text=unit)
    return _style(fig, "The yearly cycle (what we subtract first)", height=300, hovermode="closest")


def fig_sensitivity(res, unit):
    runs = res["runs"] + [dict(end_year=int(res["end"][:4]), slope_dec=res["slope_dec"], ci_dec=res["ci_dec"],
                               p=res["mk"]["p"], cls=res["cls"])]
    fig = go.Figure(go.Scatter(
        x=[r["end_year"] for r in runs], y=[r["slope_dec"] for r in runs], mode="markers",
        marker=dict(size=12, color=[COLORS[r["cls"]] for r in runs]),
        error_y=dict(type="data", symmetric=False, array=[r["ci_dec"][1] - r["slope_dec"] for r in runs],
                     arrayminus=[r["slope_dec"] - r["ci_dec"][0] for r in runs]),
        customdata=[[r["p"], r["cls"]] for r in runs],
        hovertemplate="Data until %{x}<br>%{y:.3g} per decade<br>p = %{customdata[0]:.3g} (%{customdata[1]})<extra></extra>"))
    fig.add_hline(y=0, line_dash="dot", opacity=0.5)
    fig.update_xaxes(title_text="Last year of data used")
    fig.update_yaxes(title_text=f"{unit} per decade")
    return _style(fig, "If we stop the data earlier, does the answer change? (green = real, yellow = hint, grey = nothing)",
                  hovermode="closest")


def fig_overlay(ya, yb, la, lb):
    """Two series standardised (divided by their own spread) so different units can share one chart."""
    fig = go.Figure()
    for y, lab in ((ya, la), (yb, lb)):
        z = (y - y.mean()) / y.std()
        if len(z) > 60:
            z = z.rolling(12, center=True, min_periods=6).mean()
        fig.add_trace(go.Scatter(x=z.index, y=z.values, mode="lines", name=lab, line=dict(width=3)))
    fig.add_hline(y=0, line_dash="dot", opacity=0.4)
    fig.update_yaxes(title_text="Standardised (0 = normal)")
    return _style(fig, "Side by side, on the same scale")


def fig_heatmap(corr):
    labels = list(corr.columns)
    fig = go.Figure(go.Heatmap(z=corr.values, x=labels, y=labels, zmin=-1, zmax=1, colorscale="RdBu", reversescale=True,
                               text=np.round(corr.values, 2), texttemplate="%{text}"))
    fig.update_yaxes(autorange="reversed")
    return _style(fig, "Who moves with whom? (−1 = opposite, +1 = together)", height=420, hovermode="closest")


def region_map(ds):
    """Small static preview of a dataset's region (approximate extent)."""
    fig = go.Figure()
    box = ds.get("bbox") or ds.get("bbox_hint")
    if box:
        w, s, e, n = box
        fig.add_trace(go.Scattergeo(lon=[w, e, e, w, w], lat=[s, s, n, n, s], mode="lines", fill="toself",
                                    line=dict(color=RED, width=2), fillcolor="rgba(255,107,107,0.25)", showlegend=False))
        pad = max(6, 3 * max(e - w, n - s))
        clon, clat = (w + e) / 2, (s + n) / 2
    elif ds.get("point"):
        clat, clon = ds["point"]
        fig.add_trace(go.Scattergeo(lon=[clon], lat=[clat], mode="markers", marker=dict(size=10, color=RED), showlegend=False))
        pad = 12
    else:
        return None
    fig.update_geos(projection_type="natural earth", showland=True, landcolor="#e8e4d8", showcountries=True,
                    showocean=True, oceancolor="#dbe9f4", lonaxis_range=[clon - pad, clon + pad],
                    lataxis_range=[max(-90, clat - pad), min(90, clat + pad)])
    fig.update_layout(height=260, margin=dict(t=0, b=0, l=0, r=0))
    return fig


MAP_STYLE = "carto-darkmatter"


def spots_map(spots, selected):
    """Main map: clickable Amazon spots. Trace 0 = highlight ring (not clickable), trace 1 = the spots."""
    lats, lons, names = [s[1] for s in spots], [s[2] for s in spots], [s[0] for s in spots]
    fig = go.Figure()
    fig.add_trace(go.Scattermap(lat=[] if selected is None else [lats[selected]], lon=[] if selected is None else [lons[selected]],
                                mode="markers", hoverinfo="skip",
                                marker=dict(size=34, color=GREEN, opacity=0.35), showlegend=False))
    fig.add_trace(go.Scattermap(lat=lats, lon=lons, mode="markers+text", text=names, textposition="top center",
                                textfont=dict(size=12, color="#e8f5ec"), marker=dict(size=15, color=GREEN),
                                hovertemplate="<b>%{text}</b><br>Click to investigate<extra></extra>", showlegend=False,
                                selected=dict(marker=dict(size=18, color="#ffffff")),
                                unselected=dict(marker=dict(opacity=1))))
    fig.update_layout(map=dict(style=MAP_STYLE, center=dict(lat=-5.0, lon=-62.0), zoom=3.3), height=540,
                      margin=dict(t=0, b=0, l=0, r=0), clickmode="event+select")
    return fig
