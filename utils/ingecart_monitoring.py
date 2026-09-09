"""Monitoring blueprint and digital-twin simulation for the Smart Plant dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import math
import json
import random
from typing import Any, Dict, Iterable, List, Sequence

import pandas as pd

GENERAL_SIGNALS = [
    "vibration_mm_s",
    "temperature_c",
    "drive_life_pct",
    "energy_kw",
    "alarm_count",
    "downtime_minutes",
    "fault_events",
    "mtbf_h",
    "mttr_min",
    "oee_pct",
]

FORMULA_LIBRARY: List[Dict[str, str]] = [
    {"name": "OEE", "expression": "availability_pct * performance_pct * quality_pct / 10000", "target": ">= 85%"},
    {"name": "Availability", "expression": "runtime / planned_time", "target": ">= 92%"},
    {"name": "Performance", "expression": "actual_output / ideal_output", "target": ">= 90%"},
    {"name": "Quality", "expression": "good_output / total_output", "target": ">= 98%"},
    {"name": "LPI", "expression": "(queue_pct + starvation_penalty + route_conflicts) / 3", "target": "<= 40"},
    {"name": "Queue Pressure", "expression": "queue_pct * criticality_factor", "target": "<= 55"},
    {"name": "Predictive Risk", "expression": "weighted(temp, vibration, alarms, drift, maintenance_due)", "target": "<= 35%"},
    {"name": "MTTR", "expression": "repair_minutes / failure_events", "target": "<= 45 min"},
]

ROLE_PANELS: Dict[str, Dict[str, Any]] = {
    "Ingecart": {
        "headline": "Service-led monitoring cockpit across automation, performance and lifecycle risk.",
        "focus_kpis": ["service_opportunity_eur", "active_alerts", "predicted_failure_risk_pct"],
        "decisions": [
            "Prioritize interventions on assets with high downtime cost and short maintenance horizon.",
            "Convert recurrent performance losses into retrofit and service proposals.",
            "Track hidden issues before the customer escalates them.",
        ],
    },
    "Board Cliente": {
        "headline": "Executive overview of production resilience, ROI recovery and strategic risk.",
        "focus_kpis": ["oee_pct", "annual_recovery_potential_eur", "energy_mwh_week"],
        "decisions": [
            "Approve capital-light service actions with the fastest payback.",
            "Review site-to-site performance gaps and recovery potential.",
            "Escalate assets that jeopardize delivery reliability or safety.",
        ],
    },
    "Plant manager Cliente": {
        "headline": "Plant orchestration view centered on throughput continuity, alarms and staffing impact.",
        "focus_kpis": ["throughput", "queue_pct", "downtime_minutes"],
        "decisions": [
            "Stabilize bottlenecks before queues starve or block the line.",
            "Rebalance WIP, logistics and palletizing resources by shift.",
            "Coordinate production, maintenance and shipping handovers.",
        ],
    },
    "Production manager Cliente": {
        "headline": "Shift execution cockpit for output, waste, flow pressure and changeover discipline.",
        "focus_kpis": ["throughput", "scrap_pct", "performance_pct"],
        "decisions": [
            "Attack losses from waiting, rehandling and low-speed running.",
            "Protect line rate on corrugator, RDC, FFG and palletizing choke points.",
            "Compare actual vs benchmark production by asset family.",
        ],
    },
    "Maintenance Cliente": {
        "headline": "Predictive, preventive and corrective maintenance prioritization.",
        "focus_kpis": ["predicted_failure_risk_pct", "maintenance_due_days", "mtbf_h"],
        "decisions": [
            "Schedule interventions before risk converts into unplanned downtime.",
            "Align spares coverage with wear, alarms and OEM lead times.",
            "Use evidence-backed failure patterns for root-cause elimination.",
        ],
    },
    "Operario cliente": {
        "headline": "Operator-first view focused on what is running, what is blocked and what to do next.",
        "focus_kpis": ["state", "alarm_count", "queue_pct"],
        "decisions": [
            "Identify the next action to keep production safe and flowing.",
            "Escalate only alarms with process impact or safety implications.",
            "Confirm material availability, destination readiness and recipe integrity.",
        ],
    },
    "Compras Cliente": {
        "headline": "Procurement view tied to downtime cost, spares urgency and service coverage.",
        "focus_kpis": ["cost_of_downtime_eur_h", "maintenance_due_days", "service_opportunity_eur"],
        "decisions": [
            "Buy critical spares before lead time jeopardizes uptime.",
            "Compare SLA coverage against downtime exposure by site.",
            "Prioritize offers that reduce recurring corrective spend.",
        ],
    },
}

MODULE_CATALOG: List[Dict[str, str]] = [
    {"id": "executive_twin", "label": "Executive Twin"},
    {"id": "live_signals", "label": "Live Signals"},
    {"id": "maintenance_service", "label": "Maintenance & Service"},
    {"id": "fault_resolution", "label": "Fault Resolution"},
    {"id": "ai_copilot", "label": "AI Copilot"},
    {"id": "role_cockpit", "label": "Role Cockpit"},
    {"id": "reports_offers", "label": "Reports & Offers"},
    {"id": "evidence_gaps", "label": "Evidence & Gaps"},
]

ROLE_MODULE_ACCESS: Dict[str, List[str]] = {
    "Ingecart": [item["id"] for item in MODULE_CATALOG],
    "Board Cliente": ["executive_twin", "ai_copilot", "role_cockpit", "reports_offers", "evidence_gaps"],
    "Plant manager Cliente": ["executive_twin", "live_signals", "maintenance_service", "fault_resolution", "ai_copilot", "role_cockpit", "reports_offers"],
    "Production manager Cliente": ["executive_twin", "live_signals", "maintenance_service", "fault_resolution", "ai_copilot", "role_cockpit", "reports_offers"],
    "Maintenance Cliente": ["live_signals", "maintenance_service", "fault_resolution", "ai_copilot", "role_cockpit", "reports_offers", "evidence_gaps"],
    "Operario cliente": ["live_signals", "fault_resolution", "role_cockpit"],
    "Compras Cliente": ["maintenance_service", "ai_copilot", "role_cockpit", "reports_offers", "evidence_gaps"],
}

RACI_BY_MODULE: Dict[str, Dict[str, str]] = {
    "Executive Twin": {
        "Ingecart": "A/R",
        "Board Cliente": "A",
        "Plant manager Cliente": "R",
        "Production manager Cliente": "C",
        "Maintenance Cliente": "I",
        "Operario cliente": "I",
        "Compras Cliente": "C",
    },
    "Live Signals": {
        "Ingecart": "A/R",
        "Board Cliente": "I",
        "Plant manager Cliente": "R",
        "Production manager Cliente": "R",
        "Maintenance Cliente": "C",
        "Operario cliente": "R",
        "Compras Cliente": "I",
    },
    "Maintenance & Service": {
        "Ingecart": "A/R",
        "Board Cliente": "I",
        "Plant manager Cliente": "C",
        "Production manager Cliente": "C",
        "Maintenance Cliente": "R",
        "Operario cliente": "I",
        "Compras Cliente": "C",
    },
    "Fault Resolution": {
        "Ingecart": "A/R",
        "Board Cliente": "I",
        "Plant manager Cliente": "A",
        "Production manager Cliente": "C",
        "Maintenance Cliente": "R",
        "Operario cliente": "R",
        "Compras Cliente": "I",
    },
    "AI Copilot": {
        "Ingecart": "A/R",
        "Board Cliente": "C",
        "Plant manager Cliente": "C",
        "Production manager Cliente": "C",
        "Maintenance Cliente": "C",
        "Operario cliente": "I",
        "Compras Cliente": "C",
    },
    "Role Cockpit": {
        "Ingecart": "A/R",
        "Board Cliente": "A",
        "Plant manager Cliente": "R",
        "Production manager Cliente": "R",
        "Maintenance Cliente": "R",
        "Operario cliente": "R",
        "Compras Cliente": "R",
    },
    "Reports & Offers": {
        "Ingecart": "A/R",
        "Board Cliente": "C",
        "Plant manager Cliente": "C",
        "Production manager Cliente": "C",
        "Maintenance Cliente": "C",
        "Operario cliente": "I",
        "Compras Cliente": "R",
    },
    "Evidence & Gaps": {
        "Ingecart": "A/R",
        "Board Cliente": "C",
        "Plant manager Cliente": "I",
        "Production manager Cliente": "I",
        "Maintenance Cliente": "C",
        "Operario cliente": "I",
        "Compras Cliente": "I",
    },
}

SOURCE_REGISTER: List[Dict[str, str]] = [
    {
        "id": "SRC-CALGARY-TXT",
        "title": "equipos_instalados_conocidos_2026-09-09.txt",
        "kind": "validated_workspace_extract",
        "validated_on": "2026-09-09",
    },
    {
        "id": "SRC-CALGARY-CATALOG",
        "title": "knowledge/corrugated_equipment/converter_equipment_catalog_v1.json",
        "kind": "equipment_catalog",
        "validated_on": "2026-08-17",
    },
    {
        "id": "SRC-INGETRANS-DT",
        "title": "INGECART/PRODUCTO/INGETRANS/DIGITAL_TWIN_SIMULATION_REPORT_SHORT_RUNS_2026-08-19.txt",
        "kind": "benchmark_report",
        "validated_on": "2026-08-19",
    },
    {
        "id": "SRC-INGETRANS-OPS",
        "title": "INGECART/PRODUCTO/INGETRANS/DATOS OPERATIVOS MASTERCORR 20 08 2026/ANALISIS DATOS INGETRANS TF.txt",
        "kind": "operational_analysis",
        "validated_on": "2026-08-20",
    },
    {
        "id": "SRC-HD-PALLETIZER",
        "title": "INGECART/PRODUCTO/PALETIZADOR/.../ING_HEAVYDUTYPALLETIZER®.txt",
        "kind": "product_sheet",
        "validated_on": "2026-08-26",
    },
    {
        "id": "SRC-PP-PALLETIZER",
        "title": "INGECART/PRODUCTO/PALETIZADOR/.../ING_PLUG&PALLETIZER offer text.txt",
        "kind": "product_sheet",
        "validated_on": "2026-08-26",
    },
    {
        "id": "SRC-AMR-WIP",
        "title": "INGECART/PRODUCTO/AMR INTRALOGISTICS/TECHNICAL REPORT AMR INTR.txt",
        "kind": "technical_report",
        "validated_on": "2026-08-26",
    },
    {
        "id": "SRC-RFID",
        "title": "INGECART/PRODUCTO/RFID Reel Management System/RFID Reel Management System.txt",
        "kind": "product_sheet",
        "validated_on": "2026-08-26",
    },
    {
        "id": "SRC-SR1400",
        "title": "INGECART/PRODUCTO/SISTEMA RETAL/Ingecart SR-1400 Waste System.txt",
        "kind": "product_sheet",
        "validated_on": "2026-08-26",
    },
    {
        "id": "SRC-ATLS",
        "title": "INGECART/PRODUCTO/SISTEMA CARGA AUTO CAMIONES/Automatic Truck Loading Systems.txt",
        "kind": "product_sheet",
        "validated_on": "2026-08-26",
    },
]

SPARE_PART_CATALOG: List[Dict[str, Any]] = [
    {
        "family_group": "AMR traction and safety",
        "oem_code": "IN-AMR-BATT-48V",
        "technical_description": "Lithium battery pack and BMS kit for KMP 1500P / AMR intralogistics fleet",
        "lead_time_days": 14,
        "criticality": "high",
        "compatible_alternatives": [
            {"vendor": "KUKA", "code": "KMP-48V-BAT", "technical_description": "Battery pack for KMP platform"},
            {"vendor": "WEG", "code": "LFP-48V-TR", "technical_description": "Industrial traction battery module"},
        ],
    },
    {
        "family_group": "RFID and traceability",
        "oem_code": "IN-RFID-GATE-01",
        "technical_description": "Industrial RFID reader / gateway for reel weighing and traceability stations",
        "lead_time_days": 7,
        "criticality": "medium",
        "compatible_alternatives": [
            {"vendor": "SICK", "code": "RFU61X", "technical_description": "Industrial RFID reader"},
            {"vendor": "Turck", "code": "Q80-RFID", "technical_description": "RFID identification head"},
        ],
    },
    {
        "family_group": "Servo gripper and palletizing",
        "oem_code": "IN-PAL-GRIP-180",
        "technical_description": "Universal servo gripper wear kit for heavy duty and plug and play palletizers",
        "lead_time_days": 10,
        "criticality": "high",
        "compatible_alternatives": [
            {"vendor": "KUKA", "code": "KRC-GRIP-SRV", "technical_description": "Robot gripper service kit"},
            {"vendor": "FESTO", "code": "EGC-GRIP", "technical_description": "Servo gripper components"},
        ],
    },
    {
        "family_group": "Conveyors and transfer",
        "oem_code": "IN-CONV-DRV-75",
        "technical_description": "7.5 kW drive with STO for transfer car and trident conveyor applications",
        "lead_time_days": 9,
        "criticality": "high",
        "compatible_alternatives": [
            {"vendor": "Siemens", "code": "G120X-7K5", "technical_description": "Drive with safe torque off"},
            {"vendor": "Schneider", "code": "ATV630-7K5", "technical_description": "Industrial conveyor drive"},
        ],
    },
    {
        "family_group": "Load cells and weighing",
        "oem_code": "IN-LC-3500",
        "technical_description": "Load cell kit for reel weighing station up to 3500 kg",
        "lead_time_days": 12,
        "criticality": "medium",
        "compatible_alternatives": [
            {"vendor": "HBM", "code": "PW27-3T5", "technical_description": "High-capacity load cell"},
            {"vendor": "Mettler Toledo", "code": "POWERCELL-3T5", "technical_description": "Weighing module"},
        ],
    },
]

TYPE_LIBRARY: Dict[str, Dict[str, Any]] = {
    "corrugator": {
        "label": "Corrugator",
        "throughput_unit": "m/min",
        "throughput_baseline": 220.0,
        "throughput_floor": 165.0,
        "throughput_ceiling": 320.0,
        "temperature_base": 73.0,
        "vibration_base": 1.8,
        "energy_base_kw": 420.0,
        "queue_base": 26.0,
        "quality_base": 99.1,
        "must_signals": [
            "line_speed_m_min",
            "paper_tension",
            "warp_detection",
            "steam_flow",
            "starch_flow",
            "bridge_buffer",
            "cutoff_cycles",
            "scrap_pct",
        ],
        "optional_signals": ["thermal_map", "roller_parallelism", "condensate_return", "reel_remaining_m"],
        "service_contract": "24x7 Production Continuity",
    },
    "rdc": {
        "label": "RDC / Flexo Rotary Die Cutter",
        "throughput_unit": "sheets/h",
        "throughput_baseline": 9400.0,
        "throughput_floor": 6500.0,
        "throughput_ceiling": 13000.0,
        "temperature_base": 68.0,
        "vibration_base": 2.0,
        "energy_base_kw": 175.0,
        "queue_base": 34.0,
        "quality_base": 98.5,
        "must_signals": [
            "sheet_registration",
            "die_cut_pressure",
            "feeder_vacuum",
            "anilox_or_cliche_pressure",
            "stacker_status",
            "double_feed_events",
        ],
        "optional_signals": ["ink_viscosity", "ink_ph", "hydraulic_pressure", "vision_defect_rate"],
        "service_contract": "RDC Performance Guard",
    },
    "ffg": {
        "label": "FFG / Folder Gluer",
        "throughput_unit": "sheets/min",
        "throughput_baseline": 280.0,
        "throughput_floor": 160.0,
        "throughput_ceiling": 400.0,
        "temperature_base": 64.0,
        "vibration_base": 1.6,
        "energy_base_kw": 125.0,
        "queue_base": 30.0,
        "quality_base": 98.8,
        "must_signals": [
            "glue_application_g_m2",
            "fold_alignment",
            "bundle_count",
            "vacuum_frequency",
            "fish_tail_rate",
            "changeover_minutes",
        ],
        "optional_signals": ["board_humidity_in", "glue_zone_thermal_map", "vision_pack_quality"],
        "service_contract": "Conversion Uptime Plus",
    },
    "die_cutter": {
        "label": "Flatbed Die Cutter",
        "throughput_unit": "sheets/h",
        "throughput_baseline": 3800.0,
        "throughput_floor": 2400.0,
        "throughput_ceiling": 5000.0,
        "temperature_base": 66.0,
        "vibration_base": 2.2,
        "energy_base_kw": 140.0,
        "queue_base": 22.0,
        "quality_base": 98.3,
        "must_signals": [
            "press_force_t",
            "strike_count",
            "stripping_status",
            "sheet_registration",
            "knife_wear_index",
        ],
        "optional_signals": ["hydraulic_temperature", "bed_vibration", "guide_wear"],
        "service_contract": "Die-Cut Integrity Care",
    },
    "amr": {
        "label": "AMR / AGV",
        "throughput_unit": "missions/h",
        "throughput_baseline": 42.0,
        "throughput_floor": 22.0,
        "throughput_ceiling": 65.0,
        "temperature_base": 42.0,
        "vibration_base": 0.8,
        "energy_base_kw": 12.0,
        "queue_base": 18.0,
        "quality_base": 99.4,
        "must_signals": [
            "battery_soc_pct",
            "route_conflicts",
            "charging_status",
            "mission_queue",
            "distance_travelled_m",
            "safety_scanner_events",
        ],
        "optional_signals": ["wheel_wear", "route_heatmap", "dock_alignment_mm"],
        "service_contract": "Fleet Availability Care",
    },
    "ingetrans": {
        "label": "Ingetrans Reel Logistics",
        "throughput_unit": "reel_moves/h",
        "throughput_baseline": 8.8,
        "throughput_floor": 5.2,
        "throughput_ceiling": 12.0,
        "temperature_base": 52.0,
        "vibration_base": 1.1,
        "energy_base_kw": 48.0,
        "queue_base": 24.0,
        "quality_base": 99.6,
        "must_signals": [
            "pickup_time_s",
            "dropoff_time_s",
            "auto_mode_pct",
            "manual_mode_pct",
            "reel_return_events",
            "track_occupancy_pct",
            "starvation_events",
        ],
        "optional_signals": ["dual_reel_trip_ratio", "splicer_waiting_time_s", "wrong_reel_events"],
        "service_contract": "Ingetrans Production Continuity",
    },
    "rfid": {
        "label": "RFID Reel Management",
        "throughput_unit": "reads/h",
        "throughput_baseline": 260.0,
        "throughput_floor": 120.0,
        "throughput_ceiling": 420.0,
        "temperature_base": 39.0,
        "vibration_base": 0.4,
        "energy_base_kw": 6.0,
        "queue_base": 8.0,
        "quality_base": 99.8,
        "must_signals": [
            "tag_reads_h",
            "inventory_accuracy_pct",
            "reel_remaining_m",
            "reel_weight_kg",
            "fifo_compliance_pct",
            "data_sync_latency_s",
        ],
        "optional_signals": ["forklift_portal_events", "read_retry_pct", "traceability_completeness_pct"],
        "service_contract": "Traceability Assurance",
    },
    "palletizer_hd": {
        "label": "Heavy Duty Palletizer",
        "throughput_unit": "bundles/min",
        "throughput_baseline": 13.2,
        "throughput_floor": 8.5,
        "throughput_ceiling": 26.0,
        "temperature_base": 57.0,
        "vibration_base": 1.3,
        "energy_base_kw": 62.0,
        "queue_base": 28.0,
        "quality_base": 99.0,
        "must_signals": [
            "bundle_rate",
            "robot_cycle_time_s",
            "gripper_servo_load_pct",
            "interlayer_status",
            "four_side_squaring_ok_pct",
            "pallet_stability_score",
        ],
        "optional_signals": ["trajectory_stress_index", "robot_joint_temperature", "pattern_changeovers"],
        "service_contract": "Heavy Duty Palletizing SLA",
    },
    "palletizer_pp": {
        "label": "Plug & Play Palletizer",
        "throughput_unit": "bundles/min",
        "throughput_baseline": 12.0,
        "throughput_floor": 7.0,
        "throughput_ceiling": 14.0,
        "temperature_base": 54.0,
        "vibration_base": 1.1,
        "energy_base_kw": 44.0,
        "queue_base": 24.0,
        "quality_base": 99.1,
        "must_signals": [
            "bundle_rate",
            "recipe_changeover_min",
            "gripper_position_mm",
            "bottom_sheet_status",
            "interlayer_status",
            "pallet_discharge_time_s",
        ],
        "optional_signals": ["format_count", "motion_smoothness_index", "recipe_sync_status"],
        "service_contract": "Plug & Play Uptime",
    },
    "waste_system": {
        "label": "Waste Logistics System",
        "throughput_unit": "waste_t_h",
        "throughput_baseline": 4.6,
        "throughput_floor": 2.0,
        "throughput_ceiling": 7.5,
        "temperature_base": 49.0,
        "vibration_base": 1.0,
        "energy_base_kw": 28.0,
        "queue_base": 14.0,
        "quality_base": 99.3,
        "must_signals": [
            "chain_speed",
            "sectional_stop_events",
            "ramp_flow",
            "dust_level",
            "chain_lube_status",
            "baler_feed_continuity_pct",
        ],
        "optional_signals": ["noise_level_db", "fire_risk_index", "wear_plate_remaining_pct"],
        "service_contract": "Waste Flow Reliability",
    },
    "truck_loading": {
        "label": "Automatic Truck Loading",
        "throughput_unit": "trucks/h",
        "throughput_baseline": 8.0,
        "throughput_floor": 2.0,
        "throughput_ceiling": 12.0,
        "temperature_base": 47.0,
        "vibration_base": 0.9,
        "energy_base_kw": 22.0,
        "queue_base": 20.0,
        "quality_base": 99.5,
        "must_signals": [
            "truck_cycle_minutes",
            "dock_queue",
            "belt_sync_pct",
            "dispatch_readiness_pct",
            "load_confirmation_events",
        ],
        "optional_signals": ["truck_alignment_mm", "dock_door_cycles", "dispatch_camera_ai"],
        "service_contract": "Shipping Acceleration Care",
    },
    "transfer": {
        "label": "Transfer / Trident / Conveyor",
        "throughput_unit": "moves/h",
        "throughput_baseline": 56.0,
        "throughput_floor": 24.0,
        "throughput_ceiling": 90.0,
        "temperature_base": 50.0,
        "vibration_base": 1.2,
        "energy_base_kw": 36.0,
        "queue_base": 25.0,
        "quality_base": 99.4,
        "must_signals": [
            "position_mm",
            "destination_ready_pct",
            "interlock_ok_pct",
            "handoff_time_s",
            "occupancy_pct",
            "collision_events",
        ],
        "optional_signals": ["rehandling_moves", "route_priority_swaps", "conveyor_motor_load_pct"],
        "service_contract": "Flow Orchestration Support",
    },
    "weighing_station": {
        "label": "Weighing and Data Station",
        "throughput_unit": "weighings/h",
        "throughput_baseline": 18.0,
        "throughput_floor": 8.0,
        "throughput_ceiling": 30.0,
        "temperature_base": 41.0,
        "vibration_base": 0.5,
        "energy_base_kw": 8.0,
        "queue_base": 12.0,
        "quality_base": 99.7,
        "must_signals": [
            "weight_accuracy_pct",
            "diameter_measurement_mm",
            "master_data_sync_pct",
            "load_cell_health_pct",
        ],
        "optional_signals": ["photo_capture_success_pct", "barcode_rfid_match_pct"],
        "service_contract": "Traceability Data Care",
    },
}


def _stable_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _equipment(
    site_id: str,
    equipment_id: str,
    name: str,
    kind: str,
    oem: str,
    model: str,
    evidence_level: str,
    confidence: str,
    validation_status: str,
    sources: Sequence[str],
    benchmark_note: str,
    **overrides: Any,
) -> Dict[str, Any]:
    profile = TYPE_LIBRARY[kind]
    payload = {
        "id": equipment_id,
        "site_id": site_id,
        "name": name,
        "kind": kind,
        "type_label": profile["label"],
        "oem": oem,
        "model": model,
        "evidence_level": evidence_level,
        "confidence": confidence,
        "validation_status": validation_status,
        "source_refs": list(sources),
        "benchmark_note": benchmark_note,
        "throughput_unit": profile["throughput_unit"],
        "throughput_baseline": profile["throughput_baseline"],
        "throughput_floor": profile["throughput_floor"],
        "throughput_ceiling": profile["throughput_ceiling"],
        "temperature_base": profile["temperature_base"],
        "vibration_base": profile["vibration_base"],
        "energy_base_kw": profile["energy_base_kw"],
        "queue_base": profile["queue_base"],
        "quality_base": profile["quality_base"],
        "must_signals": profile["must_signals"] + GENERAL_SIGNALS,
        "optional_signals": profile["optional_signals"],
        "service_contract": profile["service_contract"],
    }
    payload.update(overrides)
    return payload


def load_monitoring_blueprint() -> Dict[str, Any]:
    sites = [
        {
            "id": "cascades_calgary",
            "name": "Cascades Calgary",
            "country": "CA",
            "region": "North America",
            "critical_assets": 10,
            "evidence_status": "validated",
            "notes": "Most complete evidence set in the workspace: Calgary inventory, catalog and automation reports.",
            "equipment": [
                _equipment("cascades_calgary", "cg_fosber_corr", "Fosber Corrugator", "corrugator", "Fosber", "S/LINE 370 / 420", "A/B", "high", "validated", ["SRC-CALGARY-TXT", "SRC-CALGARY-CATALOG"], "OEM family plus corrugated benchmark; simulated operating speed below design maximum."),
                _equipment("cascades_calgary", "cg_mckinley_rdc", "McKinley RDC", "rdc", "McKinley", "66 x 130 in", "C/U", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-CALGARY-CATALOG"], "Installed machine identified; throughput simulated from large-format RDC benchmark."),
                _equipment("cascades_calgary", "cg_koppers_rdc", "Koppers RDC", "rdc", "Koppers", "49 in RDC", "U", "low", "partial", ["SRC-CALGARY-TXT", "SRC-CALGARY-CATALOG"], "Model incomplete; twin uses conservative legacy RDC benchmark.", throughput_baseline=7600.0),
                _equipment("cascades_calgary", "cg_ward_rdc", "Ward RDC", "rdc", "Ward", "66 x 115 in", "C", "medium", "validated", ["SRC-CALGARY-TXT", "SRC-CALGARY-CATALOG"], "Large-format heavy-duty RDC benchmark aligned to catalog evidence.", throughput_baseline=8200.0),
                _equipment("cascades_calgary", "cg_estar_fgs", "ESTAR Two-Piece FGS", "ffg", "ESTAR", "Two-Piece Folder Gluer & Stitcher", "C", "medium", "validated", ["SRC-CALGARY-TXT", "SRC-CALGARY-CATALOG"], "Twin based on stitcher/folder gluer sector benchmark due limited public plate data.", throughput_baseline=165.0),
                _equipment("cascades_calgary", "cg_ingetrans", "Ingetrans Flow Orchestrator", "ingetrans", "Ingecart", "Ingetrans", "E", "medium", "proposal-validated", ["SRC-CALGARY-TXT", "SRC-INGETRANS-DT", "SRC-INGETRANS-OPS"], "Simulated with European benchmark and Mastercorr operational patterns."),
                _equipment("cascades_calgary", "cg_transfer", "Transfer Car and Trident Cell", "transfer", "Ingecart", "Transfer car + trident stations", "E", "medium", "proposal-validated", ["SRC-CALGARY-TXT"], "Transfer and conveyor monitoring inferred from Calgary phase architecture."),
                _equipment("cascades_calgary", "cg_plugplay", "Plug & Play Palletizer", "palletizer_pp", "Ingecart", "ING_PLUG&PALLETIZER", "E", "medium", "proposal-validated", ["SRC-CALGARY-TXT", "SRC-PP-PALLETIZER"], "12 bundles/min benchmark from Ingecart product sheet."),
                _equipment("cascades_calgary", "cg_amr", "AMR WIP Cell", "amr", "Ingecart", "AMR conversion WIP cell", "E", "medium", "proposal-validated", ["SRC-CALGARY-TXT", "SRC-AMR-WIP"], "AMR fleet benchmark from WIP conversion report."),
                _equipment("cascades_calgary", "cg_rfid", "RFID Reel and Flow Traceability", "rfid", "Ingecart", "RFID management system", "E", "medium", "proposal-validated", ["SRC-CALGARY-TXT", "SRC-RFID"], "Traceability twin aligned to RFID architecture and reel data capture logic."),
            ],
        },
        {
            "id": "ip_waterloo",
            "name": "IP Waterloo",
            "country": "CA",
            "region": "North America",
            "critical_assets": 8,
            "evidence_status": "partial",
            "notes": "Workspace evidence comes from offer-level details for AMR, conveyors, weighing, EVOL and palletizing assets.",
            "equipment": [
                _equipment("ip_waterloo", "wtl_corr_amr", "Corrugator Area AMR", "amr", "Ingecart", "KMP 1500P Master", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-AMR-WIP"], "Offer-specific AMR deployment with benchmark missions per hour.", throughput_baseline=34.0),
                _equipment("ip_waterloo", "wtl_weigh", "RFID Reel Weighing Station", "weighing_station", "Ingecart", "Load-cell reel station", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-RFID"], "Weighing station explicitly referenced in the offer extract."),
                _equipment("ip_waterloo", "wtl_corr_transfer", "Corrugator Trident Conveyors", "transfer", "Ingecart", "2 x 5-line motorized belts", "proposal", "medium", "partial", ["SRC-CALGARY-TXT"], "Twin based on trident conveyor configuration referenced in the offer."),
                _equipment("ip_waterloo", "wtl_conv_amr", "Converting Area AMR Fleet", "amr", "Ingecart", "3 x KMP 1500P Master", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-AMR-WIP"], "Fleet-level simulation for converting logistics."),
                _equipment("ip_waterloo", "wtl_conv_transfer", "Converting Trident Conveyors", "transfer", "Ingecart", "3 x 5-line motorized belts", "proposal", "medium", "partial", ["SRC-CALGARY-TXT"], "Offer-specific conveyor transfer cell feeding interlayer platforms."),
                _equipment("ip_waterloo", "wtl_evol", "Mitsubishi EVOL", "ffg", "Mitsubishi", "EVOL", "proposal", "medium", "partial", ["SRC-CALGARY-TXT"], "Operating twin uses premium FFG benchmark with palletizer downstream coupling.", throughput_baseline=320.0),
                _equipment("ip_waterloo", "wtl_hd_pal_a", "Heavy Duty Palletizer A", "palletizer_hd", "Ingecart", "ING_HEAVYDUTYPALLETIZER", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "High-speed palletizer benchmark from Ingecart product sheet."),
                _equipment("ip_waterloo", "wtl_hd_pal_b", "Heavy Duty Palletizer B", "palletizer_hd", "Ingecart", "ING_HEAVYDUTYPALLETIZER", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "Twin mirrors the second palletizing unit at EVOL outfeed."),
            ],
        },
        {
            "id": "cascades_piscataway",
            "name": "Cascades Piscataway",
            "country": "US",
            "region": "North America",
            "critical_assets": 6,
            "evidence_status": "partial",
            "notes": "Evidence supports an automatic robotic palletizer system with conveyors, bundle stacker, dual robots, pad paper handling and four-side squaring.",
            "equipment": [
                _equipment("cascades_piscataway", "psc_auto_pal", "Automatic Robot Palletizer System", "palletizer_hd", "Ingecart", "Integrated palletizer system", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "System-level benchmark for end-of-line robotic palletizing."),
                _equipment("cascades_piscataway", "psc_bundle_stacker", "Bundle Stacker", "transfer", "Ingecart", "Automatic bundle stacker", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-PP-PALLETIZER"], "Throughput synchronized to robotic palletizing buffer."),
                _equipment("cascades_piscataway", "psc_robot_cell_a", "Robotic Palletizing Cell A", "palletizer_hd", "KUKA / Ingecart", "Robotic palletizing unit", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "Per-robot cycle benchmark from product sheet.", throughput_baseline=13.2, throughput_ceiling=13.8),
                _equipment("cascades_piscataway", "psc_robot_cell_b", "Robotic Palletizing Cell B", "palletizer_hd", "KUKA / Ingecart", "Robotic palletizing unit", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "Per-robot cycle benchmark from product sheet.", throughput_baseline=13.2, throughput_ceiling=13.8),
                _equipment("cascades_piscataway", "psc_pad_handling", "Pad Paper Handling", "transfer", "Ingecart", "Bottom and interlayer handling", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "Interlayer and pad-paper flow monitoring."),
                _equipment("cascades_piscataway", "psc_squaring", "Four-Side Squaring Device", "transfer", "Ingecart", "Servo squaring module", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "Servo squaring quality and readiness monitoring."),
            ],
        },
        {
            "id": "cartonajes_font",
            "name": "Cartonajes Font",
            "country": "ES",
            "region": "Europe",
            "critical_assets": 6,
            "evidence_status": "partial",
            "notes": "Offer-level evidence covers palletizing, shipping transfer, automatic truck loading and SR-1400 waste logistics.",
            "equipment": [
                _equipment("cartonajes_font", "font_hd_pal", "Heavy Duty Palletizer", "palletizer_hd", "Ingecart", "ING_HEAVYDUTYPALLETIZER", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "High-output palletizing benchmark."),
                _equipment("cartonajes_font", "font_jumbo_pal", "Jumbo Heavy Duty Palletizer", "palletizer_hd", "Ingecart", "Jumbo corrugated palletizer", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-HD-PALLETIZER"], "Jumbo-format variant simulated at lower cycle density.", throughput_baseline=10.5, throughput_floor=6.5, throughput_ceiling=18.0),
                _equipment("cartonajes_font", "font_pp_pal", "Plug & Play Palletizer", "palletizer_pp", "Ingecart", "ING_PLUG&PALLETIZER", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-PP-PALLETIZER"], "Compact palletizing benchmark."),
                _equipment("cartonajes_font", "font_truck_loading", "Automatic Truck Loading", "truck_loading", "Ingecart", "ATLS", "proposal", "medium", "partial", ["SRC-CALGARY-TXT", "SRC-ATLS"], "Truck loading cycle benchmark from ATLS product note."),
                _equipment("cartonajes_font", "font_shipping_transfer", "Shipping Transfer and Conveyors", "transfer", "Ingecart", "Shipping transfer", "proposal", "medium", "partial", ["SRC-CALGARY-TXT"], "Shipping transfer and outbound conveyor synchronization."),
                _equipment("cartonajes_font", "font_sr1400", "SR-1400 Waste System", "waste_system", "Ingecart", "SR-1400", "proposal", "high", "partial", ["SRC-CALGARY-TXT", "SRC-SR1400"], "Waste evacuation twin grounded in SR-1400 product sheet."),
            ],
        },
        {
            "id": "mastercorr_covington",
            "name": "MasterCorr, LLC Covington",
            "country": "US",
            "region": "North America",
            "critical_assets": 4,
            "evidence_status": "partial",
            "notes": "Known equipment includes BHS Speedline corrugator plus Ingecart Ingetrans and RFID systems. Additional data station inferred from paired RFID architecture and flagged as hypothesis.",
            "equipment": [
                _equipment("mastercorr_covington", "cov_bhs_corr", "BHS Speedline Corrugator", "corrugator", "BHS", "Speedline", "site note", "medium", "partial", ["SRC-CALGARY-TXT"], "Twin uses corrugator sector benchmark because no validated BHS plate data is in this workspace.", throughput_baseline=240.0, throughput_ceiling=330.0),
                _equipment("mastercorr_covington", "cov_ingetrans", "Ingetrans Reel Logistics", "ingetrans", "Ingecart", "Ingetrans", "site note", "high", "partial", ["SRC-CALGARY-TXT", "SRC-INGETRANS-DT", "SRC-INGETRANS-OPS"], "Reel logistics twin grounded in Mastercorr operational analysis and benchmark."),
                _equipment("mastercorr_covington", "cov_rfid", "RFID Reel Management System", "rfid", "Ingecart", "RFID reel management", "site note", "high", "partial", ["SRC-CALGARY-TXT", "SRC-RFID"], "RFID traceability benchmark grounded in product architecture."),
                _equipment("mastercorr_covington", "cov_weigh", "Reel Weighing and Data Station", "weighing_station", "Ingecart", "RFID-ready weighing station", "hypothesis", "medium", "hypothesis", ["SRC-RFID"], "Hypothesis with highest evidence score: RFID deployment is usually paired with weighing and dimensional capture in the Ingecart architecture."),
            ],
        },
    ]
    return {
        "name": "INGECART Corrugated Smart Plant Monitoring",
        "recommended_stack": "Streamlit + Plotly + pandas + AI-ready telemetry model",
        "sites": sites,
        "plants": sites,
        "source_register": SOURCE_REGISTER,
        "general_signals": GENERAL_SIGNALS,
    }


def get_scope_label(scope: str, blueprint: Dict[str, Any] | None = None) -> str:
    if scope in (None, "", "all"):
        return "Global portfolio"
    bp = blueprint or load_monitoring_blueprint()
    for site in bp["sites"]:
        if site["id"] == scope:
            return site["name"]
    return str(scope)


def _sites_for_scope(scope: str, blueprint: Dict[str, Any]) -> List[Dict[str, Any]]:
    if scope in (None, "", "all"):
        return list(blueprint["sites"])
    return [site for site in blueprint["sites"] if site["id"] == scope]


def _asset_state(risk: float, queue_pct: float, equipment: Dict[str, Any]) -> str:
    if equipment["validation_status"] == "hypothesis":
        return "attention"
    if risk >= 68 or queue_pct >= 78:
        return "critical"
    if risk >= 46 or queue_pct >= 48:
        return "warning"
    return "running"


def _simulate_equipment_series(
    site: Dict[str, Any],
    equipment: Dict[str, Any],
    start: datetime,
    points: int,
    interval_minutes: int,
) -> List[Dict[str, Any]]:
    rng = random.Random(_stable_seed(site["id"] + equipment["id"]))
    rows: List[Dict[str, Any]] = []
    for index in range(points):
        ts = start + timedelta(minutes=index * interval_minutes)
        wave = math.sin(index / 5.0 + rng.random() * math.pi)
        drift = math.cos(index / 11.0 + rng.random())
        queue_pct = _clamp(equipment["queue_base"] + wave * 8 + drift * 4 + rng.uniform(-3, 3), 0, 100)
        temp = _clamp(equipment["temperature_base"] + wave * 2.6 + queue_pct * 0.08 + rng.uniform(-1.1, 1.1), 25, 115)
        vibration = _clamp(equipment["vibration_base"] + drift * 0.35 + rng.uniform(-0.15, 0.25), 0.1, 8.0)
        throughput = _clamp(
            equipment["throughput_baseline"] * (0.9 + wave * 0.05 - queue_pct / 900 + rng.uniform(-0.03, 0.04)),
            equipment["throughput_floor"],
            equipment["throughput_ceiling"],
        )
        performance_pct = _clamp((throughput / equipment["throughput_baseline"]) * 100, 62, 104)
        availability_pct = _clamp(94 - queue_pct * 0.08 - max(vibration - equipment["vibration_base"], 0) * 5 + rng.uniform(-1.8, 1.4), 72, 99)
        quality_pct = _clamp(equipment["quality_base"] - max(queue_pct - 50, 0) * 0.02 - max(temp - 82, 0) * 0.05 + rng.uniform(-0.4, 0.3), 93, 100)
        oee_pct = round(_clamp((availability_pct * performance_pct * quality_pct) / 10000, 40, 99), 1)
        risk = _clamp(
            18
            + max(temp - equipment["temperature_base"], 0) * 1.8
            + max(vibration - equipment["vibration_base"], 0) * 24
            + max(queue_pct - 40, 0) * 0.55
            + max(90 - oee_pct, 0) * 0.9
            + (6 if equipment["confidence"] == "low" else 0),
            4,
            96,
        )
        alarm_count = int(0 if risk < 35 else 1 if risk < 55 else 2 if risk < 75 else 3)
        battery_pct = None
        if equipment["kind"] == "amr":
            battery_pct = round(_clamp(76 + drift * 11 - (index % 10) * 1.4 + rng.uniform(-2, 2), 22, 100), 1)
            if battery_pct < 35:
                risk = _clamp(risk + 6, 0, 99)
        reel_moves_h = round(throughput if equipment["kind"] == "ingetrans" else max(0, throughput * 0.08), 2)
        rfid_reads_h = round(throughput if equipment["kind"] == "rfid" else max(0, throughput * 0.6), 2)
        lpi_pct = round(_clamp((queue_pct * 0.55) + (risk * 0.28) + alarm_count * 5, 0, 100), 1)
        downtime_minutes = round(max(0.0, (100 - availability_pct) * 0.9), 1)
        energy_kw = round(_clamp(equipment["energy_base_kw"] * (0.78 + (throughput / equipment["throughput_baseline"]) * 0.3 + rng.uniform(-0.03, 0.05)), 1, equipment["energy_base_kw"] * 1.35), 1)
        scrap_pct = round(_clamp(max(0.2, 100 - quality_pct), 0.2, 12.0), 2)
        drive_life_pct = round(_clamp(72 - index * 0.04 + rng.uniform(-3, 3) - max(vibration - equipment["vibration_base"], 0) * 5, 12, 99), 1)
        state = _asset_state(risk, queue_pct, equipment)
        rows.append(
            {
                "timestamp": ts,
                "site_id": site["id"],
                "site_name": site["name"],
                "equipment_id": equipment["id"],
                "equipment_name": equipment["name"],
                "equipment_type": equipment["type_label"],
                "throughput": round(throughput, 2),
                "throughput_unit": equipment["throughput_unit"],
                "oee_pct": oee_pct,
                "availability_pct": round(availability_pct, 1),
                "performance_pct": round(performance_pct, 1),
                "quality_pct": round(quality_pct, 1),
                "queue_pct": round(queue_pct, 1),
                "temperature_c": round(temp, 1),
                "vibration_mm_s": round(vibration, 2),
                "battery_pct": battery_pct,
                "reel_moves_h": reel_moves_h,
                "rfid_reads_h": rfid_reads_h,
                "lpi_pct": lpi_pct,
                "predicted_failure_risk_pct": round(risk, 1),
                "alarm_count": alarm_count,
                "energy_kw": energy_kw,
                "scrap_pct": scrap_pct,
                "drive_life_pct": drive_life_pct,
                "downtime_minutes": downtime_minutes,
                "state": state,
            }
        )
    return rows


def _mastercorr_dataset() -> Dict[str, Any]:
    return {
        "auto_mode_pct": 82.0,
        "manual_mode_pct": 18.0,
        "pickup_orders": 214,
        "dropoff_orders": 209,
        "avg_pickup_time_s": 46.0,
        "avg_dropoff_time_s": 52.0,
        "benchmark": "Derived from Mastercorr operational analysis and Ingetrans short-run benchmark.",
        "confidence": "medium",
    }


def _build_role_briefing(role: str, latest_df: pd.DataFrame, portfolio: Dict[str, Any]) -> Dict[str, Any]:
    panel = ROLE_PANELS[role]
    priority_assets = latest_df.sort_values(["predicted_failure_risk_pct", "cost_of_downtime_eur_h"], ascending=[False, False]).head(5)
    return {
        "headline": panel["headline"],
        "portfolio_note": f"Portfolio OEE {portfolio['oee_pct']}%, active alerts {portfolio['active_alerts']}, annual recovery EUR {portfolio['annual_recovery_potential_eur']:.0f}.",
        "decisions": panel["decisions"],
        "handover_notes": [
            "Use the maintenance tab to convert risk into scheduled actions.",
            "Use reports and offers to export evidence and trigger service requests.",
            "Review gaps before treating proposal-level data as a confirmed installed-base baseline.",
        ],
        "priority_assets": priority_assets[["site_name", "equipment_name", "state", "predicted_failure_risk_pct"]].to_dict("records"),
        "procurement": priority_assets[["equipment_name", "cost_of_downtime_eur_h", "maintenance_due_days"]].to_dict("records"),
    }


def _build_gap_analysis(selected_sites: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    known: List[Dict[str, str]] = []
    partial: List[Dict[str, str]] = []
    contradictions: List[Dict[str, str]] = []
    pending: List[Dict[str, str]] = []
    for site in selected_sites:
        known.append({"scope": site["name"], "finding": site["notes"], "confidence": site["evidence_status"]})
        for asset in site["equipment"]:
            if asset["validation_status"] in {"partial", "proposal-validated"}:
                partial.append(
                    {
                        "scope": asset["name"],
                        "finding": "Installed or proposed asset known, but exact configuration / nameplate remains incomplete.",
                        "confidence": asset["confidence"],
                    }
                )
            if asset["validation_status"] == "hypothesis":
                contradictions.append(
                    {
                        "scope": asset["name"],
                        "finding": "Displayed because it has the strongest architectural fit, but it remains a hypothesis until site records confirm it.",
                        "confidence": asset["confidence"],
                    }
                )
            if asset["confidence"] in {"low", "medium"}:
                pending.append(
                    {
                        "scope": asset["name"],
                        "finding": "Collect OEM plate data, PLC tags, maintenance history and production baselines to improve the twin.",
                        "confidence": asset["confidence"],
                    }
                )
    if not contradictions:
        contradictions.append(
            {
                "scope": "Cross-source consistency",
                "finding": "No hard contradiction detected, but multiple non-Calgary sites still rely on offer-level evidence rather than audited installed-base records.",
                "confidence": "medium",
            }
        )
    return {
        "known": known,
        "partial": partial,
        "contradictions": contradictions,
        "pending": pending,
    }


def _build_hidden_issues(latest_df: pd.DataFrame) -> List[Dict[str, Any]]:
    hidden: List[Dict[str, Any]] = []
    for _, row in latest_df.iterrows():
        if row["predicted_failure_risk_pct"] >= 46 and row["alarm_count"] <= 1:
            hidden.append(
                {
                    "site_name": row["site_name"],
                    "equipment_name": row["equipment_name"],
                    "issue": "Risk is elevated but local alarms are still low; predictive trend is ahead of operator perception.",
                    "severity": "high",
                }
            )
        if row["state"] in {"running", "warning"} and row["queue_pct"] >= 42:
            hidden.append(
                {
                    "site_name": row["site_name"],
                    "equipment_name": row["equipment_name"],
                    "issue": "Asset is still running but queue pressure suggests hidden flow loss.",
                    "severity": "medium",
                }
            )
    return hidden[:8]


def _build_recommendations(latest_df: pd.DataFrame, portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    for _, row in latest_df.sort_values("predicted_failure_risk_pct", ascending=False).head(5).iterrows():
        recs.append(
            {
                "priority": "high" if row["predicted_failure_risk_pct"] >= 70 else "medium",
                "title": f"Stabilize {row['equipment_name']}",
                "site_name": row["site_name"],
                "impact_eur": round(row["cost_of_downtime_eur_h"] * max(2, row["alarm_count"] + 1), 0),
                "reason": f"Risk {row['predicted_failure_risk_pct']}%, queue {row['queue_pct']}%, OEE {row['oee_pct']}%.",
                "recommended_action": "Inspect critical monitored signals, validate root cause, and convert to planned intervention before the next shift window.",
            }
        )
    recs.append(
        {
            "priority": "medium",
            "title": "Expand signal coverage where evidence is partial",
            "site_name": "Portfolio",
            "impact_eur": round(portfolio["annual_recovery_potential_eur"] * 0.08, 0),
            "reason": "Several assets outside Calgary still operate with proposal-level knowledge and simulated baselines.",
            "recommended_action": "Capture PLC tag lists, downtime history and OEM plate data for Waterloo, Piscataway, Font and Covington.",
        }
    )
    return recs


def _build_contracts(latest_df: pd.DataFrame) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _, row in latest_df.sort_values(["predicted_failure_risk_pct", "cost_of_downtime_eur_h"], ascending=[False, False]).head(6).iterrows():
        rows.append(
            {
                "site_name": row["site_name"],
                "equipment_name": row["equipment_name"],
                "recommended_contract": row["service_contract"],
                "coverage": "24x7" if row["cost_of_downtime_eur_h"] >= 6000 else "extended",
                "justification": f"Downtime cost EUR {row['cost_of_downtime_eur_h']:.0f}/h with risk {row['predicted_failure_risk_pct']}%.",
            }
        )
    return rows


def _build_interventions(latest_df: pd.DataFrame) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for _, row in latest_df.sort_values("predicted_failure_risk_pct", ascending=False).head(7).iterrows():
        jobs.append(
            {
                "job_id": f"WO-{_stable_seed(row['equipment_id']) % 100000:05d}",
                "site_name": row["site_name"],
                "equipment_name": row["equipment_name"],
                "type": "predictive" if row["predicted_failure_risk_pct"] >= 60 else "preventive",
                "status": "scheduled" if row["maintenance_due_days"] <= 30 else "planning",
                "priority": "critical" if row["cost_of_downtime_eur_h"] >= 6000 else "high",
                "maintenance_due_days": int(row["maintenance_due_days"]),
            }
        )
    return jobs


def _build_fault_resolution_queue(latest_df: pd.DataFrame) -> List[Dict[str, Any]]:
    queue: List[Dict[str, Any]] = []
    top_df = latest_df.sort_values(["state", "predicted_failure_risk_pct", "cost_of_downtime_eur_h"], ascending=[True, False, False]).head(12)
    for _, row in top_df.iterrows():
        if row["state"] == "critical":
            sla = "Immediate (< 30 min)"
            action = "Switch to safe mode, isolate subsystem, execute corrective checklist and remote support bridge."
        elif row["state"] == "warning":
            sla = "Priority (< 4 h)"
            action = "Validate vibration/temperature trend, inspect drives and schedule predictive intervention before shift close."
        elif row["state"] == "attention":
            sla = "Validation (< 24 h)"
            action = "Confirm hypothesis with site evidence, then decide preventive or corrective path."
        else:
            sla = "Standard (< 24 h)"
            action = "Keep observing trend and complete preventive routine."
        queue.append(
            {
                "incident_id": f"INC-{_stable_seed(row['equipment_id']) % 100000:05d}",
                "site_name": row["site_name"],
                "equipment_name": row["equipment_name"],
                "state": row["state"],
                "risk_pct": row["predicted_failure_risk_pct"],
                "alarm_count": int(row["alarm_count"]),
                "downtime_cost_eur_h": row["cost_of_downtime_eur_h"],
                "suggested_sla": sla,
                "recommended_action": action,
                "owner_role": "Maintenance Cliente" if row["state"] != "attention" else "Ingecart",
            }
        )
    return queue


def _build_report_markdown(
    scope_label: str,
    role: str,
    portfolio: Dict[str, Any],
    sites_df: pd.DataFrame,
    latest_df: pd.DataFrame,
    recommendations: Sequence[Dict[str, Any]],
    gap_analysis: Dict[str, List[Dict[str, str]]],
) -> str:
    top_assets = latest_df.sort_values("predicted_failure_risk_pct", ascending=False).head(5)
    lines = [
        f"# INGECART Smart Plant Monitoring Report",
        "",
        f"- Scope: {scope_label}",
        f"- Role: {role}",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Portfolio Summary",
        f"- OEE: {portfolio['oee_pct']}%",
        f"- Availability: {portfolio['availability_pct']}%",
        f"- Active alerts: {portfolio['active_alerts']}",
        f"- Weekly energy: {portfolio['energy_mwh_week']} MWh",
        f"- Annual recovery potential: EUR {portfolio['annual_recovery_potential_eur']:.0f}",
        "",
        "## Site Highlights",
    ]
    for _, row in sites_df.iterrows():
        lines.append(
            f"- {row['site_name']}: OEE {row['oee_pct']}%, critical assets {row['critical_assets']}, PM due {row['pm_due_assets']}, evidence {row['evidence_status']}."
        )
    lines.extend(["", "## Priority Assets"])
    for _, row in top_assets.iterrows():
        lines.append(
            f"- {row['site_name']} · {row['equipment_name']} ({row['equipment_type']}): risk {row['predicted_failure_risk_pct']}%, queue {row['queue_pct']}%, downtime cost EUR {row['cost_of_downtime_eur_h']:.0f}/h."
        )
    lines.extend(["", "## Recommended Actions"])
    for rec in recommendations[:6]:
        lines.append(f"- [{rec['priority']}] {rec['title']}: {rec['recommended_action']}")
    lines.extend(["", "## Gap Analysis"])
    lines.append("### Known")
    for item in gap_analysis["known"][:8]:
        lines.append(f"- {item['scope']}: {item['finding']}")
    lines.append("### Partially Confirmed")
    for item in gap_analysis["partial"][:8]:
        lines.append(f"- {item['scope']}: {item['finding']}")
    lines.append("### Contradictions / Hypotheses")
    for item in gap_analysis["contradictions"][:8]:
        lines.append(f"- {item['scope']}: {item['finding']}")
    lines.append("### Still Needed")
    for item in gap_analysis["pending"][:8]:
        lines.append(f"- {item['scope']}: {item['finding']}")
    return "\n".join(lines)


def _build_offer_markdown(offer: Dict[str, Any], snapshot: Dict[str, Any]) -> str:
    lines = [
        f"# {offer['reference']}",
        "",
        f"## Client Scope",
        f"- Portfolio scope: {offer['scope']}",
        f"- Request type: {offer['request_kind']}",
        f"- Generated by role: {snapshot['role']}",
        "",
        "## Executive Offer Summary",
        f"- CAPEX: EUR {offer['capex_total_eur']:.0f}",
        f"- Monthly OPEX: EUR {offer['monthly_total_eur']:.0f}",
        f"- SLA response: {offer['response_sla_hours']} h",
        f"- Confidence: {offer['confidence']:.2f}",
        "",
        "## Technical Scope",
    ]
    for row in offer["lines"]:
        lines.append(
            f"- {row['equipment_name']}: {row['line_concept']} · risk {row['risk_basis_pct']}% · downtime EUR {row['downtime_cost_eur_h']:.0f}/h · coverage {row['coverage']}."
        )
    lines.extend(
        [
            "",
            "## Economic Notes",
            "- Offer baseline is generated from monitored risk, downtime exposure and selected SLA coverage.",
            "- Final commercial issue should be validated with customer engineering interfaces and installed-base confirmation.",
            "",
            "## Ingecart Offer Notes",
            offer["notes"],
        ]
    )
    return "\n".join(lines)


def generate_monitoring_snapshot(
    site_scope: str = "all",
    role: str = "Ingecart",
    days: int = 7,
    interval_minutes: int = 30,
    blueprint: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    bp = blueprint or load_monitoring_blueprint()
    selected_sites = _sites_for_scope(site_scope, bp)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    points = max(24, int((days * 24 * 60) / interval_minutes))

    series_rows: List[Dict[str, Any]] = []
    asset_rows: List[Dict[str, Any]] = []
    for site in selected_sites:
        for equipment in site["equipment"]:
            series_rows.extend(_simulate_equipment_series(site, equipment, start, points, interval_minutes))
            asset_rows.append(
                {
                    "equipment_id": equipment["id"],
                    "site_id": site["id"],
                    "site_name": site["name"],
                    "equipment_name": equipment["name"],
                    "equipment_type": equipment["type_label"],
                    "oem": equipment["oem"],
                    "model": equipment["model"],
                    "throughput_unit": equipment["throughput_unit"],
                    "service_contract": equipment["service_contract"],
                    "evidence_level": equipment["evidence_level"],
                    "confidence": equipment["confidence"],
                    "validation_status": equipment["validation_status"],
                    "benchmark_note": equipment["benchmark_note"],
                    "source_refs": ", ".join(equipment["source_refs"]),
                    "must_signals": ", ".join(equipment["must_signals"]),
                    "optional_signals": ", ".join(equipment["optional_signals"]),
                }
            )

    series_df = pd.DataFrame(series_rows).sort_values(["equipment_id", "timestamp"])
    assets_df = pd.DataFrame(asset_rows)
    latest_df = series_df.groupby("equipment_id", as_index=False).tail(1).merge(assets_df, on=["equipment_id", "site_id", "site_name", "equipment_name", "equipment_type", "throughput_unit"], how="left")
    latest_df["maintenance_due_days"] = latest_df["drive_life_pct"].apply(lambda value: int(_clamp((value - 15) * 1.2, 3, 120)))
    latest_df["cost_of_downtime_eur_h"] = latest_df.apply(
        lambda row: round(
            1200
            + row["throughput"] * 6
            + row["predicted_failure_risk_pct"] * 20
            + (3500 if row["equipment_type"] in {"Corrugator", "Ingetrans Reel Logistics"} else 0),
            0,
        ),
        axis=1,
    )
    latest_df["fault_events"] = latest_df["alarm_count"] + latest_df["predicted_failure_risk_pct"].floordiv(28).astype(int)
    latest_df["mtbf_h"] = latest_df["predicted_failure_risk_pct"].apply(lambda value: round(_clamp(240 - value * 2.1, 22, 260), 1))
    latest_df["mttr_min"] = latest_df["predicted_failure_risk_pct"].apply(lambda value: round(_clamp(20 + value * 0.42, 18, 72), 1))

    site_summaries = []
    for site in selected_sites:
        site_df = latest_df[latest_df["site_id"] == site["id"]]
        site_summaries.append(
            {
                "site_id": site["id"],
                "site_name": site["name"],
                "country": site["country"],
                "region": site["region"],
                "critical_assets": len(site["equipment"]),
                "oee_pct": round(site_df["oee_pct"].mean(), 1),
                "availability_pct": round(site_df["availability_pct"].mean(), 1),
                "performance_pct": round(site_df["performance_pct"].mean(), 1),
                "quality_pct": round(site_df["quality_pct"].mean(), 1),
                "lpi_pct": round(site_df["lpi_pct"].mean(), 1),
                "pm_due_assets": int((site_df["maintenance_due_days"] <= 30).sum()),
                "active_alerts": int((site_df["alarm_count"] > 0).sum()),
                "annual_recovery_potential_eur": round(site_df["cost_of_downtime_eur_h"].sum() * 7.5, 0),
                "evidence_status": site["evidence_status"],
                "summary": site["notes"],
            }
        )
    sites_df = pd.DataFrame(site_summaries)

    portfolio = {
        "oee_pct": round(latest_df["oee_pct"].mean(), 1),
        "availability_pct": round(latest_df["availability_pct"].mean(), 1),
        "performance_pct": round(latest_df["performance_pct"].mean(), 1),
        "active_alerts": int((latest_df["alarm_count"] > 0).sum()),
        "energy_mwh_week": round((series_df["energy_kw"].sum() * interval_minutes / 60) / 1000, 1),
        "annual_recovery_potential_eur": round(sites_df["annual_recovery_potential_eur"].sum(), 0),
        "service_opportunity_eur": round(latest_df["cost_of_downtime_eur_h"].sum() * 2.6, 0),
    }

    recommendations = _build_recommendations(latest_df, portfolio)
    hidden_issues = _build_hidden_issues(latest_df)
    interventions = _build_interventions(latest_df)
    fault_resolution = _build_fault_resolution_queue(latest_df)
    contracts = _build_contracts(latest_df)
    gap_analysis = _build_gap_analysis(selected_sites)
    role_briefing = _build_role_briefing(role, latest_df, portfolio)

    report_markdown = _build_report_markdown(
        scope_label=get_scope_label(site_scope, bp),
        role=role,
        portfolio=portfolio,
        sites_df=sites_df,
        latest_df=latest_df,
        recommendations=recommendations,
        gap_analysis=gap_analysis,
    )

    alerts = []
    for _, row in latest_df[latest_df["alarm_count"] > 0].sort_values("predicted_failure_risk_pct", ascending=False).head(10).iterrows():
        alerts.append(
            {
                "site_name": row["site_name"],
                "equipment_name": row["equipment_name"],
                "severity": "critical" if row["state"] == "critical" else "warning",
                "message": f"{row['equipment_name']} risk {row['predicted_failure_risk_pct']}%, queue {row['queue_pct']}%, temp {row['temperature_c']}C.",
                "timestamp": row["timestamp"].isoformat(),
            }
        )

    return {
        "scope": site_scope,
        "scope_label": get_scope_label(site_scope, bp),
        "role": role,
        "blueprint": bp,
        "portfolio": portfolio,
        "site_summaries": sites_df.to_dict("records"),
        "equipment_latest": latest_df.to_dict("records"),
        "series": [
            {**row, "timestamp": row["timestamp"].isoformat()}
            for row in series_df.to_dict("records")
        ],
        "alerts": alerts,
        "interventions": interventions,
        "fault_resolution": fault_resolution,
        "contracts": contracts,
        "recommendations": recommendations,
        "hidden_issues": hidden_issues,
        "role_briefing": role_briefing,
        "role_module_access": ROLE_MODULE_ACCESS.get(role, ROLE_MODULE_ACCESS["Ingecart"]),
        "raci_matrix": raci_matrix_rows(),
        "module_catalog": MODULE_CATALOG,
        "report_markdown": report_markdown,
        "formula_library": FORMULA_LIBRARY,
        "gap_analysis": gap_analysis,
        "mastercorr_dataset": _mastercorr_dataset(),
        "simulation_assumptions": {
            "days": days,
            "interval_minutes": interval_minutes,
            "timestamp_basis": "UTC",
            "benchmark_logic": "Evidence-weighted digital twin with deterministic simulated telemetry by equipment family.",
        },
    }


def suggest_spare_parts(search_text: str, top_k: int = 8) -> List[Dict[str, Any]]:
    tokens = {token.strip(" ,.;:-").lower() for token in search_text.split() if token.strip()}
    scored: List[tuple[int, Dict[str, Any]]] = []
    for item in SPARE_PART_CATALOG:
        haystack = " ".join(
            [
                item["family_group"],
                item["oem_code"],
                item["technical_description"],
                " ".join(alt["technical_description"] for alt in item["compatible_alternatives"]),
            ]
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score or not tokens:
            scored.append((score, item))
    scored.sort(key=lambda row: (row[0], -row[1]["lead_time_days"]), reverse=True)
    return [item for _, item in scored[:top_k]]


def generate_instant_offer(
    snapshot: Dict[str, Any],
    request_kind: str,
    target_equipment_id: str,
    coverage: str,
    urgency: str,
) -> Dict[str, Any]:
    latest_df = pd.DataFrame(snapshot["equipment_latest"])
    target_rows = latest_df if target_equipment_id == "all" else latest_df[latest_df["equipment_id"] == target_equipment_id]
    if target_rows.empty:
        target_rows = latest_df.head(1)
    scope_name = snapshot["scope_label"]
    urgency_multiplier = {"standard": 1.0, "priority": 1.18, "emergency": 1.42}[urgency]
    coverage_multiplier = {"business_hours": 1.0, "extended": 1.22, "24x7": 1.45}[coverage]
    base_capex = float(target_rows["cost_of_downtime_eur_h"].sum() * 2.1 * urgency_multiplier)
    monthly = float(target_rows["cost_of_downtime_eur_h"].mean() * 0.12 * coverage_multiplier)
    request_labels = {
        "maintenance_contract": "Lifecycle maintenance contract",
        "materials_and_spares": "Spares and materials package",
        "intervention": "Targeted intervention package",
        "improvement_upgrade": "Performance improvement upgrade",
    }
    lines = []
    for _, row in target_rows.iterrows():
        lines.append(
            {
                "equipment_name": row["equipment_name"],
                "line_concept": request_labels[request_kind],
                "risk_basis_pct": row["predicted_failure_risk_pct"],
                "downtime_cost_eur_h": row["cost_of_downtime_eur_h"],
                "coverage": coverage,
            }
        )
    reference = f"ING-{snapshot['scope']}-{request_kind}-{int(base_capex) % 100000:05d}"
    offer = {
        "reference": reference.upper(),
        "scope": scope_name,
        "request_kind": request_kind,
        "capex_total_eur": round(base_capex, 0),
        "monthly_total_eur": round(monthly, 0),
        "response_sla_hours": {"standard": 24, "priority": 12, "emergency": 4}[urgency],
        "confidence": 0.84 if snapshot["scope"] == "cascades_calgary" else 0.71,
        "lines": lines,
        "notes": (
            "Offer generated from simulated downtime exposure, risk, equipment family benchmark and selected SLA. "
            "Non-Calgary sites still require tag list, maintenance history and exact installed-base validation for a final commercial proposal."
        ),
    }
    offer["offer_markdown"] = _build_offer_markdown(offer, snapshot)
    return offer


def build_request_alert(
    request_kind: str,
    requester_name: str,
    requester_role: str,
    plant_id: str,
    plant_name: str,
    coverage: str,
    urgency: str,
    equipment_name: str,
    details: str,
) -> Dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request_type": request_kind,
        "requester_name": requester_name or "Pending name",
        "requester_role": requester_role,
        "plant_id": plant_id,
        "plant_name": plant_name,
        "coverage": coverage,
        "urgency": urgency,
        "equipment_name": equipment_name,
        "details": details,
    }


def raci_matrix_rows() -> List[Dict[str, str]]:
    return [{"module": module, **roles} for module, roles in RACI_BY_MODULE.items()]


def serialize_snapshot(snapshot: Dict[str, Any]) -> str:
    return json.dumps(snapshot, ensure_ascii=False, indent=2)


__all__ = [
    "FORMULA_LIBRARY",
    "ROLE_PANELS",
    "SOURCE_REGISTER",
    "SPARE_PART_CATALOG",
    "build_request_alert",
    "generate_instant_offer",
    "generate_monitoring_snapshot",
    "get_scope_label",
    "load_monitoring_blueprint",
    "serialize_snapshot",
    "suggest_spare_parts",
]
