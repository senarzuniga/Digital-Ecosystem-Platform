"""
Page 07 – After-Sales Engine
=============================
Installed base visibility, upsell triggers, service orders, and recurring revenue.
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
    generate_service_orders,
    generate_upsell_opportunities,
)

st.set_page_config(page_title="After-Sales Engine · DEP", page_icon="💰", layout="wide")
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
        key="ase_company",
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
    '<div class="dep-page-title">💰 After-Sales Engine</div>'
    '<div class="dep-page-subtitle">'
    'Installed base visibility · Upsell triggers · Service orders · Recurring revenue</div>',
    unsafe_allow_html=True,
)
st.markdown(render_company_header(company), unsafe_allow_html=True)

# ── Data ───────────────────────────────────────────────────────────────────────
machines_df  = generate_machines(company)
orders_df    = generate_service_orders(company, n=30)
upsell_df    = generate_upsell_opportunities(company)

total_revenue   = orders_df["Revenue ($)"].sum()
completed_rev   = orders_df[orders_df["Status"] == "Completed"]["Revenue ($)"].sum()
high_prio_upsell = len(upsell_df[upsell_df["Priority"] == "High"])
upsell_value     = upsell_df["Est. Value ($)"].sum()

# ── KPIs ───────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Contracts",     company["active_contracts"])
c2.metric("Service Revenue ($)",  f"{completed_rev:,.0f}")
c3.metric("Upsell Opportunities", len(upsell_df),  delta=f"{high_prio_upsell} high-priority")
c4.metric("Pipeline Value ($)",   f"{upsell_value:,.0f}")

st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Upsell Opportunities",
    "📋 Service Orders",
    "📊 Installed Base",
    "💡 Growth Strategy",
])

# ── Tab 1: Upsell ─────────────────────────────────────────────────────────────
with tab1:
    st.markdown('<div class="dep-section-header">AI-Generated Upsell Opportunities</div>',
                unsafe_allow_html=True)

    st.markdown(
        """
        <div class="dep-alert-info">
        🤖 <strong>Commercial Agent</strong> has identified these opportunities based on
        machine usage patterns, age profiles, and contract proximity.
        Trigger logic includes: <em>when upgrades are needed</em> and
        <em>"You will need this part in 3 weeks"</em> signals.
        </div>
        """,
        unsafe_allow_html=True,
    )

    for _, row in upsell_df.iterrows():
        priority_chip = {
            "High":   "chip-error",
            "Medium": "chip-warn",
            "Low":    "chip-info",
        }.get(row["Priority"], "chip-info")
        st.markdown(
            f"""
            <div style='background:white;border:1px solid #E2EAF3;border-radius:10px;
                        padding:14px 18px;margin-bottom:10px;'>
              <div style='display:flex;align-items:center;gap:12px;margin-bottom:6px;'>
                <span class='{priority_chip}'>{row["Priority"]}</span>
                <span style='font-size:15px;font-weight:600;color:#1A2E44;'>{row["Offer"]}</span>
                <span style='margin-left:auto;font-size:14px;font-weight:700;color:#2E7D32;'>
                  ${row["Est. Value ($)"]:,.0f}
                </span>
              </div>
              <div style='font-size:12px;color:#6B7C93;display:flex;gap:16px;'>
                <span>📦 {row["Category"]}</span>
                <span>🔩 {row["Machine"]}</span>
                <span>⚡ Trigger: <em>{row["Trigger"]}</em></span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Upsell by category chart
    cat_counts = upsell_df.groupby("Category")["Est. Value ($)"].sum().reset_index()
    fig = px.bar(
        cat_counts, x="Category", y="Est. Value ($)",
        color="Category",
        color_discrete_sequence=px.colors.qualitative.Set2,
        text_auto=True,
    )
    fig.update_layout(
        height=260, showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis_title="Pipeline Value ($)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: Service Orders ─────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="dep-section-header">Service Order Portfolio</div>',
                unsafe_allow_html=True)

    col_f, col_s = st.columns([1, 1])
    with col_f:
        type_filter = st.multiselect(
            "Filter by type", options=orders_df["Type"].unique().tolist(), default=[], placeholder="All"
        )
    with col_s:
        status_filter = st.multiselect(
            "Filter by status", options=orders_df["Status"].unique().tolist(), default=[], placeholder="All"
        )

    filtered_orders = orders_df.copy()
    if type_filter:
        filtered_orders = filtered_orders[filtered_orders["Type"].isin(type_filter)]
    if status_filter:
        filtered_orders = filtered_orders[filtered_orders["Status"].isin(status_filter)]

    def colour_order_status(val):
        c = {"Completed": "#E8F5E9", "In Progress": "#E3F2FD", "Scheduled": "#FFF8E1", "Pending": "#F3E5F5"}
        return f"background-color: {c.get(val, 'white')};"

    styled_orders = filtered_orders.style.applymap(colour_order_status, subset=["Status"])
    st.dataframe(styled_orders, use_container_width=True, height=300)

    col_l, col_r = st.columns(2)
    with col_l:
        type_rev = orders_df.groupby("Type")["Revenue ($)"].sum().reset_index()
        fig2 = px.pie(type_rev, names="Type", values="Revenue ($)", hole=0.4,
                      title="Revenue by Service Type")
        fig2.update_layout(height=280, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="white")
        st.plotly_chart(fig2, use_container_width=True)
    with col_r:
        status_rev = orders_df.groupby("Status")["Revenue ($)"].sum().reset_index()
        fig3 = px.bar(status_rev, x="Status", y="Revenue ($)", color="Status",
                      color_discrete_sequence=["#43A047", "#1E88E5", "#FFA726", "#AB47BC"])
        fig3.update_layout(height=280, showlegend=False,
                           margin=dict(l=0, r=0, t=30, b=0),
                           plot_bgcolor="white", paper_bgcolor="white",
                           title="Revenue by Status")
        st.plotly_chart(fig3, use_container_width=True)

# ── Tab 3: Installed Base ─────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="dep-section-header">Installed Base Visibility</div>',
                unsafe_allow_html=True)

    col_l, col_r = st.columns([1.4, 1])
    with col_l:
        fig4 = px.scatter(
            machines_df, x="Age (years)", y="OEE (%)",
            color="Status",
            color_discrete_map={"Online": "#43A047", "Warning": "#FFA726", "Offline": "#EF5350"},
            size="Health Score",
            hover_data=["Machine ID", "Type", "Next PM (days)"],
            title="Fleet Age vs OEE (bubble = health score)",
        )
        fig4.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0),
                           plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig4, use_container_width=True)

    with col_r:
        age_bins = machines_df.copy()
        age_bins["Age Group"] = age_bins["Age (years)"].apply(
            lambda a: "0–3 yrs" if a < 3 else ("3–7 yrs" if a < 7 else "7+ yrs")
        )
        age_counts = age_bins["Age Group"].value_counts().reset_index()
        age_counts.columns = ["Age Group", "Count"]
        fig5 = px.pie(age_counts, names="Age Group", values="Count", hole=0.45,
                      color_discrete_sequence=["#43A047", "#FFA726", "#EF5350"],
                      title="Fleet Age Distribution")
        fig5.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), paper_bgcolor="white")
        st.plotly_chart(fig5, use_container_width=True)

    # Machines nearing next PM
    st.markdown("**Machines with next PM ≤ 30 days:**")
    pm_soon = machines_df[machines_df["Next PM (days)"] <= 30].sort_values("Next PM (days)")
    if len(pm_soon):
        st.dataframe(pm_soon[["Machine ID", "Type", "Status", "Health Score", "Next PM (days)"]],
                     use_container_width=True, height=200)
    else:
        st.success("No machines with PM due in the next 30 days.")

# ── Tab 4: Growth Strategy ────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="dep-section-header">After-Sales Growth Engine</div>',
                unsafe_allow_html=True)

    GROWTH_BLOCKS = [
        ("🔍", "Installed Base Visibility", "#1565C0",
         "You need: a complete, always-current registry of every machine in the field — "
         "segmented by age, status, contract, and upgrade potential. "
         "Without it: you are flying blind on the installed base and cannot prioritise service or commercial actions."),

        ("🔮", "Reactive → Predictive → Prescriptive Service", "#6A1B9A",
         "Progress from firefighting (reactive) through ML-powered failure forecasting (predictive) "
         "to AI-generated intervention schedules (prescriptive). "
         "Without it: service teams remain reactive, costs stay high, and customer satisfaction suffers."),

        ("📦", "Productised Service Catalog", "#2E7D32",
         "Package services as repeatable, outcome-defined products: Remote Monitoring, "
         "Predictive Maintenance Add-on, Digital Twin Expansion, Energy Efficiency Package. "
         "You need: clear service SKUs with documented value propositions and pricing tiers."),

        ("💳", "Recurring Revenue Tiers", "#00695C",
         "Offer Basic (monitoring), Advanced (predictive), and Premium (autonomous) subscription tiers. "
         "Transition from one-off service revenue to predictable, compounding ARR. "
         "When upgrades are needed: the platform automatically triggers upgrade qualification checks."),

        ("⚡", "Data-Driven Upsell Triggers", "#E65100",
         "Commercial Agent monitors usage, age, and contract signals to surface upsell moments: "
         "\"You will need this part in 3 weeks\" · \"when upgrades are needed\" · "
         "\"Contract renewal in 28 days — upgrade available\". "
         "Without it: revenue opportunities are missed or discovered too late."),

        ("🔩", "Spare Parts Optimisation", "#C62828",
         "Predictive demand forecasting per machine type ensures optimal stock levels — "
         "eliminating both stockouts and excess inventory. "
         "Automated PO creation removes manual ordering latency. "
         "You need: ML demand models integrated with ERP procurement workflows."),

        ("🌐", "Customer Interface Ownership", "#283593",
         "Own the digital relationship with the end customer — not just the machine. "
         "The platform becomes the primary interaction layer for performance data, "
         "service requests, orders, and advisory. "
         "Without it: third-party platforms or customers' own systems disintermediate the OEM."),

        ("🤖", "AI Revenue Multiplier Agents", "#880E4F",
         "Commercial, Management/CEO, and Customer Success agents work together to detect "
         "opportunities, prioritise accounts, generate personalised offers, and demonstrate "
         "value in real time — scaling commercial capacity without headcount. "
         "You need: integrated commercial AI layer with CRM/ERP write-back."),
    ]

    cols = st.columns(2)
    for idx, (icon, title, color, body) in enumerate(GROWTH_BLOCKS):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div style='border-left:4px solid {color};background:white;border-radius:8px;
                            padding:14px 16px;margin-bottom:12px;border:1px solid #E2EAF3;
                            border-left:4px solid {color};'>
                  <div style='font-size:14px;font-weight:600;color:{color};margin-bottom:6px;'>
                    {icon}  {title}
                  </div>
                  <div style='font-size:13px;color:#4A5568;'>{body}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Lifecycle monetisation journey
    st.markdown("<hr class='dep-divider'/>", unsafe_allow_html=True)
    st.markdown('<div class="dep-section-header">Lifecycle Monetisation Journey</div>',
                unsafe_allow_html=True)

    stages = [
        ("📦 Sale",        "#1565C0", "Machine sold + basic connectivity package"),
        ("📊 Onboard",     "#2E7D32", "Digital twin activated · Baseline established"),
        ("🔮 Predictive",  "#6A1B9A", "Predictive maintenance subscription started"),
        ("⚡ Autonomous",  "#E65100", "Autonomous service tier · Auto-parts ordering"),
        ("💳 Expand",      "#00695C", "Upsell to Premium · Add optimisation agents"),
        ("🔄 Renew",       "#880E4F", "Multi-year renewal · Performance-based pricing"),
    ]

    stage_cols = st.columns(len(stages))
    for col, (icon_label, color, desc) in zip(stage_cols, stages):
        icon_part, label_part = icon_label.split(" ", 1)
        col.markdown(
            f"""
            <div style='background:{color}11;border:1px solid {color}33;border-radius:10px;
                        padding:12px 10px;text-align:center;'>
              <div style='font-size:22px;'>{icon_part}</div>
              <div style='font-size:12px;font-weight:700;color:{color};margin:4px 0;'>{label_part}</div>
              <div style='font-size:11px;color:#6B7C93;'>{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
