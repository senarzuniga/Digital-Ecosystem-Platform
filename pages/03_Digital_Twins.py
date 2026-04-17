"""
Page 03 – Digital Twins
========================
Live digital twin status, divergence tracking, and recalibration triggers.
"""

import sys
import random
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, MATURITY_LEVELS, render_company_header
from utils.data_generator import generate_machines, _seed

st.set_page_config(page_title="Digital Twins · DEP", page_icon="🪞", layout="wide")
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
        key="twin_company",
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
    '<div class="dep-page-title">🪞 Digital Twins</div>'
    '<div class="dep-page-subtitle">Live twin status, model divergence, and recalibration management</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)

# ── Generate twin data ─────────────────────────────────────────────────────────
machines_df = generate_machines(company)
rng = random.Random(_seed(company["id"] + "_twins"))

twin_types = ["Machine Twin", "Process Twin", "Plant Twin", "Supply Chain Twin"]
twin_data = []
for _, row in machines_df.head(min(20, len(machines_df))).iterrows():
    divergence = round(rng.uniform(0.2, 12.0), 1)
    twin_status = "Synced" if divergence < 4 else ("Diverged" if divergence < 8 else "Critical")
    twin_data.append({
        "Machine ID": row["Machine ID"],
        "Type": row["Type"],
        "Twin Type": rng.choice(twin_types[:2]),
        "Divergence (%)": divergence,
        "Twin Status": twin_status,
        "Last Sync": f"{rng.randint(1, 120)} min ago",
        "Model Version": f"v{rng.randint(1,4)}.{rng.randint(0,9)}",
    })

import pandas as pd
twin_df = pd.DataFrame(twin_data)

# ── KPIs ───────────────────────────────────────────────────────────────────────
synced   = len(twin_df[twin_df["Twin Status"] == "Synced"])
diverged = len(twin_df[twin_df["Twin Status"] == "Diverged"])
critical_tw = len(twin_df[twin_df["Twin Status"] == "Critical"])
avg_div  = twin_df["Divergence (%)"].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Twins",   len(twin_df))
c2.metric("Synced",         synced, delta=f"{synced/len(twin_df)*100:.0f}%")
c3.metric("Diverged",       diverged, delta_color="inverse", delta=str(diverged))
c4.metric("Avg Divergence", f"{avg_div:.1f}%")

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

# ── Twin status table ──────────────────────────────────────────────────────────
st.markdown('<div class="dep-section-header">Digital Twin Status Board</div>', unsafe_allow_html=True)

def colour_twin(val):
    c = {"Synced": "#E8F5E9", "Diverged": "#FFF8E1", "Critical": "#FFEBEE"}
    return f"background-color: {c.get(val, 'white')};"

styled = twin_df.style.map(colour_twin, subset=["Twin Status"])
st.dataframe(styled, use_container_width=True, height=320)

# ── Divergence chart ───────────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Divergence Distribution</div>', unsafe_allow_html=True)

col_l, col_r = st.columns([1.5, 1])

with col_l:
    fig = go.Figure()
    colors = [
        "#43A047" if v < 4 else ("#FFA726" if v < 8 else "#EF5350")
        for v in twin_df["Divergence (%)"]
    ]
    fig.add_trace(go.Bar(
        x=twin_df["Machine ID"],
        y=twin_df["Divergence (%)"],
        marker_color=colors,
        text=twin_df["Divergence (%)"].apply(lambda v: f"{v}%"),
        textposition="auto",
    ))
    fig.add_hline(y=5, line_dash="dash", line_color="#FFA726",
                  annotation_text="Divergence warning (5%)")
    fig.add_hline(y=8, line_dash="dash", line_color="#EF5350",
                  annotation_text="Critical threshold (8%)")
    fig.update_layout(
        height=320, margin=dict(l=0, r=0, t=10, b=90),
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis_tickangle=-40, xaxis_tickfont_size=10,
        yaxis_title="Divergence (%)", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_r:
    status_counts = twin_df["Twin Status"].value_counts()
    fig2 = go.Figure(go.Pie(
        labels=status_counts.index.tolist(),
        values=status_counts.values.tolist(),
        hole=0.52,
        marker_colors=["#43A047", "#FFA726", "#EF5350"],
    ))
    fig2.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10),
                       paper_bgcolor="white")
    st.plotly_chart(fig2, use_container_width=True)

# ── Twin blueprint types ───────────────────────────────────────────────────────
st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
st.markdown('<div class="dep-section-header">Digital Twin Hierarchy (Blueprint)</div>',
            unsafe_allow_html=True)

twin_scope = [
    ("🔩 Machine Twin",        "#1565C0",
     "Physical replica of each individual machine — sensors, kinematics, wear model, "
     "thermal model, and predictive component health."),
    ("⚙️ Process Twin",        "#2E7D32",
     "Captures the production process end-to-end: cycle time, throughput, "
     "quality parameters, and process parameter drift detection."),
    ("🏭 Plant Twin",          "#6A1B9A",
     "Whole-plant simulation: material flow, energy distribution, "
     "workforce allocation, and constraint-based scheduling model."),
    ("🔗 Supply Chain Twin",   "#E65100",
     "Extends visibility to upstream (parts, raw materials) and downstream "
     "(customer usage patterns) to enable demand-driven service and procurement."),
]

cols = st.columns(2)
for idx, (title, color, desc) in enumerate(twin_scope):
    with cols[idx % 2]:
        st.markdown(
            f"""
            <div style='border-left:4px solid {color};background:white;border-radius:8px;
                        padding:14px 16px;margin-bottom:12px;border:1px solid #E2EAF3;
                        border-left:4px solid {color};'>
              <div style='font-size:14px;font-weight:600;color:{color};'>{title}</div>
              <div style='font-size:13px;color:#4A5568;margin-top:6px;'>{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

if critical_tw > 0:
    st.markdown(
        f"""
        <div class="dep-alert-warning">
        ⚠️ <strong>{critical_tw} twin(s) in critical divergence state.</strong>
        Without it: digital twin accuracy degrades, predictive models lose fidelity,
        and AI agent recommendations become unreliable. Recalibration required.
        </div>
        """,
        unsafe_allow_html=True,
    )
