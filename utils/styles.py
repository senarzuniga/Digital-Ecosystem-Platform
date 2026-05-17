"""
Shared CSS/theme styles for the Digital Ecosystem Platform.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INGECART Brand Identity: Industrial Intelligence
Color Palette (70% Black/Dark + 20% Grey + 10% Orange):
  • Black Industrial Premium: #05070B
  • Naranja Técnico INGECART: #FF6A00
  • Blanco Técnico: #F4F5F7
  • Gris Metal: #7E848E
  • Gris Acero Oscuro: #1A1D24
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Color Palette (INGECART Brand) ────────────────────────────────────────
INGECART_COLORS = {
    "BLACK_PRIMARY": "#05070B",      # Industrial base
    "ORANGE_PRIMARY": "#FF6A00",     # Technical accent
    "WHITE_PRIMARY": "#F4F5F7",      # Clean, technical white
    "GREY_METAL": "#7E848E",         # Secondary text
    "GREY_DARK": "#1A1D24",          # Dark backgrounds
    "GREY_LIGHT": "#2B2E35",         # Lighter dark surfaces
}

PLATFORM_CSS = """
<style>
/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* INGECART Dark Industrial Premium Theme                                  */
/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

/* ── Global ───────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #05070B;
    color: #F4F5F7;
}

/* Main content background */
.main { background: #05070B; }

/* ── Sidebar (Dark Industrial) ─────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1A1D24 0%, #0F1115 100%);
    border-right: 2px solid #FF6A00;
}
section[data-testid="stSidebar"] * {
    color: #F4F5F7 !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label {
    color: #7E848E !important;
}

/* ── Metric cards (Dark + Orange accents) ────────────────────────────── */
div[data-testid="metric-container"] {
    background: #1A1D24;
    border: 1px solid #FF6A00;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 0 20px rgba(255, 106, 0, 0.1);
}
div[data-testid="metric-container"] label {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #7E848E !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #FF6A00 !important;
    font-family: 'Montserrat', sans-serif;
}

/* ── Page title (Industrial Technical) ───────────────────────────────── */
.dep-page-title {
    font-size: 32px;
    font-weight: 700;
    color: #FF6A00;
    margin-bottom: 4px;
    font-family: 'Montserrat', sans-serif;
    letter-spacing: -0.5px;
}
.dep-page-subtitle {
    font-size: 14px;
    color: #7E848E;
    margin-bottom: 24px;
    font-weight: 400;
}

/* ── Section header (Technical lines) ──────────────────────────────────── */
.dep-section-header {
    font-size: 16px;
    font-weight: 600;
    color: #F4F5F7;
    border-left: 3px solid #FF6A00;
    border-bottom: 1px solid #FF6A0033;
    padding-left: 12px;
    padding-bottom: 8px;
    margin: 28px 0 16px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Company badge (Orange technical) ──────────────────────────────────── */
.company-badge {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 0px;
    border-left: 3px solid #FF6A00;
    background: #1A1D24;
    font-size: 13px;
    font-weight: 600;
    color: #FF6A00;
    margin-bottom: 8px;
}

/* ── Status chips (Technical industrial) ────────────────────────────────── */
.chip-ok     { 
    background: #2B5A1A; 
    color: #90EE90; 
    border-radius: 0px;
    border-left: 2px solid #90EE90;
    padding: 4px 10px; 
    font-size: 12px; 
    font-weight: 600;
}
.chip-warn   { 
    background: #5A4A2B; 
    color: #FFB84D;
    border-radius: 0px;
    border-left: 2px solid #FFB84D;
    padding: 4px 10px; 
    font-size: 12px; 
    font-weight: 600;
}
.chip-error  { 
    background: #5A2B2B; 
    color: #FF6B6B;
    border-radius: 0px;
    border-left: 2px solid #FF6B6B;
    padding: 4px 10px; 
    font-size: 12px; 
    font-weight: 600;
}
.chip-info   { 
    background: #2B4A5A; 
    color: #FF6A00;
    border-radius: 0px;
    border-left: 2px solid #FF6A00;
    padding: 4px 10px; 
    font-size: 12px; 
    font-weight: 600;
}

/* ── Alert boxes (Dark theme with functional colors) ───────────────────── */
.dep-alert-warning {
    background: #5A4A2B;
    border-left: 4px solid #FFB84D;
    border-radius: 0px;
    padding: 12px 16px;
    font-size: 14px;
    color: #FFB84D;
    margin: 8px 0;
}
.dep-alert-success {
    background: #2B5A1A;
    border-left: 4px solid #90EE90;
    border-radius: 0px;
    padding: 12px 16px;
    font-size: 14px;
    color: #90EE90;
    margin: 8px 0;
}
.dep-alert-info {
    background: #2B4A5A;
    border-left: 4px solid #FF6A00;
    border-radius: 0px;
    padding: 12px 16px;
    font-size: 14px;
    color: #FF6A00;
    margin: 8px 0;
}

/* ── Agent card (Dark industrial card) ──────────────────────────────────── */
.agent-card {
    background: #1A1D24;
    border: 1px solid #FF6A0044;
    border-left: 3px solid #FF6A00;
    border-radius: 2px;
    padding: 16px;
    margin-bottom: 12px;
    box-shadow: 0 0 15px rgba(255, 106, 0, 0.05);
}
.agent-card-title {
    font-size: 15px;
    font-weight: 600;
    color: #FF6A00;
    font-family: 'Montserrat', sans-serif;
}
.agent-card-role {
    font-size: 12px;
    color: #7E848E;
    margin-top: 4px;
}

/* ── Maturity level pills (Industrial dark) ────────────────────────────── */
.maturity-l1 { background: #1A1D24; color: #7E848E; border-left: 3px solid #FF6A00; }
.maturity-l2 { background: #1A1D24; color: #FF6A00; border-left: 3px solid #FF6A00; }
.maturity-l3 { background: #1A1D24; color: #90EE90; border-left: 3px solid #90EE90; }
.maturity-l4 { background: #1A1D24; color: #FFB84D; border-left: 3px solid #FFB84D; }
.maturity-l5 { background: #1A1D24; color: #FF6A00; border-left: 3px solid #FF6A00; }
.maturity-pill {
    display: inline-block;
    border-radius: 0px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Divider (Technical line) ──────────────────────────────────────────── */
.dep-divider {
    border: none;
    border-top: 1px solid #FF6A0044;
    margin: 24px 0;
}

/* ── Technical Blueprint Lines ─────────────────────────────────────────── */
.blueprint-border {
    border: 1px dashed #FF6A0055;
    border-radius: 2px;
}

/* ── Orange Glow Effect (Subtle) ───────────────────────────────────────── */
.glow-orange {
    box-shadow: 0 0 20px rgba(255, 106, 0, 0.15);
}

/* ── Data elements (Tables, forms) ─────────────────────────────────────── */
[data-testid="stTable"] {
    background: #1A1D24 !important;
}
[data-testid="stTable"] tbody tr {
    border-bottom: 1px solid #FF6A0033 !important;
}
[data-testid="stTable"] thead tr {
    border-bottom: 2px solid #FF6A00 !important;
}

/* ── Inputs & Forms ────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div > select {
    background-color: #2B2E35 !important;
    color: #F4F5F7 !important;
    border: 1px solid #FF6A0055 !important;
}

/* ── Buttons ───────────────────────────────────────────────────────────── */
.stButton > button {
    background-color: #FF6A00 !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 2px !important;
}
.stButton > button:hover {
    background-color: #E85A00 !important;
    box-shadow: 0 0 15px rgba(255, 106, 0, 0.3) !important;
}

</style>
"""

MATURITY_LEVELS = {
    1: {"label": "L1 – Monitoring",        "color": "#FF6A00", "bg": "#1A1D24"},
    2: {"label": "L2 – Analytics",         "color": "#FF6A00", "bg": "#1A1D24"},
    3: {"label": "L3 – Predictive",        "color": "#90EE90", "bg": "#1A1D24"},
    4: {"label": "L4 – Semi-Autonomous",   "color": "#FFB84D", "bg": "#1A1D24"},
    5: {"label": "L5 – Fully Autonomous",  "color": "#FF6A00", "bg": "#1A1D24"},
}


def render_company_header(company: dict) -> str:
    """Return HTML for the active-company header strip (INGECART Dark Industrial Theme)."""
    name  = company.get("name", "—")
    sector = company.get("sector", "")
    country = company.get("country", "")
    lvl = company.get("maturity_level", 1)
    mat = MATURITY_LEVELS.get(lvl, MATURITY_LEVELS[1])
    
    return f"""
    <div style="background: linear-gradient(90deg, #1A1D24 0%, #0F1115 100%);
                border: 1px solid #FF6A0055;
                border-left: 3px solid #FF6A00;
                border-radius: 2px;
                padding: 14px 18px;
                margin-bottom: 24px;
                display: flex;
                align-items: center;
                gap: 18px;
                box-shadow: 0 0 20px rgba(255, 106, 0, 0.1);">
      <div style="width: 48px;
                  height: 48px;
                  border-radius: 0px;
                  background: #FF6A00;
                  display: flex;
                  align-items: center;
                  justify-content: center;
                  font-size: 20px;
                  font-weight: 700;
                  color: white;
                  border: 2px solid #05070B;">
        {name[0]}
      </div>
      <div>
        <div style="font-size: 18px;
                    font-weight: 700;
                    color: #FF6A00;
                    font-family: 'Montserrat', sans-serif;
                    letter-spacing: -0.5px;">
          {name}
        </div>
        <div style="font-size: 13px;
                    color: #7E848E;
                    margin-top: 2px;
                    font-weight: 400;">
          {sector} • {country}
        </div>
      </div>
      <div style="margin-left: auto;">
        <span class="maturity-pill" style="background: {mat['bg']};
                                           color: {mat['color']};
                                           border-left: 3px solid {mat['color']};">
          {mat['label']}
        </span>
      </div>
    </div>
    """
