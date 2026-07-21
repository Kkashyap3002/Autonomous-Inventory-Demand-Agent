"""
Phase 2: Analytical SQL Query Workbook
=======================================
12 queries of progressive complexity that answer real retail/quick-commerce
questions.  Each query includes:
  - WHY a data analyst would ask this
  - The SQL (executed against aida.db)
  - Commentary on the technique used

Run:  python analytical_queries.py
"""

import sqlite3
import os
from pathlib import Path

DB = Path(__file__).resolve().parent / "aida.db"


def run(label: str, why: str, sql: str, technique: str):
    """Execute a query and pretty-print the results."""
    print("-" * 72)
    print(f"Q: {label}")
    print(f"   WHY: {why}")
    print(f"   TECHNIQUE: {technique}")
    print("-" * 72)
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql)
    rows = cur.fetchmany(10)
    if not rows:
        print("   (no results)")
    else:
        cols = rows[0].keys()
        widths = [max(len(str(c)), max(len(str(r[c])) for r in rows)) for c in cols]
        header = " | ".join(str(c).ljust(w) for c, w in zip(cols, widths))
        print(f"   {header}")
        print("   " + "-" * len(header))
        for row in rows:
            print("   " + " | ".join(str(row[c]).ljust(w) for c, w in zip(cols, widths)))
    if len(rows) == 10:
        cur.execute(f"SELECT COUNT(*) FROM ({sql})")
        total = cur.fetchone()[0]
        print(f"   ... and {total - 10} more rows")
    conn.close()
    print()


# =============================================================================
# QUERY SET
# =============================================================================

QUERIES = [
    # -- LEVEL 1: Basic Aggregations -------------------------------------
    {
        "label": "1. Revenue & Orders by Store (Last 30 Days)",
        "why": (
            "The most basic operational dashboard query. A business analyst sees\n"
            "this every morning. It answers: which store generates the most revenue?"
        ),
        "technique": "GROUP BY, SUM, COUNT, date filtering",
        "sql": """
            SELECT
                s.store_code,
                s.city,
                COUNT(DISTINCT o.order_id)          AS total_orders,
                ROUND(SUM(o.order_total), 2)        AS total_revenue,
                ROUND(AVG(o.order_total), 2)        AS avg_order_value,
                ROUND(SUM(o.discount_total), 2)     AS total_discounts
            FROM orders o
            JOIN stores s ON o.store_id = s.store_id
            WHERE o.order_status = 'delivered'
              AND o.ordered_at >= DATE('now', '-30 days')
            GROUP BY s.store_code, s.city
            ORDER BY total_revenue DESC
        """,
    },
    {
        "label": "2. Top 10 Products by Revenue & Margin %",
        "why": (
            "Product-level contribution analysis. Identifies which SKUs drive\n"
            "revenue AND which have the best margin -- not always the same thing."
        ),
        "technique": "Multi-table JOIN, calculated columns, ORDER BY, LIMIT",
        "sql": """
            SELECT
                p.sku,
                p.product_name,
                p.category,
                SUM(oi.quantity)                        AS units_sold,
                ROUND(SUM(oi.line_total), 2)            AS revenue,
                ROUND(SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity), 2) AS gross_margin,
                ROUND(
                    (SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity))
                    / SUM(oi.line_total) * 100, 1
                ) AS margin_pct
            FROM order_items oi
            JOIN products p ON oi.product_id = p.product_id
            JOIN orders o   ON oi.order_id = o.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY p.product_id
            ORDER BY revenue DESC
            LIMIT 10
        """,
    },
    # -- LEVEL 2: Inventory & Stock Health -------------------------------
    {
        "label": "3. Products at Risk of Stockout (Current Snapshot)",
        "why": (
            "The quintessential quick-commerce query. If a dark store runs out\n"
            "of milk at 8am, every coffee order fails. The agent must flag these\n"
            "BEFORE the stockout happens."
        ),
        "technique": "CASE expression for bucketing, multi-table JOIN, filtering",
        "sql": """
            SELECT
                ist.store_code,
                ist.city,
                ist.sku,
                ist.product_name,
                ist.category,
                ist.qty_on_hand,
                ist.qty_available,
                ist.reorder_point,
                ist.stock_status,
                ist.supplier_name,
                ist.sla_delivery_hours
            FROM inventory_status ist
            WHERE ist.stock_status IN ('STOCKOUT', 'LOW')
            ORDER BY
                CASE ist.stock_status WHEN 'STOCKOUT' THEN 0 ELSE 1 END,
                ist.qty_available ASC
            LIMIT 15
        """,
    },
    {
        "label": "4. Days of Inventory Remaining (Run-Rate Based)",
        "why": (
            "Reorder point alone is dumb -- a product selling 200/day needs\n"
            "different treatment than one selling 5/day. 'Days of inventory'\n"
            "normalizes stock against actual sales velocity."
        ),
        "technique": "CTE for sales velocity, then dividing stock by daily rate",
        "sql": """
            WITH daily_velocity AS (
                SELECT
                    product_id,
                    store_id,
                    ROUND(SUM(total_units_sold) * 1.0 / COUNT(DISTINCT sale_date), 1) AS avg_daily_sales
                FROM daily_sales
                WHERE sale_date >= DATE('now', '-14 days')
                GROUP BY product_id, store_id
            )
            SELECT
                ist.store_code,
                ist.sku,
                ist.product_name,
                ist.qty_available,
                COALESCE(dv.avg_daily_sales, 0)                     AS daily_sales_rate,
                CASE
                    WHEN dv.avg_daily_sales > 0
                    THEN ROUND(ist.qty_available / dv.avg_daily_sales, 1)
                    ELSE NULL
                END                                                   AS days_of_stock,
                CASE
                    WHEN ist.qty_available = 0 THEN 'OUT'
                    WHEN dv.avg_daily_sales = 0 THEN 'NO_SALES'
                    WHEN ist.qty_available / dv.avg_daily_sales < 2 THEN 'CRITICAL'
                    WHEN ist.qty_available / dv.avg_daily_sales < 5 THEN 'LOW'
                    WHEN ist.qty_available / dv.avg_daily_sales < 14 THEN 'OK'
                    ELSE 'HEALTHY'
                END                                                   AS velocity_adjusted_status
            FROM inventory_status ist
            LEFT JOIN daily_velocity dv
                ON ist.product_id = dv.product_id AND ist.store_id = dv.store_id
            WHERE ist.qty_available > 0
            ORDER BY
                CASE WHEN dv.avg_daily_sales = 0 THEN 999
                     ELSE ist.qty_available / dv.avg_daily_sales END ASC
            LIMIT 15
        """,
    },
    # -- LEVEL 3: Time-Series & Window Functions -------------------------
    {
        "label": "5. 7-Day Moving Average of Revenue (Per Store)",
        "why": (
            "Smooths out daily noise to reveal the underlying trend. The agent\n"
            "can use this to detect anomalies: 'revenue today is 40% below the\n"
            "7-day MA -- check if the app is down or a competitor launched a promo.'"
        ),
        "technique": "Window functions: AVG() OVER (PARTITION BY ... ROWS BETWEEN)",
        "sql": """
            SELECT
                store_id,
                sale_date,
                daily_revenue,
                ROUND(
                    AVG(daily_revenue) OVER (
                        PARTITION BY store_id
                        ORDER BY sale_date
                        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                    ), 2
                ) AS ma_7day_revenue
            FROM (
                SELECT
                    store_id,
                    sale_date,
                    SUM(total_revenue) AS daily_revenue
                FROM daily_sales
                GROUP BY store_id, sale_date
            )
            ORDER BY store_id, sale_date DESC
            LIMIT 21
        """,
    },
    {
        "label": "6. Week-over-Week Growth Rate by Category",
        "why": (
            "Shows which categories are trending up or down. Used for\n"
            "assortment planning: growing categories get more shelf space,\n"
            "declining categories get marked down."
        ),
        "technique": "CTE + self-join for period-over-period comparison",
        "sql": """
            WITH weekly_revenue AS (
                SELECT
                    p.category,
                    strftime('%Y-%W', o.ordered_at) AS week,
                    SUM(oi.line_total)               AS revenue
                FROM order_items oi
                JOIN orders o   ON oi.order_id = o.order_id
                JOIN products p ON oi.product_id = p.product_id
                WHERE o.order_status = 'delivered'
                GROUP BY p.category, strftime('%Y-%W', o.ordered_at)
            ),
            latest_weeks AS (
                SELECT category, week, revenue
                FROM weekly_revenue
                WHERE week IN (
                    SELECT DISTINCT week FROM weekly_revenue
                    ORDER BY week DESC LIMIT 2
                )
            )
            SELECT
                curr.category,
                curr.week                                 AS current_week,
                ROUND(curr.revenue, 2)                    AS current_revenue,
                ROUND(prev.revenue, 2)                    AS previous_revenue,
                ROUND((curr.revenue - prev.revenue) / prev.revenue * 100, 1) AS wow_growth_pct
            FROM latest_weeks curr
            JOIN latest_weeks prev
                ON curr.category = prev.category
               AND curr.week > prev.week
            ORDER BY wow_growth_pct DESC
        """,
    },
    # -- LEVEL 4: Complex Analytical Patterns ----------------------------
    {
        "label": "7. Promotion Lift Analysis (Sales During vs. Before Promo)",
        "why": (
            "The business needs to know: did the promotion actually grow sales,\n"
            "or did it just pull forward demand that would have happened anyway?\n"
            "Compare sales during promo period to the baseline period before it."
        ),
        "technique": "Correlated subquery, date arithmetic, lift calculation",
        "sql": """
            WITH promo_sales AS (
                SELECT
                    pr.promotion_id,
                    pr.promotion_name,
                    pr.promotion_type,
                    pr.discount_pct,
                    SUM(oi.quantity)    AS promo_units,
                    SUM(oi.line_total)  AS promo_revenue
                FROM promotions pr
                JOIN promotion_products pp ON pr.promotion_id = pp.promotion_id
                JOIN order_items oi         ON pp.product_id = oi.product_id
                JOIN orders o               ON oi.order_id = o.order_id
                    AND o.ordered_at BETWEEN pr.starts_at AND pr.ends_at
                    AND o.order_status = 'delivered'
                    AND o.promotion_id = pr.promotion_id
                GROUP BY pr.promotion_id
            ),
            baseline_sales AS (
                SELECT
                    pr.promotion_id,
                    SUM(oi.quantity)    AS baseline_units,
                    SUM(oi.line_total)  AS baseline_revenue
                FROM promotions pr
                JOIN promotion_products pp ON pr.promotion_id = pp.promotion_id
                JOIN order_items oi         ON pp.product_id = oi.product_id
                JOIN orders o               ON oi.order_id = o.order_id
                    AND o.ordered_at BETWEEN
                        DATETIME(pr.starts_at, '-7 days')
                        AND pr.starts_at
                    AND o.order_status = 'delivered'
                GROUP BY pr.promotion_id
            )
            SELECT
                ps.promotion_name,
                ps.promotion_type,
                ps.discount_pct,
                ROUND(ps.promo_revenue, 2)                  AS promo_revenue,
                ROUND(bs.baseline_revenue, 2)               AS baseline_revenue,
                ROUND((ps.promo_revenue - bs.baseline_revenue)
                      / bs.baseline_revenue * 100, 1)       AS revenue_lift_pct,
                ROUND((ps.promo_units - bs.baseline_units)
                      * 1.0 / bs.baseline_units * 100, 1)   AS unit_lift_pct
            FROM promo_sales ps
            JOIN baseline_sales bs ON ps.promotion_id = bs.promotion_id
            ORDER BY revenue_lift_pct DESC
        """,
    },
    {
        "label": "8. Run Rate (units/day) for Each Product-Store (Forecast-Ready)",
        "why": (
            "This query is the direct input to your ML model (Phase 4).\n"
            "It provides daily sales at (product, store) grain with a derived\n"
            "velocity column -- the minimum viable feature for demand forecasting."
        ),
        "technique": "Aggregation at multiple grains, handling zero-sales days",
        "sql": """
            SELECT
                ds.product_id,
                p.sku,
                p.product_name,
                p.category,
                ds.store_id,
                s.store_code,
                COUNT(ds.sale_date)                                 AS days_with_sales,
                SUM(ds.total_units_sold)                            AS total_units,
                ROUND(AVG(ds.total_units_sold), 2)                  AS avg_units_per_day,
                ROUND(SUM(ds.total_units_sold) * 1.0 / 90, 2)      AS daily_run_rate_90d,
                ROUND(SUM(ds.total_units_sold) * 1.0 / 30, 2)      AS daily_run_rate_30d,
                ROUND(SUM(ds.total_units_sold) * 1.0 / 7, 2)       AS daily_run_rate_7d,
                CASE WHEN SUM(ds.total_units_sold) * 1.0 / 7
                          > SUM(ds.total_units_sold) * 1.0 / 30 * 1.2
                     THEN 'ACCELERATING'
                     WHEN SUM(ds.total_units_sold) * 1.0 / 7
                          < SUM(ds.total_units_sold) * 1.0 / 30 * 0.8
                     THEN 'DECELERATING'
                     ELSE 'STABLE'
                END AS trend_direction
            FROM daily_sales ds
            JOIN products p ON ds.product_id = p.product_id
            JOIN stores s   ON ds.store_id = s.store_id
            GROUP BY ds.product_id, ds.store_id
            ORDER BY daily_run_rate_7d DESC
            LIMIT 15
        """,
    },
    {
        "label": "9. Wastage Rate by Category (Perishable vs Non-Perishable)",
        "why": (
            "Shrinkage/wastage is a hidden cost that erodes margin. Quick-commerce\n"
            "carries many perishables (dairy, produce, meat). This query finds\n"
            "which categories lose the most to wastage."
        ),
        "technique": "Conditional aggregation with CASE inside SUM",
        "sql": """
            SELECT
                p.category,
                p.is_perishable,
                COUNT(DISTINCT p.product_id)                        AS product_count,
                SUM(CASE WHEN it.transaction_type = 'sale'
                    THEN ABS(it.quantity) ELSE 0 END)               AS units_sold,
                SUM(CASE WHEN it.transaction_type = 'adjustment'
                    THEN ABS(it.quantity) ELSE 0 END)               AS units_wasted,
                ROUND(
                    SUM(CASE WHEN it.transaction_type = 'adjustment'
                        THEN ABS(it.quantity) ELSE 0 END) * 100.0
                    / NULLIF(SUM(ABS(it.quantity)), 0), 2
                )                                                     AS wastage_pct,
                ROUND(SUM(CASE WHEN it.transaction_type = 'adjustment'
                    THEN ABS(it.quantity) * it.unit_cost ELSE 0 END), 2) AS wastage_cost
            FROM inventory_transactions it
            JOIN products p ON it.product_id = p.product_id
            WHERE it.transaction_type IN ('sale', 'adjustment')
            GROUP BY p.category, p.is_perishable
            ORDER BY wastage_pct DESC
        """,
    },
    {
        "label": "10. Supplier Fill Rate & On-Time Performance",
        "why": (
            "If your supplier delivers 80% of what you ordered 2 days late,\n"
            "your inventory model must account for that uncertainty. This query\n"
            "feeds into the supplier risk score."
        ),
        "technique": "Subquery for actual-vs-ordered comparison, fill rate",
        "sql": """
            SELECT
                sup.supplier_name,
                sup.sla_delivery_hours,
                COUNT(po.po_id)                                         AS total_pos,
                ROUND(AVG(poi.quantity_received * 1.0
                          / poi.quantity_ordered), 3)                   AS avg_fill_rate,
                SUM(poi.quantity_ordered)                               AS total_ordered,
                SUM(poi.quantity_received)                              AS total_received,
                SUM(poi.quantity_ordered) - SUM(poi.quantity_received)  AS total_shortfall,
                ROUND(SUM(poi.quantity_received * poi.unit_cost), 2)   AS total_spend
            FROM purchase_orders po
            JOIN purchase_order_items poi ON po.po_id = poi.po_id
            JOIN suppliers sup            ON po.supplier_id = sup.supplier_id
            WHERE po.po_status = 'received'
            GROUP BY sup.supplier_id
            ORDER BY avg_fill_rate ASC
        """,
    },
    {
        "label": "11. Frequently Co-Purchased Products (Basket Affinity)",
        "why": (
            "Market basket analysis. If customers who buy bread also buy butter\n"
            "70% of the time, you should never stock out of both simultaneously.\n"
            "Also used for promo bundling and recommendation engines."
        ),
        "technique": "Self-join on order_items to find product pairs in same order",
        "sql": """
            WITH pairs AS (
                SELECT
                    a.product_id AS product_a,
                    b.product_id AS product_b,
                    COUNT(DISTINCT a.order_id) AS co_occurrence_count
                FROM order_items a
                JOIN order_items b ON a.order_id = b.order_id AND a.product_id < b.product_id
                GROUP BY a.product_id, b.product_id
            ),
            product_order_counts AS (
                SELECT product_id, COUNT(DISTINCT order_id) AS order_count
                FROM order_items
                GROUP BY product_id
            )
            SELECT
                pa.sku                    AS sku_a,
                pa.product_name          AS product_a,
                pb.sku                    AS sku_b,
                pb.product_name          AS product_b,
                p.co_occurrence_count,
                ROUND(p.co_occurrence_count * 1.0
                      / MIN(oa.order_count, ob.order_count), 2) AS affinity_score
            FROM pairs p
            JOIN products pa         ON p.product_a = pa.product_id
            JOIN products pb         ON p.product_b = pb.product_id
            JOIN product_order_counts oa ON p.product_a = oa.product_id
            JOIN product_order_counts ob ON p.product_b = ob.product_id
            WHERE p.co_occurrence_count >= 20
            ORDER BY affinity_score DESC
            LIMIT 15
        """,
    },
    {
        "label": "12. Hourly Order Heatmap (Peak Demand Hours)",
        "why": (
            "Staffing and inventory picking schedules depend on knowing peak hours.\n"
            "If 40% of orders come between 6-9 PM, you need more pickers then.\n"
            "Also: the agent can use this to trigger 'pre-peak restocking' alerts."
        ),
        "technique": "Extract hour from timestamp, pivot-style aggregation",
        "sql": """
            SELECT
                s.store_code,
                CAST(strftime('%H', o.ordered_at) AS INTEGER) AS hour_of_day,
                COUNT(*)                                      AS order_count,
                ROUND(AVG(o.order_total), 2)                  AS avg_order_value,
                SUM(CASE WHEN o.promotion_id IS NOT NULL THEN 1 ELSE 0 END) AS promo_orders
            FROM orders o
            JOIN stores s ON o.store_id = s.store_id
            WHERE o.order_status = 'delivered'
            GROUP BY s.store_code, strftime('%H', o.ordered_at)
            ORDER BY s.store_code, order_count DESC
            LIMIT 25
        """,
    },
]


def main():
    if not DB.exists():
        print("ERROR: aida.db not found. Run 'python load_to_sqlite.py' first.")
        return

    print("=" * 72)
    print("  AIDA -- Phase 2: Analytical SQL Query Workbook")
    print("=" * 72)
    print(f"  Database: {DB.resolve()}")
    print()

    for q in QUERIES:
        run(q["label"], q["why"], q["sql"], q["technique"])


if __name__ == "__main__":
    main()
