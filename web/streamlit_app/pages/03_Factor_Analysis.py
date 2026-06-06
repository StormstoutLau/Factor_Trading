"""
Page 3: Factor Analysis
=======================
IC analysis, factor decay, correlation matrix, and performance visualization.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np


def render() -> None:
    st.markdown('<div class="section-header">📊 Factor Analysis</div>', unsafe_allow_html=True)

    # ── Factor Selection ──────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_factor = st.selectbox(
            "Select Factor",
            options=["factor_value", "factor_momentum"],
            index=0,
        )

    with col2:
        st.markdown("""
        <div style="display:flex; gap:16px; margin-top:8px;">
            <div class="metric-card" style="flex:1;">
                <div class="metric-label">IC Mean</div>
                <div class="metric-value" style="font-size:18px;">—</div>
            </div>
            <div class="metric-card" style="flex:1;">
                <div class="metric-label">IC IR</div>
                <div class="metric-value" style="font-size:18px;">—</div>
            </div>
            <div class="metric-card" style="flex:1;">
                <div class="metric-label">IC Win Rate</div>
                <div class="metric-value" style="font-size:18px;">—</div>
            </div>
            <div class="metric-card" style="flex:1;">
                <div class="metric-label">Turnover</div>
                <div class="metric-value" style="font-size:18px;">—</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── IC Analysis Chart ─────────────────────────────────────────────────────
    st.markdown("### 📈 IC Analysis")

    col1, col2 = st.columns(2)

    with col1:
        # Placeholder IC time series
        dates = pd.date_range("2024-01-01", periods=120, freq="W")
        ic_series = np.random.normal(0.03, 0.08, 120)
        ic_df = pd.DataFrame({"date": dates, "IC": ic_series}).set_index("date")

        st.subheader("IC Time Series")
        st.line_chart(ic_df, use_container_width=True, color="#00d4ff")

    with col2:
        # Placeholder IC histogram
        st.subheader("IC Distribution")
        hist_data = np.random.normal(0.03, 0.08, 1000)
        hist_df = pd.DataFrame({"IC": hist_data})
        st.bar_chart(
            pd.cut(hist_df["IC"], bins=20).value_counts().sort_index(),
            use_container_width=True,
        )

    # ── Factor Decay ──────────────────────────────────────────────────────────
    st.markdown("### ⏳ Factor Decay Analysis")

    decay_horizons = [1, 3, 5, 10, 20, 40, 60]
    decay_values = [0.04, 0.035, 0.03, 0.025, 0.018, 0.01, 0.005]

    decay_df = pd.DataFrame({
        "Horizon (days)": decay_horizons,
        "IC": decay_values,
    }).set_index("Horizon (days)")

    st.line_chart(decay_df, use_container_width=True, color="#10b981")

    # ── Factor Correlation Matrix ─────────────────────────────────────────────
    st.markdown("### 🔗 Factor Correlation Matrix")

    col1, col2 = st.columns([2, 1])

    with col1:
        corr_data = np.array([
            [1.00, 0.15, -0.05, 0.08, 0.12],
            [0.15, 1.00, 0.22, -0.10, 0.05],
            [-0.05, 0.22, 1.00, 0.18, 0.30],
            [0.08, -0.10, 0.18, 1.00, -0.08],
            [0.12, 0.05, 0.30, -0.08, 1.00],
        ])
        factors = ["Value", "Momentum", "Quality", "Size", "Volatility"]
        corr_df = pd.DataFrame(corr_data, index=factors, columns=factors)

        st.dataframe(
            corr_df.style.background_gradient(cmap="RdYlGn", vmin=-1, vmax=1).format("{:.2f}"),
            use_container_width=True,
        )

    with col2:
        st.markdown("### Pipeline Stages")
        st.code("""
Raw Factor
  │
  ├─ [1] Winsorize (MAD)
  │   └─ Remove extreme values
  │
  ├─ [2] Fill Missing
  │   └─ Median imputation
  │
  ├─ [3] Neutralize
  │   └─ Industry + MarketCap
  │
  ├─ [4] Standardize
  │   └─ Z-score normalization
  │
  └─ [5] Combine
      └─ Weighted average
        """, language=None)

    # ── Factor Performance Table ──────────────────────────────────────────────
    st.markdown("### 📊 Factor Performance Summary")

    perf_data = pd.DataFrame({
        "Factor": ["Value", "Momentum", "Quality", "Size", "Volatility"],
        "IC Mean": [0.035, 0.028, 0.022, 0.015, -0.018],
        "IC Std": [0.08, 0.10, 0.07, 0.09, 0.06],
        "IC IR": [0.44, 0.28, 0.31, 0.17, -0.30],
        "Win Rate": ["58%", "54%", "52%", "49%", "45%"],
        "Sharpe": [1.25, 0.98, 1.12, 0.65, -0.42],
        "MaxDD": ["-12.3%", "-15.8%", "-10.2%", "-18.5%", "-22.1%"],
    })

    st.dataframe(perf_data, use_container_width=True, hide_index=True)

    st.caption("Load real factor data to see actual analysis results. Data required: factor values, daily returns, industry classification.")