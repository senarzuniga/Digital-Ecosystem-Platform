"""
Page 05 – Maturity Model
=========================
L1–L5 ecosystem maturity assessment with radar chart and progression roadmap.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header
from utils.data_generator import generate_maturity_scores, MATURITY_DIMENSIONS

st.set_page_config(page_title="Maturity Model · DEP", page_icon="📈", layout="wide")
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
        key="mat_company",
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
    '<div class="dep-page-title">📈 Maturity Model</div>'
    '<div class="dep-page-subtitle">L1–L5 ecosystem maturity assessment, positioning and progression roadmap</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)

lvl  = company["maturity_level"]
mat  = MATURITY_LEVELS[lvl]
scores = generate_maturity_scores(company)

# ── Level definitions ──────────────────────────────────────────────────────────
LEVEL_DEFINITIONS = {
    1: {
        "label":       "L1 – Monitoring",
        "description": "Basic machine connectivity and real-time sensor data collection. "
                       "Dashboards show what is happening, but no analytics or automation.",
        "capabilities": [
            "OPC-UA / MQTT machine connectivity",
            "Real-time KPI dashboards (OEE, availability, performance)",
            "Manual alert notification",
            "Basic data historian",
        ],
        "gaps": [
            "No predictive analytics",
            "No AI-driven recommendations",
            "Reactive service model only",
        ],
        "next_step": "Deploy analytics layer and move from descriptive to diagnostic reporting.",
    },
    2: {
        "label":       "L2 – Analytics",
        "description": "Historical and root-cause analytics. The platform can explain "
                       "why something happened, but actions remain manual.",
        "capabilities": [
            "Historical trend analysis and root-cause diagnostics",
            "Cross-machine benchmarking",
            "ERP/MES data integration",
            "Basic digital twin (static)",
        ],
        "gaps": [
            "No forward-looking predictions",
            "Manual maintenance scheduling",
            "Limited commercial intelligence",
        ],
        "next_step": "Introduce ML models for failure prediction and RUL estimation.",
    },
    3: {
        "label":       "L3 – Predictive",
        "description": "Machine learning models forecast failures and recommend actions. "
                       "Humans still decide and execute.",
        "capabilities": [
            "Predictive maintenance (RUL, anomaly detection)",
            "Prescriptive maintenance scheduling",
            "Dynamic digital twins",
            "AI-generated recommendations (human-approved)",
            "Spare-part ordering triggers",
        ],
        "gaps": [
            "No autonomous execution",
            "Agent orchestration not yet active",
            "Commercial layer partially integrated",
        ],
        "next_step": "Introduce autonomous execution for low-risk actions and agent orchestration.",
    },
    4: {
        "label":       "L4 – Semi-Autonomous",
        "description": "AI agents execute pre-approved action classes automatically. "
                       "Humans supervise and handle exceptions.",
        "capabilities": [
            "Autonomous corrective actions (within defined bounds)",
            "AI agent orchestration layer active",
            "Automated spare-part ordering",
            "Commercial AI agent (upsell/renewal triggers)",
            "Management AI insights dashboard",
        ],
        "gaps": [
            "Full cross-agent autonomy not yet active",
            "Customer-facing AI interface limited",
        ],
        "next_step": "Deploy full agent mesh with cross-agent coordination and customer-facing AI.",
    },
    5: {
        "label":       "L5 – Fully Autonomous",
        "description": "Self-managing ecosystem: agents continuously optimise, maintain, "
                       "sell, and improve without manual trigger. Humans set strategy.",
        "capabilities": [
            "Full AI agent mesh with conflict resolution",
            "Autonomous production optimisation",
            "Self-ordering spare parts and scheduling",
            "Performance-based pricing and automated commercial offers",
            "Continuous learning across anonymous cross-customer fleet",
            "Embedded app & agent marketplace",
        ],
        "gaps": [],
        "next_step": "Sustain, expand to new product lines, and build platform network effects.",
    },
}

# ── Current level card ─────────────────────────────────────────────────────────
defn = LEVEL_DEFINITIONS[lvl]
col_l, col_r = st.columns([1.4, 1])

with col_l:
    st.markdown(
        f"""
        <div style='background:{mat["bg"]};border:2px solid {mat["color"]}44;border-radius:12px;
                    padding:18px 20px;margin-bottom:16px;'>
          <div style='font-size:13px;font-weight:600;color:{mat["color"]};
                      text-transform:uppercase;letter-spacing:0.6px;'>Current Maturity</div>
          <div style='font-size:22px;font-weight:700;color:#1A2E44;margin:6px 0;'>
            {mat["label"]}
          </div>
          <div style='font-size:13px;color:#4A5568;'>{defn["description"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**Current capabilities:**")
    for cap in defn["capabilities"]:
        st.markdown(f"✅ {cap}")

    if defn["gaps"]:
        st.markdown("**Gaps to address:**")
        for gap in defn["gaps"]:
            st.markdown(f"⚠️ {gap}")

    st.markdown(
        f"""
        <div class="dep-alert-info" style='margin-top:12px;'>
        🚀 <strong>Next step:</strong> {defn["next_step"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_r:
    # Radar chart
    categories = list(scores.keys())
    values     = list(scores.values())
    categories_closed = categories + [categories[0]]
    values_closed     = values + [values[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill="toself",
        fillcolor=f"{mat['color']}22",
        line=dict(color=mat["color"], width=2),
        name="Current scores",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, 100], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=11)),
        ),
        showlegend=False,
        height=340,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Dimension scores ───────────────────────────────────────────────────────────
st.markdown('<div class="dep-section-header">Maturity Dimension Scores</div>', unsafe_allow_html=True)

dim_cols = st.columns(len(MATURITY_DIMENSIONS))
for col, (dim, score) in zip(dim_cols, scores.items()):
    color = "#43A047" if score >= 70 else ("#FFA726" if score >= 40 else "#EF5350")
    col.markdown(
        f"""
        <div style='background:white;border:1px solid #E2EAF3;border-radius:10px;
                    padding:12px;text-align:center;'>
          <div style='font-size:11px;color:#6B7C93;font-weight:600;text-transform:uppercase;
                      letter-spacing:0.4px;margin-bottom:4px;'>{dim}</div>
          <div style='font-size:24px;font-weight:700;color:{color};'>{score}</div>
          <div style='font-size:10px;color:#A0AEC0;'>/ 100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Maturity progression roadmap ───────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Full Maturity Progression Roadmap (L1 → L5)</div>',
            unsafe_allow_html=True)

for level_num, level_data in LEVEL_DEFINITIONS.items():
    mat_l = MATURITY_LEVELS[level_num]
    is_current = level_num == lvl
    border = f"2px solid {mat_l['color']}" if is_current else f"1px solid #E2EAF3"
    bg     = mat_l["bg"] if is_current else "white"
    badge  = " ← Current" if is_current else ""

    with st.expander(f"{mat_l['label']}{badge}", expanded=is_current):
        st.markdown(
            f"<div style='font-size:13px;color:#4A5568;'>{level_data['description']}</div>",
            unsafe_allow_html=True,
        )
        c_a, c_b = st.columns(2)
        with c_a:
            st.markdown("**Capabilities unlocked:**")
            for cap in level_data["capabilities"]:
                st.markdown(f"✅ {cap}")
        with c_b:
            if level_data["gaps"]:
                st.markdown("**Remaining gaps:**")
                for gap in level_data["gaps"]:
                    st.markdown(f"⚠️ {gap}")
            st.markdown(f"**Next action:** {level_data['next_step']}")

# ── Market context ─────────────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Market Positioning (Where the market is vs where you should go)</div>',
            unsafe_allow_html=True)

st.markdown(
    """
    <div style='background:white;border:1px solid #E2EAF3;border-radius:10px;padding:18px 20px;'>
    <table style='width:100%;border-collapse:collapse;font-size:13px;'>
      <thead>
        <tr style='background:#F7F9FC;'>
          <th style='text-align:left;padding:8px 12px;color:#6B7C93;font-weight:600;'>Segment</th>
          <th style='text-align:left;padding:8px 12px;color:#6B7C93;font-weight:600;'>Market Median</th>
          <th style='text-align:left;padding:8px 12px;color:#1565C0;font-weight:600;'>Best-in-Class Target</th>
          <th style='text-align:left;padding:8px 12px;color:#2E7D32;font-weight:600;'>Competitive Advantage</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td style='padding:8px 12px;color:#1A2E44;font-weight:500;border-top:1px solid #E2EAF3;'>SME Manufacturers</td>
          <td style='padding:8px 12px;color:#6B7C93;border-top:1px solid #E2EAF3;'>L1–L2 (Monitoring + basic analytics)</td>
          <td style='padding:8px 12px;color:#1565C0;border-top:1px solid #E2EAF3;'>L3 (Predictive)</td>
          <td style='padding:8px 12px;color:#2E7D32;border-top:1px solid #E2EAF3;'>Faster time-to-insight, lower TCO</td>
        </tr>
        <tr style='background:#FAFBFD;'>
          <td style='padding:8px 12px;color:#1A2E44;font-weight:500;'>Mid-market OEMs</td>
          <td style='padding:8px 12px;color:#6B7C93;'>L2–L3 (Analytics + early predictive)</td>
          <td style='padding:8px 12px;color:#1565C0;'>L4 (Semi-autonomous)</td>
          <td style='padding:8px 12px;color:#2E7D32;'>Autonomous actions reduce OpEx 20–35%</td>
        </tr>
        <tr>
          <td style='padding:8px 12px;color:#1A2E44;font-weight:500;border-top:1px solid #E2EAF3;'>Enterprise / Global OEMs</td>
          <td style='padding:8px 12px;color:#6B7C93;border-top:1px solid #E2EAF3;'>L3–L4 (Predictive + semi-auto)</td>
          <td style='padding:8px 12px;color:#1565C0;border-top:1px solid #E2EAF3;'>L5 (Fully autonomous)</td>
          <td style='padding:8px 12px;color:#2E7D32;border-top:1px solid #E2EAF3;'>Platform network effects + ecosystem lock-in</td>
        </tr>
      </tbody>
    </table>
    </div>
    """,
    unsafe_allow_html=True,
)
