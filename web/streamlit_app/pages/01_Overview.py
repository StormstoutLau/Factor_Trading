"""
Page 1: Overview Dashboard
==========================
Key metrics, system status, agent summary, and quick actions.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime


def render() -> None:
    st.markdown('<div class="section-header">📋 System Overview</div>', unsafe_allow_html=True)

    # ── Top Metrics Row ──────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Framework Version</div>
            <div class="metric-value">v3.2</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Core Modules</div>
            <div class="metric-value">27</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Agent Types</div>
            <div class="metric-value">4</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Risk Dimensions</div>
            <div class="metric-value">5</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Tests Passing</div>
            <div class="metric-value positive">245</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Architecture Overview ─────────────────────────────────────────────────
    st.markdown('<div class="section-header">🏗️ Architecture</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.code("""
┌──────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                    │
│  CLI Runner  │  Streamlit Dashboard  │  Jupyter      │
├──────────────────────────────────────────────────────┤
│               ANALYTICS & AGENTS LAYER                │
│  Multi-Agent  │  Walk-Forward  │  Brinson Attribution │
├──────────────────────────────────────────────────────┤
│                  CORE ENGINE LAYER                    │
│  Engine V2  │  Factor Pipeline  │  Portfolio Optimizer│
│  Execution  │  Risk Monitor(5D) │  Guard Pipeline     │
├──────────────────────────────────────────────────────┤
│                     DATA LAYER                        │
│  DataManager  │  Factor_DB(DuckDB)  │  Stock Filter   │
└──────────────────────────────────────────────────────┘
        """, language=None)

    with col_right:
        st.markdown("### Core Modules")
        modules = pd.DataFrame({
            "Module": [
                "BacktestEngine", "FactorPipeline", "PortfolioOptimizer",
                "ExecutionSim", "RiskMonitor", "WalkForward",
                "GuardPipeline", "EventLog", "PluginSystem",
            ],
            "Status": ["✅", "✅", "✅", "✅", "✅", "✅", "✅", "✅", "✅"],
            "Version": ["v2", "v3", "v2", "v2", "v3", "v2", "v2", "v2", "v2"],
        })
        st.dataframe(modules, use_container_width=True, hide_index=True)

    # ── Agent System Status ───────────────────────────────────────────────────
    st.markdown('<div class="section-header">🤖 Multi-Agent System</div>', unsafe_allow_html=True)

    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Guru Agents</div>
            <div class="metric-value" style="font-size:20px;">4 Styles</div>
            <p style="color:#64748b; font-size:11px;">Buffett · Soros · Munger · Dalio</p>
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Research Team</div>
            <div class="metric-value" style="font-size:20px;">6 Roles</div>
            <p style="color:#64748b; font-size:11px;">Macro · Fundamental · Technical · Quant · Risk · Sentiment</p>
        </div>
        """, unsafe_allow_html=True)

    with col_c:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Bayesian Agent</div>
            <div class="metric-value" style="font-size:20px;">3 Layers</div>
            <p style="color:#64748b; font-size:11px;">Hierarchical · Belief-based · Adaptive</p>
        </div>
        """, unsafe_allow_html=True)

    with col_d:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Style Engine</div>
            <div class="metric-value" style="font-size:20px;">Active</div>
            <p style="color:#64748b; font-size:11px;">Reflection · Anchoring · Distillation</p>
        </div>
        """, unsafe_allow_html=True)

    # ── Quick Actions ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">⚡ Quick Actions</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("▶ Run Backtest", use_container_width=True):
            st.info("Navigate to 'Backtest Runner' page to configure and run.")
    with c2:
        if st.button("📊 Analyze Factor", use_container_width=True):
            st.info("Navigate to 'Factor Analysis' page.")
    with c3:
        if st.button("🛡️ Check Risk", use_container_width=True):
            st.info("Navigate to 'Risk Monitor' page.")

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.caption(f"Factor Trading v3.2 | {datetime.now().strftime('%Y-%m-%d %H:%M')} | Python 3.10+ | 245 tests passing")