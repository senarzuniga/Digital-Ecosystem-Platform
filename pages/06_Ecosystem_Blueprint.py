"""
Page 06 – Ecosystem Blueprint
==============================
Full best-practice IIoT + AI digital ecosystem blueprint (Section 6).
"""

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header

st.set_page_config(page_title="Ecosystem Blueprint · DEP", page_icon="🗺️", layout="wide")
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

import json

COMPANIES = json.loads((ROOT / "config" / "companies.json").read_text())
COMPANY_MAP = {c["name"]: c for c in COMPANIES}

# ── Sidebar ────────────────────────────────────────────────────────────────────
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
        key="bp_company",
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
    '<div class="dep-page-title">🗺️ Digital Ecosystem Blueprint</div>'
    '<div class="dep-page-subtitle">'
    'The BEST Digital Ecosystem for machine manufacturers — '
    'full blueprint incorporating IIoT foundations and AI-native capabilities'
    '</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)

# ── Blueprint pillars ──────────────────────────────────────────────────────────
BLUEPRINT_PILLARS = [
    {
        "icon": "🌐",
        "title": "Hyper-Connectivity (OEM-Agnostic)",
        "color": "#1565C0",
        "summary": "Connect any machine, any brand, any age — without ripping and replacing.",
        "details": [
            "OPC-UA, MQTT, REST, Modbus, PROFINET — universal protocol adapters",
            "Edge gateway layer for brownfield (legacy) machine integration",
            "Zero-trust security model: encrypted, authenticated data pipelines",
            "OEM-agnostic: competitor machines and third-party equipment included",
            "Plug-and-connect onboarding: <48 h from unboxing to streaming data",
        ],
        "without_it": (
            "Without it: data silos persist across machine brands, "
            "cross-fleet analytics are impossible, and AI models lack sufficient training data."
        ),
    },
    {
        "icon": "🪞",
        "title": "Digital Twin of Everything",
        "color": "#6A1B9A",
        "summary": "Persistent, accurate virtual replicas from individual components to full supply chain.",
        "details": [
            "Machine Twin: thermal, kinematic, wear, and electrical models per machine",
            "Process Twin: cycle, throughput, quality, and scrap parameter models",
            "Plant Twin: material flow, energy, workforce, and scheduling simulation",
            "Supply Chain Twin: demand-driven procurement and delivery forecasting",
            "Continuous synchronisation — divergence alerting and auto-recalibration",
        ],
        "without_it": (
            "Without it: predictive models lose accuracy over time, "
            "recommendations drift from reality, and digital investments depreciate rapidly."
        ),
    },
    {
        "icon": "🤖",
        "title": "AI Agent Orchestration Engine",
        "color": "#880E4F",
        "summary": "Coordinated multi-agent mesh with priority arbitration and conflict resolution.",
        "details": [
            "Central orchestrator routes tasks to specialized agents based on context",
            "Priority and conflict resolution: safety > reliability > efficiency > commercial",
            "7 specialized agents: Operational, Optimization, Maintenance, Commercial, Engineering, Management/CEO, Customer Success",
            "Human-in-the-loop: configurable autonomy levels per action class",
            "Auditability: every agent decision is logged, explainable, and reversible",
        ],
        "without_it": (
            "Without it: AI recommendations remain siloed, agents conflict with each other, "
            "and humans must manually coordinate between systems — eliminating the productivity multiplier."
        ),
    },
    {
        "icon": "⚡",
        "title": "Autonomous Execution Layer",
        "color": "#E65100",
        "summary": "Agents act — not just advise. Closed-loop control at PLC, MES, and ERP level.",
        "details": [
            "Bi-directional PLC integration: agents push parameter changes within safe operating windows",
            "MES integration: work order creation, scheduling adjustments, quality hold triggers",
            "ERP integration: spare-part POs, service order creation, contract actions",
            "Safety guardrails: hard limits, rollback capability, dual-approval for high-risk actions",
            "Graduated autonomy: advisory → approval-required → fully autonomous per action class",
        ],
        "without_it": (
            "Without it: the platform remains a dashboard — recommendations require human execution, "
            "response latency stays high, and the 24/7 autonomous value proposition is lost."
        ),
    },
    {
        "icon": "🏪",
        "title": "App & Agent Marketplace",
        "color": "#00695C",
        "summary": "Extensible platform where OEMs, ISVs, and customers publish and subscribe to capabilities.",
        "details": [
            "Curated marketplace for domain-specific AI agents and apps",
            "Third-party developer SDK and API gateway",
            "Subscription and revenue-sharing model for marketplace participants",
            "One-click deployment of new agents into the customer's environment",
            "Customer-created configurations and dashboards shared as reusable templates",
        ],
        "without_it": (
            "Without it: the platform remains closed, limiting extensibility and "
            "preventing network-effect value accumulation that drives platform lock-in."
        ),
    },
    {
        "icon": "🔄",
        "title": "Continuous Learning Loop",
        "color": "#2E7D32",
        "summary": "Models improve perpetually — powered by fleet data and cross-customer benchmarking.",
        "details": [
            "Federated learning: models improve from all connected fleets without sharing raw data",
            "Anonymised cross-customer benchmarking: best-in-class performance baselines",
            "Feedback loop: field outcomes (failures, fixes) retrain predictive models",
            "A/B testing framework for new recommendation strategies",
            "Concept drift detection: models auto-flag when retraining is required",
        ],
        "without_it": (
            "Without it: models degrade over time as machines age and processes change, "
            "predictions become unreliable, and the competitive advantage erodes."
        ),
    },
    {
        "icon": "💳",
        "title": "Embedded Commercial Layer",
        "color": "#C62828",
        "summary": "Revenue-generating capabilities natively embedded — not bolted on.",
        "details": [
            "Spare-parts ecommerce: in-platform ordering with smart stock recommendations",
            "Subscription tiers: Basic (monitoring) → Advanced (predictive) → Premium (autonomous)",
            "Performance-based pricing: outcomes-linked SLAs and pay-per-prevented-failure models",
            "Upsell trigger engine: usage signals, age, and contract proximity auto-generate offers",
            "Recurring revenue dashboard: ARR, churn risk, expansion MRR tracking",
        ],
        "without_it": (
            "Without it: after-sales revenue potential is unrealised, service teams remain reactive, "
            "and the platform fails to generate sustainable recurring revenue streams."
        ),
    },
    {
        "icon": "💬",
        "title": "Human-AI Interface (Conversational + Explainable)",
        "color": "#283593",
        "summary": "Natural language access to the entire platform — with reasoning transparency.",
        "details": [
            "Conversational AI: operators and managers query the platform in plain language",
            "Explainability layer: every recommendation accompanied by reasoning chain",
            "Role-based views: operator, maintenance technician, plant manager, executive, customer",
            "Mobile-first interface: full capability on mobile devices for field technicians",
            "Proactive insights: platform surfaces critical findings without being asked",
        ],
        "without_it": (
            "Without it: the platform's intelligence is inaccessible to non-technical users, "
            "adoption stalls, and the ROI of AI investments fails to materialise at scale."
        ),
    },
]

# ── Render pillars ─────────────────────────────────────────────────────────────
st.markdown('<div class="dep-section-header">Blueprint Pillars</div>', unsafe_allow_html=True)

for pillar in BLUEPRINT_PILLARS:
    with st.expander(f"{pillar['icon']}  {pillar['title']}", expanded=False):
        col_l, col_r = st.columns([1.6, 1])
        with col_l:
            st.markdown(
                f"<div style='font-size:14px;color:#4A5568;margin-bottom:10px;'>"
                f"{pillar['summary']}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("**Key capabilities:**")
            for detail in pillar["details"]:
                st.markdown(f"✅ {detail}")
        with col_r:
            st.markdown(
                f"""
                <div class="dep-alert-warning">
                  <strong>⚠️ Without it:</strong><br/>
                  {pillar['without_it'].replace("Without it:", "").strip()}
                </div>
                """,
                unsafe_allow_html=True,
            )

# ── Architecture stack visual ──────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Architecture Stack Overview</div>',
            unsafe_allow_html=True)

stack_layers = [
    ("#0D1B2A", "white",   "👤  User Layer",          "Conversational AI · Role-based dashboards · Mobile · Explainability"),
    ("#1565C0", "white",   "🤖  AI Agent Layer",       "Orchestrator · 7 Specialized Agents · Continuous Learning · Marketplace"),
    ("#2E7D32", "white",   "🪞  Digital Core",         "Streaming Pipeline · Data Lake · Feature Store · Digital Twins · ERP/MES"),
    ("#6A1B9A", "white",   "🔌  Edge & Connectivity",  "OPC-UA · MQTT · REST · Edge Gateways · Brownfield Adapters · Zero-Trust Security"),
    ("#263C55", "#A8BDD0", "🔩  Physical Layer",       "Machines · PLCs · Sensors · Actuators · Robots · Conveyor Systems"),
]

for bg, fg, label, content in stack_layers:
    st.markdown(
        f"""
        <div style='background:{bg};border-radius:8px;padding:14px 20px;margin-bottom:6px;'>
          <div style='font-size:14px;font-weight:700;color:{fg};margin-bottom:4px;'>{label}</div>
          <div style='font-size:12px;color:{"#A8BDD0" if bg == "#0D1B2A" else "#C8D8E8"};'>
            {content}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Data flow transformation ───────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">From Data to Autonomous Action</div>',
            unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown(
        """
        <div style='background:#FFF8E1;border:1px solid #FFD54F;border-radius:10px;padding:16px 18px;'>
          <div style='font-size:14px;font-weight:700;color:#E65100;margin-bottom:8px;'>
            📊 Today (IIoT Market Standard)
          </div>
          <div style='font-size:13px;color:#5D4037;'>
            Data → Dashboard → Human → Decision → Action
          </div>
          <ul style='font-size:13px;color:#5D4037;margin-top:8px;'>
            <li>Manual interpretation required</li>
            <li>Slow response to events</li>
            <li>Limited to available operator bandwidth</li>
            <li>Reactive by default</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div style='background:#E8F5E9;border:1px solid #A5D6A7;border-radius:10px;padding:16px 18px;'>
          <div style='font-size:14px;font-weight:700;color:#2E7D32;margin-bottom:8px;'>
            🤖 Tomorrow (AI-Native Ecosystem)
          </div>
          <div style='font-size:13px;color:#1B5E20;'>
            Data → AI Agents → Decision → Action (+ optional human approval)
          </div>
          <ul style='font-size:13px;color:#1B5E20;margin-top:8px;'>
            <li>Autonomous 24/7 operation</li>
            <li>Millisecond response to anomalies</li>
            <li>Unlimited scale across fleet</li>
            <li>Proactive and predictive by default</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
