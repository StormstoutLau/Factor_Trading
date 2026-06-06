"""
Factor Trading v3.2 — Streamlit Dashboard
=========================================

Multi-page quant dashboard with Bloomberg Terminal dark theme.

Usage:
    streamlit run web/streamlit_app/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Factor Trading v3.2",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark Theme CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Bloomberg Terminal inspired dark theme */
    :root {
        --bg-primary: #0a0e1a;
        --bg-card: #141824;
        --text-primary: #e2e8f0;
        --accent-cyan: #00d4ff;
        --accent-green: #10b981;
        --accent-red: #ef4444;
    }
    .stApp { background-color: #0a0e1a; }
    .metric-card {
        background: #141824;
        border: 1px solid #2a3040;
        border-radius: 8px;
        padding: 16px;
        margin: 4px 0;
    }
    .metric-value { font-size: 28px; font-weight: 700; color: #00d4ff; }
    .metric-label { font-size: 12px; color: #64748b; text-transform: uppercase; }
    .positive { color: #10b981; }
    .negative { color: #ef4444; }
    .section-header {
        color: #00d4ff;
        font-size: 18px;
        font-weight: 600;
        border-bottom: 1px solid #2a3040;
        padding-bottom: 8px;
        margin: 24px 0 12px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Sidebar Navigation ───────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="text-align:center; padding:16px 0;">
    <h1 style="color:#00d4ff; font-size:24px; margin:0;">📊 Factor Trading</h1>
    <p style="color:#64748b; font-size:12px; margin:4px 0;">v3.2 — Multi-Agent Quant Framework</p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

# Navigation state
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "📋 Overview"

pages = {
    "📋 Overview": "Dashboard overview with key metrics and system status",
    "🚀 Backtest Runner": "Configure and run backtests",
    "📊 Factor Analysis": "Factor performance, IC analysis, decay",
    "🛡️ Risk Monitor": "Five-dimensional risk monitoring dashboard",
    "📈 Performance": "Performance analytics, attribution, charts",
}

selected = st.sidebar.radio(
    "Navigation",
    list(pages.keys()),
    format_func=lambda x: f"{x}",
    index=0,
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption(pages[selected])

# ── Route to Page ────────────────────────────────────────────────────────────
st.session_state.nav_page = selected

page_modules = {
    "📋 Overview": "pages.01_Overview",
    "🚀 Backtest Runner": "pages.02_Backtest_Runner",
    "📊 Factor Analysis": "pages.03_Factor_Analysis",
    "🛡️ Risk Monitor": "pages.04_Risk_Monitor",
    "📈 Performance": "pages.05_Performance",
}

module_name = page_modules[selected]
try:
    __import__(module_name)
    mod = sys.modules[module_name]
    if hasattr(mod, "render"):
        mod.render()
    else:
        st.error(f"Page module `{module_name}` missing `render()` function.")
except ImportError as e:
    st.error(f"Failed to load page: {e}")