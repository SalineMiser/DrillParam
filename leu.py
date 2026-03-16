"""
Drilling Rig Time-Series Analysis Dashboard
=============================================
Paste your tab-separated rig data into the text area, or upload a file.
Columns expected: RigTime | BitDepth (m) | HookLoad (tonne) | BlockPosition (m)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Drilling Rig Analysis",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] { font-family: "Inter", "Segoe UI", sans-serif; }
.stApp                      { background-color: #f0f4f8; }

[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #d1dbe8;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div  { color: #344055 !important; }
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3   { color: #1a2535 !important; font-weight: 600 !important; }

[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #d1dbe8;
    border-radius: 14px;
    padding: 16px 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.06);
}
[data-testid="stMetricValue"] { color: #1558a0 !important; font-size: 1.55rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 0.82rem !important; }

.dash-header {
    background: linear-gradient(120deg, #ffffff 0%, #e8f0fa 100%);
    border: 1px solid #d1dbe8;
    border-radius: 16px;
    padding: 22px 32px;
    margin-bottom: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.dash-header h1 { color: #1a2535; font-size: 1.85rem; margin: 0; font-weight: 700; }
.dash-header p  { color: #64748b; margin: 5px 0 0; font-size: 0.92rem; }

.sec-label {
    color: #1a2535;
    font-size: 1rem;
    font-weight: 600;
    padding-bottom: 6px;
    border-bottom: 2px solid #d1dbe8;
    margin-bottom: 14px;
}

.badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:0.76rem; font-weight:600; }
.b-drill  { background:#dcfce7; color:#166534; border:1px solid #86efac; }
.b-trip   { background:#dbeafe; color:#1e40af; border:1px solid #93c5fd; }
.b-conn   { background:#fef9c3; color:#854d0e; border:1px solid #fde047; }
.b-hoist  { background:#ede9fe; color:#5b21b6; border:1px solid #c4b5fd; }
.b-static { background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; }

.etable { width:100%; border-collapse:collapse; font-size:0.82rem; color:#334155; }
.etable th {
    background:#f8fafc; color:#64748b; padding:9px 13px;
    text-align:left; border-bottom:2px solid #d1dbe8;
    font-weight:600; text-transform:uppercase; font-size:0.71rem; letter-spacing:.05em;
}
.etable td { padding:8px 13px; border-bottom:1px solid #e8eef5; vertical-align:middle; }
.etable tr:hover td { background:#f8fafc; }

[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #d1dbe8 !important;
    border-radius: 12px;
}

.stTabs [data-baseweb="tab-list"] {
    background:#ffffff; border-radius:10px; border:1px solid #d1dbe8; gap:4px;
}
.stTabs [data-baseweb="tab"]   { color:#64748b; font-weight:500; }
.stTabs [aria-selected="true"] { color:#1558a0 !important; border-bottom:2px solid #1558a0 !important; }

.stButton>button {
    background:#ffffff; color:#344055;
    border:1px solid #d1dbe8; border-radius:8px; font-weight:500;
}
.stButton>button:hover { background:#e8f0fa; border-color:#1558a0; color:#1558a0; }

.stTextArea textarea { background:#ffffff !important; border-color:#d1dbe8 !important; color:#1a2535 !important; }

::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:#f1f5f9; }
::-webkit-scrollbar-thumb { background:#c0ccd8; border-radius:4px; }
</style>
""", unsafe_allow_html=True)

# ─── Activity Config ───────────────────────────────────────────────────────────
ACT_CFG = {
    "Drilling":       {"color": "#16a34a", "badge": "b-drill"},
    "Tripping In":    {"color": "#2563eb", "badge": "b-trip"},
    "Tripping Out":   {"color": "#0891b2", "badge": "b-trip"},
    "Connection":     {"color": "#d97706", "badge": "b-conn"},
    "Hoisting":       {"color": "#7c3aed", "badge": "b-hoist"},
    "Slips / Static": {"color": "#64748b", "badge": "b-static"},
}

# ─── Shared Plotly theme ───────────────────────────────────────────────────────
LIGHT = dict(
    paper="#ffffff", plot="#fafbfd",
    grid="#e4eaf2",  line="#d1dbe8",
    tick="#64748b",  title="#374151",
    hover_bg="#ffffff", hover_border="#d1dbe8", hover_font="#1a2535",
)


def ax(title="", rev=False):
    d = dict(
        title_text=title,
        title_font=dict(color=LIGHT["title"], size=12),
        tickfont=dict(color=LIGHT["tick"], size=11),
        gridcolor=LIGHT["grid"], gridwidth=1,
        linecolor=LIGHT["line"], zeroline=False, showgrid=True,
    )
    if rev:
        d["autorange"] = "reversed"
    return d


def base_layout(height, margin=None):
    m = margin or dict(l=70, r=150, t=52, b=50)
    return dict(
        height=height,
        paper_bgcolor=LIGHT["paper"], plot_bgcolor=LIGHT["plot"],
        font=dict(family="Inter, sans-serif", color=LIGHT["title"]),
        legend=dict(
            orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.01,
            font=dict(size=11, color="#374151"),
            bgcolor="rgba(255,255,255,0.95)", bordercolor="#d1dbe8", borderwidth=1,
        ),
        margin=m,
        hovermode="y unified",
        hoverlabel=dict(bgcolor=LIGHT["hover_bg"], bordercolor=LIGHT["hover_border"],
                        font=dict(color=LIGHT["hover_font"], size=12)),
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────
def classify(hl, bd_diff, hl_trip, hl_conn, depth_thr):
    if hl > hl_trip:
        if bd_diff < -0.3:  return "Tripping In"
        if bd_diff >  0.3:  return "Tripping Out"
        return "Hoisting"
    if hl > hl_conn:
        return "Connection"
    if bd_diff < -depth_thr:
        return "Drilling"
    return "Slips / Static"


def add_activities(df, hl_trip, hl_conn, depth_thr):
    acts = []
    for i in range(len(df)):
        dd = df["BitDepth"].iloc[i] - df["BitDepth"].iloc[i-1] if i > 0 else 0
        acts.append(classify(df["HookLoad"].iloc[i], dd, hl_trip, hl_conn, depth_thr))
    df = df.copy()
    df["Activity"] = acts
    return df


def _ev(df, act, s, e):
    return {
        "activity":     act,
        "start_time":   df["RigTime"].iloc[s],
        "end_time":     df["RigTime"].iloc[e],
        "duration_min": (df["RigTime"].iloc[e] - df["RigTime"].iloc[s]).total_seconds() / 60,
        "depth_start":  df["BitDepth"].iloc[s],
        "depth_end":    df["BitDepth"].iloc[e],
        "avg_hl":       df["HookLoad"].iloc[s:e+1].mean(),
        "max_hl":       df["HookLoad"].iloc[s:e+1].max(),
    }


def detect_events(df):
    events, prev, start = [], df["Activity"].iloc[0], 0
    for i in range(1, len(df)):
        if df["Activity"].iloc[i] != prev:
            events.append(_ev(df, prev, start, i - 1))
            prev, start = df["Activity"].iloc[i], i
    events.append(_ev(df, prev, start, len(df) - 1))
    return pd.DataFrame(events)


def parse_data(text):
    pat = re.compile(
        r"(\d{1,2}[.\-/]\w{3,9}[.\-/]\d{4})\s+(\d{2}:\d{2}:\d{2})"
        r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
    )
    rows = []
    for line in text.strip().splitlines():
        m = pat.search(line.strip())
        if m:
            ds, ts, bd, hl, bp = m.groups()
            ds = ds.replace(".", " ").replace("-", " ").replace("/", " ")
            try:
                rows.append({
                    "RigTime":  pd.to_datetime(f"{ds} {ts}", dayfirst=True),
                    "BitDepth": float(bd),
                    "HookLoad": float(hl),
                    "BlockPos": float(bp),
                })
            except Exception:
                pass
    if not rows:
        raise ValueError("No rows parsed — check format: Date Time BitDepth HookLoad BlockPos")
    return (pd.DataFrame(rows)
              .sort_values("RigTime")
              .drop_duplicates("RigTime")
              .reset_index(drop=True))


# ══════════════════════════════════════════════════════════════════════════════
# CHART A — Time-Series (3 horizontal panels)
# ══════════════════════════════════════════════════════════════════════════════
def build_timeseries(df, events_df, show_depth, show_hl, show_bp,
                     show_bands, show_conn_mark, ds_n, height):
    step = max(1, len(df) // ds_n)
    ds   = df.iloc[::step].copy()

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.50, 0.28, 0.22],
        vertical_spacing=0.025,
    )

    if show_bands:
        for _, ev in events_df.iterrows():
            c = ACT_CFG.get(ev["activity"], ACT_CFG["Slips / Static"])["color"]
            for r in [1, 2, 3]:
                fig.add_vrect(x0=ev["start_time"], x1=ev["end_time"],
                              fillcolor=c, opacity=0.08, line_width=0, row=r, col=1)

    if show_depth:
        fig.add_trace(go.Scatter(
            x=ds["RigTime"], y=ds["BitDepth"],
            name="Bit Depth (m)",
            line=dict(color="#1558a0", width=2.5),
            fill="tozeroy", fillcolor="rgba(21,88,160,0.07)",
            hovertemplate="<b>%{x|%H:%M:%S}</b><br>Depth: %{y:.2f} m<extra></extra>",
        ), row=1, col=1)
        for _, ev in events_df[events_df["activity"] == "Tripping In"].iterrows():
            mid = ev["start_time"] + (ev["end_time"] - ev["start_time"]) / 2
            fig.add_annotation(
                x=mid, y=(ev["depth_start"] + ev["depth_end"]) / 2,
                text="▼ Trip In", showarrow=False,
                font=dict(size=9, color="#1e40af"),
                bgcolor="rgba(219,234,254,0.90)", bordercolor="#93c5fd",
                borderwidth=1, borderpad=3, row=1, col=1)
        for _, ev in events_df[events_df["activity"] == "Tripping Out"].iterrows():
            mid = ev["start_time"] + (ev["end_time"] - ev["start_time"]) / 2
            fig.add_annotation(
                x=mid, y=(ev["depth_start"] + ev["depth_end"]) / 2,
                text="▲ Trip Out", showarrow=False,
                font=dict(size=9, color="#0e7490"),
                bgcolor="rgba(207,250,254,0.90)", bordercolor="#67e8f9",
                borderwidth=1, borderpad=3, row=1, col=1)

    if show_hl:
        fig.add_trace(go.Scatter(
            x=ds["RigTime"], y=ds["HookLoad"],
            name="Hook Load (t)",
            line=dict(color="#d97706", width=2),
            hovertemplate="<b>%{x|%H:%M:%S}</b><br>HL: %{y:.2f} t<extra></extra>",
        ), row=2, col=1)
        fig.add_hrect(y0=35, y1=ds["HookLoad"].max() * 1.05,
                      fillcolor="rgba(217,119,6,0.05)", line_width=0, row=2, col=1)
        fig.add_hline(y=35, line_dash="dot", line_color="#d97706", line_width=1.2,
                      opacity=0.7, row=2, col=1,
                      annotation_text="35 t",
                      annotation_font=dict(color="#d97706", size=10))
        if show_conn_mark:
            conn_ev = events_df[events_df["activity"] == "Connection"]
            if not conn_ev.empty:
                ctimes = conn_ev["start_time"].tolist()
                chl = [df.loc[df["RigTime"] >= t, "HookLoad"].iloc[0]
                       if len(df.loc[df["RigTime"] >= t]) > 0 else 0 for t in ctimes]
                fig.add_trace(go.Scatter(
                    x=ctimes, y=chl, mode="markers", name="Connection",
                    marker=dict(symbol="diamond", size=9, color="#d97706",
                                line=dict(color="#ffffff", width=1.5)),
                    hovertemplate="<b>Connection</b><br>%{x|%H:%M:%S}<br>HL: %{y:.1f} t<extra></extra>",
                ), row=2, col=1)

    if show_bp:
        fig.add_trace(go.Scatter(
            x=ds["RigTime"], y=ds["BlockPos"],
            name="Block Pos (m)",
            line=dict(color="#16a34a", width=2),
            fill="tozeroy", fillcolor="rgba(22,163,74,0.07)",
            hovertemplate="<b>%{x|%H:%M:%S}</b><br>Block: %{y:.2f} m<extra></extra>",
        ), row=3, col=1)

    fig.update_yaxes(**ax("Bit Depth (m)", rev=True), row=1, col=1)
    fig.update_yaxes(**ax("Hook Load (t)"),            row=2, col=1)
    fig.update_yaxes(**ax("Block Pos (m)"),            row=3, col=1)

    xc = dict(showgrid=True, gridcolor=LIGHT["grid"],
              tickfont=dict(color=LIGHT["tick"], size=10), linecolor=LIGHT["line"])
    fig.update_xaxes(**xc, tickformat="%H:%M", row=1, col=1)
    fig.update_xaxes(**xc, tickformat="%H:%M", row=2, col=1)
    fig.update_xaxes(**xc, tickformat="%H:%M\n%d %b",
                     rangeslider=dict(visible=True, thickness=0.04,
                                      bgcolor="#f0f4f8", bordercolor="#d1dbe8"),
                     row=3, col=1)

    fig.update_layout(
        height=height,
        paper_bgcolor=LIGHT["paper"], plot_bgcolor=LIGHT["plot"],
        font=dict(family="Inter, sans-serif", color=LIGHT["title"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.008, xanchor="left", x=0,
                    font=dict(size=12, color="#374151"),
                    bgcolor="rgba(255,255,255,0.95)", bordercolor="#d1dbe8", borderwidth=1),
        margin=dict(l=65, r=20, t=36, b=70),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=LIGHT["hover_bg"], bordercolor=LIGHT["hover_border"],
                        font=dict(color=LIGHT["hover_font"], size=12)),
        xaxis=dict(showspikes=True, spikecolor="#c0ccd8", spikethickness=1, spikedash="dot"),
        xaxis2=dict(showspikes=True, spikecolor="#c0ccd8", spikethickness=1),
        xaxis3=dict(showspikes=True, spikecolor="#c0ccd8", spikethickness=1),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# CHART B — Depth Track  (Y = Bit Depth inverted,  X = HL | BP)
# ══════════════════════════════════════════════════════════════════════════════
def build_depth_track(df, events_df, height):
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True,
        column_widths=[0.5, 0.5], horizontal_spacing=0.05,
        subplot_titles=["Hook Load (t)  ←  vs  →  Bit Depth",
                        "Block Position (m)  ←  vs  →  Bit Depth"],
    )

    d_min = df["BitDepth"].min()
    d_max = df["BitDepth"].max()

    # horizontal activity bands across both columns
    for _, ev in events_df.iterrows():
        c  = ACT_CFG.get(ev["activity"], ACT_CFG["Slips / Static"])["color"]
        d0 = min(ev["depth_start"], ev["depth_end"])
        d1 = max(ev["depth_start"], ev["depth_end"])
        if d1 - d0 < 0.05:
            d0 -= 0.15; d1 += 0.15
        for col in [1, 2]:
            fig.add_hrect(y0=d0, y1=d1,
                          fillcolor=c, opacity=0.10, line_width=0, row=1, col=col)

    # Hook Load vs Depth
    fig.add_trace(go.Scatter(
        x=df["HookLoad"], y=df["BitDepth"],
        mode="lines", name="Hook Load (t)",
        line=dict(color="#d97706", width=1.8),
        fill="tozerox", fillcolor="rgba(217,119,6,0.09)",
        hovertemplate="Depth: %{y:.2f} m<br>Hook Load: %{x:.2f} t<extra></extra>",
    ), row=1, col=1)
    fig.add_vline(x=35, line_dash="dot", line_color="#d97706",
                  line_width=1.2, opacity=0.65, row=1, col=1)
    fig.add_annotation(x=35, y=d_min - 1, text="35 t", showarrow=False,
                       font=dict(size=9, color="#d97706"), yanchor="bottom", row=1, col=1)

    # Block Position vs Depth
    fig.add_trace(go.Scatter(
        x=df["BlockPos"], y=df["BitDepth"],
        mode="lines", name="Block Position (m)",
        line=dict(color="#16a34a", width=1.8),
        fill="tozerox", fillcolor="rgba(22,163,74,0.09)",
        hovertemplate="Depth: %{y:.2f} m<br>Block Pos: %{x:.2f} m<extra></extra>",
    ), row=1, col=2)

    # Activity legend entries (dummy traces)
    for act, cfg in ACT_CFG.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=11, color=cfg["color"], symbol="square"),
            name=act, showlegend=True,
        ), row=1, col=1)

    # Y axes — bit depth, inverted (deeper = down the page)
    y_range = [d_max + 8, d_min - 8]
    fig.update_yaxes(**ax("Bit Depth (m)", rev=False),
                     range=y_range, autorange=False, row=1, col=1)
    fig.update_yaxes(tickfont=dict(color=LIGHT["tick"], size=11),
                     gridcolor=LIGHT["grid"], linecolor=LIGHT["line"],
                     zeroline=False, showgrid=True,
                     range=y_range, autorange=False, row=1, col=2)

    fig.update_xaxes(**ax("Hook Load (t)"),       row=1, col=1)
    fig.update_xaxes(**ax("Block Position (m)"),  row=1, col=2)

    fig.update_layout(**base_layout(height))
    fig.update_layout(hovermode="y unified")
    for ann in fig.layout.annotations:
        ann.font = dict(size=13, color="#374151", family="Inter, sans-serif")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# CHART C — Time Track  (Y = Rig Time earliest→latest top→bottom,  X = HL | BP)
# ══════════════════════════════════════════════════════════════════════════════
def build_time_track(df, events_df, height):
    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True,
        column_widths=[0.5, 0.5], horizontal_spacing=0.05,
        subplot_titles=["Hook Load (t)  ←  vs  →  Rig Time",
                        "Block Position (m)  ←  vs  →  Rig Time"],
    )

    t_min = df["RigTime"].min()
    t_max = df["RigTime"].max()

    # horizontal activity bands (time interval bands)
    for _, ev in events_df.iterrows():
        c = ACT_CFG.get(ev["activity"], ACT_CFG["Slips / Static"])["color"]
        for col in [1, 2]:
            fig.add_hrect(y0=ev["start_time"], y1=ev["end_time"],
                          fillcolor=c, opacity=0.10, line_width=0, row=1, col=col)

    # Hook Load vs Time
    fig.add_trace(go.Scatter(
        x=df["HookLoad"], y=df["RigTime"],
        mode="lines", name="Hook Load (t)",
        line=dict(color="#d97706", width=1.8),
        fill="tozerox", fillcolor="rgba(217,119,6,0.09)",
        hovertemplate="%{y|%H:%M:%S}<br>Hook Load: %{x:.2f} t<extra></extra>",
    ), row=1, col=1)
    fig.add_vline(x=35, line_dash="dot", line_color="#d97706",
                  line_width=1.2, opacity=0.65, row=1, col=1)
    fig.add_annotation(x=35, y=t_min, text="35 t", showarrow=False,
                       font=dict(size=9, color="#d97706"), yanchor="bottom", row=1, col=1)

    # Block Position vs Time
    fig.add_trace(go.Scatter(
        x=df["BlockPos"], y=df["RigTime"],
        mode="lines", name="Block Position (m)",
        line=dict(color="#16a34a", width=1.8),
        fill="tozerox", fillcolor="rgba(22,163,74,0.09)",
        hovertemplate="%{y|%H:%M:%S}<br>Block Pos: %{x:.2f} m<extra></extra>",
    ), row=1, col=2)

    # Activity legend entries (dummy traces)
    for act, cfg in ACT_CFG.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=11, color=cfg["color"], symbol="square"),
            name=act, showlegend=True,
        ), row=1, col=1)

    # Y axes — time, earliest at top (autorange reversed = top is smallest = earliest)
    yax = dict(
        tickfont=dict(color=LIGHT["tick"], size=10),
        tickformat="%H:%M\n%d %b",
        gridcolor=LIGHT["grid"], linecolor=LIGHT["line"],
        zeroline=False, showgrid=True,
        autorange="reversed",
    )
    fig.update_yaxes(**yax,
                     title_text="Rig Time",
                     title_font=dict(color=LIGHT["title"], size=12),
                     row=1, col=1)
    fig.update_yaxes(**yax, row=1, col=2)

    fig.update_xaxes(**ax("Hook Load (t)"),       row=1, col=1)
    fig.update_xaxes(**ax("Block Position (m)"),  row=1, col=2)

    fig.update_layout(**base_layout(height))
    fig.update_layout(hovermode="y unified")
    for ann in fig.layout.annotations:
        ann.font = dict(size=13, color="#374151", family="Inter, sans-serif")
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# CHART D — Activity Donut
# ══════════════════════════════════════════════════════════════════════════════
def build_donut(events_df):
    agg    = (events_df.groupby("activity")["duration_min"].sum()
              .reset_index().sort_values("duration_min", ascending=False))
    colors = [ACT_CFG.get(a, ACT_CFG["Slips / Static"])["color"] for a in agg["activity"]]
    total  = agg["duration_min"].sum()
    fig = go.Figure(go.Pie(
        labels=agg["activity"], values=agg["duration_min"].round(1),
        hole=0.62,
        marker=dict(colors=colors, line=dict(color="#f0f4f8", width=3)),
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value:.1f} min (%{percent})<extra></extra>",
        textfont=dict(size=11),
    ))
    fig.update_layout(
        annotations=[dict(text=f"<b>{total:.0f}</b><br>min",
                          x=0.5, y=0.5, font_size=17, font_color="#1a2535",
                          showarrow=False)],
        paper_bgcolor=LIGHT["paper"], plot_bgcolor=LIGHT["paper"],
        font=dict(color="#374151"),
        legend=dict(font=dict(size=11, color="#374151"), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=270,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# CHART E — ROP
# ══════════════════════════════════════════════════════════════════════════════
def build_rop(df):
    drill = df[df["Activity"] == "Drilling"].sort_values("RigTime").reset_index(drop=True)
    if drill.empty:
        return None
    diffs = drill["BitDepth"].diff().abs()
    times = drill["RigTime"].diff().dt.total_seconds() / 3600
    rop   = (diffs / times.replace(0, np.nan)).rolling(5, min_periods=1).mean().clip(0, 200)
    fig = go.Figure(go.Scatter(
        x=drill["RigTime"], y=rop,
        fill="tozeroy", fillcolor="rgba(22,163,74,0.12)",
        line=dict(color="#16a34a", width=2),
        hovertemplate="<b>%{x|%H:%M:%S}</b><br>ROP: %{y:.1f} m/hr<extra></extra>",
    ))
    fig.update_layout(
        height=200,
        paper_bgcolor=LIGHT["paper"], plot_bgcolor=LIGHT["plot"],
        font=dict(color="#374151"),
        xaxis=dict(gridcolor=LIGHT["grid"], tickfont=dict(color=LIGHT["tick"], size=10),
                   tickformat="%H:%M", linecolor=LIGHT["line"]),
        yaxis=dict(gridcolor=LIGHT["grid"], tickfont=dict(color=LIGHT["tick"], size=10),
                   title="m/hr", title_font=dict(color=LIGHT["title"], size=11),
                   linecolor=LIGHT["line"]),
        margin=dict(l=55, r=10, t=10, b=40),
        showlegend=False,
    )
    return fig


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Controls")
    st.markdown("---")
    st.markdown("### 👁 Visibility")
    show_depth = st.toggle("Bit Depth",         value=True)
    show_hl    = st.toggle("Hook Load",          value=True)
    show_bp    = st.toggle("Block Position",     value=True)
    show_bands = st.toggle("Activity Bands",     value=True)
    show_conn  = st.toggle("Connection Markers", value=True)

    st.markdown("---")
    st.markdown("### 📐 Chart Size")
    ts_height    = st.slider("Time-Series height (px)",       500, 1600, 1000, 50)
    track_height = st.slider("Depth / Time Track height (px)", 700, 2400, 1100, 50)
    ds_n         = st.slider("Max points (perf)",              500, 5000, 2000, 100)

    st.markdown("---")
    st.markdown("### 🎯 Thresholds")
    hl_trip  = st.number_input("Tripping HL (t)",   value=35.0, step=0.5)
    hl_conn  = st.number_input("Connection HL (t)", value=10.0, step=0.5)
    dd_thr   = st.number_input("Drilling depth Δ (m)", value=0.05, step=0.01)

    st.markdown("---")
    export_ev = st.checkbox("Enable CSV downloads", value=True)
    st.markdown(
        "<div style='color:#94a3b8;font-size:0.73rem;text-align:center;margin-top:12px'>"
        "Drilling Rig Analysis v2.0</div>", unsafe_allow_html=True)


# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class='dash-header'>
  <h1>🛢️ Drilling Rig Time-Series Analysis</h1>
  <p>Bit Depth · Hook Load · Block Position · Activity Classification · Depth Tracks · ROP</p>
</div>""", unsafe_allow_html=True)

# ─── Data Input ───────────────────────────────────────────────────────────────
t_paste, t_file = st.tabs(["📋  Paste Data", "📁  Upload File"])
raw_text = None

with t_paste:
    pasted = st.text_area(
        "Paste rig data (tab- or space-separated)",
        height=140,
        placeholder="15.Mar.2026 19:30:00\t1879.70\t3.50\t1.40\n...",
        help="Format: DD.Mon.YYYY HH:MM:SS  BitDepth  HookLoad  BlockPos",
    )
    if pasted.strip():
        raw_text = pasted

with t_file:
    up = st.file_uploader("Upload .txt / .csv / .tsv", type=["txt", "csv", "tsv"])
    if up:
        raw_text = up.read().decode("utf-8", errors="ignore")

# ─── Demo data fallback ───────────────────────────────────────────────────────
DEMO = """15.Mar.2026 19:30:00\t1879.70\t3.50\t1.40
15.Mar.2026 19:30:05\t1879.70\t3.50\t1.40
15.Mar.2026 19:31:00\t1879.70\t3.61\t1.40
15.Mar.2026 19:41:04\t1879.70\t13.79\t1.80
15.Mar.2026 19:41:09\t1879.60\t44.82\t2.20
15.Mar.2026 19:41:19\t1879.75\t44.41\t2.15
15.Mar.2026 19:41:24\t1880.13\t32.93\t1.70
15.Mar.2026 19:41:34\t1880.18\t16.29\t1.40
15.Mar.2026 19:41:44\t1880.18\t11.83\t1.30
15.Mar.2026 19:44:44\t1880.18\t12.54\t1.30
15.Mar.2026 19:44:54\t1880.18\t15.94\t1.47
15.Mar.2026 19:45:09\t1880.10\t26.33\t1.70
15.Mar.2026 19:45:19\t1879.90\t34.67\t1.95
15.Mar.2026 19:45:44\t1880.03\t29.87\t1.80
15.Mar.2026 19:46:04\t1880.10\t28.74\t1.80
15.Mar.2026 19:46:34\t1880.10\t4.32\t1.40
15.Mar.2026 19:46:39\t1880.10\t3.50\t1.40
15.Mar.2026 19:53:38\t1880.10\t3.26\t1.55
15.Mar.2026 19:53:43\t1880.10\t12.22\t1.77
15.Mar.2026 19:53:48\t1880.10\t28.21\t1.80
15.Mar.2026 19:54:13\t1880.00\t33.12\t1.90
15.Mar.2026 19:55:13\t1880.18\t16.02\t1.40
15.Mar.2026 19:55:18\t1880.18\t13.71\t1.30
15.Mar.2026 19:57:18\t1880.18\t22.57\t1.60
15.Mar.2026 19:58:28\t1880.18\t3.50\t1.10
15.Mar.2026 19:59:18\t1880.18\t3.67\t1.20
15.Mar.2026 20:05:23\t1880.18\t24.59\t1.80
15.Mar.2026 20:05:53\t1880.00\t50.14\t2.50
15.Mar.2026 20:06:03\t1880.00\t50.85\t2.50
15.Mar.2026 20:08:42\t1880.18\t39.27\t1.93
15.Mar.2026 20:09:27\t1880.18\t4.55\t1.40
15.Mar.2026 20:09:57\t1880.18\t2.56\t2.45
15.Mar.2026 20:10:02\t1880.18\t3.07\t3.50
15.Mar.2026 20:10:27\t1880.18\t3.14\t10.20
15.Mar.2026 20:54:20\t1880.18\t3.26\t10.20
15.Mar.2026 20:55:55\t1880.18\t35.43\t2.10
15.Mar.2026 20:56:10\t1879.77\t55.47\t2.97
15.Mar.2026 20:56:15\t1879.70\t51.81\t3.00
15.Mar.2026 20:57:00\t1880.18\t8.51\t1.80
15.Mar.2026 21:45:57\t1880.18\t24.63\t2.35
15.Mar.2026 21:46:07\t1879.70\t49.23\t3.10
15.Mar.2026 21:47:21\t1873.23\t48.70\t10.07
15.Mar.2026 21:47:31\t1873.30\t43.06\t10.00
15.Mar.2026 21:57:06\t1873.30\t8.90\t9.90
15.Mar.2026 21:57:26\t1873.30\t3.09\t9.70
15.Mar.2026 22:25:34\t1873.30\t3.14\t9.75
15.Mar.2026 22:26:54\t1873.30\t4.20\t0.00
15.Mar.2026 22:27:54\t1873.30\t20.64\t0.00
15.Mar.2026 22:27:59\t1872.97\t45.84\t0.00
15.Mar.2026 22:31:54\t1853.50\t47.88\t19.90
15.Mar.2026 22:32:14\t1853.70\t2.62\t19.50
15.Mar.2026 22:38:18\t1853.23\t45.57\t0.23
15.Mar.2026 22:41:28\t1834.73\t45.49\t19.27
15.Mar.2026 22:41:33\t1834.90\t3.44\t19.10
15.Mar.2026 22:53:08\t1834.70\t45.72\t13.07
15.Mar.2026 23:05:02\t1834.80\t23.40\t13.00
15.Mar.2026 23:11:11\t1834.80\t3.91\t0.00
15.Mar.2026 23:14:21\t1834.80\t3.55\t1.40
15.Mar.2026 23:23:46\t1834.80\t3.69\t1.27
15.Mar.2026 23:27:25\t1834.23\t46.39\t10.73
15.Mar.2026 23:29:25\t1825.17\t36.29\t19.67
15.Mar.2026 23:29:30\t1825.30\t4.73\t19.50
15.Mar.2026 23:34:30\t1825.30\t40.89\t0.00
15.Mar.2026 23:34:40\t1824.85\t45.17\t0.00
15.Mar.2026 23:42:05\t1806.10\t5.08\t19.30
15.Mar.2026 23:46:19\t1806.10\t36.90\t0.00
15.Mar.2026 23:46:29\t1805.20\t45.29\t0.30
15.Mar.2026 23:50:14\t1786.67\t28.19\t19.43
15.Mar.2026 23:54:24\t1784.00\t3.55\t0.00
16.Mar.2026 00:00:10\t1783.93\t43.73\t0.00
16.Mar.2026 00:04:00\t1764.67\t33.08\t19.30
16.Mar.2026 00:04:10\t1764.80\t3.14\t19.10
16.Mar.2026 00:17:04\t1745.37\t7.80\t19.53
16.Mar.2026 00:20:34\t1745.17\t30.58\t0.00
16.Mar.2026 00:20:44\t1744.63\t43.81\t0.33
16.Mar.2026 00:30:03\t1726.00\t42.24\t19.60
16.Mar.2026 00:30:13\t1726.20\t3.73\t19.33
16.Mar.2026 00:34:28\t1726.20\t19.99\t0.00
16.Mar.2026 00:34:38\t1725.75\t42.59\t0.00
16.Mar.2026 00:45:27\t1706.40\t41.95\t19.80
16.Mar.2026 00:45:42\t1706.50\t3.89\t19.60
16.Mar.2026 00:49:07\t1706.30\t40.36\t0.00
16.Mar.2026 00:57:47\t1686.60\t40.48\t19.85
16.Mar.2026 00:58:16\t1686.90\t3.44\t19.50
16.Mar.2026 01:03:01\t1686.30\t41.95\t0.05
16.Mar.2026 01:10:31\t1667.30\t41.48\t19.60
16.Mar.2026 01:10:46\t1667.40\t6.63\t19.50
16.Mar.2026 01:15:20\t1667.40\t18.17\t0.00
16.Mar.2026 01:25:20\t1647.50\t40.30\t19.80
16.Mar.2026 01:25:35\t1647.60\t5.09\t19.67
16.Mar.2026 01:30:10\t1647.35\t32.85\t0.15
16.Mar.2026 01:36:09\t1629.70\t41.54\t18.40
16.Mar.2026 01:39:09\t1628.40\t5.14\t19.55
16.Mar.2026 01:41:59\t1628.47\t36.06\t0.00
16.Mar.2026 01:46:29\t1622.40\t59.38\t6.20
16.Mar.2026 01:49:03\t1622.80\t38.07\t5.70
16.Mar.2026 02:00:03\t1622.80\t38.21\t5.70"""

if not raw_text:
    st.info("👆 Paste your rig data or upload a file. Showing demo data below.")
    raw_text = DEMO

# ─── Parse & Render ───────────────────────────────────────────────────────────
try:
    df        = parse_data(raw_text)
    df        = add_activities(df, hl_trip, hl_conn, dd_thr)
    events_df = detect_events(df)

    # ── Metrics ───────────────────────────────────────────────────────────────
    total_sec     = (df["RigTime"].iloc[-1] - df["RigTime"].iloc[0]).total_seconds()
    total_hrs     = total_sec / 3600
    depth_drilled = abs(df["BitDepth"].iloc[-1] - df["BitDepth"].iloc[0])
    avg_rop       = depth_drilled / total_hrs if total_hrs > 0 else 0
    max_hl        = df["HookLoad"].max()
    n_conn        = len(events_df[events_df["activity"] == "Connection"])
    drill_min     = events_df[events_df["activity"] == "Drilling"]["duration_min"].sum()
    conn_min      = events_df[events_df["activity"] == "Connection"]["duration_min"].sum()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("⏱ Total Time",    f"{total_hrs:.1f} hr",     delta=f"{len(df):,} pts")
    c2.metric("⬇ Depth Drilled", f"{depth_drilled:.1f} m",  delta=f"{df['BitDepth'].min():.0f}–{df['BitDepth'].max():.0f} m")
    c3.metric("🔩 Avg ROP",      f"{avg_rop:.2f} m/hr")
    c4.metric("⚖ Max Hook Load", f"{max_hl:.1f} t")
    c5.metric("🔗 Connections",  f"{n_conn}",               delta=f"{conn_min:.0f} min")
    c6.metric("🕳 Drill Time",   f"{drill_min:.0f} min",    delta=f"{drill_min/total_sec*60:.0f}% eff" if total_sec > 0 else "–")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── Section A: Time-Series ────────────────────────────────────────────────
    st.markdown("<div class='sec-label'>📈 Time-Series — Depth · Hook Load · Block Position</div>",
                unsafe_allow_html=True)
    st.plotly_chart(
        build_timeseries(df, events_df, show_depth, show_hl, show_bp,
                         show_bands, show_conn, ds_n, ts_height),
        use_container_width=True,
        config={"displayModeBar": True, "scrollZoom": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                "toImageButtonOptions": {"format": "png", "filename": "timeseries", "scale": 2}},
    )

    # ── Section B: Depth Track ────────────────────────────────────────────────
    st.markdown("<div class='sec-label'>🪨 Depth Track — Hook Load & Block Position vs Bit Depth</div>",
                unsafe_allow_html=True)
    st.caption("Y-axis = Bit Depth (m) — surface at top, TD at bottom. "
               "Coloured horizontal bands show activity type at each depth. "
               "Scroll/pinch to zoom into any depth interval.")
    st.plotly_chart(
        build_depth_track(df, events_df, track_height),
        use_container_width=True,
        config={"displayModeBar": True, "scrollZoom": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                "toImageButtonOptions": {"format": "png", "filename": "depth_track", "scale": 2}},
    )

    # ── Section C: Time Track ─────────────────────────────────────────────────
    st.markdown("<div class='sec-label'>🕐 Time Track — Hook Load & Block Position vs Rig Time</div>",
                unsafe_allow_html=True)
    st.caption("Y-axis = Rig Time — start of shift at top, end at bottom. "
               "Coloured horizontal bands show activity type per time interval. "
               "Hover for exact values; zoom with the toolbar or scroll.")
    st.plotly_chart(
        build_time_track(df, events_df, track_height),
        use_container_width=True,
        config={"displayModeBar": True, "scrollZoom": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                "toImageButtonOptions": {"format": "png", "filename": "time_track", "scale": 2}},
    )

    # ── Section D: Activity + ROP + Connections ───────────────────────────────
    col_l, col_r = st.columns([1, 2])

    with col_l:
        st.markdown("<div class='sec-label'>🥧 Activity Breakdown</div>", unsafe_allow_html=True)
        st.plotly_chart(build_donut(events_df), use_container_width=True,
                        config={"displayModeBar": False})
        agg = (events_df.groupby("activity")["duration_min"].sum()
               .reset_index().sort_values("duration_min", ascending=False))
        agg["pct"] = (agg["duration_min"] / agg["duration_min"].sum() * 100).round(1)
        rows = ""
        for _, r in agg.iterrows():
            c = ACT_CFG.get(r["activity"], ACT_CFG["Slips / Static"])["color"]
            rows += (f"<tr><td><span style='display:inline-block;width:10px;height:10px;"
                     f"border-radius:2px;background:{c};margin-right:6px'></span>"
                     f"{r['activity']}</td>"
                     f"<td style='text-align:right'>{r['duration_min']:.0f} min</td>"
                     f"<td style='text-align:right'>{r['pct']}%</td></tr>")
        st.markdown(f"<table class='etable'><thead><tr>"
                    f"<th>Activity</th><th style='text-align:right'>Duration</th>"
                    f"<th style='text-align:right'>%</th></tr></thead>"
                    f"<tbody>{rows}</tbody></table>", unsafe_allow_html=True)

    with col_r:
        st.markdown("<div class='sec-label'>🚀 Rate of Penetration</div>", unsafe_allow_html=True)
        fig_rop = build_rop(df)
        if fig_rop:
            st.plotly_chart(fig_rop, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("No drilling intervals detected for ROP.")

        st.markdown("<div class='sec-label' style='margin-top:14px'>🔗 Connection Summary</div>",
                    unsafe_allow_html=True)
        conn_evs = events_df[events_df["activity"] == "Connection"].copy()
        if not conn_evs.empty:
            conn_evs["Start"]      = conn_evs["start_time"].dt.strftime("%H:%M:%S")
            conn_evs["End"]        = conn_evs["end_time"].dt.strftime("%H:%M:%S")
            conn_evs["Dur (min)"]  = conn_evs["duration_min"].round(1)
            conn_evs["Depth (m)"]  = conn_evs["depth_start"].round(2)
            conn_evs["Max HL (t)"] = conn_evs["max_hl"].round(1)
            st.dataframe(
                conn_evs[["Start","End","Dur (min)","Depth (m)","Max HL (t)"]].reset_index(drop=True),
                use_container_width=True, height=220,
            )
        else:
            st.info("No connections detected with current thresholds.")

    # ── Section E: Event Log ──────────────────────────────────────────────────
    with st.expander("📋 Full Event Log", expanded=False):
        badge_map = {
            "Drilling": "b-drill", "Tripping In": "b-trip", "Tripping Out": "b-trip",
            "Hoisting": "b-hoist", "Connection": "b-conn", "Slips / Static": "b-static",
        }
        rows = ""
        for i, ev in events_df.iterrows():
            bc  = badge_map.get(ev["activity"], "b-static")
            dd  = abs(ev["depth_end"] - ev["depth_start"])
            rows += (f"<tr><td style='color:#94a3b8'>{i+1}</td>"
                     f"<td>{ev['start_time'].strftime('%H:%M:%S')}</td>"
                     f"<td>{ev['end_time'].strftime('%H:%M:%S')}</td>"
                     f"<td>{ev['duration_min']:.1f} min</td>"
                     f"<td><span class='badge {bc}'>{ev['activity']}</span></td>"
                     f"<td>{ev['depth_start']:.2f} → {ev['depth_end']:.2f}</td>"
                     f"<td style='color:#64748b'>{dd:.2f} m</td>"
                     f"<td>{ev['avg_hl']:.1f} t</td></tr>")
        st.markdown(
            f"<div style='max-height:380px;overflow-y:auto;border:1px solid #d1dbe8;"
            f"border-radius:10px;background:#ffffff;padding:4px'>"
            f"<table class='etable'><thead><tr>"
            f"<th>#</th><th>Start</th><th>End</th><th>Duration</th>"
            f"<th>Activity</th><th>Depth (m)</th><th>Δ Depth</th><th>Avg HL (t)</th>"
            f"</tr></thead><tbody>{rows}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        if export_ev:
            st.download_button("⬇ Download Events CSV",
                               events_df.to_csv(index=False).encode(),
                               "events.csv", "text/csv")

    with st.expander("🗂 Raw Data Preview", expanded=False):
        st.dataframe(df.head(300), use_container_width=True, height=300)
        if export_ev:
            st.download_button("⬇ Download Parsed CSV",
                               df.to_csv(index=False).encode(),
                               "rig_data.csv", "text/csv")

except Exception as e:
    st.error(f"**Parse error:** {e}")
    st.code(str(e))
    st.info("Expected format: `DD.Mon.YYYY HH:MM:SS  BitDepth  HookLoad  BlockPos`")