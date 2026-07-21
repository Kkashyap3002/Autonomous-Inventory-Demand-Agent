"""
Phase 4: Forecast Tool (for LangGraph Agent)
==============================================
Provides the forecast_demand() function that the agent's Forecast_Tool
will call in Phase 5. Also doubles as a standalone CLI.

Usage:
  python phase4_forecasting/forecast_tool.py                          (summary)
  python phase4_forecasting/forecast_tool.py --product-id 10          (single product)
  python phase4_forecasting/forecast_tool.py --store-id 1 --category Dairy
  python phase4_forecasting/forecast_tool.py --low-stock              (at-risk products)

The function forecast_demand() is importable:
  from phase4_forecasting.forecast_tool import forecast_demand
  result = forecast_demand(product_id=10, store_id=1)
"""

import argparse
import sqlite3
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "phase2_sql" / "aida.db"


def forecast_demand(
    product_id: Optional[int] = None,
    store_id: Optional[int] = None,
    category: Optional[str] = None,
    low_stock_only: bool = False,
    days: int = 7,
) -> dict:
    """
    Query forecast results from the database. This is the function the
    LangGraph agent's Forecast_Tool calls.

    Args:
        product_id:  Filter to a specific product (optional)
        store_id:    Filter to a specific store (optional)
        category:    Filter to a category like 'Dairy', 'Beverages' (optional)
        low_stock_only: Only return products currently below reorder point
        days:        Number of forecast days to return (1-30)

    Returns:
        dict with keys: query_time, filters, total_forecasted, items (list)
    """
    conn = sqlite3.connect(str(DB_PATH))

    # Build WHERE clause
    where = ["1=1"]
    params = {}
    if product_id is not None:
        where.append("fr.product_id = :product_id")
        params["product_id"] = product_id
    if store_id is not None:
        where.append("fr.store_id = :store_id")
        params["store_id"] = store_id
    if category is not None:
        where.append("fr.category = :category")
        params["category"] = category
    if low_stock_only:
        where.append("""
            EXISTS (
                SELECT 1 FROM inventory_status ist
                WHERE ist.product_id = fr.product_id
                  AND ist.store_id = fr.store_id
                  AND ist.stock_status IN ('STOCKOUT', 'LOW')
            )
        """)

    # Forecast for the next `days` days
    max_date = date.today() + timedelta(days=days)

    sql = f"""
        SELECT
            fr.forecast_date,
            fr.product_id,
            fr.sku,
            fr.product_name,
            fr.category,
            fr.store_id,
            fr.store_code,
            fr.forecasted_units,
            ist.qty_available AS current_stock,
            ist.stock_status,
            CASE
                WHEN ist.qty_available = 0 THEN 'STOCKOUT'
                WHEN fr.forecasted_units > 0
                     AND ist.qty_available / fr.forecasted_units < :days
                     THEN 'LIKELY_STOCKOUT'
                WHEN ist.qty_available <= ist.reorder_point THEN 'LOW'
                ELSE 'OK'
            END AS risk_flag
        FROM forecast_results fr
        LEFT JOIN inventory_status ist
            ON fr.product_id = ist.product_id AND fr.store_id = ist.store_id
        WHERE {' AND '.join(where)}
          AND fr.forecast_date <= :max_date
        ORDER BY fr.forecast_date, fr.forecasted_units DESC
    """
    params["max_date"] = max_date.isoformat()
    params["days"] = days

    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()

    if df.empty:
        return {
            "query_time": date.today().isoformat(),
            "filters": {
                "product_id": product_id, "store_id": store_id,
                "category": category, "low_stock_only": low_stock_only,
                "days": days,
            },
            "total_forecasted": 0,
            "items": [],
            "message": "No forecast data found. Run train_forecast.py first.",
        }

    # Summarize by product-store for the agent-friendly response
    summary = (
        df.groupby(["product_id", "sku", "product_name", "category",
                     "store_id", "store_code", "current_stock", "stock_status"])
        .agg(
            total_forecasted=("forecasted_units", "sum"),
            avg_daily=("forecasted_units", "mean"),
            peak_day_units=("forecasted_units", "max"),
            risk_flag=("risk_flag", "first"),
        )
        .reset_index()
        .sort_values("total_forecasted", ascending=False)
    )

    items = summary.to_dict(orient="records")
    for item in items:
        for k in ("total_forecasted", "avg_daily", "peak_day_units"):
            item[k] = round(float(item[k]), 1)
        item["current_stock"] = int(item["current_stock"]) if item["current_stock"] is not None else 0

    return {
        "query_time": date.today().isoformat(),
        "filters": {
            "product_id": product_id, "store_id": store_id,
            "category": category, "low_stock_only": low_stock_only,
            "days": days,
        },
        "total_forecasted": round(float(summary["total_forecasted"].sum()), 1),
        "items": items,
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Query AIDA demand forecasts")
    parser.add_argument("--product-id", type=int, default=None)
    parser.add_argument("--store-id", type=int, default=None)
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--low-stock", action="store_true")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    result = forecast_demand(
        product_id=args.product_id,
        store_id=args.store_id,
        category=args.category,
        low_stock_only=args.low_stock,
        days=args.days,
    )

    print("=" * 60)
    print("AIDA Forecast Tool")
    print("=" * 60)
    print(f"Filters: {result['filters']}")
    print(f"Total forecasted demand ({args.days}d): {result['total_forecasted']:,.1f} units")
    print(f"Product-stores matched: {len(result['items'])}")
    print()

    if not result["items"]:
        print(result.get("message", "No results."))
        return

    for item in result["items"]:
        flag = item.get("risk_flag", "")
        flag_str = f" [{flag}]" if flag and flag != "OK" else ""
        print(f"  {item['sku']:30s} @ {item['store_code']:10s}  "
              f"stock={item['current_stock']:>4d}  "
              f"fcst={item['total_forecasted']:>7.1f}/{args.days}d  "
              f"avg={item['avg_daily']:>5.1f}/day"
              f"{flag_str}")


if __name__ == "__main__":
    main()
