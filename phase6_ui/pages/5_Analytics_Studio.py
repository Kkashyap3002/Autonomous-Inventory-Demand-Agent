"""
AIDA Analytics Studio — Interactive BI Explorer
=================================================
Power BI-style real-time analytics with configurable charts,
dynamic axes, aggregation, filtering, and multi-view layouts.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import date, timedelta
import numpy as np

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

from phase6_ui.style import COLORS, inject_css
from phase6_ui.components.charts import LAYOUT_DARK

DB = BASE / "phase2_sql" / "aida.db"

CHART_COLORS = ["#6366f1", "#22d3ee", "#22c55e", "#f59e0b", "#ef4444",
                "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#84cc16"]

st.set_page_config(page_title="AIDA — Analytics Studio", page_icon="📊", layout="wide")
inject_css()

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown('<p class="aida-logo">AIDA</p>', unsafe_allow_html=True)
st.markdown('<p class="aida-page-subtitle">Analytics Studio · Real-time interactive data exploration — Power BI style</p>',
            unsafe_allow_html=True)

# =============================================================================
# SIDEBAR: DATA SOURCE + CHART CONFIG
# =============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Chart Builder")

    # ── Data Source ────────────────────────────────────────────────────────
    st.markdown('<p style="font-weight:700;color:#eef0f6;">1. Data Source</p>',
                unsafe_allow_html=True)

    PREBUILT_QUERIES = {
        "Daily Sales": """
            SELECT ds.sale_date, ds.total_units_sold AS units, ds.total_revenue AS revenue,
                   ds.order_count AS orders, p.category, s.store_code
            FROM daily_sales ds
            JOIN products p ON ds.product_id = p.product_id
            JOIN stores s ON ds.store_id = s.store_id
            WHERE ds.sale_date >= DATE('now', '-{days} days')
        """,
        "Orders": """
            SELECT o.order_id, o.order_status, o.order_total, o.discount_total,
                   o.customer_zone, o.ordered_at, o.delivered_at,
                   s.store_code, s.city
            FROM orders o JOIN stores s ON o.store_id = s.store_id
            WHERE o.ordered_at >= DATE('now', '-{days} days')
        """,
        "Inventory Status": """
            SELECT ist.store_code, ist.sku, ist.product_name, ist.category,
                   ist.qty_available, ist.qty_on_hand, ist.qty_reserved,
                   ist.reorder_point, ist.stock_status, ist.selling_price,
                   ist.unit_cost, ist.supplier_name
            FROM inventory_status ist
        """,
        "Products + Margin": """
            SELECT p.sku, p.product_name, p.category, p.brand,
                   p.selling_price, p.unit_cost, p.is_perishable,
                   (p.selling_price - p.unit_cost) AS unit_margin,
                   ROUND((p.selling_price - p.unit_cost) / p.selling_price * 100, 1) AS margin_pct,
                   sup.supplier_name
            FROM products p JOIN suppliers sup ON p.supplier_id = sup.supplier_id
        """,
        "Supplier Performance": """
            SELECT sup.supplier_name, sup.category AS supplier_category,
                   sup.sla_delivery_hours, COUNT(po.po_id) AS total_pos,
                   ROUND(AVG(poi.quantity_received * 1.0 / poi.quantity_ordered), 3) AS fill_rate,
                   SUM(poi.quantity_ordered) AS ordered, SUM(poi.quantity_received) AS received
            FROM purchase_order_items poi
            JOIN purchase_orders po ON poi.po_id = po.po_id
            JOIN suppliers sup ON po.supplier_id = sup.supplier_id
            WHERE po.po_status = 'received'
            GROUP BY sup.supplier_id
        """,
        "Order Items (detailed)": """
            SELECT oi.order_item_id, oi.quantity, oi.unit_price, oi.line_total,
                   p.sku, p.product_name, p.category,
                   o.order_status, o.store_id, o.ordered_at
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o ON oi.order_id = o.order_id
            WHERE o.ordered_at >= DATE('now', '-{days} days')
        """,
    }

    selected_source = st.selectbox(
        "Choose dataset",
        list(PREBUILT_QUERIES.keys()),
        key="source_select",
    )

    # Date filter for queries that support it
    days_back = st.slider("Days of history", 7, 90, 30, key="days_slider")

    # Load the data
    @st.cache_data(ttl=30)
    def load_dataset(source_key: str, days: int) -> pd.DataFrame:
        sql = PREBUILT_QUERIES[source_key].format(days=days)
        conn = sqlite3.connect(str(DB))
        df = pd.read_sql_query(sql, conn, parse_dates=[
            c for c in ["sale_date", "ordered_at", "delivered_at"]
            if c in sql
        ])
        conn.close()
        return df

    df = load_dataset(selected_source, days_back)

    st.caption(f"Loaded: **{len(df):,} rows** × {len(df.columns)} columns")

    # ── Global Filters ─────────────────────────────────────────────────────
    st.markdown('<p style="font-weight:700;color:#eef0f6;margin-top:20px;">2. Filters</p>',
                unsafe_allow_html=True)

    # Detect columns for filtering
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

    # Category filters (up to 3)
    filter_cols = [c for c in cat_cols if df[c].nunique() < 30 and c not in ["sku", "product_name"]]
    active_filters = {}
    for fc in filter_cols[:3]:
        vals = sorted(df[fc].dropna().unique().tolist())
        if len(vals) <= 20:
            selected = st.multiselect(f"Filter: {fc}", vals, default=vals, key=f"filt_{fc}")
            if selected and len(selected) < len(vals):
                active_filters[fc] = selected

    # Apply filters
    filtered_df = df.copy()
    for col, vals in active_filters.items():
        filtered_df = filtered_df[filtered_df[col].isin(vals)]

    st.caption(f"After filters: **{len(filtered_df):,} rows**")

    # ── Chart Type ─────────────────────────────────────────────────────────
    st.markdown('<p style="font-weight:700;color:#eef0f6;margin-top:20px;">3. Chart Configuration</p>',
                unsafe_allow_html=True)

    chart_type = st.selectbox(
        "Chart type",
        ["📊 Bar", "📈 Line", "🥧 Pie / Donut", "📊 Histogram",
         "🎯 Scatter / Bubble", "🔥 Heatmap", "📐 Area",
         "📉 Combo (Bar + Line)", "📦 Box Plot", "📊 Stacked Bar"],
        key="chart_type",
    )

    # Numeric and categorical columns
    num_cols = filtered_df.select_dtypes(include=["number"]).columns.tolist()
    all_cat_cols = filtered_df.select_dtypes(include=["object", "category"]).columns.tolist()
    if date_cols:
        all_cat_cols = date_cols + all_cat_cols  # dates can be axes too

    # Axis selectors depend on chart type
    if chart_type in ["🥧 Pie / Donut", "📊 Histogram"]:
        x_axis = st.selectbox("Category / Label", all_cat_cols, key="x_axis")
        y_axis = st.selectbox("Value", num_cols, key="y_axis")
        color_by = st.selectbox("Color by (optional)", ["None"] + all_cat_cols, key="color_by")
    elif chart_type == "🔥 Heatmap":
        x_axis = st.selectbox("X Axis", all_cat_cols, key="x_axis")
        y_axis = st.selectbox("Y Axis", [c for c in all_cat_cols if c != x_axis or len(all_cat_cols) == 1], key="y_axis")
        z_value = st.selectbox("Value (color intensity)", num_cols, key="z_value")
    elif chart_type == "🎯 Scatter / Bubble":
        x_axis = st.selectbox("X Axis", num_cols, key="x_axis")
        y_axis = st.selectbox("Y Axis", [c for c in num_cols if c != x_axis or len(num_cols) == 1], key="y_axis")
        color_by = st.selectbox("Color by", ["None"] + all_cat_cols, key="color_by")
        size_by = st.selectbox("Bubble size (optional)", ["None"] + num_cols, key="size_by")
    elif chart_type in ["📦 Box Plot"]:
        y_axis = st.selectbox("Value", num_cols, key="y_axis")
        x_axis = st.selectbox("Group by", all_cat_cols, key="x_axis")
        color_by = st.selectbox("Color by", ["None"] + all_cat_cols, key="color_by")
    else:
        x_axis = st.selectbox("X Axis", all_cat_cols, key="x_axis")
        y_axis = st.selectbox("Y Axis", num_cols, key="y_axis")
        color_by = st.selectbox("Color / Group by", ["None"] + all_cat_cols, key="color_by")

    # Aggregation
    agg_func = st.selectbox(
        "Aggregation",
        ["sum", "avg", "count", "min", "max", "median", "std"],
        index=0 if chart_type != "🥧 Pie / Donut" else 0,
        key="agg_func",
    )

    # Limit
    top_n = st.slider("Top N categories", 5, 50, 15, key="top_n_slider")

    # ── Layout ─────────────────────────────────────────────────────────────
    st.markdown('<p style="font-weight:700;color:#eef0f6;margin-top:20px;">4. Layout</p>',
                unsafe_allow_html=True)
    view_mode = st.radio("View mode", ["Single Chart", "Split View (2 charts)", "Grid (4 charts)"],
                         key="view_mode", horizontal=False)


# =============================================================================
# MAIN AREA: CHARTS
# =============================================================================

# ── Aggregate Data ──────────────────────────────────────────────────────────
@st.cache_data(ttl=10)
def aggregate_data(_df: pd.DataFrame, x: str, y: str, agg: str, top_n: int,
                   color: str = None) -> pd.DataFrame:
    """Aggregate data for charting."""
    df = _df.copy()
    if df[x].dtype == "datetime64[ns]":
        df[x] = df[x].dt.date

    group_cols = [x]
    if color and color != "None" and color != x:
        group_cols.append(color)

    agg_map = {"sum": "sum", "avg": "mean", "count": "count", "min": "min",
               "max": "max", "median": "median", "std": "std"}
    result = df.groupby(group_cols, dropna=True)[y].agg(agg_map[agg]).reset_index()
    result = result.sort_values(y, ascending=False).head(top_n)
    return result


def build_histogram(_df: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    """For histogram, just return the raw data for the numeric column."""
    return _df[[x, y]].dropna() if y else _df[[x]].dropna()


def build_heatmap(_df: pd.DataFrame, x: str, y: str, z: str, agg: str) -> pd.DataFrame:
    """Pivot data for heatmap."""
    agg_map = {"sum": "sum", "avg": "mean", "count": "count"}
    pivot = _df.pivot_table(values=z, index=y, columns=x, aggfunc=agg_map.get(agg, "sum"))
    return pivot


# ── Render a single chart ───────────────────────────────────────────────────
def render_chart(data: pd.DataFrame, chart_type: str, x: str, y: str,
                 color: str = None, size: str = None, agg: str = "sum",
                 title: str = "", height: int = 450) -> go.Figure:
    """Build a Plotly figure from parsed config."""

    fig = go.Figure()

    if chart_type == "📊 Bar":
        agged = aggregate_data(data, x, y, agg, top_n, color)
        if color and color != "None":
            for grp in agged[color].unique():
                subset = agged[agged[color] == grp]
                fig.add_trace(go.Bar(x=subset[x], y=subset[y], name=str(grp),
                                     marker_cornerradius=3))
            fig.update_layout(barmode="group")
        else:
            colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(agged))]
            fig.add_trace(go.Bar(x=agged[x], y=agged[y], marker_color=colors,
                                 marker_cornerradius=4,
                                 text=[f"{v:,.1f}" if v > 100 else f"{v:.2f}" for v in agged[y]],
                                 textposition="outside"))

    elif chart_type == "📈 Line":
        agged = aggregate_data(data, x, y, agg, top_n, color)
        if color and color != "None":
            for grp in agged[color].unique():
                subset = agged[agged[color] == grp]
                fig.add_trace(go.Scatter(x=subset[x], y=subset[y], name=str(grp),
                                         mode="lines+markers", marker_size=5))
        else:
            fig.add_trace(go.Scatter(x=agged[x], y=agged[y], mode="lines+markers",
                                     line_color=CHART_COLORS[0], marker_size=6,
                                     fill="tozeroy", fillcolor="rgba(99,102,241,0.08)"))

    elif chart_type == "🥧 Pie / Donut":
        agged = aggregate_data(data, x, y, agg, top_n)
        fig.add_trace(go.Pie(labels=agged[x], values=agged[y], hole=0.5,
                             marker_colors=CHART_COLORS,
                             textinfo="label+percent",
                             textfont_size=11))

    elif chart_type == "📊 Histogram":
        raw = data[[x]].dropna()
        fig.add_trace(go.Histogram(x=raw[x], nbinsx=30,
                                    marker_color=CHART_COLORS[0],
                                    marker_line_color="#0f1117",
                                    marker_line_width=1))

    elif chart_type == "🎯 Scatter / Bubble":
        if size and size != "None":
            fig.add_trace(go.Scatter(x=data[x], y=data[y], mode="markers",
                                     marker_size=data[size] / data[size].max() * 30 + 5,
                                     marker_color=data[y], marker_colorscale="Viridis",
                                     text=data.index, opacity=0.7))
        else:
            fig.add_trace(go.Scatter(x=data[x], y=data[y], mode="markers",
                                     marker_color=CHART_COLORS[0], opacity=0.6,
                                     marker_size=8))

    elif chart_type == "🔥 Heatmap":
        pivot = build_heatmap(data, x, y, z_value if 'z_value' in dir() else y,
                             agg if agg != "count" else "sum")
        fig.add_trace(go.Heatmap(z=pivot.values, x=pivot.columns, y=pivot.index,
                                  colorscale="Viridis", texttemplate="%{z:.1f}"))

    elif chart_type == "📐 Area":
        agged = aggregate_data(data, x, y, agg, top_n)
        fig.add_trace(go.Scatter(x=agged[x], y=agged[y], mode="lines",
                                 fill="tozeroy", line_color=CHART_COLORS[0],
                                 fillcolor="rgba(99,102,241,0.15)"))

    elif chart_type == "📉 Combo (Bar + Line)":
        agged = aggregate_data(data, x, y, agg, top_n)
        fig.add_trace(go.Bar(x=agged[x], y=agged[y], name=f"{agg}({y})",
                             marker_color=CHART_COLORS[0], marker_cornerradius=3,
                             yaxis="y"))
        # Add moving average line
        agged["ma3"] = agged[y].rolling(3, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=agged[x], y=agged["ma3"], name="3-pt MA",
                                 mode="lines+markers", line_color=CHART_COLORS[3],
                                 yaxis="y"))
        fig.update_layout(hovermode="x unified")

    elif chart_type == "📦 Box Plot":
        fig = px.box(data, x=x, y=y, color=color if color and color != "None" else None,
                     color_discrete_sequence=CHART_COLORS)
        fig.update_traces(marker_outliercolor="#ef4444")

    elif chart_type == "📊 Stacked Bar":
        agged = aggregate_data(data, x, y, agg, top_n, color)
        if color and color != "None":
            fig = px.bar(agged, x=x, y=y, color=color, barmode="stack",
                        color_discrete_sequence=CHART_COLORS)
        else:
            fig.add_trace(go.Bar(x=agged[x], y=agged[y], marker_color=CHART_COLORS[0]))

    # Apply dark layout
    fig.update_layout(
        **LAYOUT_DARK,
        title=title,
        height=height,
    )
    return fig


# =============================================================================
# RENDER CHARTS BASED ON VIEW MODE
# =============================================================================

st.markdown("---")

chart_title = f"{chart_type.split(' ')[1]} — {y_axis} by {x_axis}"

if view_mode == "Single Chart":
    fig = render_chart(filtered_df, chart_type, x_axis, y_axis,
                       color_by if color_by != "None" else None,
                       size_by if 'size_by' in dir() and size_by != "None" else None,
                       agg_func, chart_title, 520)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})

elif view_mode == "Split View (2 charts)":
    c1, c2 = st.columns(2)
    with c1:
        # Chart 1: main config
        fig1 = render_chart(filtered_df, chart_type, x_axis, y_axis,
                            color_by if color_by != "None" else None,
                            size_by if 'size_by' in dir() and size_by != "None" else None,
                            agg_func, chart_title, 400)
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

    with c2:
        # Chart 2: complementary — different view of same data
        if num_cols and len(num_cols) > 1:
            alt_y = [c for c in num_cols if c != y_axis][0]
        else:
            alt_y = y_axis
        alt_chart = "📈 Line" if chart_type != "📈 Line" else "📊 Bar"
        fig2 = render_chart(filtered_df, alt_chart, x_axis, alt_y, agg_func=agg_func,
                            title=f"{alt_chart.split(' ')[1]} — {alt_y} by {x_axis}", height=400)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

else:  # Grid (4 charts)
    # Auto-generate 4 different chart types for a dashboard feel
    if len(num_cols) >= 2 and len(all_cat_cols) >= 2:
        alt_y = num_cols[1] if num_cols[0] == y_axis else num_cols[0]
        alt_x = all_cat_cols[1] if all_cat_cols[0] == x_axis else all_cat_cols[0]
    else:
        alt_y, alt_x = y_axis, x_axis

    charts = [
        ("📊 Bar", x_axis, y_axis, f"Bar — {y_axis} by {x_axis}"),
        ("📈 Line", x_axis, y_axis, f"Trend — {y_axis} over {x_axis}"),
        ("🥧 Pie / Donut", alt_x, alt_y, f"Distribution — {alt_y} by {alt_x}"),
        ("📊 Histogram", x_axis, y_axis, f"Distribution of {y_axis}"),
    ]

    row1_cols = st.columns(2)
    row2_cols = st.columns(2)

    for i, (col, (ct, cx, cy, ct_title)) in enumerate(zip(row1_cols + row2_cols, charts)):
        with col:
            fig = render_chart(filtered_df, ct, cx, cy, agg_func=agg_func,
                               title=ct_title, height=350)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# =============================================================================
# DATA PREVIEW
# =============================================================================
st.markdown("---")
with st.expander("📋 Raw Data Preview", expanded=False):
    st.caption(f"{len(filtered_df):,} rows × {len(filtered_df.columns)} columns (after filters)")
    st.dataframe(filtered_df.head(100), use_container_width=True, hide_index=True)

    # Download
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Filtered Data (CSV)", csv,
                       f"aida_analytics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                       "text/csv")
