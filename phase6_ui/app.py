"""
AIDA — Autonomous Inventory & Demand Agent
===========================================
Home page: AI Chat with the LangGraph agent.

Run:  streamlit run phase6_ui/app.py
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import sqlite3

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from phase6_ui.style import COLORS, inject_css
from phase6_ui.components.db import safe_scalar, db_ready, DB
from phase5_agent.graph import run_agent

# ── Page Setup ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AIDA — AI Agent",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_css()

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="aida-logo">AIDA</p>', unsafe_allow_html=True)
    st.caption("Autonomous Inventory & Demand Agent")

    st.markdown("---")

    if db_ready():
        orders_30d = safe_scalar("SELECT COUNT(*) FROM orders WHERE order_status = 'delivered' AND ordered_at >= DATE('now', '-30 days')")
        rev_30d = safe_scalar("SELECT ROUND(SUM(order_total), 0) FROM orders WHERE order_status = 'delivered' AND ordered_at >= DATE('now', '-30 days')")
        low = safe_scalar("SELECT COUNT(*) FROM inventory_status WHERE stock_status IN ('STOCKOUT', 'LOW')")
        fcst = safe_scalar("SELECT ROUND(SUM(forecasted_units), 0) FROM forecast_results WHERE forecast_date BETWEEN DATE('now') AND DATE('now', '+7 days')")
    else:
        orders_30d, rev_30d, low, fcst = 0, 0, 0, 0

    st.metric("Orders (30d)", f"{orders_30d:,}")
    st.metric("Revenue (30d)", f"₹{rev_30d:,}")
    st.metric("Low Stock Items", low)
    st.metric("7-Day Forecast", f"{fcst:,} units")

    st.markdown("---")

    # Data status
    if not db_ready():
        st.warning("⚠️ Database not ready")
        if st.button("🚀 Generate Data", use_container_width=True):
            with st.spinner("Generating data (this takes 2-3 minutes)..."):
                import subprocess
                steps = [
                    ["python", "phase1_schema/generate_data.py", "--csv"],
                    ["python", "phase2_sql/load_to_sqlite.py"],
                    ["python", "phase3_rag/generate_docs.py"],
                    ["python", "phase3_rag/embed_docs.py"],
                    ["python", "phase4_forecasting/train_forecast.py", "--model", "ets", "--horizon", "30"],
                ]
                for step in steps:
                    subprocess.run(step, capture_output=True, timeout=600)
            st.rerun()
    else:
        st.success("✅ Data ready")

    st.caption("Navigate to other pages via sidebar")

# ── Header ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 3])
with col1:
    st.markdown('<p class="aida-logo" style="font-size:1.8rem;margin-top:8px;">AIDA</p>',
                unsafe_allow_html=True)
with col2:
    st.markdown(
        '<span style="color:#8b8fa8;font-size:0.9rem;">'
        'Ask me about revenue, inventory, supplier contracts, or demand forecasts</span>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Quick Action Chips ──────────────────────────────────────────────────────
st.markdown('<p style="color:#5c6078;font-size:0.75rem;text-transform:uppercase;'
            'letter-spacing:0.05em;margin-bottom:8px;">Suggested queries</p>',
            unsafe_allow_html=True)

chips = st.columns([1, 1, 1, 1, 1, 1])
queries = [
    ("📊 Revenue", "Which store has the highest revenue?"),
    ("📦 Stock", "Show me all products that are low in stock"),
    ("📋 Policy", "What is the return window for dairy products?"),
    ("📈 Forecast", "Forecast dairy demand for 7 days"),
    ("🚚 Supplier", "How are my suppliers performing on fill rate?"),
    ("🔍 Fraud", "What is the fraud prevention threshold?"),
]
for col, (label, query) in zip(chips, queries):
    with col:
        if st.button(label, key=f"chip_{label}", use_container_width=True):
            st.session_state.pending = query
            st.rerun()

# ── Chat Session ────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending" not in st.session_state:
    st.session_state.pending = ""

# Process pending
if st.session_state.pending:
    query = st.session_state.pending
    st.session_state.pending = ""
    with st.spinner(""):
        result = run_agent(query)
    st.session_state.chat_history.append({"role": "user", "content": query})
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": result.get("response", ""),
        "intent": result.get("intent", "general"),
        "tool_results": result.get("tool_results", {}),
    })
    st.rerun()

# ── Chat Input ──────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask AIDA anything about your inventory, policies, or forecasts...",
                           key="chat_main"):
    with st.spinner(""):
        result = run_agent(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": result.get("response", ""),
        "intent": result.get("intent", "general"),
        "tool_results": result.get("tool_results", {}),
    })
    st.rerun()

# ── Render Chat History ─────────────────────────────────────────────────────
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        intent = msg.get("intent", "general")
        tool_results = msg.get("tool_results", {})

        # Tool badge
        tool_labels = {
            "sql": ("SQL Query", "sql"),
            "rag": ("Policy Search", "rag"),
            "forecast": ("Demand Forecast", "forecast"),
            "general": ("", ""),
        }
        label, css_class = tool_labels.get(intent, ("", ""))

        with st.chat_message("assistant", avatar="📦"):
            if label:
                st.markdown(
                    f'<span class="aida-tool-badge {css_class}">{label}</span>',
                    unsafe_allow_html=True,
                )

            if intent == "sql" and tool_results.get("success"):
                rows = tool_results.get("data", [])
                desc = tool_results.get("description", "")
                st.caption(f"{desc} ({len(rows)} rows)")
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                else:
                    st.info("Query ran successfully — no items currently at risk.")

            elif intent == "rag" and tool_results.get("success"):
                for chunk in tool_results.get("data", []):
                    relevance = chunk.get("relevance", 0)
                    border = "#22c55e" if relevance > 0.5 else "#f59e0b" if relevance > 0.3 else "#5c6078"
                    bg = "rgba(34,197,94,0.06)" if relevance > 0.5 else "rgba(245,158,11,0.06)" if relevance > 0.3 else "rgba(92,96,120,0.04)"
                    st.markdown(
                        f"""<div style="background:{bg};padding:14px 18px;border-radius:10px;
                        margin:8px 0;border-left:3px solid {border};font-size:0.9rem;">
                        <strong>{chunk.get('source','').replace('_',' ')}</strong>
                        <span style="color:#5c6078;font-size:0.75rem;"> · relevance {relevance:.2f}</span>
                        <p style="margin-top:6px;color:#8b8fa8;font-style:italic;">
                        "{chunk.get('content','')[:300]}{'...' if len(chunk.get('content',''))>300 else ''}"</p>
                        </div>""",
                        unsafe_allow_html=True,
                    )

            elif intent == "forecast" and tool_results.get("success"):
                items = tool_results.get("items", [])
                total = tool_results.get("total_forecasted", 0)
                days_val = tool_results.get("filters", {}).get("days", 7)
                at_risk = sum(1 for i in items if i.get("risk_flag", "OK") != "OK")

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Total Demand", f"{total:,.0f} units")
                with col_b:
                    st.metric("Coverage", f"{len(items)} items")
                with col_c:
                    st.metric("At Risk", at_risk, delta=f"-{at_risk}" if at_risk else "0",
                              delta_color="inverse")

                if items:
                    df = pd.DataFrame(items)
                    if "risk_flag" in df.columns:
                        def highlight(r):
                            if r.get("risk_flag", "OK") != "OK":
                                return ["background: rgba(239,68,68,0.08)"] * len(r)
                            return [""] * len(r)
                        st.dataframe(df.style.apply(highlight, axis=1),
                                     use_container_width=True, hide_index=True)
                    else:
                        st.dataframe(df, use_container_width=True, hide_index=True)

            elif intent == "general":
                st.markdown(msg["content"])

            else:
                st.markdown(msg["content"])

# ── Empty State ─────────────────────────────────────────────────────────────
if not st.session_state.chat_history:
    st.markdown("<br>", unsafe_allow_html=True)
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <p style="font-size:3rem;margin-bottom:16px;">📦</p>
            <p style="font-size:1.3rem;font-weight:700;color:#eef0f6;margin-bottom:8px;">
                Autonomous Inventory & Demand Agent
            </p>
            <p style="color:#8b8fa8;font-size:0.9rem;line-height:1.6;">
                I can run <strong>SQL analytics</strong> on 35,000+ orders,
                search <strong>supplier contracts & SOPs</strong>,
                and query <strong>30-day demand forecasts</strong> — all in plain English.
            </p>
            <p style="color:#5c6078;font-size:0.8rem;margin-top:24px;">
                Start with a suggested query above, or type your own ↓
            </p>
        </div>
        """, unsafe_allow_html=True)
