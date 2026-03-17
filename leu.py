"""
Drilling Real-Time Log Viewer
==============================
• Upload Excel (.xlsx) or CSV/TXT — any format, first row = headers, second row = units (auto-skipped)
• Mud-log style vertical strip charts:  Y = Time (top=oldest),  X = parameter value
• Bit Depth shown as a bold black curve on the rightmost shared Y-axis
• Uploaded files are stored permanently on the server — reload any time
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re, os, io, json
from datetime import datetime
import openpyxl

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Drilling Log Viewer", page_icon=None,
                   layout="wide", initial_sidebar_state="expanded")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Typography & base ───────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", system-ui, sans-serif;
    letter-spacing: -0.01em;
}
.stApp { background: #f0f4f8; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #d1dbe8;
}
[data-testid="stSidebar"] * { color: #344055 !important; }
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #1a2535 !important;
    font-weight: 600 !important;
    font-size: .85rem !important;
    text-transform: uppercase;
    letter-spacing: .06em;
}

/* ── Metric cards ────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #d1dbe8;
    border-radius: 8px;
    padding: 14px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
[data-testid="stMetricValue"] {
    color: #1558a0 !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    letter-spacing: -.02em;
}
[data-testid="stMetricLabel"] {
    color: #64748b !important;
    font-size: .72rem !important;
    text-transform: uppercase;
    letter-spacing: .05em;
    font-weight: 500 !important;
}

/* ── Top navigation bar ──────────────────────────────────────────────────── */
.top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #ffffff;
    border: 1px solid #d1dbe8;
    border-radius: 8px;
    padding: 14px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.04);
}
.top-bar-left { display: flex; align-items: baseline; gap: 14px; }
.top-bar-author {
    font-size: .8rem;
    font-weight: 600;
    color: #1558a0;
    letter-spacing: .04em;
    text-transform: uppercase;
    border-right: 1px solid #d1dbe8;
    padding-right: 14px;
}
.top-bar-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1a2535;
    letter-spacing: -.02em;
}
.top-bar-subtitle {
    font-size: .78rem;
    color: #94a3b8;
    font-weight: 400;
    letter-spacing: .01em;
}
.top-bar-right {
    font-size: .72rem;
    color: #94a3b8;
    text-align: right;
    line-height: 1.6;
    font-weight: 400;
}

/* ── Section headers ─────────────────────────────────────────────────────── */
.sec {
    color: #1a2535;
    font-size: .78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .07em;
    padding-bottom: 6px;
    border-bottom: 1.5px solid #d1dbe8;
    margin-bottom: 12px;
}

/* ── Expanders ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #d1dbe8 !important;
    border-radius: 8px;
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #ffffff;
    border-radius: 8px;
    border: 1px solid #d1dbe8;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    color: #64748b;
    font-size: .8rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: .04em;
    padding: 8px 20px;
}
.stTabs [aria-selected="true"] {
    color: #1558a0 !important;
    border-bottom: 2px solid #1558a0 !important;
    font-weight: 600 !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.stButton > button {
    font-size: .8rem;
    font-weight: 500;
    letter-spacing: .02em;
    border-radius: 6px;
}

/* ── Download buttons ────────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] button {
    font-size: .78rem;
    font-weight: 500;
    letter-spacing: .02em;
}

/* ── Scrollbar ───────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #c0ccd8; border-radius: 4px; }
</style>""", unsafe_allow_html=True)

# ── Activity colours ───────────────────────────────────────────────────────────
ACT = {
    "Drilling":       "#16a34a",
    "Tripping In":    "#2563eb",
    "Tripping Out":   "#0891b2",
    "Connection":     "#d97706",
    "Hoisting":       "#7c3aed",
    "Slips / Static": "#64748b",
}

# ── Track colour palette ───────────────────────────────────────────────────────
PALETTE = ["#e63946","#2a9d8f","#e76f51","#457b9d","#f4a261",
           "#6a4c93","#1d3557","#2b9348","#c77dff","#ff6b6b",
           "#06d6a0","#ffd166","#118ab2","#ef476f","#073b4c"]

# ═══════════════════════════════════════════════════════════════════════════════
#  FILE STORAGE
# ═══════════════════════════════════════════════════════════════════════════════
STORE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploaded_files")
INDEX_FILE = os.path.join(STORE_DIR, "index.json")
os.makedirs(STORE_DIR, exist_ok=True)

def _idx():
    return json.load(open(INDEX_FILE)) if os.path.exists(INDEX_FILE) else {}

def _save_idx(d):
    json.dump(d, open(INDEX_FILE,"w"), indent=2)

def store_file(name:str, data:bytes) -> str:
    safe = re.sub(r"[^\w.\-]","_", name)
    open(os.path.join(STORE_DIR, safe),"wb").write(data)
    idx = _idx(); idx[safe] = {"original":name,"size":len(data),"saved":datetime.now().isoformat()[:19]}
    _save_idx(idx); return safe

def list_stored():
    return [(k,v) for k,v in sorted(_idx().items(), key=lambda x:x[1].get("saved",""), reverse=True)
            if os.path.exists(os.path.join(STORE_DIR,k))]

def del_stored(safe):
    p = os.path.join(STORE_DIR, safe)
    if os.path.exists(p): os.remove(p)
    idx = _idx(); idx.pop(safe,None); _save_idx(idx)

def read_stored(safe):
    return open(os.path.join(STORE_DIR,safe),"rb").read()

# ═══════════════════════════════════════════════════════════════════════════════
#  SMART UNIVERSAL PARSER
#  Rules:
#   1. Row 1  → parameter names  (always)
#   2. Row 2  → units if non-numeric strings  (skipped automatically)
#   3. Column 0  → time/date column  (detected by name or position)
#   4. All other columns → numeric (non-numeric values become NaN)
# ═══════════════════════════════════════════════════════════════════════════════
def _looks_like_units(row):
    """True if this row is mostly text/unit strings (not real data)."""
    vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
    if not vals: return True
    # count values that look like units or are blank
    unit_like = sum(1 for v in vals
                    if re.match(r'^[a-zA-Z/%°³\-–—_]+$', v) or v in ("None",""))
    return unit_like / len(vals) >= 0.5

def _parse_time(v):
    if v is None: return pd.NaT
    if isinstance(v, datetime): return pd.Timestamp(v)
    try: return pd.to_datetime(str(v), dayfirst=True)
    except: return pd.NaT

def smart_parse(data:bytes, filename:str) -> pd.DataFrame:
    ext = os.path.splitext(filename)[1].lower()

    # ── Excel ──────────────────────────────────────────────────────────────────
    if ext in (".xlsx",".xls"):
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        # Prefer Sheet1 (more channels) over qrafik
        sh = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb[wb.sheetnames[0]]
        all_rows = list(sh.iter_rows(values_only=True))
    # ── Text / CSV ─────────────────────────────────────────────────────────────
    else:
        text = data.decode("utf-8", errors="ignore")
        lines = [l for l in text.splitlines() if l.strip()]
        # Detect separator
        first = lines[0]
        sep = "\t" if first.count("\t")>=2 else (";" if first.count(";")>=2 else ",")
        all_rows = [[c.strip().strip('"') for c in l.split(sep)] for l in lines]

    if not all_rows:
        raise ValueError("File appears to be empty.")

    # Row 0 = headers
    headers = [str(h).strip() if h is not None else f"Col_{i}"
               for i,h in enumerate(all_rows[0])]
    # Remove trailing None / empty headers (Excel artefact)
    while headers and headers[-1] in ("None","","Col_" + str(len(headers)-1)):
        headers.pop()
    n_cols = len(headers)

    # Determine data start (skip units row if present) — also capture units
    data_start = 1
    detected_units = {}   # col_name -> unit string
    if len(all_rows) > 1 and _looks_like_units(all_rows[1][:n_cols]):
        data_start = 2
        for i, h in enumerate(headers):
            uval = all_rows[1][i] if i < len(all_rows[1]) else None
            if uval is not None and str(uval).strip() not in ("None", ""):
                detected_units[h] = str(uval).strip()

    # Build DataFrame
    rows = [list(r)[:n_cols] for r in all_rows[data_start:] if any(v is not None for v in r)]
    df = pd.DataFrame(rows, columns=headers)

    # Find time column (first column whose name contains time/date/rig, or column 0)
    time_col = headers[0]
    for h in headers:
        if re.search(r'time|date|rig', h, re.I):
            time_col = h; break

    df["_rt_parsed"] = df[time_col].apply(_parse_time)
    df = df.dropna(subset=["_rt_parsed"]).reset_index(drop=True)

    # Convert everything else to numeric
    for c in df.columns:
        if c in ("_rt_parsed", time_col): continue
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Drop all-NaN numeric columns and the original time col
    if time_col != "_rt_parsed":
        df = df.drop(columns=[time_col], errors="ignore")
    df = df.dropna(axis=1, how="all")
    df = df.rename(columns={"_rt_parsed": "RigTime"})
    df = df.sort_values("RigTime").drop_duplicates("RigTime").reset_index(drop=True)

    if len(df) < 2:
        raise ValueError("Fewer than 2 valid rows after parsing — check your file.")
    return df, detected_units

def find_col(df, *patterns):
    for p in patterns:
        for c in df.columns:
            if re.search(p, c, re.I): return c
    return None

# ═══════════════════════════════════════════════════════════════════════════════
#  ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════
def classify(hl, dd, hl_trip, hl_conn, d_thr):
    if hl > hl_trip:
        if dd < -0.3: return "Tripping In"
        if dd >  0.3: return "Tripping Out"
        return "Hoisting"
    if hl > hl_conn: return "Connection"
    if dd < -d_thr:  return "Drilling"
    return "Slips / Static"

def add_activity(df, hl_col, depth_col, hl_trip, hl_conn, d_thr):
    acts = []
    for i in range(len(df)):
        dd = df[depth_col].iloc[i] - df[depth_col].iloc[i-1] if i>0 else 0
        hl = float(df[hl_col].iloc[i]) if hl_col else 0
        acts.append(classify(hl, dd, hl_trip, hl_conn, d_thr))
    df = df.copy(); df["_Activity"] = acts; return df

def detect_events(df, depth_col):
    recs, prev, s = [], df["_Activity"].iloc[0], 0
    for i in range(1, len(df)):
        if df["_Activity"].iloc[i] != prev:
            recs.append({"activity":prev,
                "start_time":df["RigTime"].iloc[s],"end_time":df["RigTime"].iloc[i-1],
                "duration_min":(df["RigTime"].iloc[i-1]-df["RigTime"].iloc[s]).total_seconds()/60,
                "depth_start":df[depth_col].iloc[s],"depth_end":df[depth_col].iloc[i-1]})
            prev,s = df["_Activity"].iloc[i],i
    recs.append({"activity":prev,
        "start_time":df["RigTime"].iloc[s],"end_time":df["RigTime"].iloc[-1],
        "duration_min":(df["RigTime"].iloc[-1]-df["RigTime"].iloc[s]).total_seconds()/60,
        "depth_start":df[depth_col].iloc[s],"depth_end":df[depth_col].iloc[-1]})
    return pd.DataFrame(recs)

# ═══════════════════════════════════════════════════════════════════════════════
#  MUD LOG — vertical strip chart
#  Matches the reference image:
#   • Strips side by side sharing the same Y axis (time, oldest at top)
#   • Each strip: X = param value, Y = time
#   • Rightmost strip = Bit Depth (bold black line, X-axis inverted so depth increases rightward)
#   • Header row above each strip shows parameter name + scale (min … max)
#   • Coloured horizontal bands = activity intervals
# ═══════════════════════════════════════════════════════════════════════════════
def build_mud_log(df, param_cols, depth_col, events_df,
                  show_bands, height, ds_n, units=None):

    if units is None:
        units = {}

    n          = len(param_cols)
    total_cols = 1 + n            # col 1 = Bit Depth, cols 2..N+1 = params

    step = max(1, len(df)//ds_n)
    ds   = df.iloc[::step].copy()

    # Depth strip slightly wider, param strips equal
    widths = [0.85] + [1.0]*n

    fig = make_subplots(
        rows=1, cols=total_cols,
        shared_yaxes=True,
        column_widths=widths,
        horizontal_spacing=0.008,
    )

    # ── Activity bands ────────────────────────────────────────────────────────
    if show_bands and events_df is not None:
        for _, ev in events_df.iterrows():
            band_color = ACT.get(ev["activity"], "#64748b")
            for ci in range(1, total_cols+1):
                fig.add_hrect(y0=ev["start_time"], y1=ev["end_time"],
                              fillcolor=band_color, opacity=0.07, line_width=0,
                              row=1, col=ci)

    # helper: build the header label  "Name (unit)"  or just "Name"
    def _label(col_name, color=None):
        u    = units.get(col_name, "").strip()
        unit = f" ({u})" if u else ""
        name = f"{col_name}{unit}"
        if color:
            return f"<b style='color:{color}'>{name}</b>"
        return f"<b>{name}</b>"

    # ── Col 1: Bit Depth ──────────────────────────────────────────────────────
    d_series = ds[depth_col].dropna()
    if not d_series.empty:
        d_min = float(d_series.min()); d_max = float(d_series.max())
        d_unit = units.get(depth_col, "").strip()
        hover_unit = f" {d_unit}" if d_unit else ""

        fig.add_trace(go.Scatter(
            x=ds[depth_col], y=ds["RigTime"],
            mode="lines",
            name=_label(depth_col).replace("<b>","").replace("</b>",""),
            line=dict(color="#1a2535", width=2.5),
            fill="tozerox",
            fillcolor="rgba(26,37,53,0.06)",
            hovertemplate=(f"<b>{depth_col}</b><br>"
                           f"%{{y|%H:%M:%S}}<br>%{{x:.2f}}{hover_unit}<extra></extra>"),
        ), row=1, col=1)

        fig.update_xaxes(
            range=[d_min-5, d_max+5],
            tickfont=dict(size=8, color="#94a3b8"),
            gridcolor="#e8eef4", gridwidth=1,
            linecolor="#d1dbe8", zeroline=False,
            showgrid=True, side="top",
            title_text=(_label(depth_col) + "<br>"
                        f"<span style='font-size:9px;color:#94a3b8'>"
                        f"{d_min:.0f} … {d_max:.0f}</span>"),
            title_font=dict(size=10, color="#1a2535"),
            title_standoff=2,
            row=1, col=1,
        )

    # ── Cols 2..N+1: parameter strips ─────────────────────────────────────────
    for i, col in enumerate(param_cols):
        color = PALETTE[i % len(PALETTE)]
        ci    = i + 2               # offset by 1 because depth is col 1
        series = ds[col].dropna()
        if series.empty: continue

        xmin = float(ds[col].min()); xmax = float(ds[col].max())
        pad  = max((xmax-xmin)*0.04, 0.5)
        u    = units.get(col, "").strip()
        hover_unit = f" {u}" if u else ""

        fig.add_trace(go.Scatter(
            x=ds[col], y=ds["RigTime"],
            mode="lines",
            name=_label(col, color).replace("<b style='color:" + color + "'>","").replace("</b>",""),
            line=dict(color=color, width=1.3),
            fill="tozerox",
            fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.08)",
            hovertemplate=(f"<b>{col}</b>{hover_unit}<br>"
                           f"%{{y|%H:%M:%S}}<br>%{{x:.2f}}{hover_unit}<extra></extra>"),
        ), row=1, col=ci)

        fig.update_xaxes(
            range=[xmin-pad, xmax+pad],
            tickfont=dict(size=8, color="#94a3b8"),
            gridcolor="#e8eef4", gridwidth=1,
            linecolor="#d1dbe8", zeroline=False,
            showgrid=True, side="top",
            title_text=(_label(col, color) + "<br>"
                        f"<span style='color:#94a3b8;font-size:9px'>"
                        f"{xmin:.1f} … {xmax:.1f}</span>"),
            title_font=dict(size=10),
            title_standoff=2,
            row=1, col=ci,
        )

    # ── Shared Y axis (time, oldest at top) ───────────────────────────────────
    fig.update_yaxes(
        autorange="reversed",
        tickformat="%H:%M\n%d %b",
        tickfont=dict(size=9, color="#64748b"),
        gridcolor="#e8eef4", gridwidth=1,
        linecolor="#d1dbe8", zeroline=False,
        showgrid=True,
        title_text="TIME",
        title_font=dict(size=10, color="#374151"),
        row=1, col=1,
    )
    for ci in range(2, total_cols+1):
        fig.update_yaxes(showticklabels=False, row=1, col=ci)

    fig.update_layout(
        height=height,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#fafbfd",
        font=dict(family="Inter, sans-serif", color="#374151"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0,
            font=dict(size=10), bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#d1dbe8", borderwidth=1,
        ),
        margin=dict(l=65, r=15, t=90, b=30),
        hovermode="y unified",
        hoverlabel=dict(bgcolor="#fff", bordercolor="#d1dbe8",
                        font=dict(color="#1a2535", size=11)),
    )
    return fig

# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
<div style='padding:18px 4px 14px 4px;border-bottom:1px solid #d1dbe8;margin-bottom:6px;'>
  <div style='font-size:.65rem;font-weight:600;color:#94a3b8;text-transform:uppercase;
              letter-spacing:.08em;margin-bottom:4px;'>Engineer</div>
  <div style='font-size:1rem;font-weight:700;color:#1558a0;letter-spacing:-.01em;'>
              Saleh Aliyev</div>
  <div style='font-size:.72rem;color:#94a3b8;margin-top:2px;letter-spacing:.01em;'>
              Drilling Real-Time Log Viewer</div>
</div>""", unsafe_allow_html=True)

    st.markdown("### Display")
    chart_height = st.slider("Chart height (px)", 600, 3000, 1500, 50)
    ds_n         = st.slider("Max points",         500, 8000, 3000, 100)
    show_bands   = st.toggle("Activity bands", True)

    st.markdown("---")
    st.markdown("### Activity Thresholds")
    hl_trip = st.number_input("Tripping HL (t)",      value=35.0, step=0.5)
    hl_conn = st.number_input("Connection HL (t)",    value=10.0, step=0.5)
    dd_thr  = st.number_input("Drilling depth Δ (m)", value=0.05, step=0.01)

# ═══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="top-bar">
  <div class="top-bar-left">
    <span class="top-bar-title">Drilling Real-Time Log Viewer</span>
  </div>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  FILE MANAGEMENT  (upload + stored)
# ═══════════════════════════════════════════════════════════════════════════════
tab_up, tab_stored = st.tabs(["Upload File", "Stored Files"])

active_bytes = None
active_name  = None

with tab_up:
    st.caption("**Excel (.xlsx)** or **CSV / TXT**.  "
               "Row 1 = parameter names. Row 2 = units if present — detected and skipped automatically.")
    uf = st.file_uploader("", type=["xlsx","xls","csv","txt","tsv"],
                          label_visibility="collapsed")
    if uf:
        raw = uf.read()
        store_file(uf.name, raw)
        active_bytes, active_name = raw, uf.name
        st.success(f"**{uf.name}** saved to server storage.")

with tab_stored:
    files = list_stored()
    if not files:
        st.info("No files stored yet. Upload a file using the tab above.")
    else:
        st.caption(f"{len(files)} file(s) stored on server — click a row to load, or delete.")
        for safe, meta in files:
            ca, cb = st.columns([6,1])
            with ca:
                label = (f"**{meta['original']}**  ·  "
                         f"{meta['saved'][:16]}  ·  {meta['size']//1024} KB")
                if st.button(label, key=f"ld_{safe}", use_container_width=True):
                    active_bytes = read_stored(safe)
                    active_name  = meta["original"]
                    st.success(f"Loaded: **{meta['original']}**")
            with cb:
                if st.button("×", key=f"dl_{safe}", help="Delete this file"):
                    del_stored(safe); st.rerun()

# Auto-load most-recent file if nothing chosen yet
if active_bytes is None:
    files = list_stored()
    if files:
        safe, meta = files[0]
        active_bytes = read_stored(safe)
        active_name  = meta["original"]
        st.info(f"Auto-loaded most recent file: **{meta['original']}**")
    else:
        st.warning("Upload a file to get started.")
        st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
#  PARSE
# ═══════════════════════════════════════════════════════════════════════════════
try:
    df, auto_units = smart_parse(active_bytes, active_name)
except Exception as e:
    st.error(f"**Parse error:** {e}")
    st.stop()

num_cols = [c for c in df.columns
            if c != "RigTime" and pd.api.types.is_numeric_dtype(df[c])]

# Auto-detect key columns
depth_col = find_col(df, r'bitdep', r'depth', r'\bmd\b') or (num_cols[0] if num_cols else None)
hl_col    = find_col(df, r'hook.?load', r'\bhl\b')
bp_col    = find_col(df, r'block.?pos', r'blockpos')

# ═══════════════════════════════════════════════════════════════════════════════
#  COLUMN SELECTOR + UNITS EDITOR
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sec'>Column Setup</div>", unsafe_allow_html=True)
cc1, cc2, cc3 = st.columns(3)

with cc1:
    depth_col = st.selectbox("Bit Depth column",
                             num_cols, index=num_cols.index(depth_col) if depth_col in num_cols else 0)
with cc2:
    hl_opts = ["(none)"] + num_cols
    hl_col  = st.selectbox("Hook Load (for activity)",
                           hl_opts, index=hl_opts.index(hl_col) if hl_col in hl_opts else 0)
    if hl_col == "(none)": hl_col = None
with cc3:
    avail   = [c for c in num_cols if c != depth_col]
    default = avail[:min(6, len(avail))]
    param_cols = st.multiselect("Parameter tracks (each = one strip)",
                                avail, default=default)

if not param_cols:
    st.warning("Pick at least one parameter track above."); st.stop()
if depth_col is None:
    st.warning("Could not find a Bit Depth column."); st.stop()

# ── Units editor ──────────────────────────────────────────────────────────────
# Pre-fill with units detected from the file; user can override any of them.
with st.expander("Units — optional, shown in strip headers", expanded=False):
    st.caption(
        "Units were **auto-detected from the file** where available. "
        "Override any value here — changes apply immediately to all chart labels."
    )
    all_track_cols = [depth_col] + param_cols
    n_ucols = min(4, len(all_track_cols))
    ucols = st.columns(n_ucols)
    units = {}
    for idx, col in enumerate(all_track_cols):
        default_unit = auto_units.get(col, "")
        with ucols[idx % n_ucols]:
            units[col] = st.text_input(
                col,
                value=default_unit,
                key=f"unit_{col}",
                placeholder="e.g. m, t, rpm",
                label_visibility="visible",
            )

# ═══════════════════════════════════════════════════════════════════════════════
#  ACTIVITY
# ═══════════════════════════════════════════════════════════════════════════════
if hl_col:
    df  = add_activity(df, hl_col, depth_col, hl_trip, hl_conn, dd_thr)
    evs = detect_events(df, depth_col)
else:
    df["_Activity"] = "Slips / Static"
    evs = None

# ═══════════════════════════════════════════════════════════════════════════════
#  METRICS ROW
# ═══════════════════════════════════════════════════════════════════════════════
t_sec  = (df["RigTime"].iloc[-1]-df["RigTime"].iloc[0]).total_seconds()
t_hrs  = t_sec/3600
drl    = abs(df[depth_col].iloc[-1]-df[depth_col].iloc[0])
rop    = drl/t_hrs if t_hrs > 0 else 0
max_hl = df[hl_col].max() if hl_col else 0
n_conn = len(evs[evs.activity=="Connection"]) if evs is not None else 0
d_min  = df["RigTime"].iloc[0].strftime("%d %b %H:%M")
d_max  = df["RigTime"].iloc[-1].strftime("%d %b %H:%M")

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Period",        f"{t_hrs:.1f} hr",   delta=f"{d_min} → {d_max}")
c2.metric("Depth Range",   f"{df[depth_col].min():.0f} – {df[depth_col].max():.0f} m",
                               delta=f"{drl:.1f} m drilled")
c3.metric("Avg ROP",       f"{rop:.2f} m/hr")
c4.metric("Max Hook Load",  f"{max_hl:.1f} t")
c5.metric("Connections",   str(n_conn))
c6.metric("Channels",      str(len(param_cols)), delta=f"{len(df):,} rows")

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  MUD LOG CHART
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='sec'>Mud Log — Vertical Strip Chart</div>",
            unsafe_allow_html=True)


fig = build_mud_log(df, param_cols, depth_col, evs,
                    show_bands, chart_height, ds_n, units)
st.plotly_chart(fig, use_container_width=True, config={
    "displayModeBar": True, "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d","select2d"],
    "toImageButtonOptions": {"format":"png","filename":"mud_log","scale":2},
})

# ═══════════════════════════════════════════════════════════════════════════════
#  ACTIVITY BREAKDOWN + EVENT LOG
# ═══════════════════════════════════════════════════════════════════════════════
if evs is not None:
    left, right = st.columns([1, 2.4])

    with left:
        st.markdown("<div class='sec'>Activity Breakdown</div>", unsafe_allow_html=True)
        agg = (evs.groupby("activity")["duration_min"].sum()
               .reset_index().sort_values("duration_min", ascending=False))
        agg["pct"] = (agg["duration_min"]/agg["duration_min"].sum()*100).round(1)
        total = agg["duration_min"].sum()
        colors = [ACT.get(a,"#64748b") for a in agg["activity"]]
        donut = go.Figure(go.Pie(
            labels=agg["activity"], values=agg["duration_min"].round(1),
            hole=0.60, marker=dict(colors=colors, line=dict(color="#f0f4f8",width=3)),
            textinfo="percent", textfont=dict(size=11),
            hovertemplate="<b>%{label}</b><br>%{value:.1f} min (%{percent})<extra></extra>",
        ))
        donut.update_layout(
            annotations=[dict(text=f"<b>{total:.0f}</b><br>min",
                              x=0.5,y=0.5,font_size=15,font_color="#1a2535",showarrow=False)],
            paper_bgcolor="#ffffff", font=dict(color="#374151"),
            legend=dict(font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=10,r=10,t=10,b=10), height=230,
        )
        st.plotly_chart(donut, use_container_width=True, config={"displayModeBar":False})

        # Summary table
        rows_h = ""
        for _, r in agg.iterrows():
            c = ACT.get(r["activity"],"#64748b")
            rows_h += (f"<tr><td style='padding:5px 8px'>"
                       f"<span style='display:inline-block;width:9px;height:9px;border-radius:2px;"
                       f"background:{c};margin-right:6px'></span>{r['activity']}</td>"
                       f"<td style='text-align:right;padding:5px 8px'>{r['duration_min']:.0f} min</td>"
                       f"<td style='text-align:right;padding:5px 8px'>{r['pct']}%</td></tr>")
        st.markdown(
            f"<table style='width:100%;border-collapse:collapse;font-size:.8rem;color:#334155'>"
            f"<thead><tr>"
            f"<th style='text-align:left;padding:5px 8px;border-bottom:2px solid #d1dbe8;"
            f"color:#64748b;font-size:.68rem;text-transform:uppercase'>Activity</th>"
            f"<th style='text-align:right;padding:5px 8px;border-bottom:2px solid #d1dbe8;"
            f"color:#64748b;font-size:.68rem;text-transform:uppercase'>Min</th>"
            f"<th style='text-align:right;padding:5px 8px;border-bottom:2px solid #d1dbe8;"
            f"color:#64748b;font-size:.68rem;text-transform:uppercase'>%</th>"
            f"</tr></thead><tbody>{rows_h}</tbody></table>",
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("<div class='sec'>Event Log</div>", unsafe_allow_html=True)
        badge = {"Drilling":"#dcfce7|#166534","Tripping In":"#dbeafe|#1e40af",
                 "Tripping Out":"#cffafe|#0e7490","Hoisting":"#ede9fe|#5b21b6",
                 "Connection":"#fef9c3|#854d0e","Slips / Static":"#f1f5f9|#475569"}
        rows_h = ""
        for i, ev in evs.iterrows():
            bg,fg = badge.get(ev["activity"],"#f1f5f9|#475569").split("|")
            dd = abs(ev["depth_end"]-ev["depth_start"])
            rows_h += (
                f"<tr style='border-bottom:1px solid #eef2f7'>"
                f"<td style='padding:5px 9px;color:#94a3b8'>{i+1}</td>"
                f"<td style='padding:5px 9px'>{ev['start_time'].strftime('%d %b %H:%M:%S')}</td>"
                f"<td style='padding:5px 9px'>{ev['end_time'].strftime('%H:%M:%S')}</td>"
                f"<td style='padding:5px 9px'>{ev['duration_min']:.1f} min</td>"
                f"<td style='padding:5px 9px'>"
                f"<span style='background:{bg};color:{fg};padding:2px 9px;border-radius:12px;"
                f"font-size:.73rem;font-weight:600'>{ev['activity']}</span></td>"
                f"<td style='padding:5px 9px;font-size:.8rem'>"
                f"{ev['depth_start']:.1f} → {ev['depth_end']:.1f} m</td>"
                f"<td style='padding:5px 9px;color:#64748b'>{dd:.1f} m</td>"
                f"</tr>"
            )
        st.markdown(
            f"<div style='max-height:370px;overflow-y:auto;border:1px solid #d1dbe8;"
            f"border-radius:10px;background:#fff'>"
            f"<table style='width:100%;border-collapse:collapse;font-size:.8rem;color:#334155'>"
            f"<thead style='position:sticky;top:0;background:#f8fafc'><tr>"
            f"{''.join(f'<th style=padding:6px_9px;border-bottom:2px_solid_#d1dbe8;text-align:left;color:#64748b;font-size:.68rem;text-transform:uppercase>{h}</th>' for h in ['#','Start','End','Duration','Activity','Depth','Δ'])}"
            f"</tr></thead><tbody>{rows_h}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        st.download_button("Download Events CSV", evs.to_csv(index=False).encode(),
                           "events.csv", "text/csv")

# ═══════════════════════════════════════════════════════════════════════════════
#  RAW DATA
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("Raw Data Preview & Download", expanded=False):
    st.dataframe(df.head(500), use_container_width=True, height=280)
    st.download_button("Download Full CSV", df.to_csv(index=False).encode(),
                       "rig_data.csv", "text/csv")
