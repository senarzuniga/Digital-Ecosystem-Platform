"""
Page 02 – Machine Connectivity
================================
Real-time IIoT machine status, sensor streams, and edge topology.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header
from utils.data_generator import generate_machines, generate_telemetry

st.set_page_config(page_title="Machine Connectivity · DEP", page_icon="🔌", layout="wide")
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
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
        key="conn_company",
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
    '<div class="dep-page-title">🔌 Machine Connectivity</div>'
    '<div class="dep-page-subtitle">Real-time IIoT status, sensor streams, and connectivity health</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)

# ── Data ───────────────────────────────────────────────────────────────────────
machines_df = generate_machines(company)
online  = len(machines_df[machines_df["Status"] == "Online"])
warning = len(machines_df[machines_df["Status"] == "Warning"])
offline = len(machines_df[machines_df["Status"] == "Offline"])
connected = machines_df["Connected"].sum()

# ── Connectivity KPIs ──────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Connected Machines", f"{connected} / {len(machines_df)}")
c2.metric("Online",   online,   delta=f"{online/len(machines_df)*100:.0f}%")
c3.metric("Warning",  warning,  delta_color="inverse", delta=str(warning) if warning else "0")
c4.metric("Offline",  offline,  delta_color="inverse", delta=str(offline) if offline else "0")

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

# ── Filters ────────────────────────────────────────────────────────────────────
col_f1, col_f2 = st.columns([1, 1])
with col_f1:
    status_filter = st.multiselect(
        "Filter by Status",
        options=["Online", "Warning", "Offline"],
        default=["Online", "Warning", "Offline"],
    )
with col_f2:
    type_filter = st.multiselect(
        "Filter by Machine Type",
        options=sorted(machines_df["Type"].unique().tolist()),
        default=[],
        placeholder="All types",
    )

filtered = machines_df[machines_df["Status"].isin(status_filter)]
if type_filter:
    filtered = filtered[filtered["Type"].isin(type_filter)]

st.markdown('<div class="dep-section-header">Machine Fleet Status</div>', unsafe_allow_html=True)

# ── Fleet table ────────────────────────────────────────────────────────────────
def colour_status(val):
    colors = {"Online": "#E8F5E9", "Warning": "#FFF8E1", "Offline": "#FFEBEE"}
    return f"background-color: {colors.get(val, 'white')};"


display_df = filtered[[
    "Machine ID", "Type", "Status", "OEE (%)", "Health Score",
    "Temp (°C)", "Vibration (mm/s)", "Age (years)", "Next PM (days)", "Connected"
]].copy()

styled = display_df.style.applymap(colour_status, subset=["Status"])
st.dataframe(styled, use_container_width=True, height=320)

# ── Telemetry drill-down ───────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Machine Sensor Stream – Drill-Down</div>', unsafe_allow_html=True)

machine_ids = filtered["Machine ID"].tolist()
if machine_ids:
    selected_machine = st.selectbox("Select machine", machine_ids)
    tel_df = generate_telemetry(selected_machine, hours=24)

    tab1, tab2, tab3 = st.tabs(["🌡️ Temperature", "📳 Vibration", "⚡ Power"])

    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=tel_df["Timestamp"], y=tel_df["Temperature (°C)"],
            line=dict(color="#1565C0", width=2), name="Temp (°C)",
        ))
        fig.add_hline(y=80, line_dash="dash", line_color="#EF5350",
                      annotation_text="Critical threshold")
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                          plot_bgcolor="white", paper_bgcolor="white",
                          yaxis_title="°C")
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=tel_df["Timestamp"], y=tel_df["Vibration (mm/s)"],
            line=dict(color="#6A1B9A", width=2), fill="tozeroy",
            fillcolor="rgba(106,27,154,0.08)", name="Vibration",
        ))
        fig2.add_hline(y=3.5, line_dash="dash", line_color="#FFA726",
                       annotation_text="Warning threshold")
        fig2.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                           plot_bgcolor="white", paper_bgcolor="white",
                           yaxis_title="mm/s")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=tel_df["Timestamp"], y=tel_df["Power (kW)"],
            line=dict(color="#2E7D32", width=2), name="Power (kW)",
        ))
        fig3.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                           plot_bgcolor="white", paper_bgcolor="white",
                           yaxis_title="kW")
        st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No machines match the current filters.")

# ── Architecture note ──────────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">IIoT Architecture Layers</div>', unsafe_allow_html=True)

layers = [
    ("Layer 1 · Physical / Data",    "#1565C0",
     "Machines, PLCs, sensors, edge gateways, SCADA, on-premise historians → "
     "OEE-agnostic data ingestion with OPC-UA / MQTT / REST adapters."),
    ("Layer 2 · Digital Core",       "#2E7D32",
     "Streaming pipeline (Kafka/Kinesis), data lake, feature store, "
     "digital twins per machine/process/plant/supply chain, ERP/MES integration."),
    ("Layer 3 · AI Agent Layer",     "#880E4F",
     "Orchestrator + 7 specialized agents: Operational, Optimization, Maintenance, "
     "Commercial, Engineering, Management/CEO, Customer Success."),
]

for title, color, desc in layers:
    st.markdown(
        f"""
        <div style='border-left:4px solid {color};background:white;border-radius:6px;
                    padding:12px 16px;margin-bottom:10px;border:1px solid #E2EAF3;
                    border-left:4px solid {color};'>
          <div style='font-size:14px;font-weight:600;color:{color};margin-bottom:4px;'>{title}</div>
          <div style='font-size:13px;color:#4A5568;'>{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
