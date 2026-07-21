"""
AIDA Forecast Studio — Demand Projections
===========================================
Interactive forecast explorer with charts, risk analysis, and filtering.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import sqlite3

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

from phase6_ui.style import COLORS, inject_css
from phase6_ui.components.charts import chart_forecast_sparkline
from phase6_ui.components.db import safe_dataframe

DB = BASE / "phase2_sql" / "aida.db"

st.set_page_config(page_title="AIDA — Forecasts", page_icon="📈", layout="wide")
inject_css()

st.markdown('<p class="aida-logo">AIDA</p>', unsafe_allow_html=True)
st.markdown('<p class="aida-page-subtitle">Forecast Studio · 30-day demand projections with risk intelligence</p>',
            unsafe_allow_html=True)

# ── Filters ─────────────────────────────────────────────────────────────────
f1, f2, f3, f4 = st.columns(4)
with f1:
    store = st.selectbox("Store", ["All", "DS-BEN-01", "DS-MUM-02", "DS-DEL-03"], key="fcst_store")
with f2:
    cats_df = safe_dataframe("SELECT DISTINCT category FROM products ORDER BY category")
    cats = cats_df["category"].tolist() if not cats_df.empty else []
    cat = st.selectbox("Category", ["All"] + cats, key="fcst_cat")
with f3:
    horizon = st.selectbox("Horizon", [7, 14, 30], index=0, key="fcst_horizon")
with f4:
    risk_only = st.checkbox("Show only at-risk items", value=False, key="fcst_risk")

# ── Build Query ─────────────────────────────────────────────────────────────
where = ["1=1"]
params = {"max_date": f"{(pd.Timestamp.now() + pd.Timedelta(days=horizon)).strftime('%Y-%m-%d')}",
          "days": horizon}
if store != "All":
    where.append("fr.store_code = :store")
    params["store"] = store
if cat != "All":
    where.append("fr.category = :cat")
    params["cat"] = cat
if risk_only:
    where.append("""EXISTS (
        SELECT 1 FROM inventory_status ist
        WHERE ist.product_id = fr.product_id AND ist.store_id = fr.store_id
          AND ist.qty_available < (SELECT SUM(forecasted_units) FROM forecast_results fr2
               WHERE fr2.product_id = fr.product_id AND fr2.store_id = fr.store_id
                 AND fr2.forecast_date <= :max_date)
    )""")

forecast_sql = f"""
    SELECT fr.sku, fr.product_name, fr.category, fr.store_code,
           fr.forecast_date, fr.forecasted_units,
           ist.qty_available AS current_stock,
           ist.stock_status,
           CASE WHEN ist.qty_available < (
               SELECT SUM(fr2.forecasted_units) FROM forecast_results fr2
               WHERE fr2.product_id = fr.product_id AND fr2.store_id = fr.store_id
                 AND fr2.forecast_date <= :max_date
           ) THEN 'LIKELY_STOCKOUT'
           WHEN ist.qty_available <= ist.reorder_point THEN 'LOW'
           ELSE 'OK' END AS risk_flag
    FROM forecast_results fr
    LEFT JOIN inventory_status ist
        ON fr.product_id = ist.product_id AND fr.store_id = ist.store_id
    WHERE {' AND '.join(where)}
      AND fr.forecast_date <= :max_date
    ORDER BY fr.forecast_date, fr.forecasted_units DESC
"""
df = safe_dataframe(forecast_sql, params)

# ── KPI Row ─────────────────────────────────────────────────────────────────
if df.empty:
    st.info("No forecast data available. Click 'Generate Data' in the sidebar first.")
    st.stop()

agg = df.groupby("forecast_date")["forecasted_units"].sum()
total_demand = agg.sum()
peak_day = agg.max()
peak_date = agg.idxmax() if not agg.empty else "-"

items = df[["sku", "store_code"]].drop_duplicates()
at_risk = sum(1 for _, row in df.groupby(["sku", "store_code"]).agg(
    total=("forecasted_units", "sum"),
    stock=("current_stock", "first")
).iterrows() if row["total"] > row["stock"])

k1, k2, k3, k4, k5 = st.columns(5)
for col, v, l in [
    (k1, f"{total_demand:,.0f}", f"{horizon}-DAY TOTAL DEMAND"),
    (k2, f"{len(items)}", "PRODUCT-STORES"),
    (k3, f"{peak_day:,.0f}", f"PEAK DAY ({peak_date})"),
    (k4, f"{at_risk}", "AT RISK"),
    (k5, f"{df['forecasted_units'].mean():.1f}", "AVG DAILY/ITEM"),
]:
    with col:
        st.markdown(
            f'<div class="aida-stat-box">'
            f'<div class="aida-kpi-label">{l}</div>'
            f'<div class="aida-kpi-value">{v}</div></div>',
            unsafe_allow_html=True,
        )

st.markdown("---")

# ── Aggregate Chart ─────────────────────────────────────────────────────────
st.markdown('<p class="aida-section-title">Aggregate Demand Forecast</p>', unsafe_allow_html=True)
agg_df = df.groupby("forecast_date")["forecasted_units"].sum().reset_index()
agg_df["forecast_date"] = pd.to_datetime(agg_df["forecast_date"])

import plotly.graph_objects as go
from phase6_ui.components.charts import LAYOUT_DARK

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=agg_df["forecast_date"], y=agg_df["forecasted_units"],
    mode="lines+markers", name="Total Demand",
    line={"color": "#6366f1", "width": 2.5},
    marker={"size": 6, "color": "#6366f1"},
    fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
    hovertemplate="%{x|%b %d}<br>%{y:,.0f} units<extra></extra>",
))
fig.update_layout(
    **LAYOUT_DARK,
    title=f"Aggregate Daily Demand — Next {horizon} Days",
    height=340,
    xaxis_title=None, yaxis_title="Units",
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── Item-Level Table ────────────────────────────────────────────────────────
st.markdown('<p class="aida-section-title">Item-Level Forecast</p>', unsafe_allow_html=True)

summary = df.groupby(["sku", "product_name", "category", "store_code", "current_stock"]) \
    .agg(total_forecasted=("forecasted_units", "sum"),
         avg_daily=("forecasted_units", "mean"),
         peak=("forecasted_units", "max"),
         risk_flag=("risk_flag", "first")) \
    .reset_index() \
    .sort_values("total_forecasted", ascending=False)

# Style
def color_risk(row):
    flag = row.get("risk_flag", "OK")
    if flag == "LIKELY_STOCKOUT":
        return ["background: rgba(239,68,68,0.08)"] * len(row)
    elif flag == "LOW":
        return ["background: rgba(245,158,11,0.06)"] * len(row)
    return [""] * len(row)

styled = summary.style \
    .apply(color_risk, axis=1) \
    .format({"total_forecasted": "{:.1f}", "avg_daily": "{:.1f}", "peak": "{:.1f}"})

st.dataframe(styled, use_container_width=True, height=500, hide_index=True)

if at_risk > 0:
    st.warning(f"**{at_risk} items** are projected to stock out within {horizon} days. "
               "Review replenishment orders for these SKUs immediately.")

# ── Sparkline for Selected Product ──────────────────────────────────────────
with st.expander("🔍 Product Detail View", expanded=False):
    if not df.empty:
        products = df[["product_name", "sku"]].drop_duplicates()
        selected = st.selectbox(
            "Select a product to view its forecast chart",
            products.apply(lambda r: f"{r['sku']} — {r['product_name']}", axis=1).tolist(),
            key="fcst_detail",
        )
        if selected:
            selected_sku = selected.split(" — ")[0]
            st.plotly_chart(
                chart_forecast_sparkline(
                    product_id=int(df[df["sku"] == selected_sku]["product_name"].index[0])
                    if not df[df["sku"] == selected_sku].empty else None
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )
