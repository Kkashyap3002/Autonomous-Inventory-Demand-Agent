"""
AIDA Dashboard — Executive Overview
=====================================
KPI cards, revenue trends, category breakdown, inventory health, top products.
"""

import sys
from pathlib import Path
import streamlit as st
import sqlite3

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

from phase6_ui.style import COLORS, inject_css
from phase6_ui.components.charts import (
    chart_revenue_trend, chart_category_breakdown,
    chart_inventory_health, chart_top_products,
)

DB = BASE / "phase2_sql" / "aida.db"

st.set_page_config(page_title="AIDA — Dashboard", page_icon="📊", layout="wide")
inject_css()

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown('<p class="aida-logo">AIDA</p>', unsafe_allow_html=True)
st.markdown('<p class="aida-page-subtitle">Executive Overview · Real-time inventory intelligence</p>',
            unsafe_allow_html=True)

# ── KPI Row ─────────────────────────────────────────────────────────────────
conn = sqlite3.connect(str(DB))
cur = conn.execute("""
    SELECT COUNT(*), ROUND(SUM(order_total), 0)
    FROM orders WHERE order_status = 'delivered'
      AND ordered_at >= DATE('now', '-30 days')
""")
orders_30d, rev_30d = cur.fetchone()

cur = conn.execute("""
    SELECT ROUND(AVG(order_total), 0) FROM orders
    WHERE order_status = 'delivered' AND ordered_at >= DATE('now', '-30 days')
""")
aov = cur.fetchone()[0] or 0

cur = conn.execute("""
    SELECT COUNT(*) FROM inventory_status WHERE stock_status IN ('STOCKOUT', 'LOW')
""")
low_stock = cur.fetchone()[0]

cur = conn.execute("""
    SELECT ROUND(SUM(forecasted_units), 0) FROM forecast_results
    WHERE forecast_date BETWEEN DATE('now') AND DATE('now', '+7 days')
""")
fcst_7d = cur.fetchone()[0] or 0

cur = conn.execute("""
    SELECT COUNT(*) FROM inventory_status WHERE stock_status = 'STOCKOUT'
""")
stockouts = cur.fetchone()[0]

cur = conn.execute("""
    SELECT COUNT(*) FROM products
""")
products = cur.fetchone()[0]

cur = conn.execute("""
    SELECT ROUND(SUM(oi.line_total - p.unit_cost * oi.quantity) / SUM(oi.line_total) * 100, 1)
    FROM order_items oi JOIN products p ON oi.product_id = p.product_id
    JOIN orders o ON oi.order_id = o.order_id WHERE o.order_status = 'delivered'
""")
margin_pct = cur.fetchone()[0] or 0

cur = conn.execute("""
    SELECT ROUND(SUM(forecasted_units), 0) FROM forecast_results
    WHERE forecast_date BETWEEN DATE('now') AND DATE('now', '+30 days')
""")
fcst_30d = cur.fetchone()[0] or 0
conn.close()

# Row 1
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
for col, value, label, delta, accent in [
    (kpi1, f"₹{rev_30d:,.0f}", "REVENUE (30D)", None, "primary"),
    (kpi2, f"{orders_30d:,}", "ORDERS (30D)", None, "primary"),
    (kpi3, f"₹{aov:,}", "AVG ORDER VALUE", None, "primary"),
    (kpi4, f"{margin_pct}%", "GROSS MARGIN", None, "success"),
    (kpi5, f"{products}", "PRODUCTS", None, "primary"),
]:
    with col:
        st.markdown(
            f'<div class="aida-stat-box">'
            f'<div class="aida-kpi-label">{label}</div>'
            f'<div class="aida-kpi-value">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# Row 2
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
for col, value, label, accent in [
    (kpi1, f"{fcst_7d:,}", "7-DAY FORECAST (UNITS)", "warning"),
    (kpi2, f"{fcst_30d:,}", "30-DAY FORECAST (UNITS)", "warning"),
    (kpi3, low_stock, "LOW STOCK ITEMS", "warning" if low_stock > 0 else "success"),
    (kpi4, stockouts, "STOCKOUTS", "danger" if stockouts > 0 else "success"),
    (kpi5, "3", "ACTIVE STORES", "primary"),
]:
    with col:
        st.markdown(
            f'<div class="aida-stat-box">'
            f'<div class="aida-kpi-label">{label}</div>'
            f'<div class="aida-kpi-value">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── Charts Row 1 ────────────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2])
with col_left:
    st.plotly_chart(chart_revenue_trend(30), use_container_width=True, config={"displayModeBar": False})
with col_right:
    st.plotly_chart(chart_category_breakdown(), use_container_width=True, config={"displayModeBar": False})

# ── Charts Row 2 ────────────────────────────────────────────────────────────
col_left, col_right = st.columns([3, 2])
with col_left:
    st.plotly_chart(chart_top_products(10), use_container_width=True, config={"displayModeBar": False})
with col_right:
    st.plotly_chart(chart_inventory_health(), use_container_width=True, config={"displayModeBar": False})
