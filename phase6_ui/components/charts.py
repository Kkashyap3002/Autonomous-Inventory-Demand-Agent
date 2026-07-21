"""
AIDA Reusable Charts — Plotly visualizations
==============================================
All charts share the dark theme defined in style.py.
Import these in any page for consistent, production-quality visuals.
"""

import sqlite3
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

DB = Path(__file__).resolve().parent.parent.parent / "phase2_sql" / "aida.db"

# ── Plotly Layout Template (Dark Mode) ─────────────────────────────────────

LAYOUT_DARK = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#8b8fa8", "family": "Inter, Segoe UI, sans-serif", "size": 12},
    "xaxis": {
        "gridcolor": "rgba(46,49,64,0.4)",
        "zerolinecolor": "#2e3140",
        "linecolor": "#2e3140",
        "tickfont": {"color": "#8b8fa8"},
    },
    "yaxis": {
        "gridcolor": "rgba(46,49,64,0.4)",
        "zerolinecolor": "#2e3140",
        "linecolor": "#2e3140",
        "tickfont": {"color": "#8b8fa8"},
    },
    "margin": {"l": 20, "r": 20, "t": 40, "b": 20},
    "hovermode": "x unified",
    "hoverlabel": {
        "bgcolor": "#1a1d27",
        "font": {"color": "#eef0f6", "family": "Inter, Segoe UI, sans-serif"},
        "bordercolor": "#2e3140",
    },
    "legend": {
        "font": {"color": "#8b8fa8"},
        "orientation": "h",
        "yanchor": "top",
        "y": -0.15,
        "xanchor": "center",
        "x": 0.5,
    },
}

COLORS = ["#6366f1", "#22d3ee", "#22c55e", "#f59e0b",
          "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]


# ── CHART FUNCTIONS ────────────────────────────────────────────────────────

def chart_revenue_trend(days: int = 30) -> go.Figure:
    """Daily revenue line chart with 7-day moving average."""
    conn = sqlite3.connect(str(DB))
    df = pd.read_sql_query(f"""
        SELECT sale_date, SUM(total_revenue) AS revenue
        FROM daily_sales
        WHERE sale_date >= DATE('now', '-{days} days')
        GROUP BY sale_date ORDER BY sale_date
    """, conn, parse_dates=["sale_date"])
    conn.close()

    if df.empty:
        return _empty_fig("No revenue data")

    df["ma7"] = df["revenue"].rolling(7, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["sale_date"], y=df["revenue"],
        mode="lines", name="Daily Revenue",
        line={"color": "#2e3140", "width": 1.5},
        hovertemplate="%{y:,.0f} INR<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["sale_date"], y=df["ma7"],
        mode="lines", name="7-Day Average",
        line={"color": "#6366f1", "width": 2.5},
        fill="tozeroy", fillcolor="rgba(99,102,241,0.08)",
        hovertemplate="%{y:,.0f} INR<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_DARK,
        title=f"Revenue Trend — Last {days} Days",
        xaxis_title=None, yaxis_title="Revenue (INR)",
        height=340,
    )
    return fig


def chart_category_breakdown() -> go.Figure:
    """Donut chart: revenue share by category."""
    conn = sqlite3.connect(str(DB))
    df = pd.read_sql_query("""
        SELECT p.category, SUM(oi.line_total) AS revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY p.category ORDER BY revenue DESC
    """, conn)
    conn.close()

    if df.empty:
        return _empty_fig("No data")

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=df["category"], values=df["revenue"],
        hole=0.58,
        marker={"colors": COLORS, "line": {"color": "#0f1117", "width": 3}},
        textinfo="label+percent",
        textfont={"color": "#eef0f6", "size": 11},
        hovertemplate="%{label}<br>%{value:,.0f} INR<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_DARK,
        title="Revenue by Category",
        height=340,
        showlegend=False,
    )
    return fig


def chart_inventory_health() -> go.Figure:
    """Horizontal bar chart: days of stock by category."""
    conn = sqlite3.connect(str(DB))
    df = pd.read_sql_query("""
        SELECT ist.category,
               ROUND(AVG(ist.qty_available * 1.0 / NULLIF(dv.avg_daily_sales, 0)), 1) AS avg_days
        FROM inventory_status ist
        LEFT JOIN (
            SELECT product_id, store_id,
                   SUM(total_units_sold)*1.0 / COUNT(DISTINCT sale_date) AS avg_daily_sales
            FROM daily_sales
            WHERE sale_date >= DATE('now', '-14 days')
            GROUP BY product_id, store_id
        ) dv ON ist.product_id = dv.product_id AND ist.store_id = dv.store_id
        WHERE dv.avg_daily_sales > 0 AND ist.qty_available > 0
        GROUP BY ist.category
        ORDER BY avg_days ASC
    """, conn)
    conn.close()

    if df.empty:
        return _empty_fig("No inventory data")

    colors = []
    for d in df["avg_days"]:
        if d < 3:
            colors.append("#ef4444")
        elif d < 7:
            colors.append("#f59e0b")
        else:
            colors.append("#22c55e")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["category"], x=df["avg_days"],
        orientation="h",
        marker={"color": colors, "cornerradius": 4},
        text=[f"{d:.1f}d" for d in df["avg_days"]],
        textposition="outside",
        textfont={"color": "#eef0f6", "size": 12},
        hovertemplate="%{y}: %{x:.1f} days<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_DARK,
        title="Inventory Health — Days of Stock by Category",
        xaxis_title="Days of Inventory Remaining",
        yaxis_title=None,
        height=340,
        showlegend=False,
    )
    # Add threshold lines
    fig.add_vline(x=3, line_dash="dash", line_color="#ef4444", opacity=0.5,
                  annotation_text="Critical (3d)")
    fig.add_vline(x=7, line_dash="dash", line_color="#f59e0b", opacity=0.5,
                  annotation_text="Low (7d)")
    return fig


def chart_forecast_sparkline(product_id: int = None, store_id: int = None,
                              days: int = 30) -> go.Figure:
    """Line chart showing historical + forecasted demand for a product-store."""
    conn = sqlite3.connect(str(DB))

    where = "1=1"
    params = {}
    if product_id:
        where += " AND ds.product_id = :pid"
        params["pid"] = product_id
    if store_id:
        where += " AND ds.store_id = :sid"
        params["sid"] = store_id

    hist = pd.read_sql_query(f"""
        SELECT sale_date, SUM(total_units_sold) AS units
        FROM daily_sales ds WHERE {where} AND sale_date >= DATE('now', '-{days} days')
        GROUP BY sale_date ORDER BY sale_date
    """, conn, params=params, parse_dates=["sale_date"])

    fcst = pd.read_sql_query(f"""
        SELECT forecast_date AS sale_date, SUM(forecasted_units) AS units
        FROM forecast_results WHERE {where.replace('ds.', '')}
          AND forecast_date >= DATE('now')
        GROUP BY forecast_date ORDER BY forecast_date
    """, conn, params=params, parse_dates=["sale_date"])
    fcst["is_forecast"] = True
    hist["is_forecast"] = False

    all_data = pd.concat([hist, fcst], ignore_index=True)
    conn.close()

    if all_data.empty:
        return _empty_fig("No forecast data")

    fig = go.Figure()
    # Historical
    hist_only = all_data[~all_data["is_forecast"]]
    fig.add_trace(go.Scatter(
        x=hist_only["sale_date"], y=hist_only["units"],
        mode="lines", name="Historical",
        line={"color": "#6366f1", "width": 2},
        hovertemplate="%{y:.0f} units<extra></extra>",
    ))
    # Forecast
    fcst_only = all_data[all_data["is_forecast"]]
    if not fcst_only.empty:
        fig.add_trace(go.Scatter(
            x=fcst_only["sale_date"], y=fcst_only["units"],
            mode="lines", name="Forecast",
            line={"color": "#f59e0b", "width": 2, "dash": "dash"},
            fill="tozeroy", fillcolor="rgba(245,158,11,0.06)",
            hovertemplate="%{y:.0f} units<extra></extra>",
        ))

    fig.update_layout(
        **LAYOUT_DARK,
        title="Demand Forecast",
        xaxis_title=None, yaxis_title="Units",
        height=320,
    )
    return fig


def chart_top_products(n: int = 10) -> go.Figure:
    """Horizontal bar chart: top N products by revenue."""
    conn = sqlite3.connect(str(DB))
    df = pd.read_sql_query(f"""
        SELECT p.product_name, SUM(oi.line_total) AS revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY p.product_id
        ORDER BY revenue DESC LIMIT {n}
    """, conn)
    conn.close()

    if df.empty:
        return _empty_fig("No product data")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=[n[:35] for n in df["product_name"]],
        x=df["revenue"],
        orientation="h",
        marker={
            "color": df["revenue"].apply(
                lambda x: COLORS[min(range(len(COLORS)),
                                    key=lambda i: abs(i/len(COLORS) - x/df['revenue'].max()))]
            ),
            "cornerradius": 4,
        },
        text=[f"₹{r:,.0f}" for r in df["revenue"]],
        textposition="outside",
        textfont={"color": "#eef0f6", "size": 11},
        hovertemplate="%{y}<br>Revenue: ₹%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_DARK,
        title=f"Top {n} Products by Revenue",
        xaxis_title="Revenue (INR)",
        yaxis_title=None,
        height=380,
        showlegend=False,
    )
    return fig


def _empty_fig(message: str = "No data available") -> go.Figure:
    """Return an empty figure with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=2, y=2, showarrow=False,
        font={"color": "#5c6078", "size": 14},
    )
    fig.update_layout(**LAYOUT_DARK, height=200, xaxis={"visible": False}, yaxis={"visible": False})
    return fig
