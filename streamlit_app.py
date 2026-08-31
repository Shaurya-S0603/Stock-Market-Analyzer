from pathlib import Path
import sys

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

st.set_page_config(
    page_title="Stock Market Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from stockmarket.ui import render_app

render_app()
