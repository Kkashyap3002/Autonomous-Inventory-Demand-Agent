"""
AIDA Design System — Colors, Typography & Custom CSS
=====================================================
Single source of truth for the UI's visual language.
Import COLORS and inject_css() in every page for consistency.
"""

import streamlit as st

# ── COLOR PALETTE ──────────────────────────────────────────────────────────
# Inspired by modern SaaS dashboards (Vercel, Linear, Stripe)

COLORS = {
    # Surfaces
    "bg":              "#0f1117",  # deep charcoal (dark mode default)
    "bg_card":         "#1a1d27",  # card background
    "bg_sidebar":      "#0a0c12",  # sidebar
    "bg_input":        "#242736",  # input fields
    "bg_hover":        "#2a2d3a",  # hover state

    # Text
    "text_primary":    "#eef0f6",
    "text_secondary":  "#8b8fa8",
    "text_muted":      "#5c6078",

    # Accents
    "primary":         "#6366f1",  # indigo-500
    "primary_light":   "#818cf8",  # indigo-400
    "primary_dark":    "#4f46e5",  # indigo-600
    "secondary":       "#22d3ee",  # cyan-400
    "success":         "#22c55e",  # green-500
    "warning":         "#f59e0b",  # amber-500
    "danger":          "#ef4444",  # red-500
    "info":            "#3b82f6",  # blue-500

    # Borders
    "border":          "#2e3140",
    "border_light":    "#3a3d50",

    # Semantic
    "stock_ok":        "#22c55e",
    "stock_low":       "#f59e0b",
    "stock_critical":  "#ef4444",
    "stock_out":       "#6b21a8",

    # Chart palette
    "chart_colors":    ["#6366f1", "#22d3ee", "#22c55e", "#f59e0b",
                        "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6",
                        "#f97316", "#84cc16"],
}

# ── TYPOGRAPHY ─────────────────────────────────────────────────────────────

FONTS = {
    "display":   "'Inter', 'Segoe UI', sans-serif",
    "body":      "'Inter', 'Segoe UI', sans-serif",
    "mono":      "'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace",
}

# ── CSS INJECTION ──────────────────────────────────────────────────────────

def inject_css():
    """Inject global custom CSS. Call once at the top of every page."""
    css = f"""
    <style>
    /* ── Google Fonts ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ── Global Resets ── */
    .stApp {{
        background-color: {COLORS['bg']};
        color: {COLORS['text_primary']};
        font-family: {FONTS['body']};
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background-color: {COLORS['bg_sidebar']};
        border-right: 1px solid {COLORS['border']};
    }}
    [data-testid="stSidebar"] .stMarkdown {{
        color: {COLORS['text_secondary']};
    }}

    /* ── Cards ── */
    .aida-card {{
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .aida-card:hover {{
        border-color: {COLORS['border_light']};
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
    }}
    .aida-card.accent-primary {{
        border-left: 4px solid {COLORS['primary']};
    }}
    .aida-card.accent-success {{
        border-left: 4px solid {COLORS['success']};
    }}
    .aida-card.accent-warning {{
        border-left: 4px solid {COLORS['warning']};
    }}
    .aida-card.accent-danger {{
        border-left: 4px solid {COLORS['danger']};
    }}

    /* ── KPI Value ── */
    .aida-kpi-value {{
        font-size: 2rem;
        font-weight: 700;
        color: {COLORS['text_primary']};
        line-height: 1.2;
    }}
    .aida-kpi-label {{
        font-size: 0.8rem;
        font-weight: 500;
        color: {COLORS['text_muted']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .aida-kpi-delta-positive {{
        color: {COLORS['success']};
        font-size: 0.85rem;
        font-weight: 600;
    }}
    .aida-kpi-delta-negative {{
        color: {COLORS['danger']};
        font-size: 0.85rem;
        font-weight: 600;
    }}

    /* ── Stat Row ── */
    .aida-stat-row {{
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 24px;
    }}
    .aida-stat-box {{
        flex: 1;
        min-width: 160px;
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        border-radius: 10px;
        padding: 16px 20px;
    }}

    /* ── Chat Messages ── */
    .aida-chat-msg {{
        padding: 16px 20px;
        border-radius: 12px;
        margin: 8px 0;
        max-width: 85%;
    }}
    .aida-chat-user {{
        background: linear-gradient(135deg, {COLORS['primary_dark']}, {COLORS['primary']});
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 4px;
    }}
    .aida-chat-agent {{
        background: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        margin-right: auto;
        border-bottom-left-radius: 4px;
    }}

    /* ── Tool Badge ── */
    .aida-tool-badge {{
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 2px 10px;
        border-radius: 20px;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    .aida-tool-badge.sql {{
        background: rgba(99,102,241,0.15);
        color: {COLORS['primary_light']};
    }}
    .aida-tool-badge.rag {{
        background: rgba(34,211,238,0.15);
        color: {COLORS['secondary']};
    }}
    .aida-tool-badge.forecast {{
        background: rgba(245,158,11,0.15);
        color: {COLORS['warning']};
    }}

    /* ── Status Badges ── */
    .aida-status {{
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 3px 12px;
        border-radius: 50px;
    }}
    .aida-status.healthy {{
        background: rgba(34,197,94,0.12);
        color: {COLORS['stock_ok']};
    }}
    .aida-status.low {{
        background: rgba(245,158,11,0.12);
        color: {COLORS['stock_low']};
    }}
    .aida-status.critical {{
        background: rgba(239,68,68,0.12);
        color: {COLORS['stock_critical']};
    }}
    .aida-status.out {{
        background: rgba(107,33,168,0.12);
        color: {COLORS['stock_out']};
    }}

    /* ── Headers ── */
    .aida-page-title {{
        font-size: 1.6rem;
        font-weight: 700;
        color: {COLORS['text_primary']};
        margin-bottom: 4px;
    }}
    .aida-page-subtitle {{
        font-size: 0.9rem;
        color: {COLORS['text_secondary']};
        margin-bottom: 24px;
    }}
    .aida-section-title {{
        font-size: 1.05rem;
        font-weight: 600;
        color: {COLORS['text_primary']};
        margin: 20px 0 12px 0;
    }}

    /* ── DataFrames ── */
    [data-testid="stDataFrame"] {{
        border: 1px solid {COLORS['border']} !important;
        border-radius: 8px !important;
        overflow: hidden;
    }}
    [data-testid="stDataFrame"] thead th {{
        background: {COLORS['bg_input']} !important;
        color: {COLORS['text_secondary']} !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }}

    /* ── Metric tweaks ── */
    [data-testid="stMetricValue"] {{
        font-weight: 700 !important;
        color: {COLORS['text_primary']} !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-weight: 600 !important;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        background: {COLORS['bg_input']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }}
    .stButton > button:hover {{
        background: {COLORS['bg_hover']};
        border-color: {COLORS['primary']};
        color: {COLORS['primary_light']};
    }}

    /* ── Chat input ── */
    [data-testid="stChatInput"] textarea {{
        background: {COLORS['bg_input']} !important;
        border: 1px solid {COLORS['border']} !important;
        color: {COLORS['text_primary']} !important;
        border-radius: 12px !important;
    }}

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {{
        width: 6px;
    }}
    ::-webkit-scrollbar-track {{
        background: {COLORS['bg']};
    }}
    ::-webkit-scrollbar-thumb {{
        background: {COLORS['border']};
        border-radius: 3px;
    }}

    /* ── Animations ── */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .aida-card, .aida-stat-box {{
        animation: fadeIn 0.3s ease-out;
    }}

    /* ── Logo / Brand ── */
    .aida-logo {{
        font-size: 1.3rem;
        font-weight: 800;
        background: linear-gradient(135deg, {COLORS['primary_light']}, {COLORS['secondary']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)
