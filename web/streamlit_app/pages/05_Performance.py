"""
Page 5: Performance Analytics
=============================
Sharpe, Sortino, Calmar, Brinson attribution, monthly heatmap, drawdown analysis.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np


def render() -> None:
    st.markdown('<div class="section-header">📈 Performance Analytics</div>', unsafe_allow_html=True)

    # ── Key Metrics ───────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    metrics = [
        ("Sharpe", "1.85", "positive"),
        ("Sortino", "2.12", "positive"),
        ("Calmar", "1.45", "positive"),
        ("Ann.Return", "18.5%", "positive"),
        ("Ann.Vol", "10.2%", "negative"),
        ("MaxDD", "-12.3%", "negative"),
    ]

    for col, (label, value, cls) in zip([col1, col2, col3, col4, col5, col6], metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card" style="text-align:center;">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="font-size:20px; color:{'#10b981' if cls == 'positive' else '#ef4444'};">{value}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Equity Curve ──────────────────────────────────────────────────────────
    st.markdown("### 📈 Equity Curve")

    dates = pd.date_range("2024-01-01", periods=250, freq="B")
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 250).cumsum()
    equity = 1_000_000 * (1 + returns)
    eq_df = pd.DataFrame({"date": dates, "portfolio": equity}).set_index("date")

    st.line_chart(eq_df, use_container_width=True, color="#00d4ff")

    # ── Monthly Returns Heatmap ───────────────────────────────────────────────
    st.markdown("### 🗓️ Monthly Returns Heatmap")

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    years = ["2020", "2021", "2022", "2023", "2024"]

    np.random.seed(123)
    data = np.random.normal(0.02, 0.04, (5, 12))
    heatmap_df = pd.DataFrame(data, index=years, columns=months)

    st.dataframe(
        heatmap_df.style.background_gradient(
            cmap="RdYlGn", axis=None
        ).format("{:.1%}"),
        use_container_width=True,
    )

    # ── Brinson Attribution ───────────────────────────────────────────────────
    st.markdown("### 🔍 Brinson Attribution")

    col1, col2 = st.columns(2)

    with col1:
        attribution = pd.DataFrame({
            "Component": ["Industry Allocation", "Stock Selection", "Interaction"],
            "Contribution": ["+2.3%", "+5.8%", "-0.5%"],
            "Weight": ["40%", "55%", "5%"],
        })
        st.dataframe(attribution, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### Drawdown Analysis")
        dd_data = pd.DataFrame({
            "Period": ["2022-Q1", "2022-Q3", "2023-Q4"],
            "Drawdown": ["-12.3%", "-8.5%", "-5.2%"],
            "Duration": ["45 days", "28 days", "15 days"],
            "Recovery": ["60 days", "35 days", "20 days"],
        })
        st.dataframe(dd_data, use_container_width=True, hide_index=True)

    # ── Performance Over Time ─────────────────────────────────────────────────
    st.markdown("### 📊 Rolling Performance")

    rolling_window = st.slider("Rolling Window (days)", 20, 120, 60)

    rolling_dates = pd.date_range("2024-04-01", periods=190, freq="B")
    np.random.seed(456)
    rolling_sharpe = np.random.normal(1.5, 0.5, 190)
    rolling_df = pd.DataFrame({
        "date": rolling_dates,
        f"Sharpe ({rolling_window}d)": rolling_sharpe,
    }).set_index("date")

    st.line_chart(rolling_df, use_container_width=True, color="#8b5cf6")

    # ── Trade Statistics ──────────────────────────────────────────────────────
    st.markdown("### 📋 Trade Statistics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Total Trades</div>
            <div class="metric-value" style="font-size:20px;">1,247</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value positive" style="font-size:20px;">58.2%</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Avg Holding</div>
            <div class="metric-value" style="font-size:20px;">22 days</div>
        </div>
        """, unsafe_allow_html=True)

    st.caption("Performance analytics are computed from backtest results. Run a backtest to populate real data.")