"""Mock data generator for IIoT machine and company telemetry."""

import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


# ── Reproducible seed per company ─────────────────────────────────────────────
def _seed(company_id: str) -> int:
    return abs(hash(company_id)) % (2**31)


# ── Machine list ───────────────────────────────────────────────────────────────
MACHINE_TYPES = [
    "CNC Machining Center", "Hydraulic Press", "Robotic Arm",
    "Conveyor System", "Injection Mold", "Laser Cutter",
    "Assembly Station", "Welding Robot", "Packaging Line", "Paint Booth",
]

STATUS_OPTIONS = ["Online", "Online", "Online", "Warning", "Offline"]


def generate_machines(company: dict) -> pd.DataFrame:
    rng = random.Random(_seed(company["id"]))
    n = company["machines"]
    rows = []
    for i in range(1, n + 1):
        mtype = rng.choice(MACHINE_TYPES)
        status = rng.choice(STATUS_OPTIONS)
        oee = round(rng.uniform(55, 96), 1)
        age = round(rng.uniform(0.5, company["installed_base_age_avg_years"] * 1.8), 1)
        temp = round(rng.uniform(52, 88), 1)
        vibration = round(rng.uniform(0.3, 4.2), 2)
        health_score = max(10, min(100, int(oee + rng.uniform(-10, 10))))
        next_pm = rng.randint(2, 180)
        rows.append({
            "Machine ID": f"MCH-{company['id'].upper()[:3]}-{i:04d}",
            "Type": mtype,
            "Status": status,
            "OEE (%)": oee,
            "Age (years)": age,
            "Temp (°C)": temp,
            "Vibration (mm/s)": vibration,
            "Health Score": health_score,
            "Next PM (days)": next_pm,
            "Connected": rng.choices([True, False], weights=[90, 10])[0],
        })
    return pd.DataFrame(rows)


# ── Time-series telemetry ──────────────────────────────────────────────────────
def generate_telemetry(machine_id: str, hours: int = 24) -> pd.DataFrame:
    rng = np.random.default_rng(_seed(machine_id) % (2**31))
    now = datetime.utcnow()
    timestamps = [now - timedelta(minutes=15 * i) for i in range(hours * 4)]
    timestamps.reverse()
    base_temp = 65 + rng.random() * 15
    base_vib  = 1.5 + rng.random() * 1.5
    temps = base_temp + rng.normal(0, 1.5, len(timestamps)).cumsum() * 0.05
    temps = np.clip(temps, 40, 100)
    vibs  = base_vib  + rng.normal(0, 0.2, len(timestamps))
    vibs  = np.clip(vibs, 0.1, 6.0)
    power = 20 + rng.uniform(0, 30) + rng.normal(0, 2, len(timestamps))
    power = np.clip(power, 5, 80)
    return pd.DataFrame({
        "Timestamp": timestamps,
        "Temperature (°C)": temps.round(2),
        "Vibration (mm/s)": vibs.round(3),
        "Power (kW)": power.round(2),
    })


# ── Alerts ────────────────────────────────────────────────────────────────────
ALERT_TEMPLATES = [
    ("High vibration detected on spindle bearing",     "Warning",  "Maintenance"),
    ("Temperature threshold exceeded — coolant check", "Critical", "Operational"),
    ("OEE drop below 60% — throughput impact",         "Warning",  "Optimization"),
    ("Predictive wear pattern — bearing replacement",  "Info",     "Maintenance"),
    ("Upsell trigger: upgrade eligibility reached",    "Info",     "Commercial"),
    ("Power consumption anomaly — 18% above baseline", "Warning",  "Operational"),
    ("Spare part low stock: SKU-4821 (3 units left)",  "Warning",  "Maintenance"),
    ("Contract renewal due in 30 days",                "Info",     "Commercial"),
    ("Digital twin divergence > 5% — recalibrate",    "Warning",  "Engineering"),
    ("Energy optimization opportunity: -12% possible", "Info",     "Optimization"),
]


def generate_alerts(company: dict, n: int = 8) -> pd.DataFrame:
    rng = random.Random(_seed(company["id"] + "_alerts"))
    rows = []
    for i in range(n):
        tmpl = rng.choice(ALERT_TEMPLATES)
        mid = f"MCH-{company['id'].upper()[:3]}-{rng.randint(1, company['machines']):04d}"
        ago = rng.randint(1, 720)
        ts  = datetime.utcnow() - timedelta(minutes=ago)
        rows.append({
            "Timestamp": ts.strftime("%Y-%m-%d %H:%M"),
            "Machine": mid,
            "Description": tmpl[0],
            "Severity": tmpl[1],
            "Agent": tmpl[2],
        })
    rows.sort(key=lambda r: r["Timestamp"], reverse=True)
    return pd.DataFrame(rows)


# ── After-sales data ──────────────────────────────────────────────────────────
def generate_service_orders(company: dict, n: int = 20) -> pd.DataFrame:
    rng = random.Random(_seed(company["id"] + "_svc"))
    types  = ["Reactive Repair", "Preventive Maintenance", "Predictive Intervention",
              "Upgrade Installation", "Remote Diagnostic", "Inspection"]
    statuses = ["Completed", "Completed", "In Progress", "Scheduled", "Pending"]
    rows = []
    for i in range(n):
        stype   = rng.choice(types)
        status  = rng.choice(statuses)
        revenue = round(rng.uniform(800, 18000), 2)
        mid = f"MCH-{company['id'].upper()[:3]}-{rng.randint(1, company['machines']):04d}"
        ago_days = rng.randint(0, 180)
        rows.append({
            "Order ID":   f"SO-{rng.randint(10000, 99999)}",
            "Machine":    mid,
            "Type":       stype,
            "Status":     status,
            "Revenue ($)": revenue,
            "Days Ago":   ago_days,
        })
    return pd.DataFrame(rows)


def generate_upsell_opportunities(company: dict) -> pd.DataFrame:
    rng = random.Random(_seed(company["id"] + "_upsell"))
    offers = [
        ("Predictive Maintenance Add-on",   "Software",  "when upgrades are needed", "High"),
        ("Remote Monitoring Premium",        "Service",   "You will need this part in 3 weeks", "High"),
        ("Digital Twin Expansion Pack",      "Software",  "when upgrades are needed", "Medium"),
        ("AI Optimization Module",           "Software",  "when upgrades are needed", "High"),
        ("Extended Warranty +3Y",            "Contract",  "Contract expiry in 45 days",  "Medium"),
        ("Spare Parts Bundle — Bearings",    "Parts",     "You will need this part in 3 weeks", "High"),
        ("Performance-Based SLA Upgrade",    "Contract",  "when upgrades are needed", "Medium"),
        ("Energy Efficiency Retrofit Kit",   "Hardware",  "when upgrades are needed", "Low"),
    ]
    rows = []
    for offer in rng.sample(offers, min(5, len(offers))):
        mid = f"MCH-{company['id'].upper()[:3]}-{rng.randint(1, company['machines']):04d}"
        value = round(rng.uniform(3000, 75000), 0)
        rows.append({
            "Machine":     mid,
            "Offer":       offer[0],
            "Category":    offer[1],
            "Trigger":     offer[2],
            "Priority":    offer[3],
            "Est. Value ($)": value,
        })
    return pd.DataFrame(rows)


# ── Maturity model scores ─────────────────────────────────────────────────────
MATURITY_DIMENSIONS = [
    "Connectivity",
    "Data Management",
    "Analytics",
    "AI / Automation",
    "Commercial Integration",
    "Customer Experience",
]


def generate_maturity_scores(company: dict) -> dict:
    lvl = company["maturity_level"]
    rng = random.Random(_seed(company["id"] + "_maturity"))
    base = lvl * 18
    scores = {}
    for dim in MATURITY_DIMENSIONS:
        scores[dim] = min(100, max(5, base + rng.randint(-12, 12)))
    return scores
