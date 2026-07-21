
"""
Phase 2: Load CSVs into SQLite & Create Analytical Views
==========================================================
One command:  python load_to_sqlite.py
Creates:      aida.db  (SQLite, zero config)
Also adds:    helper views for the LangGraph agent to query
"""
import csv
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # AIDA/
DATA_DIR = BASE / "phase1_schema" / "synthetic_data"
DB_PATH = Path(__file__).resolve().parent / "aida.db"  # phase2_sql/aida.db

# Map CSV → (table_name, column_type_overrides)
TABLES = {
    "suppliers": (
        "suppliers",
        {"supplier_id": "INTEGER PRIMARY KEY", "is_active": "INTEGER"},
    ),
    "stores": (
        "stores",
        {"store_id": "INTEGER PRIMARY KEY", "is_active": "INTEGER"},
    ),
    "products": (
        "products",
        {
            "product_id": "INTEGER PRIMARY KEY",
            "is_perishable": "INTEGER",
            "unit_cost": "REAL",
            "selling_price": "REAL",
        },
    ),
    "promotions": (
        "promotions",
        {"promotion_id": "INTEGER PRIMARY KEY", "is_active": "INTEGER", "discount_pct": "REAL"},
    ),
    "promotion_products": (
        "promotion_products",
        {"promotion_id": "INTEGER", "product_id": "INTEGER"},
    ),
    "inventory_levels": (
        "inventory_levels",
        {"inventory_id": "INTEGER PRIMARY KEY", "qty_on_hand": "INTEGER", "qty_reserved": "INTEGER",
         "reorder_point": "INTEGER", "reorder_qty": "INTEGER"},
    ),
    "inventory_transactions": (
        "inventory_transactions",
        {"transaction_id": "INTEGER PRIMARY KEY", "quantity": "INTEGER",
         "running_qty": "INTEGER", "unit_cost": "REAL"},
    ),
    "orders": (
        "orders",
        {"order_id": "INTEGER PRIMARY KEY", "order_total": "REAL",
         "discount_total": "REAL"},
    ),
    "order_items": (
        "order_items",
        {"order_item_id": "INTEGER PRIMARY KEY", "quantity": "INTEGER",
         "unit_price": "REAL", "line_total": "REAL"},
    ),
    "purchase_orders": (
        "purchase_orders",
        {"po_id": "INTEGER PRIMARY KEY", "total_cost": "REAL"},
    ),
    "purchase_order_items": (
        "purchase_order_items",
        {"po_item_id": "INTEGER PRIMARY KEY", "quantity_ordered": "INTEGER",
         "quantity_received": "INTEGER", "unit_cost": "REAL"},
    ),
}

POST_LOAD_SQL = """
-- =============================================================================
-- Analytical views (materialized as tables for speed — SQLite doesn't do
-- materialized views, so we create tables and populate them)
-- =============================================================================

-- View 1: Daily sales at (date, product, store) grain — the forecasting table
DROP TABLE IF EXISTS daily_sales;
CREATE TABLE daily_sales AS
SELECT
    DATE(ot.created_at)         AS sale_date,
    oi.product_id,
    o.store_id,
    COUNT(DISTINCT o.order_id)  AS order_count,
    SUM(oi.quantity)            AS total_units_sold,
    SUM(oi.line_total)          AS total_revenue,
    SUM(oi.line_total) - SUM(p.unit_cost * oi.quantity) AS estimated_gross_margin
FROM order_items oi
JOIN orders o        ON oi.order_id = o.order_id
JOIN products p      ON oi.product_id = p.product_id
JOIN inventory_transactions ot ON ot.reference_id = oi.order_item_id
    AND ot.transaction_type = 'sale'
    AND ot.reference_type = 'order'
WHERE o.order_status = 'delivered'
GROUP BY 1, 2, 3;

-- Index the view table
CREATE INDEX idx_daily_sales_date ON daily_sales(sale_date);
CREATE INDEX idx_daily_sales_prod  ON daily_sales(product_id);
CREATE INDEX idx_daily_sales_store ON daily_sales(store_id);

-- View 2: Product-store current state (join inventory with product info)
DROP TABLE IF EXISTS inventory_status;
CREATE TABLE inventory_status AS
SELECT
    il.store_id,
    s.store_code,
    s.city,
    il.product_id,
    p.sku,
    p.product_name,
    p.category,
    p.subcategory,
    p.selling_price,
    p.unit_cost,
    p.is_perishable,
    p.shelf_life_days,
    p.supplier_id,
    sup.supplier_name,
    sup.sla_delivery_hours,
    il.qty_on_hand,
    il.qty_reserved,
    (il.qty_on_hand - il.qty_reserved) AS qty_available,
    il.reorder_point,
    il.reorder_qty,
    CASE WHEN (il.qty_on_hand - il.qty_reserved) <= il.reorder_point THEN 1 ELSE 0 END AS needs_replenishment,
    CASE WHEN (il.qty_on_hand - il.qty_reserved) = 0 THEN 'STOCKOUT'
         WHEN (il.qty_on_hand - il.qty_reserved) <= il.reorder_point THEN 'LOW'
         WHEN (il.qty_on_hand - il.qty_reserved) <= il.reorder_point * 3 THEN 'OK'
         ELSE 'HEALTHY' END AS stock_status
FROM inventory_levels il
JOIN stores s       ON il.store_id = s.store_id
JOIN products p     ON il.product_id = p.product_id
JOIN suppliers sup  ON p.supplier_id = sup.supplier_id;

CREATE INDEX idx_inv_status_store ON inventory_status(store_id);
CREATE INDEX idx_inv_status_cat   ON inventory_status(category);
CREATE INDEX idx_inv_status_stock ON inventory_status(stock_status);

-- View 3: Supplier performance metrics
DROP TABLE IF EXISTS supplier_performance;
CREATE TABLE supplier_performance AS
SELECT
    po.supplier_id,
    sup.supplier_name,
    sup.sla_delivery_hours,
    COUNT(DISTINCT po.po_id)                                AS total_pos,
    ROUND(AVG(poi.quantity_received * 1.0 / poi.quantity_ordered), 3) AS avg_fill_rate,
    COUNT(DISTINCT CASE WHEN po.po_status = 'received' THEN po.po_id END) AS fulfilled_pos
FROM purchase_order_items poi
JOIN purchase_orders po ON poi.po_id = po.po_id
JOIN suppliers sup     ON po.supplier_id = sup.supplier_id
GROUP BY 1;

CREATE INDEX idx_supp_perf_supplier ON supplier_performance(supplier_id);
"""


def infer_sqlite_type(col_name: str, sample_val: str, overrides: dict) -> str:
    """Map a CSV sample value + column name to a SQLite type."""
    if col_name in overrides:
        return overrides[col_name]
    if sample_val is None or sample_val == "":
        return "TEXT"
    try:
        int(sample_val)
        return "INTEGER"
    except ValueError:
        pass
    try:
        float(sample_val)
        return "REAL"
    except ValueError:
        pass
    if sample_val.lower() in ("true", "false"):
        return "INTEGER"  # SQLite has no BOOLEAN
    return "TEXT"


def load_table(conn: sqlite3.Connection, csv_path: Path,
               table_name: str, type_overrides: dict) -> int:
    """Load a CSV into a SQLite table, auto-creating the schema."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"  SKIP {table_name}: empty CSV")
        return 0

    # Infer column types from the first data row
    cols = list(rows[0].keys())
    col_defs = []
    for col in cols:
        sample = rows[0].get(col)
        sql_type = infer_sqlite_type(col, sample, type_overrides)
        col_defs.append(f'"{col}" {sql_type}')

    ddl = f'DROP TABLE IF EXISTS "{table_name}"; CREATE TABLE "{table_name}" ({", ".join(col_defs)});'
    conn.executescript(ddl)

    # Insert data
    placeholders = ", ".join(["?" for _ in cols])
    insert_sql = f'INSERT INTO "{table_name}" ({", ".join(f'"{c}"' for c in cols)}) VALUES ({placeholders})'

    batch = []
    for row in rows:
        values = []
        for col in cols:
            v = row.get(col, "")
            if v == "" or v == "None":
                values.append(None)
            elif v.lower() == "true":
                values.append(1)
            elif v.lower() == "false":
                values.append(0)
            else:
                values.append(v)
        batch.append(tuple(values))

    conn.executemany(insert_sql, batch)
    conn.commit()
    return len(rows)


def main():
    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(str(DB_PATH))

    print("=" * 60)
    print("AIDA — Loading synthetic data into SQLite")
    print("=" * 60)

    for csv_file, (table_name, overrides) in TABLES.items():
        csv_path = DATA_DIR / f"{csv_file}.csv"
        if not csv_path.exists():
            print(f"  MISS {csv_path} — skipping")
            continue
        count = load_table(conn, csv_path, table_name, overrides)
        print(f"  OK {table_name:<30} {count:>8,} rows")

    print("\nCreating analytical views ...")
    conn.executescript(POST_LOAD_SQL)
    conn.commit()

    # Quick verification
    print("\nVerification queries:")
    for q, label in [
        ("SELECT COUNT(*) FROM orders", "Total orders"),
        ("SELECT COUNT(*) FROM daily_sales", "Daily sales rows"),
        ("SELECT COUNT(*) FROM inventory_status WHERE stock_status = 'LOW'", "Low-stock items"),
        ("SELECT COUNT(*) FROM inventory_status WHERE stock_status = 'STOCKOUT'", "Stockouts"),
    ]:
        cur = conn.execute(q)
        print(f"  {label:<25} {cur.fetchone()[0]:>8,}")

    conn.close()
    print(f"\nDatabase ready: {DB_PATH.resolve()}")
    print("Next:  python analytical_queries.py  to run the Phase 2 query workbook")


if __name__ == "__main__":
    main()
