"""
Page 08 — CMMS Work Orders
===========================
Displays live work orders from the FastAPI backend (falls back to mock data).
Supports creating, updating status, and filtering.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, render_company_header
from utils.api_client import (
    create_work_order,
    is_backend_healthy,
    list_work_orders,
    update_work_order,
)

st.set_page_config(page_title="CMMS — Work Orders", page_icon="🔧", layout="wide")
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

# ── Company selection (shared across pages) ────────────────────────────────────
if "selected_company" not in st.session_state:
    st.session_state.selected_company = {"id": "ACME-001", "name": "ACME Manufacturing"}

company = st.session_state.selected_company
render_company_header(company)

st.title("🔧 CMMS — Work Order Management")

# ── Backend status ─────────────────────────────────────────────────────────────
token = st.session_state.get("api_token")
backend_live = is_backend_healthy()

if backend_live:
    st.success("✅ Connected to live backend", icon="🟢")
else:
    st.warning("⚠️ Backend offline — showing mock data", icon="🟡")


# ── Mock data fallback ─────────────────────────────────────────────────────────
def _mock_work_orders(company_id: str) -> list[dict]:
    now = datetime.now(tz=timezone.utc)
    return [
        {"id": f"wo-{i:04d}", "wo_number": f"WO-{1000+i:06d}", "title": t,
         "status": s, "priority": p, "wo_type": wt, "asset_id": f"machine-{i:03d}",
         "company_id": company_id, "created_at": (now - timedelta(hours=i*3)).isoformat(),
         "due_date": (now + timedelta(days=2)).isoformat(),
         "spare_parts": [], "comments": []}
        for i, (t, s, p, wt) in enumerate([
            ("Bearing replacement — Line 3",          "open",        "critical",  "corrective"),
            ("Scheduled lubrication service",          "assigned",    "medium",    "preventive"),
            ("Vibration sensor recalibration",         "in_progress", "high",      "predictive"),
            ("Coolant system inspection",              "open",        "medium",    "inspection"),
            ("PLC firmware upgrade — Press #2",        "open",        "low",       "upgrade"),
            ("Conveyor belt tension adjustment",       "closed",      "medium",    "corrective"),
            ("Hydraulic hose leak — Station 7",        "assigned",    "critical",  "corrective"),
            ("Monthly electrical panel inspection",   "open",        "low",       "inspection"),
        ])
    ]


# ── Load data ─────────────────────────────────────────────────────────────────
company_id = company.get("id", "ACME-001")
raw_orders = (list_work_orders(company_id, token=token) if backend_live else None) or _mock_work_orders(company_id)

# ── Filters ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    filter_status = st.selectbox("Filter by Status", ["All", "open", "assigned", "in_progress", "on_hold", "closed"])
with col2:
    filter_priority = st.selectbox("Filter by Priority", ["All", "critical", "high", "medium", "low"])
with col3:
    filter_type = st.selectbox("Filter by Type", ["All", "corrective", "preventive", "predictive", "inspection", "upgrade"])

df = pd.DataFrame(raw_orders)

if filter_status != "All":
    df = df[df["status"] == filter_status]
if filter_priority != "All":
    df = df[df["priority"] == filter_priority]
if filter_type != "All" and "wo_type" in df.columns:
    df = df[df["wo_type"] == filter_type]

# ── KPI row ────────────────────────────────────────────────────────────────────
all_df = pd.DataFrame(raw_orders)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total WOs",     len(all_df))
k2.metric("Open",          len(all_df[all_df["status"] == "open"]))
k3.metric("Critical",      len(all_df[all_df["priority"] == "critical"]))
k4.metric("Closed today",  len(all_df[all_df["status"] == "closed"]))

st.markdown("---")

# ── Charts ─────────────────────────────────────────────────────────────────────
chart1, chart2 = st.columns(2)
with chart1:
    status_counts = all_df["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]
    fig = px.bar(status_counts, x="Status", y="Count", color="Status",
                 title="Work Orders by Status",
                 color_discrete_map={"open": "#ef4444", "assigned": "#f97316",
                                     "in_progress": "#3b82f6", "closed": "#22c55e"})
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with chart2:
    if "priority" in all_df.columns:
        prio_counts = all_df["priority"].value_counts().reset_index()
        prio_counts.columns = ["Priority", "Count"]
        fig2 = px.pie(prio_counts, names="Priority", values="Count",
                      title="Work Orders by Priority",
                      color_discrete_sequence=["#ef4444", "#f97316", "#eab308", "#22c55e"])
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

# ── Work order table ──────────────────────────────────────────────────────────
st.subheader(f"Work Orders ({len(df)} results)")

STATUS_COLORS = {
    "open":        "🔴",
    "assigned":    "🟠",
    "in_progress": "🔵",
    "on_hold":     "⚪",
    "closed":      "🟢",
    "cancelled":   "⛔",
}
PRIORITY_COLORS = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
}

if df.empty:
    st.info("No work orders match the current filters.")
else:
    display_cols = ["wo_number", "title", "status", "priority", "wo_type", "asset_id"]
    display_cols = [c for c in display_cols if c in df.columns]
    display_df = df[display_cols].copy()
    display_df["status"]   = display_df["status"].map(lambda s: f"{STATUS_COLORS.get(s, '⚪')} {s}")
    display_df["priority"] = display_df["priority"].map(lambda p: f"{PRIORITY_COLORS.get(p, '⚪')} {p}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)

# ── Create new work order ────────────────────────────────────────────────────
with st.expander("➕ Create New Work Order"):
    with st.form("create_wo_form"):
        wo_title    = st.text_input("Title *")
        wo_desc     = st.text_area("Description")
        wo_type     = st.selectbox("Type",     ["corrective", "preventive", "predictive", "inspection", "upgrade"])
        wo_priority = st.selectbox("Priority", ["critical", "high", "medium", "low"])
        wo_asset    = st.text_input("Asset ID (optional)")
        submitted   = st.form_submit_button("Create Work Order")

        if submitted:
            if not wo_title:
                st.error("Title is required")
            elif not backend_live:
                st.warning("Backend offline — work order not saved (demo mode)")
            elif not token:
                st.error("You must be logged in to create work orders. Use the sidebar.")
            else:
                result = create_work_order(
                    {
                        "company_id": company_id,
                        "title":      wo_title,
                        "description": wo_desc,
                        "wo_type":    wo_type,
                        "priority":   wo_priority,
                        "asset_id":   wo_asset or None,
                    },
                    token=token,
                )
                if result:
                    st.success(f"✅ Work order created: {result['wo_number']}")
                    st.rerun()
                else:
                    st.error("Failed to create work order")

# ── Update work order status ──────────────────────────────────────────────────
if backend_live and token and not df.empty:
    with st.expander("✏️ Update Work Order Status"):
        wo_ids   = df["wo_number"].tolist() if "wo_number" in df.columns else []
        selected = st.selectbox("Select Work Order", wo_ids)
        new_status = st.selectbox("New Status", ["open", "assigned", "in_progress", "on_hold", "closed"])
        if st.button("Update Status"):
            matching = df[df["wo_number"] == selected]
            if not matching.empty:
                wo_id = matching.iloc[0]["id"]
                result = update_work_order(wo_id, {"status": new_status}, token=token)
                if result:
                    st.success(f"Status updated to **{new_status}**")
                    st.rerun()
                else:
                    st.error("Failed to update work order")
