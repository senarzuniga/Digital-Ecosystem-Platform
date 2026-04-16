"""Shared CSS/theme styles for the Digital Ecosystem Platform."""

PLATFORM_CSS = """
<style>
/* ── Global ───────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Sidebar ──────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1B2A 0%, #1B2B40 100%);
    border-right: 1px solid #263C55;
}
section[data-testid="stSidebar"] * {
    color: #E0E8F0 !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stMarkdown p {
    color: #A8BDD0 !important;
}

/* ── Metric cards ─────────────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: #F7F9FC;
    border: 1px solid #E2EAF3;
    border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
div[data-testid="metric-container"] label {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #6B7C93 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #1A2E44 !important;
}

/* ── Page title ───────────────────────────────────────────────── */
.dep-page-title {
    font-size: 28px;
    font-weight: 700;
    color: #1A2E44;
    margin-bottom: 4px;
}
.dep-page-subtitle {
    font-size: 14px;
    color: #6B7C93;
    margin-bottom: 24px;
}

/* ── Section header ───────────────────────────────────────────── */
.dep-section-header {
    font-size: 16px;
    font-weight: 600;
    color: #1A2E44;
    border-left: 4px solid #1565C0;
    padding-left: 10px;
    margin: 20px 0 12px;
}

/* ── Company badge ────────────────────────────────────────────── */
.company-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    color: white;
    margin-bottom: 8px;
}

/* ── Status chips ─────────────────────────────────────────────── */
.chip-ok     { background:#E8F5E9; color:#2E7D32; border-radius:12px; padding:3px 10px; font-size:12px; font-weight:600; }
.chip-warn   { background:#FFF8E1; color:#F57F17; border-radius:12px; padding:3px 10px; font-size:12px; font-weight:600; }
.chip-error  { background:#FFEBEE; color:#C62828; border-radius:12px; padding:3px 10px; font-size:12px; font-weight:600; }
.chip-info   { background:#E3F2FD; color:#1565C0; border-radius:12px; padding:3px 10px; font-size:12px; font-weight:600; }

/* ── Alert boxes ──────────────────────────────────────────────── */
.dep-alert-warning {
    background: #FFF8E1;
    border-left: 4px solid #FFC107;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 14px;
    color: #5D4037;
    margin: 8px 0;
}
.dep-alert-success {
    background: #E8F5E9;
    border-left: 4px solid #43A047;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 14px;
    color: #1B5E20;
    margin: 8px 0;
}
.dep-alert-info {
    background: #E3F2FD;
    border-left: 4px solid #1E88E5;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 14px;
    color: #0D47A1;
    margin: 8px 0;
}

/* ── Agent card ───────────────────────────────────────────────── */
.agent-card {
    background: white;
    border: 1px solid #E2EAF3;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.agent-card-title {
    font-size: 15px;
    font-weight: 600;
    color: #1A2E44;
}
.agent-card-role {
    font-size: 12px;
    color: #6B7C93;
    margin-top: 2px;
}

/* ── Maturity level pills ─────────────────────────────────────── */
.maturity-l1 { background:#EDE7F6; color:#4527A0; }
.maturity-l2 { background:#E3F2FD; color:#1565C0; }
.maturity-l3 { background:#E8F5E9; color:#2E7D32; }
.maturity-l4 { background:#FFF8E1; color:#E65100; }
.maturity-l5 { background:#FCE4EC; color:#880E4F; }
.maturity-pill {
    display: inline-block;
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 700;
}

/* ── Divider ──────────────────────────────────────────────────── */
.dep-divider {
    border: none;
    border-top: 1px solid #E2EAF3;
    margin: 20px 0;
}
</style>
"""

MATURITY_LEVELS = {
    1: {"label": "L1 – Monitoring",        "color": "#4527A0", "bg": "#EDE7F6"},
    2: {"label": "L2 – Analytics",         "color": "#1565C0", "bg": "#E3F2FD"},
    3: {"label": "L3 – Predictive",        "color": "#2E7D32", "bg": "#E8F5E9"},
    4: {"label": "L4 – Semi-Autonomous",   "color": "#E65100", "bg": "#FFF8E1"},
    5: {"label": "L5 – Fully Autonomous",  "color": "#880E4F", "bg": "#FCE4EC"},
}


def render_company_header(company: dict) -> str:
    """Return HTML for the active-company header strip."""
    color = company.get("logo_color", "#1565C0")
    name  = company.get("name", "—")
    sector = company.get("sector", "")
    country = company.get("country", "")
    lvl = company.get("maturity_level", 1)
    mat = MATURITY_LEVELS.get(lvl, MATURITY_LEVELS[1])
    return f"""
    <div style="background:{color}12; border:1px solid {color}44;
                border-radius:10px; padding:12px 18px; margin-bottom:20px;
                display:flex; align-items:center; gap:16px;">
      <div style="width:42px;height:42px;border-radius:50%;background:{color};
                  display:flex;align-items:center;justify-content:center;
                  font-size:18px;font-weight:700;color:white;">
        {name[0]}
      </div>
      <div>
        <div style="font-size:17px;font-weight:700;color:#1A2E44;">{name}</div>
        <div style="font-size:13px;color:#6B7C93;">{sector} · {country}</div>
      </div>
      <div style="margin-left:auto;">
        <span class="maturity-pill" style="background:{mat['bg']};color:{mat['color']};">
          {mat['label']}
        </span>
      </div>
    </div>
    """
