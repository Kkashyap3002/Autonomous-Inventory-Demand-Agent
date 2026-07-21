"""
AIDA SQL Workspace — Direct Query Editor & Table Explorer
===========================================================
Write raw SQL, browse tables, view schemas, and export results.
For analysts who want full control beyond natural language queries.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import sqlite3
import time

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

from phase6_ui.style import COLORS, inject_css

DB = BASE / "phase2_sql" / "aida.db"

st.set_page_config(page_title="AIDA — SQL Workspace", page_icon="⚡", layout="wide")
inject_css()

# ── Session State ───────────────────────────────────────────────────────────
if "sql_history" not in st.session_state:
    st.session_state.sql_history = []
if "sql_editor_text" not in st.session_state:
    st.session_state.sql_editor_text = "SELECT * FROM orders LIMIT 10;"
if "last_results" not in st.session_state:
    st.session_state.last_results = None
if "last_error" not in st.session_state:
    st.session_state.last_error = None

# ── Header ──────────────────────────────────────────────────────────────────
st.markdown('<p class="aida-logo">AIDA</p>', unsafe_allow_html=True)
st.markdown('<p class="aida-page-subtitle">SQL Workspace · Write, execute, and explore queries directly against the AIDA database</p>',
            unsafe_allow_html=True)

# ── Layout: Sidebar (schema browser) | Main (editor + results) ──────────────
sidebar, main = st.columns([1, 3])

# =============================================================================
# SIDEBAR: DATABASE EXPLORER
# =============================================================================
with sidebar:
    st.markdown('<p style="font-weight:700;color:#eef0f6;margin-bottom:8px;">📋 Database Explorer</p>',
                unsafe_allow_html=True)

    # Get tables and their row counts
    conn = sqlite3.connect(str(DB))
    tables = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn
    )["name"].tolist()

    # Row counts
    table_info = {}
    for t in tables:
        try:
            cur = conn.execute(f'SELECT COUNT(*) FROM "{t}"')
            table_info[t] = cur.fetchone()[0]
        except:
            table_info[t] = "—"

    # Also get views
    views = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='view' ORDER BY name", conn
    )["name"].tolist()
    for v in views:
        try:
            cur = conn.execute(f'SELECT COUNT(*) FROM "{v}"')
            table_info[v] = cur.fetchone()[0]
        except:
            table_info[v] = "—"
    conn.close()

    all_objects = tables + views

    # Search
    search = st.text_input("Search tables", placeholder="e.g. orders, inventory...",
                           key="table_search", label_visibility="collapsed")
    if search:
        all_objects = [t for t in all_objects if search.lower() in t.lower()]

    # Table list with click-to-preview
    for obj_name in all_objects:
        count = table_info.get(obj_name, "—")
        obj_type = "view" if obj_name in views else "table"
        icon = "📊" if obj_type == "view" else "📋"

        col_btn, col_info = st.columns([3, 1])
        with col_btn:
            if st.button(
                f"{icon} {obj_name}",
                key=f"tbl_{obj_name}",
                use_container_width=True,
                help=f"Click to preview schema & data of {obj_name}",
            ):
                st.session_state[f"show_{obj_name}"] = not st.session_state.get(f"show_{obj_name}", False)
        with col_info:
            if isinstance(count, int):
                st.caption(f"{count:,}")
            else:
                st.caption(count)

        # Expand to show schema + preview
        if st.session_state.get(f"show_{obj_name}", False):
            conn = sqlite3.connect(str(DB))

            # Schema
            schema_df = pd.read_sql_query(f'PRAGMA table_info("{obj_name}")', conn)
            st.caption(f"**Schema** ({len(schema_df)} columns)")
            st.dataframe(
                schema_df[["name", "type"]].rename(columns={"name": "Column", "type": "Type"}),
                use_container_width=True, hide_index=True, height=min(200, 35 * len(schema_df) + 38),
            )

            # Quick insert
            if st.button(f"📝 SELECT * FROM {obj_name}", key=f"sel_{obj_name}", use_container_width=True):
                st.session_state.sql_editor_text = f"SELECT * FROM {obj_name} LIMIT 50;"

            # Preview first 5 rows
            try:
                preview = pd.read_sql_query(f'SELECT * FROM "{obj_name}" LIMIT 5', conn)
                st.caption(f"**Preview** (first 5 of {count} rows)")
                st.dataframe(preview, use_container_width=True, hide_index=True)
            except Exception as e:
                st.caption(f"Could not preview: {e}")

            conn.close()
            st.markdown("---")

    st.caption(f"{len(tables)} tables · {len(views)} views · {sum(isinstance(v, int) for v in table_info.values()):,} total rows")

# =============================================================================
# MAIN: SQL EDITOR + RESULTS
# =============================================================================
with main:
    # ── Query Templates ─────────────────────────────────────────────────────
    st.markdown('<p style="font-weight:600;color:#8b8fa8;font-size:0.75rem;'
                'text-transform:uppercase;letter-spacing:0.05em;">Quick Templates</p>',
                unsafe_allow_html=True)

    templates = {
        "📊 Revenue by Store": """
SELECT s.store_code, s.city,
       COUNT(DISTINCT o.order_id) AS total_orders,
       ROUND(SUM(o.order_total), 2) AS total_revenue,
       ROUND(AVG(o.order_total), 2) AS avg_order_value
FROM orders o JOIN stores s ON o.store_id = s.store_id
WHERE o.order_status = 'delivered' AND o.ordered_at >= DATE('now', '-30 days')
GROUP BY s.store_code, s.city ORDER BY total_revenue DESC;
""",
        "📦 Inventory Status": """
SELECT ist.store_code, ist.sku, ist.product_name, ist.category,
       ist.qty_available, ist.reorder_point, ist.stock_status,
       ist.supplier_name, ist.sla_delivery_hours
FROM inventory_status ist
WHERE ist.stock_status IN ('STOCKOUT', 'LOW')
ORDER BY CASE ist.stock_status WHEN 'STOCKOUT' THEN 0 ELSE 1 END, ist.qty_available ASC
LIMIT 20;
""",
        "📈 Daily Sales Trend": """
SELECT sale_date, SUM(total_units_sold) AS total_units,
       ROUND(SUM(total_revenue), 2) AS total_revenue,
       SUM(order_count) AS total_orders
FROM daily_sales
WHERE sale_date >= DATE('now', '-14 days')
GROUP BY sale_date ORDER BY sale_date DESC;
""",
        "🏷️ Category Margin": """
SELECT p.category, COUNT(DISTINCT p.product_id) AS products,
       SUM(oi.quantity) AS units_sold,
       ROUND(SUM(oi.line_total), 2) AS revenue,
       ROUND((SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity)) / SUM(oi.line_total) * 100, 1) AS margin_pct
FROM order_items oi JOIN products p ON oi.product_id = p.product_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY p.category ORDER BY margin_pct DESC;
""",
        "🚚 Supplier Fill Rate": """
SELECT sup.supplier_name, sup.sla_delivery_hours,
       COUNT(DISTINCT po.po_id) AS total_pos,
       ROUND(AVG(poi.quantity_received * 1.0 / poi.quantity_ordered), 3) AS fill_rate,
       SUM(poi.quantity_ordered) AS ordered, SUM(poi.quantity_received) AS received
FROM purchase_order_items poi
JOIN purchase_orders po ON poi.po_id = po.po_id
JOIN suppliers sup ON po.supplier_id = sup.supplier_id
WHERE po.po_status = 'received'
GROUP BY sup.supplier_id ORDER BY fill_rate ASC;
""",
        "📅 Peak Hours": """
SELECT CAST(strftime('%H', ordered_at) AS INTEGER) AS hour,
       COUNT(*) AS orders, ROUND(AVG(order_total), 2) AS avg_value
FROM orders WHERE order_status = 'delivered'
GROUP BY strftime('%H', ordered_at) ORDER BY orders DESC;
""",
        "🔮 7-Day Forecast": """
SELECT fr.sku, fr.product_name, fr.store_code, fr.forecast_date, fr.forecasted_units,
       ist.qty_available AS current_stock
FROM forecast_results fr
LEFT JOIN inventory_status ist ON fr.product_id = ist.product_id AND fr.store_id = ist.store_id
WHERE fr.forecast_date BETWEEN DATE('now') AND DATE('now', '+7 days')
ORDER BY fr.forecasted_units DESC LIMIT 20;
""",
    }

    t_cols = st.columns(len(templates))
    for i, (label, sql) in enumerate(templates.items()):
        with t_cols[i]:
            if st.button(label, key=f"tmpl_{i}", use_container_width=True,
                        help=f"Load: {label}"):
                st.session_state.sql_editor_text = sql.strip()

    st.markdown("---")

    # ── SQL Editor ──────────────────────────────────────────────────────────
    st.markdown('<p style="font-weight:600;color:#eef0f6;margin-bottom:6px;">⚡ SQL Editor</p>',
                unsafe_allow_html=True)

    # Editor
    sql_query = st.text_area(
        "SQL Query",
        value=st.session_state.sql_editor_text,
        height=160,
        key="sql_editor",
        label_visibility="collapsed",
        placeholder="Write your SQL query here...\ne.g. SELECT * FROM orders WHERE order_total > 500 LIMIT 10;",
    )

    # Sync editor text
    st.session_state.sql_editor_text = sql_query

    col_run, col_clear, col_export = st.columns([1, 1, 4])
    with col_run:
        run_clicked = st.button("▶ Run Query", type="primary", use_container_width=True,
                                key="run_sql")
        # Keyboard shortcut hint
        st.caption("Ctrl+Enter to run")
    with col_clear:
        if st.button("🗑 Clear", use_container_width=True, key="clear_sql"):
            st.session_state.sql_editor_text = ""
            st.session_state.last_results = None
            st.session_state.last_error = None
            st.rerun()

    # ── Execute Query ──────────────────────────────────────────────────────
    if run_clicked and sql_query.strip():
        start_time = time.time()
        try:
            conn = sqlite3.connect(str(DB))
            df = pd.read_sql_query(sql_query, conn)
            conn.close()
            elapsed = (time.time() - start_time) * 1000  # ms

            st.session_state.last_results = df
            st.session_state.last_error = None

            # Add to history
            st.session_state.sql_history.insert(0, {
                "query": sql_query,
                "rows": len(df),
                "cols": len(df.columns),
                "time_ms": elapsed,
                "timestamp": pd.Timestamp.now().strftime("%H:%M:%S"),
            })
            # Keep last 20
            st.session_state.sql_history = st.session_state.sql_history[:20]

        except Exception as e:
            st.session_state.last_results = None
            st.session_state.last_error = str(e)
            st.session_state.sql_history.insert(0, {
                "query": sql_query,
                "rows": 0,
                "cols": 0,
                "time_ms": 0,
                "timestamp": pd.Timestamp.now().strftime("%H:%M:%S"),
                "error": str(e),
            })
            st.session_state.sql_history = st.session_state.sql_history[:20]

    # ── Results Area ────────────────────────────────────────────────────────
    st.markdown("---")

    if st.session_state.last_error:
        st.error(f"**Query Error:** {st.session_state.last_error}")

    if st.session_state.last_results is not None:
        df = st.session_state.last_results
        elapsed = (time.time() - start_time) * 1000 if run_clicked else 0

        # Results header
        res_col1, res_col2, res_col3 = st.columns([2, 2, 3])
        with res_col1:
            st.markdown(
                f'<span style="color:#22c55e;font-weight:600;">✓ Query returned</span> '
                f'<span style="color:#eef0f6;font-weight:700;">{len(df):,} rows</span> '
                f'<span style="color:#8b8fa8;">× {len(df.columns)} columns</span>',
                unsafe_allow_html=True,
            )
        with res_col2:
            if elapsed > 0:
                st.caption(f"⏱ {elapsed:.1f} ms")
        with res_col3:
            # Download CSV button
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download CSV",
                csv,
                f"aida_query_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                key="dl_csv",
            )

        # Styled data table
        st.dataframe(
            df,
            use_container_width=True,
            height=min(600, 35 * len(df) + 38),
            hide_index=True,
        )

        # Summary stats for numeric columns
        num_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if num_cols and len(df) > 0:
            with st.expander("📊 Column Statistics", expanded=False):
                stats = df[num_cols].describe().round(2)
                st.dataframe(stats, use_container_width=True)

    elif not st.session_state.last_error and not run_clicked:
        # Empty state
        st.markdown("""
        <div style="text-align:center;padding:40px 20px;border:1px dashed #2e3140;border-radius:12px;">
            <p style="font-size:2rem;margin-bottom:8px;">⚡</p>
            <p style="color:#eef0f6;font-weight:600;">Write a SQL query and click <strong>Run</strong></p>
            <p style="color:#5c6078;font-size:0.85rem;">
                Select a template above, browse tables in the sidebar, or write your own SQL.<br>
                All queries run against the AIDA SQLite database (35K+ orders, 11 tables).
            </p>
        </div>
        """, unsafe_allow_html=True)

    # ── Query History ───────────────────────────────────────────────────────
    if st.session_state.sql_history:
        with st.expander(f"📝 Query History ({len(st.session_state.sql_history)} recent)", expanded=False):
            for i, h in enumerate(st.session_state.sql_history):
                error = h.get("error", "")
                status_color = "#ef4444" if error else "#22c55e"
                status_text = f"❌ {error[:80]}" if error else f"✓ {h['rows']:,} rows · {h['time_ms']:.0f}ms"

                hist_col1, hist_col2 = st.columns([6, 1])
                with hist_col1:
                    st.code(h["query"].strip()[:200], language="sql")
                    st.caption(f"{h['timestamp']} · {status_text}")
                with hist_col2:
                    if st.button("📋 Load", key=f"hist_{i}", use_container_width=True):
                        st.session_state.sql_editor_text = h["query"].strip()
                        st.rerun()
                st.markdown("---")
