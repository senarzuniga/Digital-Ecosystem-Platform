"""
Public Streamlit entrypoint for Machine Connectivity only.
Exposes only the ING_SYNC connectivity panel without the rest of the platform pages.
"""

import json
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header
from utils.data_generator import generate_machines, generate_telemetry
from utils.api_client import (
    ensure_factory_simulator_client,
    is_backend_healthy,
    list_external_clients,
    list_normalized_events,
    list_normalized_requests,
    poll_external_client,
)

st.set_page_config(
    page_title="ING_SYNC · Machine Connectivity",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

COMPANIES = json.loads((ROOT / "config" / "companies.json").read_text())
COMPANY_MAP = {c["name"]: c for c in COMPANIES}

with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:16px 0 12px;border-bottom:1px solid rgba(255,106,0,0.2);margin-bottom:14px;'>"
        "<div style='font-size:10px;font-weight:700;color:#FF6A00;letter-spacing:4px;text-transform:uppercase;margin-bottom:6px;'>◆ ING_SYNC</div>"
        "<div style='font-family:Poppins,sans-serif;font-size:18px;font-weight:800;color:#EDEFF2;letter-spacing:-0.5px;'>PUBLIC PANEL</div>"
        "<div style='font-size:10px;color:#8898AA;margin-top:3px;letter-spacing:0.5px;'>Machine Connectivity</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    default_company = st.session_state.get("active_company", {}).get("name", COMPANIES[0]["name"])
    selected_name = st.selectbox(
        "Active company",
        options=[c["name"] for c in COMPANIES],
        index=[c["name"] for c in COMPANIES].index(default_company) if default_company in [c["name"] for c in COMPANIES] else 0,
    )
    company = COMPANY_MAP[selected_name]
    st.session_state["active_company"] = company

    mat = MATURITY_LEVELS[company["maturity_level"]]
    st.markdown(
        f"<span class='maturity-pill' style='background:{mat['bg']};color:{mat['color']};'>{mat['label']}</span>",
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="dep-page-title">🔌 ING_SYNC · Machine Connectivity</div>'
    '<div class="dep-page-subtitle">Public real-time IIoT status, sensor streams and connectivity health</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)
token = st.session_state.get("api_token")

if company["id"] == "digital_factory_1":
    st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
    st.markdown('<div class="dep-section-header">Factory-Simulator · Live Monitoring</div>', unsafe_allow_html=True)

    backend_live = is_backend_healthy()
    simulator_clients = []
    selected_client = None

    if backend_live and token:
        clients = list_external_clients(token=token) or []
        simulator_clients = [
            client
            for client in clients
            if client.get("company_id") == company["id"]
            or client.get("id") == company["id"]
            or client.get("name") == "Factory-Simulator"
        ]
        if not simulator_clients:
            bootstrapped_client = ensure_factory_simulator_client(token)
            if bootstrapped_client:
                simulator_clients = [bootstrapped_client]

    client_id = company["id"]
    if simulator_clients:
        client_options = {
            f"{client.get('name', client.get('id', 'External source'))} · {client.get('status', 'unknown')}": client
            for client in simulator_clients
        }
        selected_label = st.selectbox("External source", options=list(client_options.keys()), key="factory_simulator_source")
        selected_client = client_options[selected_label]
        client_id = selected_client.get("id", company["id"])

    col_poll, col_status = st.columns([1, 2])
    with col_poll:
        if st.button("🔄 Poll external source now", disabled=not (backend_live and token and selected_client)):
            result = poll_external_client(client_id, token=token) if backend_live and token and selected_client else None
            if result:
                st.success(
                    f"Ingested events={result.get('events_ingested', 0)} · requests={result.get('requests_ingested', 0)}"
                )
            else:
                st.warning("Polling failed. Check API login and simulator endpoint configuration.")

    with col_status:
        if not backend_live:
            st.warning("Backend is not reachable. Start FastAPI backend to enable live ingestion.")
        elif not token:
            st.info("Live simulator access requires API login.")
        elif not selected_client:
            st.warning("Factory-Simulator client is not available in backend registry.")
        else:
            st.success(
                f"Connected to {selected_client.get('name', client_id)} via {selected_client.get('connection_type', 'REST')}"
            )

    ext_events = list_normalized_events(client_id, limit=25, token=token) or [] if backend_live and token and selected_client else []
    ext_requests = list_normalized_requests(client_id, limit=25, token=token) or [] if backend_live and token and selected_client else []

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Normalized Events", len(ext_events))
    k2.metric("Critical/High Events", sum(1 for e in ext_events if e.get("severity") in ("critical", "high")))
    k3.metric("Normalized Requests", len(ext_requests))
    k4.metric("Active Requests", sum(1 for r in ext_requests if r.get("status") not in ("completed", "closed")))

machines_df = generate_machines(company)
online = len(machines_df[machines_df["Status"] == "Online"])
warning = len(machines_df[machines_df["Status"] == "Warning"])
offline = len(machines_df[machines_df["Status"] == "Offline"])
connected = machines_df["Connected"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Connected Machines", f"{connected} / {len(machines_df)}")
c2.metric("Online", online, delta=f"{online/len(machines_df)*100:.0f}%")
c3.metric("Warning", warning, delta_color="inverse", delta=str(warning) if warning else "0")
c4.metric("Offline", offline, delta_color="inverse", delta=str(offline) if offline else "0")

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

col_f1, col_f2 = st.columns([1, 1])
with col_f1:
    status_filter = st.multiselect("Filter by Status", options=["Online", "Warning", "Offline"], default=["Online", "Warning", "Offline"])
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

def colour_status(val):
    colors = {
        "Online": "background-color: rgba(34,197,94,0.16);",
        "Warning": "background-color: rgba(255,184,77,0.16);",
        "Offline": "background-color: rgba(255,107,107,0.16);",
    }
    return colors.get(val, "")

show_df = filtered[[
    "Machine ID", "Type", "Status", "OEE (%)", "Health Score",
    "Temp (°C)", "Vibration (mm/s)", "Age (years)", "Next PM (days)", "Connected"
]].copy()

st.dataframe(show_df.style.map(colour_status, subset=["Status"]), use_container_width=True, height=320)

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Machine Sensor Stream · Drill-Down</div>', unsafe_allow_html=True)

machine_ids = filtered["Machine ID"].tolist()
if machine_ids:
    selected_machine = st.selectbox("Select machine", machine_ids)
    tel_df = generate_telemetry(selected_machine, hours=24)

    tab1, tab2, tab3 = st.tabs(["🌡️ Temperature", "📳 Vibration", "⚡ Power"])

    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=tel_df["Timestamp"], y=tel_df["Temperature (°C)"], line=dict(color="#FF6A00", width=2)))
        fig.add_hline(y=80, line_dash="dash", line_color="#EF5350", annotation_text="Critical threshold")
        fig.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(26,33,43,0.6)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis_title="°C",
            font=dict(color="#EDEFF2"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=tel_df["Timestamp"],
                y=tel_df["Vibration (mm/s)"],
                line=dict(color="#6A1B9A", width=2),
                fill="tozeroy",
                fillcolor="rgba(106,27,154,0.08)",
            )
        )
        fig2.add_hline(y=3.5, line_dash="dash", line_color="#FFA726", annotation_text="Warning threshold")
        fig2.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(26,33,43,0.6)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis_title="mm/s",
            font=dict(color="#EDEFF2"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=tel_df["Timestamp"], y=tel_df["Power (kW)"], line=dict(color="#2E7D32", width=2)))
        fig3.update_layout(
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(26,33,43,0.6)",
            paper_bgcolor="rgba(0,0,0,0)",
            yaxis_title="kW",
            font=dict(color="#EDEFF2"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
        )
        st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No machines match the current filters.")
