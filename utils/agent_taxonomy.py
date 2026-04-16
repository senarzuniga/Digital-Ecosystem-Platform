"""AI Agent taxonomy definitions aligned with the Digital Ecosystem Platform blueprint."""

AGENTS = [
    {
        "id": "operational",
        "name": "Operational Agent",
        "icon": "⚙️",
        "color": "#1565C0",
        "role": "Real-time anomaly detection & corrective action",
        "description": (
            "Continuously monitors machine telemetry streams, detects anomalies "
            "using ML models, proposes corrective actions, and — with appropriate "
            "permissions — executes them directly on PLC/MES level."
        ),
        "capabilities": [
            "Real-time anomaly detection on sensor streams",
            "Root-cause classification (thermal, mechanical, electrical)",
            "Corrective action proposals with confidence scores",
            "Autonomous execution trigger (PLC/MES integration)",
            "Shift-level OEE reporting and bottleneck identification",
        ],
        "kpis": ["Anomalies detected / week", "MTTR reduction (%)", "OEE delta"],
        "maturity_min": 2,
    },
    {
        "id": "optimization",
        "name": "Optimization Agent",
        "icon": "📈",
        "color": "#2E7D32",
        "role": "Energy, material & throughput optimization",
        "description": (
            "Runs continuous scenario simulations to optimize energy consumption, "
            "material usage, and production throughput. Surfaces trade-off analyses "
            "and, in autonomous mode, adjusts process parameters within safe bounds."
        ),
        "capabilities": [
            "Multi-objective process parameter optimization",
            "Energy consumption reduction modelling",
            "Scenario simulation (what-if analysis)",
            "Material waste reduction recommendations",
            "Throughput / cycle-time improvement proposals",
        ],
        "kpis": ["Energy savings (kWh/month)", "Throughput improvement (%)", "Scrap rate reduction (%)"],
        "maturity_min": 3,
    },
    {
        "id": "maintenance",
        "name": "Maintenance Agent",
        "icon": "🔧",
        "color": "#6A1B9A",
        "role": "Failure prediction, scheduling & spare-parts orchestration",
        "description": (
            "Predicts component failures before they occur, schedules preventive "
            "interventions at optimal production windows, and automatically triggers "
            "spare-part ordering — including sending alerts like: "
            "\"You will need this part in 3 weeks\"."
        ),
        "capabilities": [
            "Remaining useful life (RUL) estimation per component",
            "Intervention scheduling at minimal production impact",
            "Automated spare-part purchase order creation",
            "Technician skill-matching and work-order dispatch",
            "Post-repair learning loop for model refinement",
        ],
        "kpis": ["Unplanned downtime reduction (%)", "Maintenance cost savings ($)", "Parts ordering lead-time (days)"],
        "maturity_min": 3,
    },
    {
        "id": "commercial",
        "name": "Commercial Agent",
        "icon": "💼",
        "color": "#E65100",
        "role": "Upsell, cross-sell & contract intelligence",
        "description": (
            "Analyses usage patterns, contract timelines, and machine lifecycle data "
            "to surface revenue opportunities. Generates personalised upgrade proposals "
            "and detects 'when upgrades are needed' across the installed base."
        ),
        "capabilities": [
            "Usage-based upsell opportunity detection",
            "Contract renewal forecasting and risk scoring",
            "Personalised commercial offer generation",
            "Installed base segmentation for campaign targeting",
            "Revenue impact simulation per offer",
        ],
        "kpis": ["Upsell conversion rate (%)", "Revenue influenced ($)", "Contract renewal rate (%)"],
        "maturity_min": 2,
    },
    {
        "id": "engineering",
        "name": "Engineering Agent",
        "icon": "🛠️",
        "color": "#00695C",
        "role": "Field-to-design feedback loop",
        "description": (
            "Aggregates field performance data across the installed base and feeds "
            "anonymised insights back into product engineering — closing the loop "
            "between deployed machines and next-generation design."
        ),
        "capabilities": [
            "Cross-fleet performance benchmarking",
            "Failure-mode clustering and design implication mapping",
            "Anonymised customer usage pattern aggregation",
            "Design improvement hypothesis generation",
            "NPI (new product introduction) field-readiness assessment",
        ],
        "kpis": ["Design improvements triggered / quarter", "Warranty claim reduction (%)", "MTBF improvement (%)"],
        "maturity_min": 3,
    },
    {
        "id": "management",
        "name": "Management / CEO Agent",
        "icon": "🏛️",
        "color": "#283593",
        "role": "Strategic synthesis, risk & investment intelligence",
        "description": (
            "Synthesises operational, commercial, and engineering signals into "
            "executive-level insights: portfolio risk, investment recommendations, "
            "strategic readiness scores, and ecosystem maturity benchmarking."
        ),
        "capabilities": [
            "Cross-company portfolio health dashboard",
            "Strategic risk identification and impact ranking",
            "Investment ROI simulation for digital initiatives",
            "Competitive maturity benchmarking (L1–L5 positioning)",
            "Executive narrative generation (board-ready summaries)",
        ],
        "kpis": ["Strategic initiatives accelerated", "Portfolio risk score", "Digital ROI attributed ($)"],
        "maturity_min": 4,
    },
    {
        "id": "customer_success",
        "name": "Customer Success Agent",
        "icon": "🤝",
        "color": "#AD1457",
        "role": "Conversational advisory for plant performance",
        "description": (
            "Acts as the primary conversational interface for customers, answering "
            "questions about their machines, guiding improvement actions, and providing "
            "explainable recommendations in plain language."
        ),
        "capabilities": [
            "Natural-language Q&A on machine and plant performance",
            "Explainable AI — reasoning transparency per recommendation",
            "Guided improvement workflow (next-best-action prompts)",
            "Escalation routing to human experts when needed",
            "Customer satisfaction signal collection and analysis",
        ],
        "kpis": ["Customer satisfaction score (CSAT)", "Self-service resolution rate (%)", "Time-to-insight (minutes)"],
        "maturity_min": 3,
    },
]

AGENT_INDEX = {a["id"]: a for a in AGENTS}


def get_active_agents(maturity_level: int) -> list:
    """Return agents available at the given maturity level."""
    return [a for a in AGENTS if a["maturity_min"] <= maturity_level]


def get_locked_agents(maturity_level: int) -> list:
    """Return agents not yet available at the given maturity level."""
    return [a for a in AGENTS if a["maturity_min"] > maturity_level]
