"""
AIDA Inventory Intelligence — Deep Dive
=========================================
Searchable, filterable inventory explorer with supplier metrics.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import sqlite3

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

from phase6_ui.style import COLORS, inject_css
from phase6_ui.components.charts import chart_inventory_health

DB = BASE / "phase2_sql" / "aida.db"

st.set_page_config(page_title="AIDA — Inventory", page_icon="📦", layout="wide")
inject_css()

st.markdown('<p class="aida-logo">AIDA</p>', unsafe_allow_html=True)
st.markdown('<p class="aida-page-subtitle">Inventory Intelligence · Real-time stock visibility across all dark stores</p>',
            unsafe_allow_html=True)

# ── Filters ─────────────────────────────────────────────────────────────────
f_col1, f_col2, f_col3, f_col4 = st.columns(4)
with f_col1:
    store_filter = st.selectbox("Store", ["All"] + ["DS-BEN-01", "DS-MUM-02", "DS-DEL-03"],
                                key="inv_store")
with f_col2:
    conn = sqlite3.connect(str(DB))
    cats = pd.read_sql_query("SELECT DISTINCT category FROM products ORDER BY category", conn)["category"].tolist()
    conn.close()
    cat_filter = st.selectbox("Category", ["All"] + cats, key="inv_cat")
with f_col3:
    status_filter = st.selectbox("Stock Status", ["All", "HEALTHY", "OK", "LOW", "STOCKOUT"],
                                 key="inv_status")
with f_col4:
    search = st.text_input("Search SKU or Product", placeholder="e.g. milk, paneer...", key="inv_search")

# ── Build Query ─────────────────────────────────────────────────────────────
where = ["1=1"]
params = {}
if store_filter != "All":
    where.append("ist.store_code = :store")
    params["store"] = store_filter
if cat_filter != "All":
    where.append("ist.category = :cat")
    params["cat"] = cat_filter
if status_filter != "All":
    where.append("ist.stock_status = :status")
    params["status"] = status_filter
if search:
    where.append("(LOWER(ist.sku) LIKE :s OR LOWER(ist.product_name) LIKE :s)")
    params["s"] = f"%{search.lower()}%"

conn = sqlite3.connect(str(DB))
df = pd.read_sql_query(f"""
    SELECT
        ist.store_code, ist.sku, ist.product_name, ist.category,
        ist.qty_available, ist.qty_on_hand, ist.qty_reserved,
        ist.reorder_point, ist.stock_status,
        ist.supplier_name, ist.sla_delivery_hours,
        ist.selling_price, ist.unit_cost,
        ROUND((ist.selling_price - ist.unit_cost) / ist.selling_price * 100, 1) AS margin_pct,
        ROUND(COALESCE(dv.avg_daily_sales, 0), 1) AS daily_sales_rate,
        CASE WHEN COALESCE(dv.avg_daily_sales, 0) > 0
             THEN ROUND(ist.qty_available / dv.avg_daily_sales, 1)
             ELSE NULL END AS days_of_stock
    FROM inventory_status ist
    LEFT JOIN (
        SELECT product_id, store_id,
               SUM(total_units_sold)*1.0 / COUNT(DISTINCT sale_date) AS avg_daily_sales
        FROM daily_sales WHERE sale_date >= DATE('now', '-14 days')
        GROUP BY product_id, store_id
    ) dv ON ist.product_id = dv.product_id AND ist.store_id = dv.store_id
    WHERE {' AND '.join(where)}
    ORDER BY CASE ist.stock_status
        WHEN 'STOCKOUT' THEN 0 WHEN 'LOW' THEN 1 WHEN 'OK' THEN 2 ELSE 3 END,
        ist.qty_available ASC
""", conn, params=params)
conn.close()

# ── Stats Row ───────────────────────────────────────────────────────────────
s1, s2, s3, s4, s5 = st.columns(5)
with s1:
    st.metric("Total Items", len(df))
with s2:
    st.metric("Stockouts", len(df[df["stock_status"] == "STOCKOUT"]))
with s3:
    st.metric("Low Stock", len(df[df["stock_status"] == "LOW"]))
with s4:
    st.metric("Healthy", len(df[df["stock_status"] == "HEALTHY"]))
with s5:
    if len(df) > 0:
        st.metric("Avg Days Stock", f"{df['days_of_stock'].mean():.1f}")
    else:
        st.metric("Avg Days Stock", "—")

st.markdown("---")

# ── Styled Data Table ───────────────────────────────────────────────────────
if df.empty:
    st.info("No items match your filters.")
else:
    # Style the status column
    def color_status(val):
        colors = {
            "STOCKOUT": f"background: rgba(239,68,68,0.15); color: #ef4444; font-weight: 600",
            "LOW": f"background: rgba(245,158,11,0.15); color: #f59e0b; font-weight: 600",
            "OK": f"color: #8b8fa8",
            "HEALTHY": f"background: rgba(34,197,94,0.10); color: #22c55e; font-weight: 600",
        }
        return colors.get(val, "")

    display_cols = ["store_code", "sku", "product_name", "category",
                    "qty_available", "days_of_stock", "daily_sales_rate",
                    "reorder_point", "stock_status", "margin_pct",
                    "supplier_name", "sla_delivery_hours"]
    display_df = df[[c for c in display_cols if c in df.columns]]

    styled = display_df.style.map(color_status, subset=["stock_status"]) \
                           .format({"days_of_stock": "{:.1f}", "daily_sales_rate": "{:.1f}",
                                    "margin_pct": "{:.1f}%"})
    st.dataframe(styled, use_container_width=True, height=600, hide_index=True)

# ── Supplier Performance Section ────────────────────────────────────────────
st.markdown("---")
st.markdown('<p class="aida-section-title">Supplier Performance</p>', unsafe_allow_html=True)

conn = sqlite3.connect(str(DB))
supp_df = pd.read_sql_query("""
    SELECT
        sup.supplier_name,
        sup.sla_delivery_hours,
        sup.category AS primary_category,
        COUNT(DISTINCT po.po_id) AS total_pos,
        ROUND(AVG(poi.quantity_received * 1.0 / poi.quantity_ordered), 3) AS fill_rate,
        SUM(poi.quantity_ordered) AS total_ordered,
        SUM(poi.quantity_received) AS total_received,
        SUM(poi.quantity_ordered) - SUM(poi.quantity_received) AS shortfall
    FROM purchase_order_items poi
    JOIN purchase_orders po ON poi.po_id = po.po_id
    JOIN suppliers sup ON po.supplier_id = sup.supplier_id
    WHERE po.po_status = 'received'
    GROUP BY sup.supplier_id
    ORDER BY fill_rate ASC
""", conn)
conn.close()

supp_df["fill_rate_pct"] = (supp_df["fill_rate"] * 100).round(1)

supp_cols = st.columns([2, 2, 2, 1, 1, 1])
for col, label in zip(supp_cols, ["Supplier", "Category", "SLAs", "Fill Rate", "Ordered", "Shortfall"]):
    with col:
        st.markdown(f'<span class="aida-kpi-label">{label}</span>', unsafe_allow_html=True)

for _, row in supp_df.iterrows():
    c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 2, 1, 1, 1])
    fr = row["fill_rate_pct"]
    fill_color = "#22c55e" if fr > 95 else "#f59e0b" if fr > 90 else "#ef4444"
    with c1:
        st.markdown(f'<span style="color:#eef0f6;font-weight:500;">{row["supplier_name"]}</span>',
                    unsafe_allow_html=True)
    with c2:
        st.caption(row["primary_category"])
    with c3:
        st.caption(f'{row["sla_delivery_hours"]}h SLA')
    with c4:
        st.markdown(f'<span style="color:{fill_color};font-weight:700;">{fr:.1f}%</span>',
                    unsafe_allow_html=True)
    with c5:
        st.caption(f'{row["total_ordered"]:,}')
    with c6:
        st.caption(f'{int(row["shortfall"]):,}')
