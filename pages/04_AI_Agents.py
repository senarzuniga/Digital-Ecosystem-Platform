"""
Page 04 – AI Agent Center
==========================
7 specialized AI agents, active/locked status, and agent action log.
"""

import sys
import random
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header
from utils.agent_taxonomy import AGENTS, get_active_agents, get_locked_agents
from utils.data_generator import _seed

st.set_page_config(page_title="AI Agent Center · DEP", page_icon="🤖", layout="wide")
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
        key="agent_company",
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
    '<div class="dep-page-title">🤖 AI Agent Center</div>'
    '<div class="dep-page-subtitle">Specialized AI agents — active, locked, and action log</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)

lvl = company["maturity_level"]
active_agents = get_active_agents(lvl)
locked_agents = get_locked_agents(lvl)

c1, c2, c3 = st.columns(3)
c1.metric("Total Agents",  len(AGENTS))
c2.metric("Active",        len(active_agents))
c3.metric("Locked (maturity gate)", len(locked_agents), delta_color="off")

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

# ── Active agents ──────────────────────────────────────────────────────────────
st.markdown('<div class="dep-section-header">Active Agents</div>', unsafe_allow_html=True)

cols = st.columns(2)
for idx, agent in enumerate(active_agents):
    with cols[idx % 2]:
        with st.expander(f"{agent['icon']} {agent['name']}  ·  {agent['role']}", expanded=False):
            st.markdown(
                f"""
                <div style='font-size:13px;color:#4A5568;margin-bottom:10px;'>
                  {agent['description']}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("**Capabilities:**")
            for cap in agent["capabilities"]:
                st.markdown(f"- {cap}")
            st.markdown("**KPIs tracked:**")
            for kpi in agent["kpis"]:
                st.markdown(f"- {kpi}")
            st.markdown(
                f"<div class='chip-info' style='display:inline-block;margin-top:6px;'>"
                f"Available from Maturity L{agent['maturity_min']}</div>",
                unsafe_allow_html=True,
            )

# ── Locked agents ──────────────────────────────────────────────────────────────
if locked_agents:
    st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
    st.markdown('<div class="dep-section-header">Locked Agents (Maturity Upgrade Required)</div>',
                unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="dep-alert-info">
        🔒 <strong>{len(locked_agents)} agent(s) are locked</strong> at the current maturity level
        (L{lvl}). Upgrade your ecosystem maturity to unlock them.
        <br><em>Without it: these automation capabilities remain unavailable, requiring manual
        human intervention and limiting autonomous decision-making.</em>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols2 = st.columns(2)
    for idx, agent in enumerate(locked_agents):
        with cols2[idx % 2]:
            st.markdown(
                f"""
                <div style='background:#F7F9FC;border:1px solid #E2EAF3;border-radius:10px;
                            padding:14px 16px;margin-bottom:10px;opacity:0.65;'>
                  <div style='font-size:24px;'>{agent['icon']}</div>
                  <div style='font-size:14px;font-weight:600;color:#6B7C93;margin-top:4px;'>
                    {agent['name']}
                  </div>
                  <div style='font-size:12px;color:#A0AEC0;'>{agent['role']}</div>
                  <div style='margin-top:8px;'>
                    <span class='chip-warn'>Requires Maturity L{agent['maturity_min']}</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ── Agent action log ───────────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Agent Action Log</div>', unsafe_allow_html=True)

ACTION_TEMPLATES = {
    "operational":     [
        "Anomaly detected on spindle — corrective action proposed: reduce feed rate 15%.",
        "Temperature spike on MCH → coolant flow increased autonomously.",
        "OEE drop detected — root cause: upstream material delay flagged.",
    ],
    "optimization":    [
        "Energy optimization: shift cycle start by 8 min → estimated saving 12%.",
        "Throughput scenario: +7% possible with parameter set B (simulation run).",
    ],
    "maintenance":     [
        "RUL estimate: bearing on MCH-004 → 18 days to failure.",
        "Spare part PO created: SKU-4821 × 3 units — You will need this part in 3 weeks.",
        "Preventive maintenance scheduled for MCH-012: Tuesday 02:00–04:00.",
    ],
    "commercial":      [
        "Upsell opportunity: upgrade eligibility detected — when upgrades are needed.",
        "Contract renewal due in 28 days — auto-proposal sent to account manager.",
    ],
    "engineering":     [
        "Design feedback: bearing failure cluster → 3 machines same root cause → R&D ticket opened.",
    ],
    "management":      [
        "Portfolio risk report generated: 2 high-risk assets flagged for Q2 board review.",
    ],
    "customer_success": [
        "Customer query answered: 'How do I reduce energy on line 3?' — guided action plan sent.",
    ],
}

rng = random.Random(_seed(company["id"] + "_agent_log"))
log_entries = []
for agent in active_agents:
    templates = ACTION_TEMPLATES.get(agent["id"], ["Action recorded."])
    tmpl = rng.choice(templates)
    ago = rng.randint(1, 480)
    ts = datetime.utcnow() - timedelta(minutes=ago)
    log_entries.append({
        "time": ts,
        "agent": agent["name"],
        "icon": agent["icon"],
        "color": agent["color"],
        "action": tmpl,
    })

log_entries.sort(key=lambda x: x["time"], reverse=True)

for entry in log_entries:
    ts_str = entry["time"].strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <div style='background:white;border:1px solid #E2EAF3;border-radius:8px;
                    padding:10px 16px;margin-bottom:6px;display:flex;align-items:center;gap:12px;'>
          <div style='width:32px;height:32px;border-radius:50%;
                      background:{entry["color"]}22;display:flex;align-items:center;
                      justify-content:center;font-size:16px;'>{entry["icon"]}</div>
          <div style='flex:1;'>
            <span style='font-size:12px;font-weight:600;color:{entry["color"]};'>
              {entry["agent"]}</span>
            <div style='font-size:13px;color:#1A2E44;margin-top:2px;'>{entry["action"]}</div>
          </div>
          <span style='font-size:11px;color:#A0AEC0;white-space:nowrap;'>{ts_str}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
