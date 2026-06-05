"""
Shared CSS/theme styles for the Digital Ecosystem Platform.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ING_DIGHUB Brand Identity: Industrial Intelligence Platform
Color Palette (ING_DIGHUB Design System):
  • Negro Tecnológico:   #080F14  – primary background
  • Azul Industrial IA: #0B3BFF  – IA / analytics / highlights
  • Naranja INGECART:   #FF6A00  – CTAs / key elements / hover
  • Gris Acero:         #1A212B  – cards / secondary backgrounds
  • Blanco Técnico:     #EDEFF2  – primary text / contrast
  • Verde Status:       #22C55E  – online / connected / live
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ── Color Palette (ING_DIGHUB Design System) ─────────────────────────────
INGECART_COLORS = {
    "BLACK_PRIMARY":  "#080F14",     # Negro tecnológico – main bg
    "BLUE_IA":        "#0B3BFF",     # Azul Industrial IA
    "ORANGE_PRIMARY": "#FF6A00",     # Naranja INGECART – CTAs
    "WHITE_PRIMARY":  "#EDEFF2",     # Blanco técnico – primary text
    "GREY_STEEL":     "#1A212B",     # Gris acero – cards / surfaces
    "GREY_META":      "#8898AA",     # Secondary / muted text
    "GREEN_STATUS":   "#22C55E",     # Live / online / operational
}

PLATFORM_CSS = """
<style>
/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
/* ING_DIGHUB – Industrial Intelligence Platform  v2.0                    */
/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

/* ── Fonts ────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global Reset ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #080F14;
    color: #EDEFF2;
}

/* ── Main content area with subtle grid ──────────────────────────────── */
.main {
    background: #080F14;
    background-image:
        linear-gradient(rgba(11, 59, 255, 0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(11, 59, 255, 0.025) 1px, transparent 1px);
    background-size: 48px 48px;
}
.block-container { padding-top: 1.5rem !important; }

/* ── Sidebar ──────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1520 0%, #080F14 100%);
    border-right: 1px solid rgba(255, 106, 0, 0.25);
}
section[data-testid="stSidebar"] * { color: #EDEFF2 !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] label { color: #8898AA !important; }

/* ── Metric cards ─────────────────────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: rgba(15, 22, 35, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    padding: 18px;
    backdrop-filter: blur(12px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="metric-container"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(255, 106, 0, 0.18);
}
div[data-testid="metric-container"] label {
    font-size: 10px !important;
    font-weight: 700 !important;
    color: #8898AA !important;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 700 !important;
    color: #FF6A00 !important;
    font-family: 'Poppins', sans-serif;
}

/* ── Page title ───────────────────────────────────────────────────────── */
.dep-page-title {
    font-family: 'Poppins', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: #EDEFF2;
    margin-bottom: 4px;
    letter-spacing: -0.5px;
}
.dep-page-subtitle {
    font-size: 14px;
    color: #8898AA;
    margin-bottom: 24px;
    font-weight: 400;
}

/* ── Section header ───────────────────────────────────────────────────── */
.dep-section-header {
    font-family: 'Poppins', sans-serif;
    font-size: 11px;
    font-weight: 700;
    color: #8898AA;
    border-left: 3px solid #FF6A00;
    border-bottom: 1px solid #FF6A0033;
    padding-left: 12px;
    padding-bottom: 8px;
    margin: 28px 0 16px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Company badge ────────────────────────────────────────────────────── */
.company-badge {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 8px;
    border-left: 3px solid #FF6A00;
    background: rgba(15, 22, 35, 0.9);
    font-size: 13px;
    font-weight: 600;
    color: #FF6A00;
    margin-bottom: 8px;
}

/* ── Status chips ─────────────────────────────────────────────────────── */
.chip-ok {
    background: rgba(34, 197, 94, 0.12);
    color: #22C55E;
    border-radius: 8px;
    border: 1px solid rgba(34, 197, 94, 0.25);
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
.chip-warn {
    background: rgba(255, 184, 77, 0.12);
    color: #FFB84D;
    border-radius: 8px;
    border: 1px solid rgba(255, 184, 77, 0.25);
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
.chip-error {
    background: rgba(255, 107, 107, 0.12);
    color: #FF6B6B;
    border-radius: 8px;
    border: 1px solid rgba(255, 107, 107, 0.25);
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
.chip-info {
    background: rgba(11, 59, 255, 0.12);
    color: #4D7CFF;
    border-radius: 8px;
    border: 1px solid rgba(11, 59, 255, 0.25);
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* ── Alert boxes ──────────────────────────────────────────────────────── */
.dep-alert-warning {
    background: rgba(255, 184, 77, 0.08);
    border-left: 4px solid #FFB84D;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 14px;
    color: #FFB84D;
    margin: 8px 0;
}
.dep-alert-success {
    background: rgba(34, 197, 94, 0.08);
    border-left: 4px solid #22C55E;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 14px;
    color: #22C55E;
    margin: 8px 0;
}
.dep-alert-info {
    background: rgba(11, 59, 255, 0.08);
    border-left: 4px solid #4D7CFF;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 14px;
    color: #4D7CFF;
    margin: 8px 0;
}

/* ── Glassmorphism card ───────────────────────────────────────────────── */
.glass-card {
    background: rgba(15, 22, 35, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.07);
    backdrop-filter: blur(12px);
    border-radius: 20px;
    padding: 24px;
    transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
}
.glass-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(255, 106, 0, 0.18);
    border-color: rgba(255, 106, 0, 0.2);
}

/* ── Agent card ───────────────────────────────────────────────────────── */
.agent-card {
    background: rgba(15, 22, 35, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-left: 3px solid #FF6A00;
    border-radius: 16px;
    padding: 18px;
    margin-bottom: 12px;
    backdrop-filter: blur(12px);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.agent-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(255, 106, 0, 0.15);
}
.agent-card-title {
    font-size: 15px;
    font-weight: 600;
    color: #FF6A00;
    font-family: 'Poppins', sans-serif;
}
.agent-card-role {
    font-size: 12px;
    color: #8898AA;
    margin-top: 4px;
}

/* ── Maturity pills ───────────────────────────────────────────────────── */
.maturity-l1 { background: rgba(26,33,43,0.9); color: #8898AA;  border-left: 3px solid #8898AA; }
.maturity-l2 { background: rgba(26,33,43,0.9); color: #FF6A00;  border-left: 3px solid #FF6A00; }
.maturity-l3 { background: rgba(26,33,43,0.9); color: #22C55E;  border-left: 3px solid #22C55E; }
.maturity-l4 { background: rgba(26,33,43,0.9); color: #FFB84D;  border-left: 3px solid #FFB84D; }
.maturity-l5 { background: rgba(26,33,43,0.9); color: #4D7CFF;  border-left: 3px solid #4D7CFF; }
.maturity-pill {
    display: inline-block;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

/* ── Status live indicator ────────────────────────────────────────────── */
.status-live {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 700;
    color: #22C55E;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

/* ── Divider ──────────────────────────────────────────────────────────── */
.dep-divider {
    border: none;
    border-top: 1px solid rgba(255, 106, 0, 0.12);
    margin: 28px 0;
}

/* ── Blueprint border ─────────────────────────────────────────────────── */
.blueprint-border {
    border: 1px dashed rgba(255, 106, 0, 0.25);
    border-radius: 16px;
}

/* ── Glow utilities ───────────────────────────────────────────────────── */
.glow-orange { box-shadow: 0 0 30px rgba(255, 106, 0, 0.2); }
.glow-blue   { box-shadow: 0 0 30px rgba(11, 59, 255, 0.2); }

/* ── Fade-in animation ────────────────────────────────────────────────── */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
}
.fade-in-up { animation: fadeInUp 0.5s ease forwards; }

/* ── Live pulse ───────────────────────────────────────────────────────── */
@keyframes pulse-green {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.35; }
}

/* ── Data tables ──────────────────────────────────────────────────────── */
[data-testid="stTable"] {
    background: rgba(15, 22, 35, 0.85) !important;
    border-radius: 12px !important;
}
[data-testid="stTable"] tbody tr {
    border-bottom: 1px solid rgba(255, 106, 0, 0.08) !important;
}
[data-testid="stTable"] thead tr {
    border-bottom: 2px solid #FF6A00 !important;
}

/* ── Inputs ───────────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div > select {
    background-color: rgba(15, 22, 35, 0.9) !important;
    color: #EDEFF2 !important;
    border: 1px solid rgba(255, 106, 0, 0.25) !important;
    border-radius: 10px !important;
}

/* ── Streamlit buttons ────────────────────────────────────────────────── */
.stButton > button {
    background: #FF6A00 !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    padding: 10px 24px !important;
    font-family: 'Inter', sans-serif !important;
    letter-spacing: 0.5px !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 0 25px rgba(255, 106, 0, 0.35) !important;
    background: #E85A00 !important;
}

</style>
"""

MATURITY_LEVELS = {
    1: {"label": "L1 – Monitoring",        "color": "#8898AA", "bg": "rgba(26,33,43,0.9)"},
    2: {"label": "L2 – Analytics",         "color": "#FF6A00", "bg": "rgba(26,33,43,0.9)"},
    3: {"label": "L3 – Predictive",        "color": "#22C55E", "bg": "rgba(26,33,43,0.9)"},
    4: {"label": "L4 – Semi-Autonomous",   "color": "#FFB84D", "bg": "rgba(26,33,43,0.9)"},
    5: {"label": "L5 – Fully Autonomous",  "color": "#4D7CFF", "bg": "rgba(26,33,43,0.9)"},
}


def render_company_header(company: dict) -> str:
    """Return HTML for the active-company header strip (ING_DIGHUB design system)."""
    name    = company.get("name", "—")
    sector  = company.get("sector", "")
    country = company.get("country", "")
    lvl     = company.get("maturity_level", 1)
    mat     = MATURITY_LEVELS.get(lvl, MATURITY_LEVELS[1])

    return f"""
    <div style="
        background: linear-gradient(135deg, rgba(15,22,35,0.95) 0%, rgba(8,15,20,0.95) 100%);
        border: 1px solid rgba(255,255,255,0.07);
        border-left: 3px solid #FF6A00;
        border-radius: 16px;
        padding: 16px 20px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 16px;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);">
      <div style="
          width: 44px; height: 44px;
          border-radius: 12px;
          background: linear-gradient(135deg, #FF6A00, #E85A00);
          display: flex; align-items: center; justify-content: center;
          font-size: 18px; font-weight: 800;
          color: white;
          font-family: 'Poppins', sans-serif;
          flex-shrink: 0;">
        {name[0]}
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="
            font-size: 16px; font-weight: 700;
            color: #EDEFF2;
            font-family: 'Poppins', sans-serif;
            letter-spacing: -0.3px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
          {name}
        </div>
        <div style="font-size: 12px; color: #8898AA; margin-top: 2px; font-weight: 400;">
          {sector} &nbsp;·&nbsp; {country}
        </div>
      </div>
      <div style="flex-shrink: 0;">
        <span class="maturity-pill" style="
            background: {mat['bg']};
            color: {mat['color']};
            border-left: 3px solid {mat['color']};">
          {mat['label']}
        </span>
      </div>
    </div>
    """
