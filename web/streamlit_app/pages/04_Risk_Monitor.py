"""
Page 4: Risk Monitor
====================
Five-dimensional risk monitoring: Fundamental, Industry, Macro, CapitalFlow, Sentiment.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np


def render() -> None:
    st.markdown('<div class="section-header">🛡️ Risk Monitor</div>', unsafe_allow_html=True)

    # ── Overall Risk Score ────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class="metric-card" style="text-align:center;">
            <div class="metric-label">Composite Risk Score</div>
            <div class="metric-value" style="color:#10b981; font-size:36px;">0.32</div>
            <p style="color:#10b981; font-size:12px;">L3 — Monitor</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="metric-card" style="text-align:center;">
            <div class="metric-label">Active Alerts</div>
            <div class="metric-value" style="color:#f59e0b; font-size:36px;">1</div>
            <p style="color:#64748b; font-size:12px;">Last: 2024-06-15</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="metric-card" style="text-align:center;">
            <div class="metric-label">Max Drawdown</div>
            <div class="metric-value negative" style="font-size:36px;">-12.3%</div>
            <p style="color:#64748b; font-size:12px;">Limit: -20%</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class="metric-card" style="text-align:center;">
            <div class="metric-label">VaR (95%)</div>
            <div class="metric-value negative" style="font-size:36px;">-2.8%</div>
            <p style="color:#64748b; font-size:12px;">Daily</p>
        </div>
        """, unsafe_allow_html=True)

    # ── Five-Dimensional Radar ────────────────────────────────────────────────
    st.markdown("### 🎯 Five-Dimensional Risk Breakdown")

    st.markdown("""
    <div style="display:flex; gap:16px; margin:16px 0;">
        <div class="metric-card" style="flex:1; text-align:center;">
            <div class="metric-label">Fundamental</div>
            <div class="metric-value" style="font-size:24px; color:#10b981;">0.15</div>
            <div style="width:100%; height:4px; background:#2a3040; border-radius:2px; margin-top:8px;">
                <div style="width:15%; height:100%; background:#10b981; border-radius:2px;"></div>
            </div>
        </div>
        <div class="metric-card" style="flex:1; text-align:center;">
            <div class="metric-label">Industry</div>
            <div class="metric-value" style="font-size:24px; color:#10b981;">0.22</div>
            <div style="width:100%; height:4px; background:#2a3040; border-radius:2px; margin-top:8px;">
                <div style="width:22%; height:100%; background:#10b981; border-radius:2px;"></div>
            </div>
        </div>
        <div class="metric-card" style="flex:1; text-align:center;">
            <div class="metric-label">Macro</div>
            <div class="metric-value" style="font-size:24px; color:#f59e0b;">0.48</div>
            <div style="width:100%; height:4px; background:#2a3040; border-radius:2px; margin-top:8px;">
                <div style="width:48%; height:100%; background:#f59e0b; border-radius:2px;"></div>
            </div>
        </div>
        <div class="metric-card" style="flex:1; text-align:center;">
            <div class="metric-label">CapitalFlow</div>
            <div class="metric-value" style="font-size:24px; color:#10b981;">0.18</div>
            <div style="width:100%; height:4px; background:#2a3040; border-radius:2px; margin-top:8px;">
                <div style="width:18%; height:100%; background:#10b981; border-radius:2px;"></div>
            </div>
        </div>
        <div class="metric-card" style="flex:1; text-align:center;">
            <div class="metric-label">Sentiment</div>
            <div class="metric-value" style="font-size:24px; color:#10b981;">0.25</div>
            <div style="width:100%; height:4px; background:#2a3040; border-radius:2px; margin-top:8px;">
                <div style="width:25%; height:100%; background:#10b981; border-radius:2px;"></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Risk Level Table ──────────────────────────────────────────────────────
    st.markdown("### 📊 Risk Level Triggers")

    risk_levels = pd.DataFrame({
        "Level": ["🟢 L3", "🟡 L2", "🔴 L1"],
        "Score Threshold": [">= 0.3", ">= 0.6", ">= 0.85"],
        "Action": ["加强监控", "仓位降至50%", "不计成本清仓"],
        "Status": ["Active", "Standby", "Standby"],
    })
    st.dataframe(risk_levels, use_container_width=True, hide_index=True)

    # ── Guard Pipeline Status ─────────────────────────────────────────────────
    st.markdown("### 🛡️ Guard Pipeline Checks")

    guards = pd.DataFrame({
        "Check": [
            "Position Limit", "Max Drawdown", "Cooldown Period",
            "Turnover Limit", "Concentration", "Leverage",
        ],
        "Status": ["✅", "✅", "✅", "✅", "⚠️", "✅"],
        "Limit": ["≤ 10%", "≤ 20%", "≥ 5 days", "≤ 50%", "≤ 30%", "≤ 1.5x"],
        "Current": ["3.2%", "12.3%", "7 days", "22%", "28%", "1.0x"],
    })

    st.dataframe(guards, use_container_width=True, hide_index=True)

    # ── Global Contagion ──────────────────────────────────────────────────────
    st.markdown("### 🌐 Global Contagion Monitor")

    col1, col2 = st.columns(2)

    with col1:
        contagion = pd.DataFrame({
            "Market": ["S&P 500", "HSI", "Nikkei 225", "FTSE 100", "DAX"],
            "Correlation": [0.45, 0.72, 0.38, 0.25, 0.31],
            "Spillover": [0.12, 0.35, 0.08, 0.05, 0.09],
            "CoVaR": ["-1.8%", "-3.2%", "-1.2%", "-0.8%", "-1.0%"],
        })
        st.dataframe(contagion, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### Recent Alerts")
        alerts = pd.DataFrame({
            "Time": ["2024-06-15 14:30", "2024-05-20 09:45"],
            "Dimension": ["Macro", "Sentiment"],
            "Level": ["🟡 L2", "🟢 L3"],
            "Message": ["PMI below 50 for 3 months", "Negative news sentiment spike"],
        })
        st.dataframe(alerts, use_container_width=True, hide_index=True)

    st.caption("Risk monitoring requires real-time market data, fundamental data, and news sentiment feeds.")