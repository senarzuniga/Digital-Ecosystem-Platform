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
        <div style='text-align:center;padding:20px 0 14px;border-bottom:1px solid rgba(255,106,0,0.2);margin-bottom:16px;'>
          <div style='font-size:11px;font-weight:700;color:#FF6A00;letter-spacing:4px;text-transform:uppercase;margin-bottom:8px;'>◆ ING_DIGHUB</div>
          <div style='font-family:Poppins,sans-serif;font-size:20px;font-weight:800;color:#EDEFF2;letter-spacing:-0.5px;'>
            INGECART
          </div>
          <div style='font-size:11px;color:#8898AA;font-weight:500;margin-top:4px;letter-spacing:0.5px;'>
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
        <div style='background:rgba(15,22,35,0.9);border:1px solid rgba(255,255,255,0.07);
                    border-left:3px solid #FF6A00;border-radius:12px;padding:12px;margin-top:12px;
                    backdrop-filter:blur(12px);'>
          <div style='font-size:10px;color:#8898AA;font-weight:700;text-transform:uppercase;
                      letter-spacing:1.2px;'>Maturity Level</div>
          <div style='margin-top:6px;'>
            <span class='maturity-pill' style='background:{mat["bg"]};color:{mat["color"]};
                  font-size:11px;padding:6px 12px;border-left:3px solid {mat["color"]};'>
              {mat["label"]}
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='border-top:1px solid rgba(255,106,0,0.12);margin:20px 0;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='font-size:10px;color:#8898AA;font-weight:700;text-transform:uppercase;
                    letter-spacing:1.2px;margin-bottom:12px;'>Navigation</div>
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

    st.markdown("<div style='border-top:1px solid rgba(255,106,0,0.12);margin:20px 0;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:10px;color:#8898AA;text-align:center;letter-spacing:0.5px;'>"
        "© 2026 INGECART · Industrial Intelligence</div>",
        unsafe_allow_html=True,
    )

# ── Hero section ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="
        position: relative;
        background: linear-gradient(135deg, #080F14 0%, #0D1B2A 60%, #080F14 100%);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 24px;
        padding: 56px 48px 52px;
        margin-bottom: 40px;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 32px;
    ">
        <!-- subtle grid overlay -->
        <div style="position:absolute;inset:0;background-image:linear-gradient(rgba(11,59,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(11,59,255,0.03) 1px,transparent 1px);background-size:44px 44px;border-radius:24px;pointer-events:none;"></div>
        <!-- orange ambient glow -->
        <div style="position:absolute;top:-60px;right:260px;width:320px;height:320px;background:radial-gradient(circle,rgba(255,106,0,0.07) 0%,transparent 65%);pointer-events:none;"></div>
        <!-- blue ambient glow -->
        <div style="position:absolute;bottom:-40px;left:80px;width:260px;height:260px;background:radial-gradient(circle,rgba(11,59,255,0.05) 0%,transparent 65%);pointer-events:none;"></div>

        <!-- Left: text content -->
        <div style="position:relative;flex:1;max-width:580px;">
            <div style="font-size:10px;font-weight:700;color:#FF6A00;letter-spacing:4px;text-transform:uppercase;margin-bottom:20px;display:flex;align-items:center;gap:10px;">
                <span style="display:inline-block;width:24px;height:1px;background:#FF6A00;"></span>
                DIGITAL INDUSTRIAL OPERATING ECOSYSTEM
            </div>
            <div style="font-family:'Poppins',sans-serif;font-size:38px;font-weight:800;color:#EDEFF2;line-height:1.1;letter-spacing:-1.5px;margin-bottom:20px;">
                FROM INDUSTRIAL<br>
                <span style="color:#FF6A00;">ENGINEERING</span><br>
                TO DIGITAL<br>
                <span style="color:#4D7CFF;">INTELLIGENCE</span>
            </div>
            <div style="font-size:15px;color:#8898AA;line-height:1.75;max-width:500px;margin-bottom:32px;font-weight:400;">
                ING_DIGHUB connects industrial engineering, automation, AI systems,
                IoT infrastructure, technical documentation and operational analytics
                through one intelligent ecosystem.
            </div>
            <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <span style="background:#FF6A00;color:white;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:14px 28px;border-radius:12px;cursor:pointer;">
                    EXPLORE ECOSYSTEM &rsaquo;
                </span>
                <span style="background:rgba(255,255,255,0.04);color:#EDEFF2;font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;padding:13px 24px;border-radius:12px;border:1px solid rgba(255,255,255,0.1);cursor:pointer;">
                    VIEW SERVICES
                </span>
                <span style="margin-left:6px;font-size:11px;font-weight:700;color:#22C55E;display:inline-flex;align-items:center;gap:6px;letter-spacing:0.8px;text-transform:uppercase;">
                    <span style="width:6px;height:6px;border-radius:50%;background:#22C55E;display:inline-block;box-shadow:0 0 8px #22C55E;animation:pulse-green 2s infinite;"></span>
                    LIVE
                </span>
            </div>
        </div>

        <!-- Right: network topology SVG -->
        <div style="position:relative;flex-shrink:0;opacity:0.75;">
            <svg width="260" height="240" viewBox="0 0 260 240" xmlns="http://www.w3.org/2000/svg">
                <!-- connection lines -->
                <line x1="130" y1="120" x2="50"  y2="50"  stroke="rgba(255,106,0,0.35)"  stroke-width="1.2"/>
                <line x1="130" y1="120" x2="210" y2="50"  stroke="rgba(11,59,255,0.35)"   stroke-width="1.2"/>
                <line x1="130" y1="120" x2="50"  y2="190" stroke="rgba(11,59,255,0.35)"   stroke-width="1.2"/>
                <line x1="130" y1="120" x2="210" y2="190" stroke="rgba(255,106,0,0.35)"   stroke-width="1.2"/>
                <line x1="130" y1="120" x2="130" y2="20"  stroke="rgba(255,255,255,0.12)" stroke-width="1"/>
                <line x1="50"  y1="50"  x2="210" y2="50"  stroke="rgba(255,255,255,0.06)" stroke-width="1" stroke-dasharray="4,4"/>
                <line x1="50"  y1="190" x2="210" y2="190" stroke="rgba(255,255,255,0.06)" stroke-width="1" stroke-dasharray="4,4"/>
                <!-- center hub -->
                <circle cx="130" cy="120" r="16" fill="rgba(255,106,0,0.15)" stroke="#FF6A00" stroke-width="1.5"/>
                <circle cx="130" cy="120" r="6"  fill="#FF6A00"/>
                <!-- satellite nodes -->
                <circle cx="50"  cy="50"  r="9" fill="rgba(11,59,255,0.15)"  stroke="#4D7CFF" stroke-width="1.2"/>
                <circle cx="50"  cy="50"  r="3" fill="#4D7CFF"/>
                <circle cx="210" cy="50"  r="9" fill="rgba(11,59,255,0.15)"  stroke="#4D7CFF" stroke-width="1.2"/>
                <circle cx="210" cy="50"  r="3" fill="#4D7CFF"/>
                <circle cx="50"  cy="190" r="9" fill="rgba(34,197,94,0.15)"  stroke="#22C55E" stroke-width="1.2"/>
                <circle cx="50"  cy="190" r="3" fill="#22C55E"/>
                <circle cx="210" cy="190" r="9" fill="rgba(255,184,77,0.15)" stroke="#FFB84D" stroke-width="1.2"/>
                <circle cx="210" cy="190" r="3" fill="#FFB84D"/>
                <circle cx="130" cy="20"  r="7" fill="rgba(255,106,0,0.15)"  stroke="#FF6A00" stroke-width="1"/>
                <circle cx="130" cy="20"  r="2" fill="#FF6A00"/>
                <!-- labels -->
                <text x="130" y="147" text-anchor="middle" fill="#FF6A00"  font-size="7.5" font-family="Inter" font-weight="700" letter-spacing="0.5">ING_DIGHUB</text>
                <text x="50"  y="38"  text-anchor="middle" fill="#8898AA"  font-size="7"   font-family="Inter" font-weight="600">ING_SYNC</text>
                <text x="210" y="38"  text-anchor="middle" fill="#8898AA"  font-size="7"   font-family="Inter" font-weight="600">ING_TRADE</text>
                <text x="50"  y="210" text-anchor="middle" fill="#8898AA"  font-size="7"   font-family="Inter" font-weight="600">ING_CTA</text>
                <text x="210" y="210" text-anchor="middle" fill="#8898AA"  font-size="7"   font-family="Inter" font-weight="600">ING_DOCLOUD</text>
                <text x="130" y="11"  text-anchor="middle" fill="#8898AA"  font-size="7"   font-family="Inter" font-weight="600">ING_ANALYTICS</text>
            </svg>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Active company context ─────────────────────────────────────────────────────
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

# ── Ecosystem services ─────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-bottom:8px;">
        <div style="font-size:10px;font-weight:700;color:#FF6A00;letter-spacing:4px;text-transform:uppercase;margin-bottom:10px;">◆ THE ING_DIGHUB ECOSYSTEM</div>
        <div style="font-family:'Poppins',sans-serif;font-size:22px;font-weight:700;color:#EDEFF2;letter-spacing:-0.5px;">
            Five Services. One Intelligent Platform.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

ECOSYSTEM_SERVICES = [
    {
        "id": "ING_SYNC",
        "claim": "Where machines speak the same language",
        "desc": "IoT connectivity, real-time data streams and industrial protocols — OPC-UA, MQTT, REST — unified in one edge-to-cloud layer.",
        "color": "#4D7CFF",
        "tags": ["IoT", "OPC-UA", "MQTT", "Edge Computing"],
    },
    {
        "id": "ING_TRADE",
        "claim": "Smart trade for smart factories",
        "desc": "Supply chain intelligence, logistics AI, warehouse management and procurement automation for industrial ecosystems.",
        "color": "#FF6A00",
        "tags": ["Supply Chain", "Logistics AI", "Procurement"],
    },
    {
        "id": "ING_CTA",
        "claim": "From concept to automation",
        "desc": "Advanced engineering, technical diagrams, industrial automation design and full system integration services.",
        "color": "#EDEFF2",
        "tags": ["Engineering", "Automation", "Integration"],
    },
    {
        "id": "ING_ANALYTICS",
        "claim": "Decisions powered by data",
        "desc": "Predictive AI, operational analytics, KPI dashboards and real-time data visualization for manufacturing intelligence.",
        "color": "#00C8FF",
        "tags": ["Predictive AI", "Analytics", "Dashboards"],
    },
    {
        "id": "ING_DOCLOUD",
        "claim": "Industrial knowledge. Structured digitally.",
        "desc": "Smart documentation, cloud knowledge base and digital industrial repository for structured technical information.",
        "color": "#7B93B0",
        "tags": ["Documentation", "Cloud", "Knowledge Base"],
    },
]

eco_cols = st.columns(5)
for idx, svc in enumerate(ECOSYSTEM_SERVICES):
    with eco_cols[idx]:
        st.markdown(
            f"""
            <div style="
                background: rgba(15,22,35,0.85);
                border: 1px solid rgba(255,255,255,0.07);
                border-top: 2px solid {svc['color']};
                border-radius: 20px;
                padding: 20px 16px;
                backdrop-filter: blur(12px);
                box-shadow: 0 4px 24px rgba(0,0,0,0.3);
                min-height: 220px;
                transition: transform 0.25s ease;
            ">
                <div style="font-family:'Poppins',sans-serif;font-size:14px;font-weight:800;
                            color:{svc['color']};letter-spacing:0.5px;margin-bottom:6px;">
                    {svc['id']}
                </div>
                <div style="font-size:12px;color:#8898AA;font-style:italic;margin-bottom:10px;line-height:1.45;">
                    {svc['claim']}
                </div>
                <div style="font-size:12px;color:#8898AA;line-height:1.6;margin-bottom:14px;">
                    {svc['desc']}
                </div>
                <div>
                    {"".join(f'<span style="display:inline-block;font-size:9px;font-weight:700;letter-spacing:0.8px;text-transform:uppercase;padding:3px 8px;border-radius:6px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);color:#8898AA;margin:2px 2px 0 0;">{t}</span>' for t in svc['tags'])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

# ── Core technologies strip ────────────────────────────────────────────────────
st.markdown(
    """
    <div style="font-size:10px;font-weight:700;color:#FF6A00;letter-spacing:4px;text-transform:uppercase;margin-bottom:14px;">◆ CORE TECHNOLOGIES</div>
    """,
    unsafe_allow_html=True,
)
tech_items = [
    ("⚡", "Artificial Intelligence",    "#4D7CFF"),
    ("🔗", "Industrial IoT",             "#FF6A00"),
    ("⚙️", "Process Automation",        "#22C55E"),
    ("📊", "Predictive Analytics",       "#4D7CFF"),
    ("☁️", "Cloud Infrastructure",       "#8898AA"),
    ("🔒", "Cybersecurity",              "#FFB84D"),
]
tech_cols = st.columns(6)
for idx, (icon, label, color) in enumerate(tech_items):
    with tech_cols[idx]:
        st.markdown(
            f"""
            <div style="
                background: rgba(15,22,35,0.85);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 14px;
                padding: 16px 12px;
                text-align: center;
                backdrop-filter: blur(8px);
            ">
                <div style="font-size:22px;margin-bottom:8px;">{icon}</div>
                <div style="font-size:11px;font-weight:600;color:{color};letter-spacing:0.3px;">{label}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
            <div style="
                background: rgba(15,22,35,0.85);
                border: 1px solid rgba(255,255,255,0.07);
                border-radius: 20px;
                padding: 20px;
                margin-bottom: 14px;
                backdrop-filter: blur(12px);
                box-shadow: 0 4px 24px rgba(0,0,0,0.25);
                min-height: 110px;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            ">
                <div style="font-size:24px;margin-bottom:8px;">{icon}</div>
                <div style="font-family:'Poppins',sans-serif;font-size:14px;font-weight:700;
                            color:#EDEFF2;margin-bottom:5px;">{title}</div>
                <div style="font-size:12px;color:#8898AA;line-height:1.55;">{desc}</div>
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
        <div style="
            background: rgba(15,22,35,0.85);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 14px;
            padding: 12px 18px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
            backdrop-filter: blur(8px);
        ">
          <span class='{chip_class}'>{sev}</span>
          <span style="font-size:13px;color:#EDEFF2;flex:1;">{row["Description"]}</span>
          <span style="font-size:11px;color:#8898AA;white-space:nowrap;">{row["Machine"]} · {row["Timestamp"]}</span>
          <span style="font-size:10px;color:#4D7CFF;background:rgba(11,59,255,0.1);
                       border:1px solid rgba(11,59,255,0.2);border-radius:6px;
                       padding:3px 10px;font-weight:600;white-space:nowrap;">{row["Agent"]}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
