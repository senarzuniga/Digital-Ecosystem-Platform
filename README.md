# 🏭 Digital Ecosystem Platform

AI-powered IIoT platform for machine manufacturers — built with Streamlit.

## Overview

The **Digital Ecosystem Platform** is a multi-company Streamlit application that gives machine manufacturers a single workspace to monitor their installed base, deploy AI agents, assess maturity, and drive after-sales growth.

It implements the full blueprint for the *best possible Digital Ecosystem*, incorporating current IIoT platform capabilities and next-generation AI-agent-enabled capabilities.

---

## Features

| Module | Description |
|--------|-------------|
| 🏠 **Platform Overview** | Company selector, fleet KPIs, live alert strip |
| 📊 **Company Dashboard** | OEE distribution, fleet status, health scatter, alerts |
| 🔌 **Machine Connectivity** | Real-time IIoT status, sensor streams (temp/vibration/power), architecture layers |
| 🪞 **Digital Twins** | Twin status board, divergence tracking, recalibration alerts |
| 🤖 **AI Agent Center** | 7 specialized agents (Operational, Optimization, Maintenance, Commercial, Engineering, Management/CEO, Customer Success), active/locked by maturity, agent action log |
| 📈 **Maturity Model** | L1–L5 assessment, radar chart, dimension scores, progression roadmap, market positioning |
| 🗺️ **Ecosystem Blueprint** | Full 8-pillar best-practice blueprint with "Without it" impact statements |
| 💰 **After-Sales Engine** | Upsell opportunities, service orders, installed base, growth strategy with lifecycle monetisation |

---

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Ensure that you have all the necessary dependencies installed, including `asyncio-mqtt`, which is required for certain asynchronous operations within the platform.

---

## Architecture

```
app.py                          ← Main entry + company selector
pages/
  01_Dashboard.py               ← Company KPIs & alerts
  02_Machine_Connectivity.py    ← IIoT status & sensor streams
  03_Digital_Twins.py           ← Twin board & divergence
  04_AI_Agents.py               ← Agent center & action log
  05_Maturity_Model.py          ← L1–L5 assessment & roadmap
  06_Ecosystem_Blueprint.py     ← Full blueprint (8 pillars)
  07_After_Sales_Engine.py      ← Growth engine & upsell
utils/
  styles.py                     ← CSS theme & shared components
  data_generator.py             ← Mock IIoT / company data
  agent_taxonomy.py             ← AI agent definitions
config/
  companies.json                ← Sample company data (5 companies)
```

---

## AI Agent Taxonomy

| Agent | Role | Maturity Min |
|-------|------|-------------|
| ⚙️ Operational | Anomaly detection & corrective actions | L2 |
| 📈 Optimization | Energy, material & throughput optimization | L3 |
| 🔧 Maintenance | Failure prediction, scheduling & parts | L3 |
| 💼 Commercial | Upsell, cross-sell & contract intelligence | L2 |
| 🛠️ Engineering | Field-to-design feedback loop | L3 |
| 🏛️ Management/CEO | Strategic synthesis & investment intel | L4 |
| 🤝 Customer Success | Conversational advisory | L3 |

---

## Maturity Model (L1–L5)

| Level | Label | Description |
|-------|-------|-------------|
| L1 | Monitoring | Basic connectivity, KPI dashboards |
| L2 | Analytics | Root-cause analytics, benchmarking |
| L3 | Predictive | ML failure prediction, recommended actions |
| L4 | Semi-Autonomous | Agents execute pre-approved actions |
| L5 | Fully Autonomous | Self-managing AI ecosystem |
