"""Smart Plant Dashboard for corrugated multi-site monitoring and digital twins."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.ingecart_monitoring import (
    FORMULA_LIBRARY,
    ROLE_PANELS,
    SOURCE_REGISTER,
    build_request_alert,
    generate_instant_offer,
    generate_monitoring_snapshot,
    get_scope_label,
    load_monitoring_blueprint,
    suggest_spare_parts,
)
from utils.styles import PLATFORM_CSS

st.set_page_config(page_title="Smart Plant Dashboard · DEP", page_icon="🏭", layout="wide")
st.markdown(PLATFORM_CSS, unsafe_allow_html=True)


def _inject_local_styles() -> None:
    st.markdown(
        """
        <style>
        .smart-hero {
            background: linear-gradient(135deg, rgba(255,106,0,0.18), rgba(11,59,255,0.16));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            padding: 24px 28px;
            margin-bottom: 18px;
        }
        .smart-chip {
            display: inline-block;
            padding: 6px 10px;
            margin-right: 8px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(8,15,20,0.35);
            color: #EDEFF2;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .smart-card {
            background: rgba(15,22,35,0.88);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 16px;
            min-height: 208px;
        }
        .smart-card h4 {
            margin: 0 0 4px 0;
            color: #EDEFF2;
            font-family: Poppins, sans-serif;
            font-size: 15px;
        }
        .smart-card p {
            color: #AEBBCB;
            font-size: 12px;
            margin-bottom: 8px;
        }
        .smart-kpi {
            font-size: 28px;
            color: #FF6A00;
            font-family: Poppins, sans-serif;
            font-weight: 800;
            margin: 6px 0 2px 0;
        }
        .smart-mini {
            color: #8898AA;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background: #FF6A00 !important;
            border-color: #FF6A00 !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] * {
            color: #EDEFF2 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_nav() -> None:
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center;padding:16px 0 12px;border-bottom:1px solid rgba(255,106,0,0.2);margin-bottom:14px;'>"
            "<div style='font-size:10px;font-weight:700;color:#FF6A00;letter-spacing:4px;text-transform:uppercase;margin-bottom:6px;'>◆ ING_DIGHUB</div>"
            "<div style='font-family:Poppins,sans-serif;font-size:18px;font-weight:800;color:#EDEFF2;letter-spacing:-0.5px;'>INGECART</div>"
            "<div style='font-size:10px;color:#8898AA;margin-top:3px;letter-spacing:0.5px;'>Corrugated Intelligence Platform</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.page_link("app.py", label="🏠  Overview")
        st.page_link("pages/01_Dashboard.py", label="📊  Dashboard")
        st.page_link("pages/02_Machine_Connectivity.py", label="🔌  Connectivity")
        st.page_link("pages/03_Digital_Twins.py", label="🪞  Digital Twins")
        st.page_link("pages/04_AI_Agents.py", label="🤖  AI Agents")
        st.page_link("pages/05_Maturity_Model.py", label="📈  Maturity Model")
        st.page_link("pages/06_Ecosystem_Blueprint.py", label="🗺️  Blueprint")
        st.page_link("pages/07_After_Sales_Engine.py", label="💰  After-Sales")
        st.page_link("pages/08_CMMS.py", label="🔧  CMMS")
        st.page_link("pages/10_smart_plant_dashboard.py", label="🏭  Smart Plant Dashboard")


def _render_site_cards(site_rows: list[dict]) -> None:
    cols = st.columns(min(3, max(1, len(site_rows))))
    for idx, site in enumerate(site_rows):
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="smart-card">
                    <div class="smart-mini">{site['country']} · {site['region']}</div>
                    <h4>{site['site_name']}</h4>
                    <p>{site['summary']}</p>
                    <div class="smart-kpi">{site['oee_pct']}%</div>
                    <div class="smart-mini">OEE</div>
                    <p style="margin-top:10px;">Critical assets: {site['critical_assets']}<br>
                    Active alerts: {site['active_alerts']}<br>
                    Evidence: {site['evidence_status']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _signal_label_map() -> dict[str, str]:
    return {
        "oee_pct": "OEE (%)",
        "throughput": "Throughput",
        "predicted_failure_risk_pct": "Predicted risk (%)",
        "queue_pct": "Queue (%)",
        "temperature_c": "Temperature (C)",
        "vibration_mm_s": "Vibration (mm/s)",
        "battery_pct": "Battery (%)",
        "reel_moves_h": "Reel moves / h",
        "rfid_reads_h": "RFID reads / h",
        "lpi_pct": "Logistic Pressure Index",
        "energy_kw": "Energy (kW)",
        "scrap_pct": "Scrap (%)",
        "drive_life_pct": "Drive life (%)",
    }


def _state_color(state: str) -> str:
    return {
        "running": "#22C55E",
        "warning": "#FFB84D",
        "critical": "#EF4444",
        "attention": "#4D7CFF",
    }.get(state, "#8898AA")


def _ensure_state() -> None:
    st.session_state.setdefault("smart_request_alerts", [])
    st.session_state.setdefault("smart_spare_matches", [])


def main() -> None:
    _inject_local_styles()
    _render_nav()
    _ensure_state()

    blueprint = load_monitoring_blueprint()
    with st.sidebar:
        role_names = list(ROLE_PANELS.keys())
        role = st.selectbox("Role cockpit", role_names, index=role_names.index("Ingecart"))
        scope_options = ["all"] + [site["id"] for site in blueprint["sites"]]
        scope = st.selectbox("Scope", scope_options, format_func=lambda value: get_scope_label(value, blueprint))
        days = st.slider("History window (days)", min_value=2, max_value=14, value=7)
        interval_minutes = st.select_slider("Resolution", options=[15, 30, 60], value=30)
        st.caption(ROLE_PANELS[role]["headline"])

    snapshot = generate_monitoring_snapshot(
        site_scope=scope,
        role=role,
        days=days,
        interval_minutes=interval_minutes,
        blueprint=blueprint,
    )

    series_df = pd.DataFrame(snapshot["series"])
    series_df["timestamp"] = pd.to_datetime(series_df["timestamp"])
    latest_df = pd.DataFrame(snapshot["equipment_latest"])
    sites_df = pd.DataFrame(snapshot["site_summaries"])
    recommendations_df = pd.DataFrame(snapshot["recommendations"])
    interventions_df = pd.DataFrame(snapshot["interventions"])
    contracts_df = pd.DataFrame(snapshot["contracts"])
    alerts_df = pd.DataFrame(snapshot["alerts"])
    formulas_df = pd.DataFrame(FORMULA_LIBRARY)
    hidden_df = pd.DataFrame(snapshot["hidden_issues"])
    briefing = snapshot["role_briefing"]
    mastercorr = snapshot["mastercorr_dataset"]

    st.markdown(
        f"""
        <div class="smart-hero">
            <span class="smart-chip">{snapshot['scope_label']}</span>
            <span class="smart-chip">{role}</span>
            <span class="smart-chip">{len(latest_df)} active twins</span>
            <h1 style="margin:10px 0 6px 0;font-family:Poppins,sans-serif;">INGECART Smart Plant Dashboard</h1>
            <p style="margin:0;color:#D7E0EA;">
                Multi-plant Corrugated 4.0 cockpit with live digital twins, alerts, AI recommendations,
                maintenance planning, service proposals and evidence-aware gap analysis.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Plants", len(sites_df))
    kpi_cols[1].metric("Assets", len(latest_df))
    kpi_cols[2].metric("Portfolio OEE", f"{snapshot['portfolio']['oee_pct']}%")
    kpi_cols[3].metric("Active alerts", snapshot["portfolio"]["active_alerts"])
    kpi_cols[4].metric("Service opportunity", f"EUR {snapshot['portfolio']['service_opportunity_eur']:.0f}")

    st.markdown('<div class="dep-section-header">Executive Twin</div>', unsafe_allow_html=True)
    _render_site_cards(snapshot["site_summaries"])

    tabs = st.tabs(
        [
            "Executive Twin",
            "Live Signals",
            "Maintenance & Service",
            "AI Copilot",
            "Role Cockpit",
            "Reports & Offers",
            "Evidence & Gaps",
        ]
    )

    with tabs[0]:
        overview_col, chart_col = st.columns([1.1, 1.4])
        with overview_col:
            st.markdown("#### Portfolio summary")
            st.write(briefing["portfolio_note"])
            st.markdown("#### Priority assets")
            st.dataframe(pd.DataFrame(briefing["priority_assets"]), use_container_width=True, hide_index=True)
        with chart_col:
            fig = px.bar(
                sites_df,
                x="site_name",
                y=["oee_pct", "availability_pct", "performance_pct", "quality_pct"],
                barmode="group",
                title="KPI comparison by plant",
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EDEFF2")
            st.plotly_chart(fig, use_container_width=True)

        if not alerts_df.empty:
            st.markdown("#### Live alert stack")
            st.dataframe(alerts_df, use_container_width=True, hide_index=True)

        bubble = px.scatter(
            sites_df,
            x="lpi_pct",
            y="oee_pct",
            size="annual_recovery_potential_eur",
            color="evidence_status",
            hover_name="site_name",
            title="Performance vs flow pressure",
        )
        bubble.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EDEFF2")
        st.plotly_chart(bubble, use_container_width=True)
        st.dataframe(sites_df, use_container_width=True, hide_index=True)

    with tabs[1]:
        signal_labels = _signal_label_map()
        equipment_values = ["all"] + latest_df["equipment_id"].tolist()
        live_col_1, live_col_2, live_col_3 = st.columns(3)
        with live_col_1:
            selected_equipment = st.selectbox(
                "Equipment",
                equipment_values,
                format_func=lambda value: "All equipment" if value == "all" else latest_df.loc[latest_df["equipment_id"] == value, "equipment_name"].iloc[0],
            )
        with live_col_2:
            selected_signal = st.selectbox("Signal", list(signal_labels.keys()), format_func=lambda value: signal_labels[value])
        with live_col_3:
            state_filter = st.multiselect("State", ["running", "warning", "critical", "attention"], default=["running", "warning", "critical", "attention"])

        chart_df = series_df.copy()
        filtered_latest = latest_df[latest_df["state"].isin(state_filter)]
        if selected_equipment != "all":
            chart_df = chart_df[chart_df["equipment_id"] == selected_equipment]
        else:
            chart_df = chart_df[chart_df["equipment_id"].isin(filtered_latest["equipment_id"])]
        if selected_signal == "battery_pct":
            chart_df = chart_df[chart_df["battery_pct"].notna()]

        if not chart_df.empty:
            fig = px.line(
                chart_df,
                x="timestamp",
                y=selected_signal,
                color="equipment_name" if selected_equipment == "all" else None,
                title=f"Live signal trend · {signal_labels[selected_signal]}",
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EDEFF2")
            st.plotly_chart(fig, use_container_width=True)

        mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
        mc1.metric("Automation mode", f"{mastercorr['auto_mode_pct']}%")
        mc2.metric("Manual mode", f"{mastercorr['manual_mode_pct']}%")
        mc3.metric("Pickup orders", mastercorr["pickup_orders"])
        mc4.metric("Drop-off orders", mastercorr["dropoff_orders"])
        mc5.metric("Avg pickup", f"{mastercorr['avg_pickup_time_s']} s")
        mc6.metric("Avg drop-off", f"{mastercorr['avg_dropoff_time_s']} s")
        st.caption(mastercorr["benchmark"])

        display_live = filtered_latest.copy()
        display_live["state"] = display_live["state"].apply(lambda value: f"<span style='color:{_state_color(value)};font-weight:700'>{value.upper()}</span>")
        st.write(
            display_live[
                [
                    "site_name",
                    "equipment_name",
                    "equipment_type",
                    "state",
                    "oee_pct",
                    "throughput",
                    "throughput_unit",
                    "queue_pct",
                    "predicted_failure_risk_pct",
                    "alarm_count",
                ]
            ].to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )

    with tabs[2]:
        maintenance_col, service_col = st.columns([1.2, 1])
        with maintenance_col:
            scatter = px.scatter(
                latest_df,
                x="maintenance_due_days",
                y="predicted_failure_risk_pct",
                size="cost_of_downtime_eur_h",
                color="site_name",
                hover_name="equipment_name",
                title="Maintenance horizon vs predicted failure risk",
            )
            scatter.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#EDEFF2")
            st.plotly_chart(scatter, use_container_width=True)
        with service_col:
            risk_counts = latest_df["state"].value_counts().reset_index()
            risk_counts.columns = ["state", "count"]
            donut = go.Figure(
                go.Pie(
                    labels=risk_counts["state"],
                    values=risk_counts["count"],
                    hole=0.5,
                    marker_colors=[_state_color(value) for value in risk_counts["state"]],
                )
            )
            donut.update_layout(title="Asset state mix", paper_bgcolor="rgba(0,0,0,0)", font_color="#EDEFF2")
            st.plotly_chart(donut, use_container_width=True)

        left, right = st.columns(2)
        with left:
            st.markdown("#### Intervention requests")
            st.dataframe(interventions_df, use_container_width=True, hide_index=True)
        with right:
            st.markdown("#### Recommended service contracts")
            st.dataframe(contracts_df, use_container_width=True, hide_index=True)

        st.markdown("#### Maintenance signal blueprint")
        st.dataframe(
            latest_df[
                [
                    "site_name",
                    "equipment_name",
                    "equipment_type",
                    "maintenance_due_days",
                    "predicted_failure_risk_pct",
                    "mtbf_h",
                    "mttr_min",
                    "drive_life_pct",
                    "cost_of_downtime_eur_h",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[3]:
        st.markdown("#### AI Copilot recommendations")
        st.dataframe(recommendations_df, use_container_width=True, hide_index=True)
        if role == "Ingecart":
            st.markdown("#### Hidden issues detected by the evidence engine")
            if hidden_df.empty:
                st.success("No latent issues detected for the selected scope.")
            else:
                st.dataframe(hidden_df, use_container_width=True, hide_index=True)
        with st.expander("Formula library"):
            st.dataframe(formulas_df, use_container_width=True, hide_index=True)
        with st.expander("Signal coverage by machine"):
            st.dataframe(
                latest_df[
                    [
                        "site_name",
                        "equipment_name",
                        "equipment_type",
                        "must_signals",
                        "optional_signals",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tabs[4]:
        st.markdown(f"### {briefing['headline']}")
        rc1, rc2 = st.columns([1, 1.3])
        with rc1:
            st.markdown("#### Decision stack")
            for item in briefing["decisions"]:
                st.write(f"- {item}")
            st.markdown("#### Handover notes")
            for item in briefing["handover_notes"]:
                st.write(f"- {item}")
        with rc2:
            st.markdown("#### Procurement and downtime exposure")
            st.dataframe(pd.DataFrame(briefing["procurement"]), use_container_width=True, hide_index=True)
        st.markdown("#### Operational asset ledger")
        st.dataframe(
            latest_df[
                [
                    "site_name",
                    "equipment_name",
                    "equipment_type",
                    "oem",
                    "model",
                    "benchmark_note",
                    "confidence",
                    "validation_status",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[5]:
        st.markdown("#### Automatic report")
        st.text_area("Preview", snapshot["report_markdown"], height=320)
        st.download_button(
            "Download report (.md)",
            data=snapshot["report_markdown"].encode("utf-8"),
            file_name=f"smart_plant_{scope}_{role.replace(' ', '_').lower()}.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download signals (.csv)",
            data=series_df.to_csv(index=False).encode("utf-8"),
            file_name=f"smart_plant_signals_{scope}.csv",
            mime="text/csv",
        )
        st.markdown("---")
        st.markdown("#### Immediate request to Ingecart")
        req_1, req_2, req_3 = st.columns(3)
        with req_1:
            request_kind = st.selectbox(
                "Request type",
                ["maintenance_contract", "materials_and_spares", "intervention", "improvement_upgrade"],
            )
        with req_2:
            target_equipment = st.selectbox(
                "Target equipment",
                ["all"] + latest_df["equipment_id"].tolist(),
                format_func=lambda value: "All equipment in scope" if value == "all" else latest_df.loc[latest_df["equipment_id"] == value, "equipment_name"].iloc[0],
            )
        with req_3:
            coverage = st.selectbox("Coverage", ["business_hours", "extended", "24x7"], index=2)
        urgency = st.radio("Urgency", ["standard", "priority", "emergency"], horizontal=True, index=1)
        rq1, rq2, rq3 = st.columns(3)
        with rq1:
            requester_name = st.text_input("Requester")
        with rq2:
            requester_role = st.selectbox("Requester role", ["Board", "Plant manager", "Production manager", "Maintenance", "Operator", "Purchasing"], index=4)
        with rq3:
            request_site_id = st.selectbox(
                "Plant",
                [site["id"] for site in blueprint["sites"]],
                format_func=lambda value: get_scope_label(value, blueprint),
            )

        spare_description = ""
        if request_kind == "materials_and_spares":
            spare_description = st.text_area(
                "Technical description",
                placeholder="Example: 7.5 kW conveyor drive with STO for transfer line or RFID reader for reel station",
                height=100,
            )
            if st.button("Search compatible spares", use_container_width=True):
                st.session_state["smart_spare_matches"] = suggest_spare_parts(spare_description, top_k=8)
            matches = st.session_state.get("smart_spare_matches", [])
            if matches:
                rows = []
                for match in matches:
                    rows.append(
                        {
                            "Family": match["family_group"],
                            "OEM code": match["oem_code"],
                            "Description": match["technical_description"],
                            "Lead time": match["lead_time_days"],
                            "Criticality": match["criticality"],
                        }
                    )
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        offer = generate_instant_offer(snapshot, request_kind, target_equipment, coverage, urgency)
        offer_cols = st.columns(4)
        offer_cols[0].metric("Reference", offer["reference"])
        offer_cols[1].metric("CAPEX", f"EUR {offer['capex_total_eur']:.0f}")
        offer_cols[2].metric("Monthly OPEX", f"EUR {offer['monthly_total_eur']:.0f}")
        offer_cols[3].metric("SLA", f"{offer['response_sla_hours']} h")
        st.dataframe(pd.DataFrame(offer["lines"]), use_container_width=True, hide_index=True)
        st.info(offer["notes"])
        if st.button("Register request and create alert", use_container_width=True):
            details = spare_description.strip() or f"{request_kind} request for {offer['reference']}"
            if request_kind == "materials_and_spares" and not spare_description.strip():
                st.warning("Add a technical description before registering a spares request.")
            else:
                alert = build_request_alert(
                    request_kind=request_kind,
                    requester_name=requester_name,
                    requester_role=requester_role,
                    plant_id=request_site_id,
                    plant_name=get_scope_label(request_site_id, blueprint),
                    coverage=coverage,
                    urgency=urgency,
                    equipment_name="All equipment" if target_equipment == "all" else latest_df.loc[latest_df["equipment_id"] == target_equipment, "equipment_name"].iloc[0],
                    details=details,
                )
                st.session_state["smart_request_alerts"].append(alert)
                st.success("Request registered in session state for Ingecart follow-up.")
        if st.session_state["smart_request_alerts"]:
            st.markdown("#### Session request queue")
            st.dataframe(pd.DataFrame(st.session_state["smart_request_alerts"]), use_container_width=True, hide_index=True)

    with tabs[6]:
        gap = snapshot["gap_analysis"]
        st.markdown("#### Source register")
        st.dataframe(pd.DataFrame(SOURCE_REGISTER), use_container_width=True, hide_index=True)
        st.markdown("#### Validation matrix")
        st.dataframe(
            latest_df[
                [
                    "site_name",
                    "equipment_name",
                    "equipment_type",
                    "evidence_level",
                    "confidence",
                    "validation_status",
                    "source_refs",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
        g1, g2 = st.columns(2)
        with g1:
            st.markdown("#### Partially confirmed")
            st.dataframe(pd.DataFrame(gap["partial"]), use_container_width=True, hide_index=True)
            st.markdown("#### Contradictions / hypotheses")
            st.dataframe(pd.DataFrame(gap["contradictions"]), use_container_width=True, hide_index=True)
        with g2:
            st.markdown("#### Known")
            st.dataframe(pd.DataFrame(gap["known"]), use_container_width=True, hide_index=True)
            st.markdown("#### Still needed")
            st.dataframe(pd.DataFrame(gap["pending"]), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
