"""
Safe database helpers — graceful degradation when data isn't ready.
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent.parent / "phase2_sql" / "aida.db"


def safe_query(sql: str, params: dict = None, default=None):
    """Run a SQL query safely, returning default on any error."""
    try:
        conn = sqlite3.connect(str(DB))
        conn.row_factory = sqlite3.Row
        if params:
            cur = conn.execute(sql, params)
        else:
            cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        return default if default is not None else []


def safe_scalar(sql: str, params: dict = None, default=0):
    """Run a SQL query returning a single scalar value."""
    try:
        conn = sqlite3.connect(str(DB))
        cur = conn.execute(sql, params or {})
        val = cur.fetchone()
        conn.close()
        return val[0] if val and val[0] is not None else default
    except Exception:
        return default


def db_ready() -> bool:
    """Check if the database exists and has data."""
    try:
        return DB.exists() and safe_scalar("SELECT COUNT(*) FROM orders") > 0
    except Exception:
        return False


def safe_dataframe(sql: str, params: dict = None):
    """Run SQL and return a pandas DataFrame, or empty DataFrame on error."""
    import pandas as pd
    try:
        conn = sqlite3.connect(str(DB))
        df = pd.read_sql_query(sql, conn, params=params or {}, parse_dates=[
            c for c in ["sale_date", "ordered_at", "delivered_at", "forecast_date"]
            if c in sql
        ])
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()
