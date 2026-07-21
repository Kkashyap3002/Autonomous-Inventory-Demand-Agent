"""
AIDA Bootstrap — Auto-initialize on Streamlit Cloud deploy
============================================================
Checks if required data files exist and generates them if missing.
Called automatically by app.py on startup in cloud environments.
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def ensure_data():
    """Run data generation pipelines if outputs don't exist."""
    synthetic = BASE / "phase1_schema" / "synthetic_data" / "orders.csv"
    db = BASE / "phase2_sql" / "aida.db"
    chroma = BASE / "phase3_rag" / "chroma_db"
    forecasts = BASE / "phase4_forecasting" / "forecast_results.csv"

    steps_needed = []

    if not synthetic.exists():
        steps_needed.append(("Generating synthetic data", [
            sys.executable, str(BASE / "phase1_schema" / "generate_data.py"), "--csv",
        ]))

    if not db.exists() or not synthetic.exists():
        if synthetic.exists() or not steps_needed:
            steps_needed.append(("Loading SQLite database", [
                sys.executable, str(BASE / "phase2_sql" / "load_to_sqlite.py"),
            ]))

    if not chroma.exists():
        # first generate docs, then embed
        steps_needed.append(("Generating policy documents", [
            sys.executable, str(BASE / "phase3_rag" / "generate_docs.py"),
        ]))
        steps_needed.append(("Building ChromaDB vector store", [
            sys.executable, str(BASE / "phase3_rag" / "embed_docs.py"),
        ]))

    if not forecasts.exists() and db.exists():
        steps_needed.append(("Training forecast models", [
            sys.executable, str(BASE / "phase4_forecasting" / "train_forecast.py"),
            "--model", "ets", "--horizon", "30",
        ]))

    for label, cmd in steps_needed:
        print(f"[AIDA Bootstrap] {label} ...")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
            print(f"[AIDA Bootstrap]   ✓ done")
        except subprocess.CalledProcessError as e:
            print(f"[AIDA Bootstrap]   ⚠ may have failed: {e.stderr[-200:] if e.stderr else 'no output'}")
            # Continue anyway — the app may still work partially
        except Exception as e:
            print(f"[AIDA Bootstrap]   ⚠ error: {e}")

    print("[AIDA Bootstrap] Ready.")


if __name__ == "__main__":
    ensure_data()
