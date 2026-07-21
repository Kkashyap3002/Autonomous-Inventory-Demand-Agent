# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIDA (Autonomous Inventory & Demand Agent) is a full-stack AI project for quick-commerce inventory management. It combines a relational retail database, RAG over business documents, demand forecasting, and a LangGraph agent behind a Streamlit dashboard.

## Commands

```bash
# Setup (run once, in order)
python phase1_schema/generate_data.py --csv      # Generate synthetic data CSVs
python phase2_sql/load_to_sqlite.py              # Load CSVs into SQLite + create views
python phase3_rag/generate_docs.py               # Create 10 synthetic business docs
python phase3_rag/embed_docs.py                  # Chunk + embed into ChromaDB
python phase4_forecasting/train_forecast.py      # Train ETS forecast models

# Running individual phases
python phase2_sql/analytical_queries.py          # Run all 12 analytical SQL queries
python phase3_rag/query_docs.py "your question"  # Test RAG retrieval
python phase4_forecasting/forecast_tool.py       # Query forecasts (CLI)
python phase5_agent/run_agent.py                 # Interactive agent chat
python phase5_agent/run_agent.py --demo          # 18-query demo tour
streamlit run phase6_ui/app.py                   # Launch dashboard

# Single query via agent
python phase5_agent/run_agent.py "revenue by store"
```

## Architecture

The LangGraph agent (`phase5_agent/graph.py`) uses a keyword-based intent classifier to route queries to one of three tools:
- **sql** → `phase5_agent/tools.py::sql_query_tool()` — pattern-matches against 7 SQL templates
- **rag** → `phase3_rag/query_docs.py::query_policy()` — ChromaDB similarity search
- **forecast** → `phase4_forecasting/forecast_tool.py::forecast_demand()` — queries forecast_results table

The Streamlit app (`phase6_ui/app.py`) imports `run_agent` from Phase 5 and renders results based on intent type (SQL tables, RAG excerpts, forecast risk tables).

## Key Files

- `phase5_agent/graph.py` — LangGraph StateGraph builder and intent classifier
- `phase5_agent/tools.py` — Tool implementations wrapping Phases 2-4
- `phase2_sql/analytical_queries.py` — 12 SQL query reference (CTEs, windows, self-joins)
- `phase1_schema/schema.sql` — PostgreSQL-flavored schema definition

## Data Regeneration

To get fresh data (different random seed), delete the old files and re-run:
```bash
rm -rf phase1_schema/synthetic_data phase2_sql/aida.db phase3_rag/chroma_db phase4_forecasting/forecast_results.csv
python phase1_schema/generate_data.py --csv
python phase2_sql/load_to_sqlite.py
python phase3_rag/embed_docs.py
python phase4_forecasting/train_forecast.py
```

## Dependencies

- Python 3.12 (Streamlit must use Python 3.12, not Anaconda: `C:\Python312\python.exe -m streamlit run phase6_ui/app.py`)
- All Python packages in `requirements.txt`
