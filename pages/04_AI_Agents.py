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
from utils.data_generator import _seed, generate_alerts, generate_machines

st.set_page_config(page_title="AI Agent Center · DEP", page_icon="🤖", layout="wide")
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

import json

COMPANIES = json.loads((ROOT / "config" / "companies.json").read_text())
COMPANY_MAP = {c["name"]: c for c in COMPANIES}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='text-align:center;padding:16px 0 12px;border-bottom:1px solid rgba(255,106,0,0.2);margin-bottom:14px;'>"
        "<div style='font-size:10px;font-weight:700;color:#FF6A00;letter-spacing:4px;text-transform:uppercase;margin-bottom:6px;'>◆ ING_DIGHUB</div>"
        "<div style='font-family:Poppins,sans-serif;font-size:18px;font-weight:800;color:#EDEFF2;letter-spacing:-0.5px;'>INGECART</div>"
        "<div style='font-size:10px;color:#8898AA;margin-top:3px;letter-spacing:0.5px;'>Industrial Intelligence Platform</div>"
        "</div>",
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
    st.markdown("<hr style='border-color:#FF6A0044;margin:12px 0;'/>", unsafe_allow_html=True)
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

machines_df = generate_machines(company)
alerts_df = generate_alerts(company, n=max(8, min(24, company.get("machines", 12) // 4)))

warning_count = int((machines_df["Status"] == "Warning").sum())
offline_count = int((machines_df["Status"] == "Offline").sum())
online_count = int((machines_df["Status"] == "Online").sum())
fleet_size = max(1, len(machines_df))
warning_rate = (warning_count + offline_count) / fleet_size
avg_oee = float(machines_df["OEE (%)"].mean())
high_temp_count = int((machines_df["Temp (°C)"] >= 80).sum())
high_vibration_count = int((machines_df["Vibration (mm/s)"] >= 3.5).sum())
low_health_count = int((machines_df["Health Score"] < 60).sum())
pm_due_14 = int((machines_df["Next PM (days)"] <= 14).sum())

critical_alerts = int((alerts_df["Severity"] == "Critical").sum()) if not alerts_df.empty else 0
warning_alerts = int((alerts_df["Severity"] == "Warning").sum()) if not alerts_df.empty else 0


def _build_agent_recommendations(agent_id: str) -> tuple[str, list[str]]:
    if agent_id == "operational":
        analysis = (
            f"Fleet stability is mixed: {online_count}/{fleet_size} online, "
            f"{warning_count} warning, {offline_count} offline. "
            f"Detected {high_temp_count} high-temperature and {high_vibration_count} high-vibration machines."
        )
        recs = [
            "Prioritize root-cause checks on offline and warning machines by production criticality.",
            "Apply temporary safe-setpoint correction on thermal/vibration hotspots and monitor for 2 shifts.",
            "Enable stricter anomaly thresholds during peak load windows to reduce MTTR.",
        ]
        return analysis, recs

    if agent_id == "maintenance":
        analysis = (
            f"Maintenance risk is elevated on {low_health_count} low-health assets; "
            f"{pm_due_14} machine(s) require PM in <=14 days with {critical_alerts} critical alert(s)."
        )
        recs = [
            "Lock PM slots this week for low-health assets and sequence by downtime impact.",
            "Pre-order critical spare parts for assets with PM <=14 days.",
            "Trigger post-maintenance verification to close the learning loop in failure prediction.",
        ]
        return analysis, recs

    if agent_id == "engineering":
        hotspot = "bearing" if (alerts_df["Description"].str.contains("bearing", case=False).any()) else "thermal drift"
        analysis = (
            f"Field feedback indicates repeatable {hotspot} patterns and {warning_alerts + critical_alerts} "
            "relevant alert events suitable for design-loop feedback."
        )
        recs = [
            "Cluster recurring failure modes by machine type and open one design improvement ticket per cluster.",
            "Prioritize redesign validation on the top 20% highest-downtime assets.",
            "Track design change impact through MTBF and warranty-claim deltas.",
        ]
        return analysis, recs

    if agent_id == "optimization":
        analysis = (
            f"Current avg OEE is {avg_oee:.1f}% with a fleet instability rate of {warning_rate * 100:.1f}%. "
            "Optimization potential is available through parameter harmonization and load balancing."
        )
        recs = [
            "Run two what-if recipes for cycle-time vs. quality trade-off and promote the better profile.",
            "Shift non-critical loads to lower-tariff windows to reduce energy intensity.",
            "Use bottleneck-based dispatching when warning/offline ratio exceeds baseline.",
        ]
        return analysis, recs

    if agent_id == "commercial":
        analysis = (
            f"Commercial signals are favorable: {company['active_contracts']} active contracts and "
            f"{warning_count + offline_count} assets with upgrade/retrofit context."
        )
        recs = [
            "Trigger upgrade qualification on assets with repeated warning events.",
            "Create contract-renewal bundles combining predictive maintenance and optimization add-ons.",
            "Prioritize high-value accounts with aging installed base for modernization offers.",
        ]
        return analysis, recs

    if agent_id == "customer_success":
        analysis = (
            f"Customer success load is moderate with {warning_alerts} warning and {critical_alerts} critical alerts. "
            "Operators need guided, explainable next-best actions."
        )
        recs = [
            "Publish an operator playbook for top recurring issues with plain-language steps.",
            "Auto-generate proactive guidance for lines with repeated alerts in the last 24h.",
            "Escalate unresolved advisory threads to a human specialist after SLA threshold.",
        ]
        return analysis, recs

    if agent_id == "management":
        analysis = (
            f"Executive risk posture: warning/offline footprint at {warning_rate * 100:.1f}% and "
            f"{critical_alerts} critical alert(s), with OEE baseline at {avg_oee:.1f}%."
        )
        recs = [
            "Approve short-term reliability sprint focused on top-risk assets.",
            "Rebalance CAPEX toward predictive and optimization modules with fastest payback.",
            "Review cross-site risk monthly with a board-ready scorecard and mitigation owner.",
        ]
        return analysis, recs

    return "No analysis available for this agent.", ["No recommendations available."]

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

# ── Agent analysis and recommendations ────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Agent Analysis & Recommendations</div>', unsafe_allow_html=True)
st.caption("Operational analysis generated from live fleet signals (status, telemetry proxies, alerts).")

for agent in active_agents:
    analysis, recs = _build_agent_recommendations(agent["id"])
    with st.container():
        st.markdown(f"### {agent['icon']} {agent['name']}")
        st.markdown(f"**Analysis:** {analysis}")
        st.markdown("**Recommendations:**")
        for rec in recs:
            st.markdown(f"- {rec}")

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
                                <div style='background:#F4F5F7;border:1px solid #E2EAF3;border-radius:10px;
                                                        padding:14px 16px;margin-bottom:10px;opacity:0.85;'>
                                    <div style='font-size:24px;color:#1A1D24;'>{agent['icon']}</div>
                                    <div style='font-size:14px;font-weight:700;color:#1A1D24;margin-top:4px;'>
                                        {agent['name']}
                                    </div>
                                    <div style='font-size:12px;color:#7E848E;'>{agent['role']}</div>
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
                <div style='background:#F4F5F7;border:1px solid #E2EAF3;border-radius:8px;
                                        padding:10px 16px;margin-bottom:6px;display:flex;align-items:center;gap:12px;'>
                    <div style='width:32px;height:32px;border-radius:50%;
                                            background:{entry["color"]}22;display:flex;align-items:center;
                                            justify-content:center;font-size:16px;color:#1A1D24;'>{entry["icon"]}</div>
                    <div style='flex:1;'>
                        <span style='font-size:12px;font-weight:700;color:#1A1D24;'>
                            {entry["agent"]}</span>
            <div style='font-size:13px;color:#1A2E44;margin-top:2px;'>{entry["action"]}</div>
          </div>
          <span style='font-size:11px;color:#A0AEC0;white-space:nowrap;'>{ts_str}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
