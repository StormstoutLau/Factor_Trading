"""
Page 2: Backtest Runner
=======================
Configure and execute backtests with live progress.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from pathlib import Path


def render() -> None:
    st.markdown('<div class="section-header">🚀 Backtest Runner</div>', unsafe_allow_html=True)

    # ── Configuration Form ────────────────────────────────────────────────────
    st.markdown("### ⚙️ Configuration")

    col1, col2 = st.columns(2)

    with col1:
        data_dir = st.text_input("Data Directory", value="./demo_data",
                                 help="Path to market data directory")
        factor_files = st.multiselect(
            "Factor Files",
            options=["factor_value.pkl", "factor_momentum.pkl"],
            default=["factor_value.pkl"],
        )
        initial_capital = st.number_input(
            "Initial Capital", min_value=100_000, value=10_000_000,
            step=1_000_000, format="%d",
        )

    with col2:
        start_date = st.text_input("Start Date", value="2020-01-01")
        end_date = st.text_input("End Date", value="2024-12-31")
        target_count = st.slider("Target Stock Count", 5, 100, 30)

    # ── Factor Config ─────────────────────────────────────────────────────────
    st.markdown("### 📊 Factor Pipeline Config")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        winsorize = st.selectbox("Winsorize", ["mad", "percentile", "std", "none"], index=0)
    with c2:
        fill_method = st.selectbox("Fill Missing", ["median", "mean", "industry", "none"], index=0)
    with c3:
        standardize = st.selectbox("Standardize", ["zscore", "rank", "minmax", "none"], index=0)
    with c4:
        neutralize = st.checkbox("Neutralize (Industry+MarketCap)", value=True)

    # ── Optimizer Config ──────────────────────────────────────────────────────
    st.markdown("### 🎯 Portfolio Optimizer")

    c1, c2, c3 = st.columns(3)
    with c1:
        opt_method = st.selectbox(
            "Optimizer", ["equal_weight", "min_variance", "mean_variance", "risk_parity"],
            index=0,
        )
    with c2:
        rebalance_freq = st.selectbox("Rebalance", ["monthly", "weekly", "daily", "quarterly"], index=0)
    with c3:
        commission = st.number_input("Commission Rate", value=0.0003, format="%.4f", step=0.0001)

    # ── Run Button ────────────────────────────────────────────────────────────
    st.markdown("---")

    col_btn, col_status = st.columns([1, 3])

    with col_btn:
        run_clicked = st.button("▶ Run Backtest", type="primary", use_container_width=True)

    with col_status:
        if run_clicked:
            st.info("Backtest configuration ready. Add real data to execute.")

    # ── Config Summary ────────────────────────────────────────────────────────
    with st.expander("📋 Configuration Summary (JSON)", expanded=False):
        config_dict = {
            "data_dir": data_dir,
            "factor_files": factor_files,
            "initial_capital": initial_capital,
            "start_date": start_date,
            "end_date": end_date,
            "target_count": target_count,
            "factor": {
                "winsorize_method": winsorize,
                "fill_method": fill_method,
                "standardize": standardize,
                "neutralize": neutralize,
            },
            "optimizer": {
                "method": opt_method,
                "rebalance_frequency": rebalance_freq,
            },
            "cost": {
                "commission_rate": commission,
            },
        }
        st.json(config_dict)

    # ── Recent Runs ───────────────────────────────────────────────────────────
    st.markdown("### 📜 Recent Backtest Runs")

    st.dataframe(
        pd.DataFrame({
            "Timestamp": ["—"],
            "Factors": ["—"],
            "Sharpe": ["—"],
            "Return": ["—"],
            "MaxDD": ["—"],
            "Status": ["No runs yet"],
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.caption("Run a backtest to see results here. Output will be saved to `output/` directory.")