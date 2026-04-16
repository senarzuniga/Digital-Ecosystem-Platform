"""
Page 01 – Company Dashboard
===========================
KPIs, machine fleet overview, live alerts, and OEE trend.
"""

import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header
from utils.data_generator import (
    generate_machines,
    generate_alerts,
    generate_service_orders,
)

st.set_page_config(page_title="Dashboard · DEP", page_icon="📊", layout="wide")
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

# ── Active company ─────────────────────────────────────────────────────────────
import json

COMPANIES = json.loads((ROOT / "config" / "companies.json").read_text())
COMPANY_MAP = {c["name"]: c for c in COMPANIES}

with st.sidebar:
    st.markdown(
        "<div style='font-size:16px;font-weight:700;color:#E0E8F0;padding:12px 0 4px;'>"
        "🏭 Digital Ecosystem</div>"
        "<hr style='border-color:#263C55;margin:4px 0 12px;'/>",
        unsafe_allow_html=True,
    )
    st.markdown("**🏢 Active Company**")
    sel = st.selectbox(
        "Company",
        [c["name"] for c in COMPANIES],
        index=COMPANIES.index(
            next((c for c in COMPANIES if c["name"] == st.session_state.get("active_company", {}).get("name")),
                 COMPANIES[0])
        ),
        label_visibility="collapsed",
        key="dash_company",
    )
    company = COMPANY_MAP[sel]
    st.session_state["active_company"] = company
    mat = MATURITY_LEVELS[company["maturity_level"]]
    st.markdown(
        f"<span class='maturity-pill' style='background:{mat['bg']};color:{mat['color']};'>"
        f"{mat['label']}</span>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='border-color:#263C55;margin:12px 0;'/>", unsafe_allow_html=True)
    st.page_link("app.py",                           label="🏠  Overview")
    st.page_link("pages/01_Dashboard.py",            label="📊  Dashboard")
    st.page_link("pages/02_Machine_Connectivity.py", label="🔌  Connectivity")
    st.page_link("pages/03_Digital_Twins.py",        label="🪞  Digital Twins")
    st.page_link("pages/04_AI_Agents.py",            label="🤖  AI Agents")
    st.page_link("pages/05_Maturity_Model.py",       label="📈  Maturity Model")
    st.page_link("pages/06_Ecosystem_Blueprint.py",  label="🗺️  Blueprint")
    st.page_link("pages/07_After_Sales_Engine.py",   label="💰  After-Sales")

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="dep-page-title">📊 Company Dashboard</div>'
    '<div class="dep-page-subtitle">Fleet health, OEE, service performance and live alerts</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)

# ── Data ───────────────────────────────────────────────────────────────────────
machines_df = generate_machines(company)
alerts_df   = generate_alerts(company, n=10)
orders_df   = generate_service_orders(company, n=30)

# ── KPI row ────────────────────────────────────────────────────────────────────
online   = len(machines_df[machines_df["Status"] == "Online"])
warnings = len(machines_df[machines_df["Status"] == "Warning"])
offline  = len(machines_df[machines_df["Status"] == "Offline"])
avg_oee  = machines_df["OEE (%)"].mean()
avg_health = machines_df["Health Score"].mean()
critical_alerts = len(alerts_df[alerts_df["Severity"] == "Critical"])
completed_orders = len(orders_df[orders_df["Status"] == "Completed"])
svc_revenue = orders_df[orders_df["Status"] == "Completed"]["Revenue ($)"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Machines Online",   f"{online} / {company['machines']}")
c2.metric("Avg Fleet OEE",     f"{avg_oee:.1f}%",  delta=f"{avg_oee - 75:.1f}% vs target")
c3.metric("Avg Health Score",  f"{avg_health:.0f}/100")
c4.metric("Critical Alerts",   critical_alerts,   delta_color="inverse", delta=f"-{critical_alerts}" if critical_alerts else "0")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Active Contracts",   company["active_contracts"])
c6.metric("Employees",          company["employees"])
c7.metric("Service Orders (YTD)", completed_orders)
c8.metric("Service Revenue ($)", f"{svc_revenue:,.0f}")

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

# ── Charts row ─────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.markdown('<div class="dep-section-header">OEE Distribution by Machine Type</div>', unsafe_allow_html=True)
    fig = px.box(
        machines_df, x="Type", y="OEE (%)",
        color="Type",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(
        showlegend=False, height=320,
        margin=dict(l=0, r=0, t=10, b=80),
        xaxis_title="", yaxis_title="OEE (%)",
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(tickangle=-30, tickfont=dict(size=11))
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.markdown('<div class="dep-section-header">Fleet Status Breakdown</div>', unsafe_allow_html=True)
    status_counts = machines_df["Status"].value_counts()
    fig2 = go.Figure(go.Pie(
        labels=status_counts.index.tolist(),
        values=status_counts.values.tolist(),
        hole=0.52,
        marker_colors=["#43A047", "#FFA726", "#EF5350"],
    ))
    fig2.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10),
                       paper_bgcolor="white", showlegend=True)
    st.plotly_chart(fig2, use_container_width=True)

# ── Health score scatter ───────────────────────────────────────────────────────
st.markdown('<div class="dep-section-header">Machine Age vs Health Score</div>', unsafe_allow_html=True)
fig3 = px.scatter(
    machines_df, x="Age (years)", y="Health Score",
    color="Status",
    color_discrete_map={"Online": "#43A047", "Warning": "#FFA726", "Offline": "#EF5350"},
    hover_data=["Machine ID", "Type", "OEE (%)"],
    size_max=10,
)
fig3.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                   plot_bgcolor="white", paper_bgcolor="white")
st.plotly_chart(fig3, use_container_width=True)

# ── Recent alerts ──────────────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Live Platform Alerts</div>', unsafe_allow_html=True)

for _, row in alerts_df.iterrows():
    sev = row["Severity"]
    chip = {"Critical": "chip-error", "Warning": "chip-warn", "Info": "chip-info"}.get(sev, "chip-info")
    st.markdown(
        f"""
        <div style='background:white;border:1px solid #E2EAF3;border-radius:8px;
                    padding:10px 16px;margin-bottom:6px;display:flex;align-items:center;gap:12px;'>
          <span class='{chip}'>{sev}</span>
          <span style='font-size:13px;color:#1A2E44;flex:1;'>{row["Description"]}</span>
          <span style='font-size:11px;color:#A0AEC0;white-space:nowrap;'>{row["Machine"]} · {row["Timestamp"]}</span>
          <span style='font-size:11px;color:#6B7C93;background:#F7F9FC;border-radius:10px;
                       padding:2px 8px;'>{row["Agent"]}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
