"""
Digital Ecosystem Platform – Main Entry Point
==============================================
Multi-company workspace selection and platform overview.
"""

import json
import sys
from pathlib import Path

import streamlit as st

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header
from utils.data_generator import generate_machines, generate_alerts

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Digital Ecosystem Platform",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

# ── Load companies ─────────────────────────────────────────────────────────────
@st.cache_data
def load_companies():
    with open(ROOT / "config" / "companies.json") as f:
        return json.load(f)

COMPANIES = load_companies()
COMPANY_MAP = {c["name"]: c for c in COMPANIES}

# ── Sidebar – company selector ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style='text-align:center;padding:20px 0 12px;border-bottom:2px solid #FF6A00;margin-bottom:16px;'>
          <div style='font-size:32px;margin-bottom:4px;'>🏭</div>
          <div style='font-size:17px;font-weight:700;color:#FF6A00;letter-spacing:-0.5px;font-family:"Montserrat", sans-serif;'>
            INGECART
          </div>
          <div style='font-size:12px;color:#7E848E;font-weight:500;margin-top:4px;'>
            Industrial Intelligence Platform
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**🏢 ACTIVE COMPANY**")
    selected_name = st.selectbox(
        "Select company to work with",
        options=[c["name"] for c in COMPANIES],
        key="active_company_name",
        label_visibility="collapsed",
    )
    company = COMPANY_MAP[selected_name]

    # Persist company in session state
    st.session_state["active_company"] = company

    mat = MATURITY_LEVELS[company["maturity_level"]]
    st.markdown(
        f"""
        <div style='background:#1A1D24;border:1px solid #FF6A0055;border-left:3px solid #FF6A00;padding:12px;margin-top:12px;'>
          <div style='font-size:11px;color:#7E848E;font-weight:600;text-transform:uppercase;
                      letter-spacing:0.8px;'>Maturity Level</div>
          <div style='margin-top:6px;'>
            <span class='maturity-pill' style='background:{mat["bg"]};color:{mat["color"]};
                  font-size:12px;padding:6px 10px;border-left:3px solid {mat["color"]};'>
              {mat["label"]}
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='border-top:1px solid #FF6A0044;margin:20px 0;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='font-size:11px;color:#7E848E;font-weight:600;text-transform:uppercase;
                    letter-spacing:0.8px;margin-bottom:12px;'>Navigation</div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link("app.py",                          label="🏠  Platform Overview")
    st.page_link("pages/01_Dashboard.py",           label="📊  Company Dashboard")
    st.page_link("pages/02_Machine_Connectivity.py",label="🔌  Machine Connectivity")
    st.page_link("pages/03_Digital_Twins.py",       label="🪞  Digital Twins")
    st.page_link("pages/04_AI_Agents.py",           label="🤖  AI Agent Center")
    st.page_link("pages/05_Maturity_Model.py",      label="📈  Maturity Model")
    st.page_link("pages/06_Ecosystem_Blueprint.py", label="🗺️  Ecosystem Blueprint")
    st.page_link("pages/07_After_Sales_Engine.py",  label="💰  After-Sales Engine")

    st.markdown("<div style='border-top:1px solid #FF6A0044;margin:20px 0;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:11px;color:#7E848E;text-align:center;'>"
        "© 2026 INGECART · Industrial Intelligence</div>",
        unsafe_allow_html=True,
    )

# ── Main content ───────────────────────────────────────────────────────────────
st.markdown(
    '<div class="dep-page-title">INDUSTRIAL INTELLIGENCE PLATFORM</div>'
    '<div class="dep-page-subtitle">'
    'AI-powered automation & optimization for machine manufacturers'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(render_company_header(company), unsafe_allow_html=True)

# ── Platform KPIs ──────────────────────────────────────────────────────────────
machines_df = generate_machines(company)
online   = len(machines_df[machines_df["Status"] == "Online"])
warnings = len(machines_df[machines_df["Status"] == "Warning"])
offline  = len(machines_df[machines_df["Status"] == "Offline"])
avg_oee  = machines_df["OEE (%)"].mean()
avg_health = machines_df["Health Score"].mean()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Machines",     company["machines"])
col2.metric("Online",             online,   delta=f"{online/company['machines']*100:.0f}%")
col3.metric("Warnings",           warnings, delta=f"-{warnings}" if warnings else "0", delta_color="inverse")
col4.metric("Avg OEE",            f"{avg_oee:.1f}%")
col5.metric("Avg Health Score",   f"{avg_health:.0f}/100")

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

# ── Platform module cards ──────────────────────────────────────────────────────
st.markdown('<div class="dep-section-header">Platform Modules</div>', unsafe_allow_html=True)

modules = [
    ("📊", "Company Dashboard",      "KPIs, alerts, and operational overview for the active company."),
    ("🔌", "Machine Connectivity",   "Real-time IIoT machine status, sensor streams, and edge topology."),
    ("🪞", "Digital Twins",          "Live digital twin status, divergence tracking, and recalibration triggers."),
    ("🤖", "AI Agent Center",        "7 specialized AI agents across operations, maintenance, commerce and strategy."),
    ("📈", "Maturity Model",         "L1–L5 ecosystem maturity assessment with progression roadmap."),
    ("🗺️", "Ecosystem Blueprint",   "Full best-practice IIoT + AI digital ecosystem blueprint."),
    ("💰", "After-Sales Engine",     "Installed base visibility, upsell triggers, service orders, and recurring revenue."),
]

cols = st.columns(3)
for idx, (icon, title, desc) in enumerate(modules):
    with cols[idx % 3]:
        st.markdown(
            f"""
            <div style='background:#1A1D24;
                        border: 1px solid #FF6A0044;
                        border-left: 3px solid #FF6A00;
                        border-radius: 2px;
                        padding: 18px;
                        margin-bottom: 14px;
                        box-shadow: 0 0 15px rgba(255, 106, 0, 0.05);
                        min-height: 110px;'>
              <div style='font-size: 26px; margin-bottom: 6px;'>{icon}</div>
              <div style='font-size: 15px; font-weight: 600; color: #FF6A00; margin-bottom: 4px; font-family: "Montserrat", sans-serif;'>{title}</div>
              <div style='font-size: 13px; color: #7E848E;'>{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Recent alerts strip ────────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Recent Platform Alerts</div>', unsafe_allow_html=True)

alerts_df = generate_alerts(company, n=5)
for _, row in alerts_df.iterrows():
    sev = row["Severity"]
    chip_class = {"Critical": "chip-error", "Warning": "chip-warn", "Info": "chip-info"}.get(sev, "chip-info")
    st.markdown(
        f"""
        <div style='background: #1A1D24;
                    border: 1px solid #FF6A0044;
                    border-left: 3px solid #FF6A00;
                    border-radius: 2px;
                    padding: 10px 16px;
                    margin-bottom: 6px;
                    display: flex;
                    align-items: center;
                    gap: 12px;'>
          <span class='{chip_class}'>{sev}</span>
          <span style='font-size: 13px; color: #F4F5F7; flex: 1;'>{row["Description"]}</span>
          <span style='font-size: 11px; color: #7E848E; white-space: nowrap;'>{row["Machine"]} · {row["Timestamp"]}</span>
          <span style='font-size: 11px; color: #FF6A00; background: #1A1D24; border: 1px solid #FF6A0055;
                       border-radius: 0px; padding: 3px 8px;'>{row["Agent"]}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
