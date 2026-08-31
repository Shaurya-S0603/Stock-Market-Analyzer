from __future__ import annotations

import streamlit as st


THEME_CSS = r"""
<style>
:root {
    --qe-bg: #060b18;
    --qe-bg-2: #091127;
    --qe-panel: rgba(15, 26, 51, 0.74);
    --qe-panel-strong: rgba(17, 31, 59, 0.92);
    --qe-panel-soft: rgba(25, 40, 72, 0.52);
    --qe-text: #f7f9ff;
    --qe-muted: #95a4c6;
    --qe-line: rgba(128, 163, 235, 0.16);
    --qe-line-strong: rgba(128, 163, 235, 0.28);
    --qe-blue: #3b82f6;
    --qe-blue-bright: #60a5fa;
    --qe-cyan: #38bdf8;
    --qe-teal: #22d3ee;
    --qe-positive: #34d399;
    --qe-warning: #fbbf24;
    --qe-negative: #fb7185;
    --qe-radius: 16px;
    --qe-radius-sm: 12px;
    --qe-shadow: 0 20px 60px rgba(0, 0, 0, .26);
}

html, body, [class*="css"] {
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: var(--qe-text);
}

[data-testid="stAppViewContainer"] {
    background:
      radial-gradient(780px 520px at 92% -8%, rgba(59,130,246,.15), transparent 68%),
      radial-gradient(620px 420px at 20% 0%, rgba(34,211,238,.08), transparent 66%),
      linear-gradient(180deg, #050914 0%, var(--qe-bg) 42%, #070d1c 100%);
}

[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { padding-top: 1.35rem; padding-bottom: 3rem; max-width: 1580px; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(6,11,24,.98), rgba(7,14,31,.98));
    border-right: 1px solid var(--qe-line);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1.25rem; }
[data-testid="stSidebar"] hr { border-color: var(--qe-line); }

.qe-brand { display:flex; align-items:center; gap:.72rem; margin:.2rem 0 1.1rem; }
.qe-brand-mark { width:38px; height:38px; border-radius:12px; display:grid; place-items:center; color:#dff4ff; font-weight:800; letter-spacing:-.04em; background: linear-gradient(145deg, rgba(59,130,246,.30), rgba(34,211,238,.08)); border:1px solid rgba(96,165,250,.34); box-shadow: inset 0 1px 0 rgba(255,255,255,.06); }
.qe-brand-title { color:var(--qe-text); font-size:1.02rem; font-weight:760; line-height:1.05; }
.qe-brand-subtitle { color:var(--qe-muted); font-size:.72rem; margin-top:.2rem; }
.qe-page-head { display:flex; align-items:flex-end; justify-content:space-between; gap:1rem; margin:.2rem 0 1.15rem; flex-wrap:wrap; }
.qe-eyebrow { color:var(--qe-blue-bright); font-weight:760; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; margin-bottom:.4rem; }
.qe-title { color:var(--qe-text); font-size:clamp(1.65rem, 2.6vw, 2.45rem); letter-spacing:-.035em; line-height:1.08; font-weight:760; margin:0; }
.qe-subtitle { color:var(--qe-muted); max-width:800px; margin:.55rem 0 0; font-size:.94rem; line-height:1.55; }
.qe-meta { color:var(--qe-muted); font-size:.78rem; text-align:right; }
.qe-section-head { display:flex; align-items:center; justify-content:space-between; gap:.8rem; margin:1.25rem 0 .65rem; }
.qe-section-title { color:#e8efff; font-size:.86rem; font-weight:760; text-transform:uppercase; letter-spacing:.055em; }
.qe-section-note { color:var(--qe-muted); font-size:.76rem; }
.qe-kpi { min-height:142px; padding:1rem 1.05rem; border-radius:var(--qe-radius); background: linear-gradient(145deg, rgba(19,33,63,.82), rgba(10,20,41,.72)); border:1px solid var(--qe-line); box-shadow: inset 0 1px 0 rgba(255,255,255,.035); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); }
.qe-kpi-top { display:flex; align-items:center; justify-content:space-between; gap:.75rem; }
.qe-kpi-label { color:#a7b5d4; font-size:.76rem; font-weight:650; text-transform:uppercase; letter-spacing:.045em; }
.qe-kpi-icon { width:34px; height:34px; border-radius:10px; display:grid; place-items:center; background:rgba(59,130,246,.12); color:#8fc5ff; border:1px solid rgba(96,165,250,.16); }
.qe-kpi-value { color:#fff; margin:.72rem 0 .35rem; font-size:clamp(1.35rem,2vw,1.86rem); font-weight:760; letter-spacing:-.025em; font-variant-numeric:tabular-nums; }
.qe-kpi-delta { color:var(--qe-muted); font-size:.76rem; }
.qe-positive { color:var(--qe-positive) !important; }
.qe-negative { color:var(--qe-negative) !important; }
.qe-warning { color:var(--qe-warning) !important; }
.qe-blue { color:var(--qe-blue-bright) !important; }
.qe-status { display:inline-flex; align-items:center; gap:.42rem; padding:.34rem .62rem; border-radius:999px; border:1px solid var(--qe-line); background:rgba(255,255,255,.025); color:#c5d0e8; font-size:.72rem; font-weight:700; }
.qe-dot { width:7px; height:7px; border-radius:50%; background:var(--qe-muted); box-shadow:0 0 0 4px rgba(149,164,198,.08); }
.qe-status.active .qe-dot { background:var(--qe-positive); box-shadow:0 0 0 4px rgba(52,211,153,.10); }
.qe-status.warn .qe-dot { background:var(--qe-warning); box-shadow:0 0 0 4px rgba(251,191,36,.10); }
.qe-status.danger .qe-dot { background:var(--qe-negative); box-shadow:0 0 0 4px rgba(251,113,133,.10); }
.qe-callout { padding:.85rem 1rem; border:1px solid var(--qe-line); border-radius:var(--qe-radius-sm); background:rgba(13,25,49,.58); color:#c5d0e8; font-size:.82rem; line-height:1.5; }
.qe-callout strong { color:#eef4ff; }

div[data-testid="stMetric"] { background: linear-gradient(145deg, rgba(19,33,63,.82), rgba(10,20,41,.72)); border:1px solid var(--qe-line); border-radius:var(--qe-radius); padding:1rem 1.05rem; min-height:124px; box-shadow: inset 0 1px 0 rgba(255,255,255,.035); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); }
div[data-testid="stMetric"] label { color:#9eacc9; font-weight:650; letter-spacing:.01em; }
div[data-testid="stMetricValue"] { color:#f9fbff; font-variant-numeric:tabular-nums; letter-spacing:-.025em; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color:var(--qe-line) !important; background:rgba(12,23,45,.48); border-radius:var(--qe-radius); }
[data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid var(--qe-line); border-radius:var(--qe-radius-sm); overflow:hidden; }
[data-testid="stTabs"] [role="tablist"] { gap:.35rem; border-bottom:1px solid var(--qe-line); }
[data-testid="stTabs"] button { min-height:44px; color:#93a3c4; }
[data-testid="stTabs"] button[aria-selected="true"] { color:#eaf2ff; }
input, textarea, [data-baseweb="select"] > div, [data-testid="stNumberInput"] input { border-color: var(--qe-line-strong) !important; }
div.stButton > button, div.stFormSubmitButton > button, div.stDownloadButton > button { min-height:44px; border-radius:11px; font-weight:720; border:1px solid rgba(96,165,250,.26); background:rgba(21,37,69,.86); color:#edf4ff; }
div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] { background:linear-gradient(135deg,#2563eb,#3b82f6 58%,#0ea5e9); color:#fff; border-color:rgba(96,165,250,.55); }
div.stButton > button:hover, div.stFormSubmitButton > button:hover, div.stDownloadButton > button:hover { border-color:rgba(96,165,250,.72); background:rgba(28,48,88,.94); }
div.stButton > button:focus-visible, div.stFormSubmitButton > button:focus-visible, div.stDownloadButton > button:focus-visible, input:focus-visible, textarea:focus-visible, button:focus-visible, select:focus-visible, [tabindex]:focus-visible { outline:3px solid rgba(125,211,252,.92) !important; outline-offset:2px !important; }
[data-testid="stAlert"] { border-radius:var(--qe-radius-sm); border-color:var(--qe-line); }
[data-testid="stExpander"] { border-color:var(--qe-line) !important; border-radius:var(--qe-radius-sm) !important; background:rgba(10,20,40,.5); }
@media (max-width: 780px) { [data-testid="stMainBlockContainer"] { padding-left:1rem; padding-right:1rem; } .qe-kpi { min-height:124px; } .qe-meta { text-align:left; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior:auto !important; transition:none !important; animation:none !important; } }
</style>
"""


def apply_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)
