"""
Phase 6: AIDA Streamlit Dashboard
==================================
Interactive chat dashboard with:
  - Agent conversation (SQL, RAG, Forecast)
  - Live KPI sidebar pulled from the database
  - Formatted results: tables, policy excerpts, forecast risk flags

Run:
  pip install streamlit plotly
  streamlit run phase6_ui/app.py
"""

import sys
import sqlite3
from pathlib import Path
from datetime import date

# Ensure project root is importable
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import streamlit as st
import pandas as pd
from phase5_agent.graph import run_agent

DB_PATH = BASE / "phase2_sql" / "aida.db"

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="AIDA — Autonomous Inventory & Demand Agent",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# SIDEBAR: LIVE KPIs
# =============================================================================

@st.cache_data(ttl=60)  # refresh every 60 seconds
def load_kpis():
    """Pull live KPI numbers from the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    kpis = {}

    # Revenue (last 30 days)
    cur = conn.execute("""
        SELECT ROUND(SUM(order_total), 2) FROM orders
        WHERE order_status = 'delivered'
          AND ordered_at >= DATE('now', '-30 days')
    """)
    kpis["revenue_30d"] = cur.fetchone()[0] or 0

    # Total orders (last 30 days)
    cur = conn.execute("""
        SELECT COUNT(*) FROM orders
        WHERE order_status = 'delivered'
          AND ordered_at >= DATE('now', '-30 days')
    """)
    kpis["orders_30d"] = cur.fetchone()[0] or 0

    # Average order value
    kpis["aov"] = round(kpis["revenue_30d"] / kpis["orders_30d"], 2) if kpis["orders_30d"] else 0

    # Low stock items
    cur = conn.execute("""
        SELECT COUNT(*) FROM inventory_status
        WHERE stock_status IN ('STOCKOUT', 'LOW')
    """)
    kpis["low_stock_count"] = cur.fetchone()[0]

    # Stockout items
    cur = conn.execute("""
        SELECT COUNT(*) FROM inventory_status WHERE stock_status = 'STOCKOUT'
    """)
    kpis["stockout_count"] = cur.fetchone()[0]

    # Products
    cur = conn.execute("SELECT COUNT(*) FROM products")
    kpis["product_count"] = cur.fetchone()[0]

    # Stores
    cur = conn.execute("SELECT COUNT(*) FROM stores")
    kpis["store_count"] = cur.fetchone()[0]

    # Forecast: total projected demand next 7 days
    cur = conn.execute("""
        SELECT ROUND(SUM(forecasted_units), 0)
        FROM forecast_results
        WHERE forecast_date BETWEEN DATE('now') AND DATE('now', '+7 days')
    """)
    kpis["fcst_7d"] = cur.fetchone()[0] or 0

    # Forecast: items at risk
    cur = conn.execute("""
        SELECT COUNT(DISTINCT product_id || '-' || store_id)
        FROM forecast_results fr
        JOIN inventory_status ist USING (product_id, store_id)
        WHERE fr.forecast_date BETWEEN DATE('now') AND DATE('now', '+7 days')
          AND ist.qty_available < fr.forecasted_units * 7
    """)
    kpis["fcst_at_risk"] = cur.fetchone()[0] or 0

    conn.close()
    return kpis


def render_sidebar(kpis: dict):
    """Draw the KPI sidebar."""
    st.sidebar.title("AIDA Dashboard")
    st.sidebar.caption(f"Last updated: {date.today().isoformat()}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Revenue (30 Days)")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Revenue", f"₹{kpis['revenue_30d']:,.0f}")
    with col2:
        st.metric("Orders", f"{kpis['orders_30d']:,}")

    st.sidebar.metric("Avg Order Value", f"₹{kpis['aov']:,.0f}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Inventory Health")

    col1, col2, col3 = st.sidebar.columns(3)
    with col1:
        st.metric("Products", kpis["product_count"])
    with col2:
        st.metric("Stores", kpis["store_count"])
    with col3:
        delta = f"-{kpis['low_stock_count']}" if kpis["low_stock_count"] > 0 else "0"
        st.metric("Low Stock", kpis["low_stock_count"], delta=delta,
                  delta_color="inverse")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Demand Forecast (7-Day)")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Projected Units", f"{kpis['fcst_7d']:,}")
    with col2:
        st.metric("At-Risk Items", kpis["fcst_at_risk"],
                  delta=f"{kpis['fcst_at_risk']}" if kpis["fcst_at_risk"] > 0 else "0",
                  delta_color="inverse")

    st.sidebar.markdown("---")
    st.sidebar.caption("Built with Streamlit + LangGraph + ChromaDB")

    # Quick-action buttons
    st.sidebar.markdown("### Quick Actions")
    if st.sidebar.button("Revenue by Store"):
        st.session_state.pending_query = "Which store has the highest revenue?"
    if st.sidebar.button("Low Stock Alert"):
        st.session_state.pending_query = "Show me all products that are low in stock"
    if st.sidebar.button("Supplier Performance"):
        st.session_state.pending_query = "How are my suppliers performing on fill rate?"
    if st.sidebar.button("Dairy Forecast"):
        st.session_state.pending_query = "Forecast demand for dairy for the next 7 days"
    if st.sidebar.button("Return Policy: Dairy"):
        st.session_state.pending_query = "What is the return window for perishable dairy products?"
    if st.sidebar.button("Fraud Policy"):
        st.session_state.pending_query = "What is the fraud prevention threshold for customer returns?"


# =============================================================================
# MAIN CHAT AREA
# =============================================================================

def render_sql_result(tool_results: dict):
    """Render SQL results as a dataframe + description."""
    if not tool_results.get("success"):
        st.error(tool_results.get("error", "SQL query failed"))
        if tool_results.get("suggestion"):
            st.info(tool_results["suggestion"])
        return

    st.markdown(f"**{tool_results.get('description', 'Query Result')}** "
                f"({tool_results.get('row_count', 0)} rows)")

    rows = tool_results.get("data", [])
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Query ran successfully but returned no data. "
                 "All items may be above reorder point.")


def render_rag_result(tool_results: dict):
    """Render RAG search results as excerpts with source cards."""
    if not tool_results.get("success"):
        st.error(tool_results.get("error", "RAG search failed"))
        if tool_results.get("suggestion"):
            st.info(tool_results["suggestion"])
        return

    chunks = tool_results.get("data", [])
    st.markdown(f"**Found {len(chunks)} relevant policy excerpts:**")

    for i, chunk in enumerate(chunks):
        source = chunk.get("source", "unknown").replace("_", " ")
        relevance = chunk.get("relevance", 0)
        doc_type = chunk.get("doc_type", "unknown").replace("_", " ").title()
        content = chunk.get("content", "")

        # Color-code by relevance
        if relevance > 0.5:
            color = "#d4edda"  # green
        elif relevance > 0.3:
            color = "#fff3cd"  # yellow
        else:
            color = "#f8f9fa"  # grey

        with st.container():
            st.markdown(
                f"""<div style="background:{color};padding:12px;border-radius:8px;margin:8px 0;
                border-left:4px solid {'#28a745' if relevance > 0.5 else '#ffc107' if relevance > 0.3 else '#6c757d'}">
                <strong>{doc_type}</strong> — <em>{source}</em><br>
                <small>Relevance: {relevance:.2f}</small>
                <p style="margin-top:8px;font-style:italic">"{content[:400]}{'...' if len(content) > 400 else ''}"</p>
                </div>""",
                unsafe_allow_html=True,
            )


def render_forecast_result(tool_results: dict):
    """Render forecast results with risk highlighting."""
    if not tool_results.get("success"):
        msg = tool_results.get("message", "") or tool_results.get("error", "Forecast unavailable")
        st.warning(msg)
        if tool_results.get("suggestion"):
            st.info(tool_results["suggestion"])
        return

    items = tool_results.get("items", [])
    days = tool_results.get("filters", {}).get("days", 7)
    total = tool_results.get("total_forecasted", 0)

    # KPI row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Forecasted Demand", f"{total:,.0f} units")
    with col2:
        st.metric("Product-Stores", len(items))
    with col3:
        at_risk = sum(1 for i in items if i.get("risk_flag", "OK") != "OK")
        st.metric("At Risk", at_risk, delta=f"{at_risk}" if at_risk > 0 else "0",
                  delta_color="inverse")

    if at_risk > 0:
        st.warning(f"**{at_risk} items flagged** as likely to stock out in the next {days} days!")

    # Build a DataFrame for display
    if items:
        df = pd.DataFrame(items)
        display_cols = ["sku", "store_code", "current_stock", "total_forecasted",
                        "avg_daily", "risk_flag"]
        df = df[[c for c in display_cols if c in df.columns]]

        # Color rows by risk
        def color_rows(row):
            if row.get("risk_flag", "OK") != "OK":
                return ["background-color: #f8d7da"] * len(row)
            return [""] * len(row)

        styled = df.style.apply(color_rows, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)


def render_general_response(response: str):
    """Render a general/help response."""
    st.markdown(response)


# =============================================================================
# CHAT LOGIC
# =============================================================================

def init_session():
    """Initialize session state."""
    defaults = {
        "messages": [],       # list of {role, content, tool_results}
        "pending_query": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def handle_query(user_query: str):
    """Process a user query through the agent and add to chat."""
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_query})

    # Run agent
    with st.spinner("AIDA is thinking..."):
        result = run_agent(user_query, [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[-10:]  # last 10 for context
        ])

    response = result.get("response", "Sorry, I couldn't process that.")
    intent = result.get("intent", "?")
    tool_results = result.get("tool_results", {})

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "intent": intent,
        "tool_results": tool_results,
    })


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    init_session()

    # Sidebar
    kpis = load_kpis()
    render_sidebar(kpis)

    # Header
    st.title("AIDA — Autonomous Inventory & Demand Agent")
    st.caption("Ask me about revenue, inventory, supplier contracts, or demand forecasts.")

    # Process pending query from sidebar button
    if st.session_state.pending_query:
        query = st.session_state.pending_query
        st.session_state.pending_query = ""
        handle_query(query)
        st.rerun()

    # Chat input
    if prompt := st.chat_input("e.g. What is the return window for dairy products?"):
        handle_query(prompt)
        st.rerun()

    # Render chat history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant", avatar="📦"):
                intent = msg.get("intent", "")
                tool_results = msg.get("tool_results", {})

                # Show which tool was used
                tool_label = {
                    "sql": "SQL Query",
                    "rag": "Policy Search",
                    "forecast": "Demand Forecast",
                    "general": "General",
                }.get(intent, intent)
                st.caption(f"🔧 {tool_label}")

                # Render based on intent
                if intent == "sql":
                    render_sql_result(tool_results)
                elif intent == "rag":
                    render_rag_result(tool_results)
                elif intent == "forecast":
                    render_forecast_result(tool_results)
                else:
                    render_general_response(msg["content"])

    # Empty state
    if not st.session_state.messages:
        with st.chat_message("assistant", avatar="📦"):
            st.markdown("""
            👋 I'm **AIDA**, your Autonomous Inventory & Demand Agent.

            I can help you with:

            | Tool | Example Questions |
            |------|------------------|
            | **SQL Analytics** | *"Which store has the highest revenue?"* |
            | **Policy RAG** | *"What's the return window for dairy?"* |
            | **Demand Forecast** | *"Forecast dairy demand for the next 7 days"* |

            Type a question above or click a Quick Action in the sidebar →
            """)


if __name__ == "__main__":
    main()
