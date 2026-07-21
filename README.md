# AIDA — Autonomous Inventory & Demand Agent

**Live Demo:** [aida-autonomous-inventory-demand-agent.streamlit.app](https://aida-autonomous-inventory-demand-agent.streamlit.app)

A full-stack AI agent for quick-commerce inventory intelligence. Combines a relational database (SQLite), RAG-powered policy search (ChromaDB + LangChain), demand forecasting (Holt-Winters ETS), and a LangGraph agent orchestration layer — all behind a 6-page production Streamlit dashboard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     STREAMLIT DASHBOARD (6 pages)               │
│  Chat │ Dashboard │ Inventory │ Forecasts │ SQL Workspace │ BI  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │     LANGGRAPH AGENT      │
              │  Intent Classifier       │
              │     │       │       │     │
              │  ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ │
              │  │ SQL │ │ RAG │ │FCST │ │
              │  └──┬──┘ └──┬──┘ └──┬──┘ │
              └─────┼───────┼───────┼─────┘
                    │       │       │
              ┌─────┴─┐ ┌───┴───┐ ┌─┴──────────┐
              │SQLite │ │ChromaDB│ │ H-W ETS     │
              │35K rows│ │137 docs│ │ 132 models  │
              └───────┘ └───────┘ └─────────────┘
```

## Live Dashboard — 6 Pages

| Page | What It Does |
|------|-------------|
| **💬 Chat** | AI agent with natural language → SQL / RAG / Forecast. Chip-based quick actions, tool-specific result rendering (styled tables, policy cards, risk-highlighted forecasts) |
| **📊 Dashboard** | Executive KPI cards (10 metrics), revenue trend with 7-day moving average, category revenue donut, top products bar chart, inventory health by days-of-stock |
| **📦 Inventory** | Real-time search + multi-filter explorer (store, category, stock status). Velocity-adjusted days-of-stock. Full supplier performance table with fill rates |
| **📈 Forecasts** | 7/14/30-day demand projections. Aggregate daily trend chart. Item-level risk table with `LIKELY_STOCKOUT` flagging. Product detail sparkline view |
| **⚡ SQL Workspace** | Raw SQL editor with table schema explorer, 7 query templates, execution timer, CSV export, and 20-query history |
| **📊 Analytics Studio** | Power BI-style interactive chart builder. 10 chart types (Bar, Line, Pie, Histogram, Scatter, Heatmap, Area, Combo, Box Plot, Stacked Bar). Dynamic X/Y axes, aggregation (sum/avg/count/min/max/median/std), multi-select filters, 3 layout modes (single, split, 4-grid) |

## Project Structure

```
AIDA/
├── phase1_schema/              # Database Design
│   ├── schema.sql              #   11 tables, indexes, analytical views
│   └── generate_data.py        #   Synthetic data: 35K+ orders, 118K transactions
│
├── phase2_sql/                 # SQL Analytics
│   ├── load_to_sqlite.py       #   CSV → SQLite with materialized views
│   └── analytical_queries.py   #   12 queries (CTEs, windows, self-joins, aggregates)
│
├── phase3_rag/                 # RAG Pipeline
│   ├── generate_docs.py        #   10 synthetic business documents
│   ├── embed_docs.py           #   Chunk → Embed (all-MiniLM-L6-v2) → ChromaDB
│   └── query_docs.py           #   Semantic search + relevance scoring
│
├── phase4_forecasting/         # Demand Forecasting
│   ├── train_forecast.py       #   Holt-Winters ETS (primary), XGBoost (optional)
│   └── forecast_tool.py        #   Query interface for LangGraph agent
│
├── phase5_agent/               # Agent Orchestration
│   ├── graph.py                #   LangGraph StateGraph + intent classifier
│   ├── tools.py                #   3 tools: SQL (7 templates), RAG, Forecast
│   └── run_agent.py            #   Interactive CLI + 18-query demo tour
│
├── phase6_ui/                  # Dashboard
│   ├── app.py                  #   Main chat interface
│   ├── pages/                  #   5 additional pages
│   ├── components/charts.py    #   Reusable Plotly chart functions
│   ├── style.py                #   Design system (dark theme, typography, CSS)
│   └── bootstrap.py            #   Auto-initialize on cloud deploy
│
└── requirements.txt            # All Python dependencies
```

## Key Technical Highlights

### Agentic AI (LangGraph + LangChain)
- **StateGraph** with 4 nodes: `classify` → `sql` | `rag` | `forecast` → `respond`
- **Intent classifier** using weighted keyword scoring across 3 domains
- **Conditional routing** — the agent decides which tool to invoke based on what you ask
- Each tool returns structured results that the response node formats for display
- Easily extensible: swap the classifier for an LLM call (OpenAI/Claude) for production use

### RAG Pipeline (LangChain + ChromaDB)
- **10 business documents**: 5 supplier contracts (Amul, PepsiCo, Unilever, Suguna, LocalPro) + 3 SOPs (inventory, cold chain, fulfillment) + 2 policies (customer returns, supplier claims)
- **137 semantic chunks** embedded with `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- **Cosine similarity search** with relevance scoring — queries like "What is the penalty for late delivery from Amul?" return the exact contract clause
- Documents contain realistic, query-able details: SLA percentages, temperature ranges, penalty clauses, return windows

### Demand Forecasting
- **Holt-Winters Exponential Smoothing** (statsmodels) with additive trend + 7-day seasonality
- **132 individual models** — one per (product, store) combination
- **30-day horizon** with daily granularity
- Risk flags: compares forecasted demand against current inventory to flag `LIKELY_STOCKOUT` items
- Optional XGBoost mode with lag features (t-1, t-2, t-3, t-7, t-14) + rolling means + promo flags

### Database Schema (Quick-Commerce)
```
products ──< inventory_levels >── stores
   │              │
   │              └── inventory_transactions (118K-row audit trail)
   │
   ├──< order_items >── orders (35K+) ──< promotions
   │
   └──< purchase_order_items >── purchase_orders ── suppliers
```
11 tables with proper indexes, foreign keys, generated columns, and 3 materialized analytical views.

### Analytics & BI (Plotly)
- **10 chart types** with dark theme, hover tooltips, and interactive legends
- Dynamic axis selection from actual database columns
- Multi-metric aggregation (sum, avg, count, min, max, median, std)
- Real-time filtering across categories, stores, and date ranges
- Grid layout for dashboard-style multi-chart views

## Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/Kkashyap3002/Autonomous-Inventory-Demand-Agent.git
cd Autonomous-Inventory-Demand-Agent

# 2. Install
pip install -r requirements.txt

# 3. Generate data & train models (one-time)
python phase1_schema/generate_data.py --csv
python phase2_sql/load_to_sqlite.py
python phase3_rag/generate_docs.py
python phase3_rag/embed_docs.py
python phase4_forecasting/train_forecast.py --model ets --horizon 30

# 4. Launch
streamlit run phase6_ui/app.py
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Database** | SQLite (11 tables, 3 views, 35K+ orders) |
| **Vector Store** | ChromaDB + sentence-transformers (all-MiniLM-L6-v2) |
| **RAG Framework** | LangChain (text splitters, document loaders) |
| **Agent Orchestration** | LangGraph (StateGraph, conditional edges, tool routing) |
| **Forecasting** | statsmodels (Holt-Winters ETS), optional XGBoost |
| **Charts & BI** | Plotly (10 chart types, interactive, dark-themed) |
| **Frontend** | Streamlit (6 pages, custom CSS design system) |
| **Data Generation** | Faker (Indian locale, realistic noise + demand patterns) |
| **Deployment** | Streamlit Community Cloud |

## License

MIT
