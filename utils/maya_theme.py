"""Maya brand colors (from assets/Maya Brand Guide_v1.pdf) for in-app styling."""

# Primary
MINT_GREEN = "#2ff29e"
MONEY_GREEN = "#00b464"
ELECTRIC_PURPLE = "#4929aa"
ONLINE_WINE = "#1f155f"

# Secondary (alerts / accents)
MANGO_YELLOW = "#f2bb3d"
PEACH = "#f16c59"
STRAWBERRY_RED = "#db2754"
SEAFOAM = "#69d8c5"
FRESH_BLUE = "#3098e1"
OCEAN_BLUE = "#294cda"
DEEP_BLUE = "#294294"
ICE_BLUE = "#b2edff"

GRADIENT_MINT_PURPLE = f"linear-gradient(135deg, {MINT_GREEN} 0%, {ELECTRIC_PURPLE} 100%)"
GRADIENT_MINT_MONEY = f"linear-gradient(135deg, {MINT_GREEN} 0%, {MONEY_GREEN} 100%)"
GRADIENT_AMBER = f"linear-gradient(135deg, {MANGO_YELLOW} 0%, {PEACH} 100%)"
GRADIENT_RED = f"linear-gradient(135deg, {PEACH} 0%, {STRAWBERRY_RED} 100%)"
GRADIENT_BLUE = f"linear-gradient(135deg, {ICE_BLUE} 0%, {OCEAN_BLUE} 100%)"
GRADIENT_RECOVERY = f"linear-gradient(135deg, {SEAFOAM} 0%, {MONEY_GREEN} 100%)"


def dashboard_styles() -> str:
    return f"""
    <style>
    .maya-dash-section {{
        background: {GRADIENT_MINT_PURPLE};
        color: {ONLINE_WINE};
        padding: 0.85rem 1.1rem;
        border-radius: 12px;
        margin: 0.5rem 0 1rem 0;
        font-weight: 600;
        font-size: 1.05rem;
        letter-spacing: 0.02em;
    }}
    .maya-metric-card {{
        border-radius: 12px;
        padding: 0.75rem 1rem;
        min-height: 5.5rem;
        box-shadow: 0 2px 8px rgba(31, 21, 95, 0.08);
    }}
    .maya-metric-card .label {{
        font-size: 0.78rem;
        font-weight: 600;
        line-height: 1.25;
        opacity: 0.95;
        margin-bottom: 0.35rem;
    }}
    .maya-metric-card .value {{
        font-size: 1.75rem;
        font-weight: 700;
        line-height: 1.1;
    }}
    .maya-rag-card {{
        border-radius: 12px;
        padding: 0.85rem 1rem;
        text-align: center;
        color: {ONLINE_WINE};
        font-weight: 600;
    }}
    .maya-rag-card .n {{ font-size: 1.85rem; font-weight: 700; }}
    </style>
    """


def metric_card_html(label: str, value: int | str, gradient: str, text_color: str = ONLINE_WINE) -> str:
    return f"""
    <div class="maya-metric-card" style="background: {gradient}; color: {text_color};">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
    </div>
    """
