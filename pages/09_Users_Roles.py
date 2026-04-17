"""
Page 09 — Users & Roles
========================
User management, role assignment, and API token acquisition.
Falls back gracefully when backend is offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.styles import PLATFORM_CSS, render_company_header
from utils.api_client import get_me, is_backend_healthy, list_users, login

st.set_page_config(page_title="Users & Roles", page_icon="👥", layout="wide")
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)

if "selected_company" not in st.session_state:
    st.session_state.selected_company = {"id": "ACME-001", "name": "ACME Manufacturing"}

company = st.session_state.selected_company
render_company_header(company)

st.title("👥 Users & Role Management")

backend_live = is_backend_healthy()
token        = st.session_state.get("api_token")

# ── Login section ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("🔐 API Authentication")
    if token:
        me = get_me(token)
        if me:
            st.success(f"Logged in as **{me['full_name']}** ({me['role']})")
            if st.button("Log out"):
                st.session_state.pop("api_token", None)
                st.rerun()
        else:
            st.session_state.pop("api_token", None)
            st.warning("Session expired")
    else:
        if backend_live:
            with st.form("login_form"):
                email    = st.text_input("Email", value="admin@dep.local")
                password = st.text_input("Password", type="password", value="Admin1234!")
                if st.form_submit_button("Login"):
                    tok = login(email, password)
                    if tok:
                        st.session_state["api_token"] = tok
                        st.success("Logged in ✅")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        else:
            st.info("Backend offline — login unavailable")

# ── Backend status ─────────────────────────────────────────────────────────────
if backend_live:
    st.success("✅ Connected to live backend", icon="🟢")
else:
    st.warning("⚠️ Backend offline — showing demo data", icon="🟡")

# ── Mock data ─────────────────────────────────────────────────────────────────
_MOCK_USERS = [
    {"id": "u-001", "full_name": "Inaki Senar",     "email": "inaki@dep.com",     "role": "admin",      "is_active": True, "company_id": "ACME-001"},
    {"id": "u-002", "full_name": "Maria García",    "email": "maria@dep.com",     "role": "manager",    "is_active": True, "company_id": "ACME-001"},
    {"id": "u-003", "full_name": "Tom Wilson",      "email": "tom@dep.com",       "role": "technician", "is_active": True, "company_id": "ACME-001"},
    {"id": "u-004", "full_name": "Sara Müller",     "email": "sara@dep.com",      "role": "technician", "is_active": True, "company_id": "ACME-001"},
    {"id": "u-005", "full_name": "Javier López",    "email": "javier@dep.com",    "role": "customer",   "is_active": True, "company_id": "ACME-001"},
    {"id": "u-006", "full_name": "Ana Ferreira",    "email": "ana@dep.com",       "role": "technician", "is_active": False,"company_id": "ACME-001"},
]

company_id = company.get("id", "ACME-001")
raw_users = (list_users(company_id=company_id, token=token) if (backend_live and token) else None) or _MOCK_USERS

df = pd.DataFrame(raw_users)

# ── KPIs ───────────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Users",  len(df))
k2.metric("Active",       len(df[df["is_active"] == True]) if "is_active" in df.columns else "—")
k3.metric("Technicians",  len(df[df["role"] == "technician"]) if "role" in df.columns else "—")
k4.metric("Admins/Mgrs",  len(df[df["role"].isin(["admin", "manager"])]) if "role" in df.columns else "—")

st.markdown("---")

# ── Charts ─────────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    role_counts = df["role"].value_counts().reset_index()
    role_counts.columns = ["Role", "Count"]
    fig = px.bar(role_counts, x="Role", y="Count", color="Role",
                 title="Users by Role",
                 color_discrete_sequence=["#6366f1", "#3b82f6", "#22c55e", "#f97316"])
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with c2:
    active_counts = df["is_active"].value_counts().reset_index() if "is_active" in df.columns else pd.DataFrame()
    if not active_counts.empty:
        active_counts.columns = ["Active", "Count"]
        active_counts["Active"] = active_counts["Active"].map({True: "Active", False: "Inactive"})
        fig2 = px.pie(active_counts, names="Active", values="Count",
                      title="Active vs Inactive",
                      color_discrete_sequence=["#22c55e", "#ef4444"])
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

# ── User table ─────────────────────────────────────────────────────────────────
st.subheader("User Roster")
ROLE_ICONS = {"admin": "🛡️", "manager": "📊", "technician": "🔧", "customer": "🏢"}

display_cols = ["full_name", "email", "role", "is_active", "company_id"]
display_cols = [c for c in display_cols if c in df.columns]
display_df = df[display_cols].copy()

if "role" in display_df.columns:
    display_df["role"] = display_df["role"].map(lambda r: f"{ROLE_ICONS.get(r, '👤')} {r}")
if "is_active" in display_df.columns:
    display_df["is_active"] = display_df["is_active"].map(lambda v: "✅ Active" if v else "❌ Inactive")

st.dataframe(display_df, use_container_width=True, hide_index=True)

# ── RBAC explanation ──────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("🔐 Role-Based Access Control")
rbac_data = {
    "Role": ["Admin", "Manager", "Technician", "Customer"],
    "Create WO": ["✅", "✅", "✅", "❌"],
    "Close WO":  ["✅", "✅", "✅", "❌"],
    "View Finance": ["✅", "✅", "❌", "❌"],
    "Manage Users": ["✅", "✅", "❌", "❌"],
    "Run Agents": ["✅", "✅", "❌", "❌"],
    "View Dashboard": ["✅", "✅", "✅", "✅"],
}
st.dataframe(pd.DataFrame(rbac_data), use_container_width=True, hide_index=True)
