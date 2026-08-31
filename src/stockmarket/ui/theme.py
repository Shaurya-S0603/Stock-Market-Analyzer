from __future__ import annotations

import streamlit as st


THEME_CSS = """
<style>
:root { --bg:#07110b; --surface:#0d1b12; --surface-2:#11251a; --text:#f1f7f3; --muted:#b4c8bc; --line:#2b4637; --brand:#43d17b; --brand-strong:#79e6a2; --danger:#ff7a8d; }
html, body, [class*="css"] { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
[data-testid="stAppViewContainer"] { background:radial-gradient(900px 420px at 100% -10%,rgba(67,209,123,.12),transparent 65%),linear-gradient(180deg,#061009 0%,var(--bg) 100%); }
[data-testid="stSidebar"] { background:#07130c; border-right:1px solid var(--line); }
.hero { background:linear-gradient(135deg,#0f2a1b 0%,#123f28 100%); border:1px solid rgba(121,230,162,.36); border-radius:18px; padding:24px 26px; margin-bottom:18px; }
.hero-title { margin:0; color:var(--text); font-size:clamp(1.65rem,2.8vw,2.35rem); font-weight:750; line-height:1.15; }
.hero-copy { margin:9px 0 0; color:#d4e9dc; font-size:1rem; max-width:900px; }
.notice { margin:12px 0 0; padding:8px 12px; display:inline-block; border:1px solid rgba(121,230,162,.42); border-radius:999px; color:#e9fff1; background:rgba(0,0,0,.18); font-size:.83rem; font-weight:650; }
div[data-testid="stMetric"] { background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:14px; }
div[data-testid="stMetric"] label { color:#c1d4c8; }
div.stButton>button,div.stFormSubmitButton>button,div.stDownloadButton>button { min-height:44px; border-radius:10px; font-weight:700; border:1px solid #3b644d; }
div.stButton>button:hover,div.stFormSubmitButton>button:hover,div.stDownloadButton>button:hover { border-color:var(--brand-strong); }
div.stButton>button:focus-visible,div.stFormSubmitButton>button:focus-visible,div.stDownloadButton>button:focus-visible,input:focus-visible,textarea:focus-visible,button:focus-visible,select:focus-visible { outline:3px solid #d8ffe6 !important; outline-offset:2px !important; }
[data-testid="stDataFrame"],[data-testid="stTable"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
[data-testid="stTabs"] button { min-height:44px; }
@media (prefers-reduced-motion:reduce) { *,*::before,*::after { scroll-behavior:auto !important; transition:none !important; animation:none !important; } }
</style>
"""


def apply_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)
