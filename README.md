# AIDA - Autonomous Inventory & Demand Agent

A full-stack AI agent for quick-commerce inventory management. Combines a relational retail database, vector search over supplier contracts, demand forecasting, and a LangGraph agent — all behind a Streamlit dashboard.

## Architecture

```
User Query → LangGraph Agent → Classifier → ┌─ SQL Tool (NL → SQL → SQLite)
                                             ├─ RAG Tool (ChromaDB vector search)
                                             └─ Forecast Tool (Holt-Winters ETS)
                                          → Response Synthesizer → Streamlit UI
```

## Project Structure

| Phase | Module | Description |
|-------|--------|-------------|
| 1 | `phase1_schema/` | 11-table retail schema + synthetic data generator (35K+ orders) |
| 2 | `phase2_sql/` | SQLite loader + 12 analytical queries (CTEs, windows, aggregations) |
| 3 | `phase3_rag/` | 10 business documents → 137 chunks → ChromaDB vector store |
| 4 | `phase4_forecasting/` | ETS/XGBoost demand forecasting (132 product-stores, 30-day horizon) |
| 5 | `phase5_agent/` | LangGraph StateGraph with intent classifier + 3-tool routing |
| 6 | `phase6_ui/` | Streamlit dashboard with live KPIs and chat interface |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate synthetic data
python phase1_schema/generate_data.py --csv

# 3. Load into SQLite
python phase2_sql/load_to_sqlite.py

# 4. Index documents into ChromaDB
python phase3_rag/generate_docs.py
python phase3_rag/embed_docs.py

# 5. Train forecast models
python phase4_forecasting/train_forecast.py --model ets --horizon 30

# 6. Launch the dashboard
streamlit run phase6_ui/app.py
```

## Agent Tools

| Tool | What it does | Example |
|------|-------------|---------|
| `SQL_Query_Tool` | Natural language → SQL → live results | *"Which store has the highest revenue?"* |
| `Policy_RAG_Tool` | Semantic search across contracts, SOPs, policies | *"What is the return window for dairy?"* |
| `Forecast_Tool` | 7-30 day demand projections with risk flags | *"Forecast dairy demand for next 7 days"* |

## Tech Stack

- **Database:** SQLite with 11-table quick-commerce schema
- **Vector Store:** ChromaDB + sentence-transformers (all-MiniLM-L6-v2)
- **Forecasting:** statsmodels (Holt-Winters ETS) + optional XGBoost
- **Agent:** LangGraph StateGraph with intent classification
- **UI:** Streamlit with live KPI sidebar

## Database Schema

```
products ──< inventory_levels >── stores
   │              │
   │              └── inventory_transactions (audit trail)
   │
   ├──< order_items >── orders ──< promotions
   │
   └──< purchase_order_items >── purchase_orders ── suppliers
```

## License

MIT
