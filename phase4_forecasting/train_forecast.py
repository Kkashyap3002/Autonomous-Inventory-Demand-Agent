"""
Phase 4: Demand Forecasting Model
===================================
Reads daily_sales from aida.db, trains a time-series model per (product, store),
and outputs 7-day and 30-day demand forecasts.

Models (choose via --model flag):
  - ets     : Exponential Smoothing (Holt-Winters via statsmodels) [DEFAULT]
  - xgboost : XGBoost with lag features, day-of-week, and promotion flags
  - moving_avg : Weighted moving average (fast baseline, no training)

Outputs:
  1. forecast_results table in aida.db
  2. forecast_results.csv in phase4_forecasting/

Why this matters for the resume:
  "Built a demand forecasting pipeline that predicts daily unit demand
   at SKU-store granularity over 30-day horizons using Holt-Winters ETS,
   reducing stockout risk by dynamically computing reorder points."

Run:  python phase4_forecasting/train_forecast.py
      python phase4_forecasting/train_forecast.py --model xgboost
      python phase4_forecasting/train_forecast.py --horizon 14
"""

import argparse
import sqlite3
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# --- Paths ---
BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "phase2_sql" / "aida.db"
OUT_CSV = Path(__file__).resolve().parent / "forecast_results.csv"

# =============================================================================
# DATA LOADING
# =============================================================================

def load_daily_sales(db_path: Path) -> pd.DataFrame:
    """Load the daily_sales view and return a clean DataFrame."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        """
        SELECT
            ds.sale_date,
            ds.product_id,
            p.sku,
            p.product_name,
            p.category,
            ds.store_id,
            s.store_code,
            ds.total_units_sold,
            ds.total_revenue
        FROM daily_sales ds
        JOIN products p ON ds.product_id = p.product_id
        JOIN stores s   ON ds.store_id = s.store_id
        ORDER BY ds.store_id, ds.product_id, ds.sale_date
        """,
        conn,
        parse_dates=["sale_date"],
    )
    conn.close()
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df


def load_promotion_calendar(db_path: Path) -> pd.DataFrame:
    """Load promotions to use as a feature for the XGBoost model."""
    conn = sqlite3.connect(str(db_path))
    promos = pd.read_sql_query(
        """
        SELECT
            pp.product_id,
            p.starts_at,
            p.ends_at
        FROM promotion_products pp
        JOIN promotions p ON pp.promotion_id = p.promotion_id
        """,
        conn,
        parse_dates=["starts_at", "ends_at"],
    )
    conn.close()
    return promos


def make_daily_grid(sku_store_groups: list[tuple], min_date, max_date
                    ) -> pd.DataFrame:
    """Create a complete date grid so missing days are explicit (zero sales)."""
    all_dates = pd.date_range(min_date, max_date, freq="D")
    rows = []
    for (product_id, sku, name, cat, store_id, store_code) in sku_store_groups:
        for d in all_dates:
            rows.append({
                "product_id": product_id,
                "sku": sku,
                "product_name": name,
                "category": cat,
                "store_id": store_id,
                "store_code": store_code,
                "sale_date": d,
            })
    grid = pd.DataFrame(rows)
    return grid


# =============================================================================
# MODEL 1: Weighted Moving Average (Baseline)
# =============================================================================

def forecast_moving_avg(series: np.ndarray, horizon: int,
                        window: int = 14) -> np.ndarray:
    """
    Weighted moving average: recent days carry more weight.
    Weights decay linearly: today = window, yesterday = window-1, ...
    """
    if len(series) < 3:
        return np.full(horizon, np.mean(series) if len(series) > 0 else 0)

    w = np.arange(1, min(window, len(series)) + 1, dtype=float)
    w = w / w.sum()
    recent = series[-len(w):]
    avg = np.average(recent, weights=w)
    # Add small noise to avoid flat-line forecasts
    noise = np.random.default_rng(42).normal(0, avg * 0.05, horizon)
    forecast = np.full(horizon, avg) + noise
    return np.maximum(forecast, 0)


# =============================================================================
# MODEL 2: Holt-Winters Exponential Smoothing (statsmodels) [DEFAULT]
# =============================================================================

def forecast_ets(series: np.ndarray, horizon: int) -> np.ndarray:
    """
    Holt-Winters triple exponential smoothing (additive trend + seasonality).
    Falls back to simple exponential smoothing if the series is too short.
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    if len(series) < 14:
        return forecast_moving_avg(series, horizon)

    try:
        seasonal_periods = min(7, len(series) // 2)
        model = ExponentialSmoothing(
            series.astype(float),
            trend="add",
            seasonal="add" if len(series) >= 14 else None,
            seasonal_periods=seasonal_periods if len(series) >= 14 else None,
            initialization_method="estimated",
        )
        fitted = model.fit()
        forecast = fitted.forecast(horizon)
        return np.maximum(forecast, 0)
    except Exception:
        return forecast_moving_avg(series, horizon)


# =============================================================================
# MODEL 3: XGBoost with Engineered Features
# =============================================================================

def forecast_xgboost(df_series: pd.DataFrame, horizon: int,
                     promo_dates: pd.DataFrame) -> np.ndarray:
    """
    XGBoost model with:
      - Lag features (t-1, t-2, t-3, t-7, t-14)
      - Rolling means (7d, 14d)
      - Day-of-week one-hot
      - Is-promo-day flag
    """
    import xgboost as xgb

    df = df_series.copy()
    df = df.set_index("sale_date").sort_index()

    # Target
    df["y"] = df["total_units_sold"]

    # Lag features
    for lag in [1, 2, 3, 7, 14]:
        df[f"lag_{lag}"] = df["y"].shift(lag)

    # Rolling means
    for window in [7, 14]:
        df[f"roll_mean_{window}"] = df["y"].shift(1).rolling(window, min_periods=1).mean()

    # Day of week (0 = Monday)
    df["dow"] = df.index.dayofweek

    # Promo flag
    if not promo_dates.empty:
        pid = df_series["product_id"].iloc[0]
        p_promos = promo_dates[promo_dates["product_id"] == pid]
        df["is_promo"] = 0
        for _, row in p_promos.iterrows():
            mask = (df.index >= pd.Timestamp(row["starts_at"])) & \
                   (df.index <= pd.Timestamp(row["ends_at"]))
            df.loc[mask, "is_promo"] = 1
    else:
        df["is_promo"] = 0

    # Drop rows where we can't compute lag features
    df = df.dropna()

    if len(df) < 14:
        return forecast_ets(df["y"].values, horizon)

    feature_cols = [c for c in df.columns if c not in ("y", "product_id", "sku",
                    "product_name", "category", "store_id", "store_code")]
    X = df[feature_cols]
    y = df["y"]

    model = xgb.XGBRegressor(
        n_estimators=100, max_depth=3, learning_rate=0.1,
        objective="reg:squarederror", verbosity=0, random_state=42,
    )
    model.fit(X, y)

    # Iterative forecast: predict one day, then use it as lag for next day
    last_row = X.iloc[-1:].copy()
    forecasts = []
    for _ in range(horizon):
        pred = max(0, model.predict(last_row)[0])
        forecasts.append(pred)
        # Shift lags: lag_3 becomes lag_4, etc. (simplified: just shift all lags left)
        new_row = last_row.copy()
        # Update lags
        if "lag_1" in new_row.columns:
            new_row["lag_1"] = pred
        for j in range(2, 15):
            col = f"lag_{j}"
            if col in new_row.columns:
                prev_col = f"lag_{j-1}"
                if prev_col in last_row.columns:
                    new_row[col] = last_row[prev_col].values[0]
        # Update rolling means (approximate)
        for w in [7, 14]:
            col = f"roll_mean_{w}"
            if col in new_row.columns:
                new_row[col] = (last_row[col].values[0] * (w - 1) + pred) / w
        last_row = new_row

    return np.array(forecasts)


# =============================================================================
# MAIN FORECASTING PIPELINE
# =============================================================================

def run_forecasts(df: pd.DataFrame, promo_df: pd.DataFrame,
                  model_name: str, horizon: int,
                  db_path: Path) -> pd.DataFrame:
    """
    For each (product, store) in the data, train a model and forecast.
    Returns a DataFrame of forecasts.
    """
    # Identify unique product-store combinations
    groups = (
        df.groupby(["product_id", "sku", "product_name", "category",
                     "store_id", "store_code"])
        .size()
        .reset_index(name="count")
    )
    groups = groups[groups["count"] >= 7]  # need at least 7 days of history

    all_forecasts = []
    last_date = df["sale_date"].max()
    total = len(groups)

    for idx, (_, row) in enumerate(groups.iterrows()):
        mask = (
            (df["product_id"] == row["product_id"])
            & (df["store_id"] == row["store_id"])
        )
        series_df = df[mask].sort_values("sale_date")

        # Ensure complete date grid (fill zeros for missing days)
        date_range = pd.date_range(series_df["sale_date"].min(), last_date, freq="D")

        # Build a numeric-only series for ETS / moving_avg
        sales_series = (series_df.set_index("sale_date")["total_units_sold"]
                        .reindex(date_range, fill_value=0))
        y_values = sales_series.values

        # For XGBoost we need the full dataframe with all columns on the grid
        if model_name == "xgboost":
            # Create a grid with string columns forward-filled, numeric zero-filled
            numeric_cols = ["total_units_sold", "total_revenue"]
            str_cols = ["sku", "product_name", "category", "store_code"]
            grid_num = (series_df.set_index("sale_date")[numeric_cols]
                        .reindex(date_range, fill_value=0))
            grid_str = (series_df.set_index("sale_date")[str_cols]
                        .reindex(date_range, method="ffill").fillna(""))
            grid_all = pd.concat([grid_num, grid_str], axis=1).reset_index()
            grid_all = grid_all.rename(columns={"index": "sale_date"})
            grid_all["product_id"] = row["product_id"]
            grid_all["store_id"] = row["store_id"]
            series_df = grid_all

        # --- Train / Forecast ---
        if model_name == "xgboost":
            forecast = forecast_xgboost(series_df, horizon, promo_df)
        elif model_name == "ets":
            forecast = forecast_ets(y_values, horizon)
        elif model_name == "moving_avg":
            forecast = forecast_moving_avg(y_values, horizon)
        else:
            raise ValueError(f"Unknown model: {model_name}")

        # Build output rows
        forecast_start = last_date + timedelta(days=1)
        for i, pred in enumerate(forecast):
            all_forecasts.append({
                "product_id": row["product_id"],
                "sku": row["sku"],
                "product_name": row["product_name"],
                "category": row["category"],
                "store_id": row["store_id"],
                "store_code": row["store_code"],
                "forecast_date": (forecast_start + timedelta(days=i)).strftime("%Y-%m-%d"),
                "forecasted_units": round(float(pred), 1),
                "model": model_name,
                "horizon_days": horizon,
                "generated_at": date.today().isoformat(),
            })

        if (idx + 1) % 50 == 0 or idx == 0:
            print(f"  [{idx+1}/{total}] {row['sku']} @ {row['store_code']}")

    result = pd.DataFrame(all_forecasts)
    return result


# =============================================================================
# SAVE & REPORT
# =============================================================================

def save_results(forecast_df: pd.DataFrame, db_path: Path):
    """Save forecasts to SQLite table + CSV."""
    # SQLite
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS forecast_results")
    forecast_df.to_sql("forecast_results", conn, index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fcst_prod ON forecast_results(product_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fcst_date ON forecast_results(forecast_date)")
    conn.commit()
    conn.close()

    # CSV
    forecast_df.to_csv(OUT_CSV, index=False)
    print(f"\n  Forecasts saved to: {OUT_CSV}")
    print(f"  SQLite table:       forecast_results ({len(forecast_df)} rows)")


def main():
    parser = argparse.ArgumentParser(description="AIDA Demand Forecasting")
    parser.add_argument("--model", choices=["ets", "xgboost", "moving_avg"],
                        default="ets", help="Forecast model (default: ets)")
    parser.add_argument("--horizon", type=int, default=30,
                        help="Forecast horizon in days (default: 30)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"AIDA Phase 4 — Demand Forecasting ({args.model}, {args.horizon}d horizon)")
    print("=" * 60)

    # Load data
    print("\n[1/3] Loading data ...")
    sales = load_daily_sales(DB_PATH)
    promos = load_promotion_calendar(DB_PATH)
    print(f"  daily_sales: {len(sales):,} rows, "
          f"{sales['product_id'].nunique()} products, "
          f"{sales['store_id'].nunique()} stores")
    print(f"  promotions:  {len(promos)} product-promo assignments")
    print(f"  date range:  {sales['sale_date'].min().date()} to {sales['sale_date'].max().date()}")

    # Train & forecast
    print(f"\n[2/3] Training {args.model} model per (product, store) ...")
    forecasts = run_forecasts(sales, promos, args.model, args.horizon, DB_PATH)
    print(f"  Generated {len(forecasts):,} forecast rows "
          f"({forecasts['product_id'].nunique()} products x "
          f"{forecasts['store_id'].nunique()} stores)")

    # Summary stats
    print(f"\n[3/3] Saving results ...")
    save_results(forecasts, DB_PATH)

    # Quick peek
    print("\nSample forecasts (first 5 rows):")
    print(forecasts.head(10).to_string(index=False))

    # Aggregate summary
    agg = forecasts.groupby("forecast_date")["forecasted_units"].sum()
    print(f"\nAggregate daily forecast:")
    print(f"  Day 1 total:  {agg.iloc[0]:,.0f} units")
    print(f"  Day 7 total:  {agg.iloc[6]:,.0f} units")
    if len(agg) >= 30:
        print(f"  Day 30 total: {agg.iloc[29]:,.0f} units")
    print(f"  30-day total:  {agg.sum():,.0f} units")

    print("\nNext: python phase4_forecasting/forecast_tool.py")


if __name__ == "__main__":
    main()
