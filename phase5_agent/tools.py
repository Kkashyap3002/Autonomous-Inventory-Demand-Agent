"""
Phase 5: Agent Tools
=====================
Each tool wraps functionality from previous phases into a callable
function with a consistent interface that the LangGraph agent invokes.

Tools:
  1. sql_query_tool(query: str)  — NL → SQL → execute → results
  2. rag_search_tool(query: str) — Search ChromaDB policy docs
  3. forecast_tool(query: str)   — Query forecast results
"""

import re
import sqlite3
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "phase2_sql" / "aida.db"

# =============================================================================
# TOOL 1: SQL Query Tool
# =============================================================================

# Pre-built query templates: (intent_patterns, SQL, param_extractor)
# The classifier matches user NL against these patterns and fills params.
SQL_TEMPLATES = [
    {
        "name": "store_revenue",
        "patterns": ["revenue by store", "store sales", "which store", "store performance"],
        "sql": """
            SELECT s.store_code, s.city,
                   COUNT(DISTINCT o.order_id) AS total_orders,
                   ROUND(SUM(o.order_total), 2) AS total_revenue,
                   ROUND(AVG(o.order_total), 2) AS avg_order_value
            FROM orders o
            JOIN stores s ON o.store_id = s.store_id
            WHERE o.order_status = 'delivered'
              AND o.ordered_at >= DATE('now', '-30 days')
            GROUP BY s.store_code, s.city
            ORDER BY total_revenue DESC
        """,
        "description": "Revenue and order counts by store for the last 30 days",
    },
    {
        "name": "top_products",
        "patterns": ["top product", "best selling", "highest revenue product",
                      "most popular", "top selling"],
        "sql": """
            SELECT p.sku, p.product_name, p.category,
                   SUM(oi.quantity) AS units_sold,
                   ROUND(SUM(oi.line_total), 2) AS revenue,
                   ROUND((SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity))
                         / SUM(oi.line_total) * 100, 1) AS margin_pct
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o   ON oi.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY p.product_id
            ORDER BY revenue DESC
            LIMIT 10
        """,
        "description": "Top 10 products by revenue with margin percentage",
    },
    {
        "name": "low_stock",
        "patterns": ["low stock", "low in stock", "stockout", "out of stock",
                      "running out", "reorder", "restock", "inventory level",
                      "stock level", "low on stock"],
        "sql": """
            SELECT ist.store_code, ist.sku, ist.product_name,
                   ist.category, ist.qty_available, ist.reorder_point,
                   ist.stock_status, ist.supplier_name,
                   ist.sla_delivery_hours
            FROM inventory_status ist
            WHERE ist.stock_status IN ('STOCKOUT', 'LOW')
            ORDER BY CASE ist.stock_status WHEN 'STOCKOUT' THEN 0 ELSE 1 END,
                     ist.qty_available ASC
            LIMIT 15
        """,
        "description": "Products currently at risk of stockout across all stores",
    },
    {
        "name": "category_margin",
        "patterns": ["margin by category", "category margin", "category profit",
                      "margin analysis", "profit category"],
        "sql": """
            SELECT p.category,
                   SUM(oi.quantity) AS units_sold,
                   ROUND(SUM(oi.line_total), 2) AS revenue,
                   ROUND(SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity), 2) AS gross_margin,
                   ROUND((SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity))
                         / SUM(oi.line_total) * 100, 1) AS margin_pct
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o   ON oi.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY p.category
            ORDER BY margin_pct DESC
        """,
        "description": "Gross margin by product category",
    },
    {
        "name": "supplier_performance",
        "patterns": ["supplier perform", "supplier score", "fill rate",
                      "supplier quality", "vendor", "supplier rating"],
        "sql": """
            SELECT sup.supplier_name, sup.sla_delivery_hours,
                   ROUND(AVG(poi.quantity_received * 1.0 / poi.quantity_ordered), 3) AS avg_fill_rate,
                   COUNT(DISTINCT po.po_id) AS total_pos,
                   SUM(poi.quantity_ordered) AS total_ordered,
                   SUM(poi.quantity_received) AS total_received
            FROM purchase_order_items poi
            JOIN purchase_orders po ON poi.po_id = po.po_id
            JOIN suppliers sup     ON po.supplier_id = sup.supplier_id
            WHERE po.po_status = 'received'
            GROUP BY sup.supplier_id
            ORDER BY avg_fill_rate ASC
        """,
        "description": "Supplier performance metrics including fill rate",
    },
    {
        "name": "hourly_orders",
        "patterns": ["peak hour", "peak order", "busy hour", "busiest hour",
                      "hourly", "time of day", "order pattern",
                      "peak time", "busiest", "what are the peak"],
        "sql": """
            SELECT CAST(strftime('%H', o.ordered_at) AS INTEGER) AS hour_of_day,
                   COUNT(*) AS order_count,
                   ROUND(AVG(o.order_total), 2) AS avg_order_value
            FROM orders o
            WHERE o.order_status = 'delivered'
            GROUP BY strftime('%H', o.ordered_at)
            ORDER BY order_count DESC
            LIMIT 10
        """,
        "description": "Peak order hours across all stores",
    },
    {
        "name": "daily_sales_trend",
        "patterns": ["sales trend", "daily sales", "revenue trend", "sales over time",
                      "sales history", "how have sales"],
        "sql": """
            SELECT sale_date,
                   SUM(total_units_sold) AS total_units,
                   ROUND(SUM(total_revenue), 2) AS total_revenue
            FROM daily_sales
            WHERE sale_date >= DATE('now', '-14 days')
            GROUP BY sale_date
            ORDER BY sale_date DESC
        """,
        "description": "Daily sales trend for the last 14 days",
    },
]


def sql_query_tool(user_query: str) -> dict:
    """
    Match a natural-language query to a pre-built SQL template and execute it.

    In production, an LLM would generate the SQL dynamically. For this demo,
    we use pattern matching against known query templates — the same queries
    we designed and tested in Phase 2.
    """
    user_lower = user_query.lower()

    # Score each template by how many patterns match
    best_score = 0
    best_template = None
    for template in SQL_TEMPLATES:
        score = sum(1 for p in template["patterns"] if p in user_lower)
        if score > best_score:
            best_score = score
            best_template = template

    if best_score == 0 or best_template is None:
        return {
            "tool": "sql_query",
            "success": False,
            "error": "Could not match your query to a known SQL template.",
            "suggestion": "Try: 'revenue by store', 'top products', 'low stock alert', "
                          "'category margin', 'supplier performance', 'peak hours', "
                          "or 'daily sales trend'.",
        }

    # Check if database is ready
    if not DB_PATH.exists():
        return {
            "tool": "sql_query",
            "success": False,
            "error": "Database not found. Click 'Generate Data' in the sidebar to create it.",
        }

    # Execute the matched SQL
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        # Verify the table exists
        tbl_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
        if not tbl_check:
            conn.close()
            return {
                "tool": "sql_query",
                "success": False,
                "error": "Database is empty. Click 'Generate Data' in the sidebar first.",
            }
        cur = conn.execute(best_template["sql"])
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        return {
            "tool": "sql_query",
            "success": True,
            "template": best_template["name"],
            "description": best_template["description"],
            "row_count": len(rows),
            "data": rows,
        }
    except Exception as e:
        return {
            "tool": "sql_query",
            "success": False,
            "error": str(e),
            "template": best_template["name"],
        }


# =============================================================================
# TOOL 2: Policy RAG Tool
# =============================================================================

def rag_search_tool(user_query: str) -> dict:
    """
    Search the ChromaDB vector store for relevant policy/contract chunks.
    Wraps phase3_rag/query_docs.py's query_policy().
    """
    try:
        # Add the phase3_rag directory to path for import
        import sys
        rag_path = str(BASE / "phase3_rag")
        if rag_path not in sys.path:
            sys.path.insert(0, rag_path)
        from query_docs import query_policy
    except ImportError as e:
        return {
            "tool": "rag_search",
            "success": False,
            "error": f"Cannot import RAG module. Run embed_docs.py first. ({e})",
        }

    try:
        results = query_policy(user_query, k=3)
        return {
            "tool": "rag_search",
            "success": True,
            "result_count": len(results),
            "data": results,
        }
    except Exception as e:
        return {
            "tool": "rag_search",
            "success": False,
            "error": str(e),
            "suggestion": "Run 'python phase3_rag/embed_docs.py' first.",
        }


# =============================================================================
# TOOL 3: Forecast Tool
# =============================================================================

def forecast_tool(user_query: str) -> dict:
    """
    Query the forecast_results table. Extracts optional filters from NL.
    Wraps phase4_forecasting/forecast_tool.py's forecast_demand().
    """
    try:
        import sys
        fcst_path = str(BASE / "phase4_forecasting")
        if fcst_path not in sys.path:
            sys.path.insert(0, fcst_path)
        from forecast_tool import forecast_demand
    except ImportError as e:
        return {
            "tool": "forecast",
            "success": False,
            "error": f"Cannot import forecast module. Run train_forecast.py first. ({e})",
        }

    # Extract optional filters from NL query
    q = user_query.lower()
    kwargs: dict[str, Any] = {"days": 7}

    # Category filter
    for cat in ["dairy", "beverages", "snacks", "fmcg", "bakery",
                "fruits & vegetables", "meat & poultry", "frozen foods"]:
        if cat in q:
            kwargs["category"] = cat.title() if "&" not in cat else cat.title()
            break

    # Store filter
    store_match = re.search(r"store\s*(\d+)", q)
    if store_match:
        kwargs["store_id"] = int(store_match.group(1))

    # Product filter
    prod_match = re.search(r"product\s*(\d+)", q)
    if prod_match:
        kwargs["product_id"] = int(prod_match.group(1))

    # Low stock only
    if any(w in q for w in ["low stock", "at risk", "stockout", "critical"]):
        kwargs["low_stock_only"] = True

    # Horizon
    day_match = re.search(r"(\d+)[\s-]*day", q)
    if day_match:
        kwargs["days"] = min(int(day_match.group(1)), 30)

    try:
        result = forecast_demand(**kwargs)
        result["tool"] = "forecast"
        result["success"] = result["total_forecasted"] > 0
        return result
    except Exception as e:
        return {
            "tool": "forecast",
            "success": False,
            "error": str(e),
            "suggestion": "Run 'python phase4_forecasting/train_forecast.py' first.",
        }
