"""
Phase 5: LangGraph Agent State Machine
=======================================
Builds the core agentic workflow that:
  1. Classifies user intent (sql / rag / forecast / general)
  2. Routes to the appropriate tool node
  3. Executes the tool and collects results
  4. Synthesizes a final human-readable response

Architecture:
  START → classify → [conditional edges]
                       ├→ sql_node ──────┐
                       ├→ rag_node ──────┤
                       ├→ forecast_node ─┤
                       └→ respond ───────┘
                                          ↓
                                        respond → END

Run:  python phase5_agent/run_agent.py
"""

import sys
from pathlib import Path
from typing import TypedDict, Literal, Annotated
from datetime import datetime

# Add project root to path
BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from langgraph.graph import StateGraph, START, END

# Import our tools
from phase5_agent.tools import sql_query_tool, rag_search_tool, forecast_tool


# =============================================================================
# STATE DEFINITION
# =============================================================================

class AgentState(TypedDict):
    """The shared state that flows through the agent graph."""
    user_query: str              # latest user message
    messages: list[dict]         # conversation history
    intent: str                  # classified intent: sql | rag | forecast | general
    tool_name: str               # which tool was called
    tool_results: dict           # raw results from the tool
    response: str                # final human-readable response
    error: str                   # error message if something failed


# =============================================================================
# NODE 1: INTENT CLASSIFIER
# =============================================================================

# Keyword → intent mappings. Each intent has trigger words with weights.
# Higher score = more likely match. In production, an LLM does this.
INTENT_RULES = {
    "sql": [
        # SQL-triggering keywords — each match adds 1 point
        "revenue", "sales", "order count", "top selling", "best selling",
        "store", "margin", "profit",
        "category", "inventory", "stock level", "fill rate",
        "how many", "how much revenue", "which store", "which product",
        "worst", "trend", "daily sales", "hourly", "peak hour", "growth",
        "units sold", "gross margin", "average order",
        "compare", "ranking", "rank", "performance",
        "wastage", "basket", "co-purchased", "affinity",
        "shelf life", "spoilage", "low stock", "low in stock",
        "stockout", "peak order", "peak time",
    ],
    "rag": [
        "policy", "contract", "sop", "agreement", "return policy",
        "return window", "return ", "refund", "penalty", "sla", "temperature",
        "cold chain", "delivery window", "late delivery", "clause", "terms",
        "supplier agreement", "service level", "what does the",
        "according to", "what is the policy", "what are the rules",
        "how long do i have to return", "what temperature",
        "force majeure", "termination", "compliance",
        "quality grade", "fraud prevention", "what happens if",
        "who is the supplier", "supplier for", "marketing fund",
        "wastage sharing", "share", "scored below",
        "what is the penalty", "returned", "returning",
    ],
    "forecast": [
        "forecast", "predict", "future demand", "coming days",
        "next week", "next month", "projected", "expected demand",
        "how much will we sell", "demand forecast", "replenish",
        "will run out", "going to stockout", "days of stock",
        "how long will", "when will we run out",
    ],
}


def classify_intent(user_query: str) -> dict:
    """
    Classify user intent using keyword scoring.
    Returns {"intent": str, "confidence": float, "tool_name": str}
    """
    q = user_query.lower()
    scores = {}
    for intent, keywords in INTENT_RULES.items():
        score = sum(1 for kw in keywords if kw in q)
        scores[intent] = score

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    # If no keywords match at all, default to general
    if best_score == 0:
        return {"intent": "general", "confidence": 0.0, "tool_name": "none"}

    # Normalize confidence (rough)
    total = sum(scores.values()) or 1
    confidence = best_score / total

    tool_map = {"sql": "sql_query", "rag": "rag_search", "forecast": "forecast"}
    return {
        "intent": best_intent,
        "confidence": round(confidence, 2),
        "tool_name": tool_map.get(best_intent, "none"),
    }


def classify_node(state: AgentState) -> AgentState:
    """Node: classify the user's query and determine the routing path."""
    query = state.get("user_query", "")
    classification = classify_intent(query)
    return {
        **state,
        "intent": classification["intent"],
        "tool_name": classification["tool_name"],
        "error": "",
    }


# =============================================================================
# NODE 2a: SQL EXECUTION
# =============================================================================

def sql_node(state: AgentState) -> AgentState:
    """Node: execute a SQL query based on the user's natural language."""
    query = state["user_query"]
    results = sql_query_tool(query)

    if results["success"]:
        # Build a quick text summary for the response node
        rows = results.get("data", [])
        summary = f"SQL query '{results['template']}' returned {results['row_count']} rows."
    else:
        summary = ""
        results = {**results, "data": []}

    return {
        **state,
        "tool_name": "sql_query",
        "tool_results": results,
        "error": "" if results["success"] else results.get("error", "SQL query failed"),
    }


# =============================================================================
# NODE 2b: RAG SEARCH
# =============================================================================

def rag_node(state: AgentState) -> AgentState:
    """Node: search the vector DB for policy/contract information."""
    query = state["user_query"]
    results = rag_search_tool(query)

    if results["success"]:
        chunks = results.get("data", [])
        sources = set(c["source"] for c in chunks)
        summary = f"RAG search found {len(chunks)} relevant chunks across {len(sources)} documents."
    else:
        summary = ""
        results = {**results, "data": []}

    return {
        **state,
        "tool_name": "rag_search",
        "tool_results": results,
        "error": "" if results["success"] else results.get("error", "RAG search failed"),
    }


# =============================================================================
# NODE 2c: FORECAST
# =============================================================================

def forecast_node(state: AgentState) -> AgentState:
    """Node: query the demand forecast results."""
    query = state["user_query"]
    results = forecast_tool(query)

    if results["success"]:
        items = results.get("items", [])
        total = results.get("total_forecasted", 0)
        summary = f"Forecast returned {len(items)} product-stores, {total:.0f} total units."
    else:
        summary = ""
        results = {**results, "data": []}

    return {
        **state,
        "tool_name": "forecast",
        "tool_results": results,
        "error": "" if results["success"] else results.get("error", "Forecast query failed"),
    }


# =============================================================================
# NODE 3: RESPONSE SYNTHESIS
# =============================================================================

def format_sql_response(results: dict) -> str:
    """Format SQL results into a readable text response."""
    if not results.get("success"):
        return f"I couldn't run that SQL query. {results.get('error', '')}\n\n{results.get('suggestion', '')}"

    rows = results.get("data", [])
    if not rows:
        return f"Query '{results['template']}' ran successfully but returned no data."

    # Build a markdown table
    cols = list(rows[0].keys())[:7]  # max 7 columns for readability
    lines = [
        f"**{results['description']}** ({results['row_count']} rows)\n",
        "| " + " | ".join(cols) + " |",
        "|" + "|".join("---" for _ in cols) + "|",
    ]

    for row in rows[:10]:
        vals = [str(row.get(c, ""))[:30] for c in cols]
        lines.append("| " + " | ".join(vals) + " |")

    if len(rows) > 10:
        lines.append(f"\n*... and {len(rows) - 10} more rows*")

    return "\n".join(lines)


def format_rag_response(results: dict) -> str:
    """Format RAG search results into a readable response."""
    if not results.get("success"):
        return f"I couldn't search the policy documents. {results.get('error', '')}\n\n{results.get('suggestion', '')}"

    chunks = results.get("data", [])
    if not chunks:
        return "No relevant policy documents found for your query."

    lines = [f"**Found {len(chunks)} relevant policy excerpts:**\n"]
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "unknown").replace("_", " ")
        relevance = chunk.get("relevance", 0)
        content = chunk.get("content", "")[:300]
        lines.append(f"### {i}. {source} (relevance: {relevance:.2f})")
        lines.append(f"> {content}\n")

    return "\n".join(lines)


def format_forecast_response(results: dict) -> str:
    """Format forecast results into a readable response."""
    if not results.get("success"):
        msg = results.get("message", "") or results.get("error", "")
        return f"I couldn't retrieve forecasts. {msg}"

    items = results.get("items", [])
    if not items:
        return "No forecast data available. Try running `train_forecast.py` first."

    days = results.get("filters", {}).get("days", 7)
    total = results.get("total_forecasted", 0)

    lines = [
        f"**Demand Forecast ({days}-day horizon)**",
        f"Total projected demand: **{total:,.0f} units** across {len(items)} product-stores.\n",
        "| SKU | Store | Stock | Forecast | Avg/Day | Risk |",
        "|-----|-------|-------|----------|---------|------|",
    ]

    # Show flagged items first, then top forecasted
    flagged = [i for i in items if i.get("risk_flag", "OK") != "OK"]
    rest = [i for i in items if i.get("risk_flag", "OK") == "OK"]

    for item in (flagged[:8] + rest[:4])[:12]:
        risk = item.get("risk_flag", "")
        flag = f"**{risk}**" if risk and risk != "OK" else risk
        lines.append(
            f"| {item['sku'][:25]} | {item['store_code']} | "
            f"{item['current_stock']} | {item['total_forecasted']:.0f} | "
            f"{item['avg_daily']:.1f} | {flag} |"
        )

    if flagged:
        lines.append(f"\n**{len(flagged)} items flagged** as likely to stock out during this period!")

    return "\n".join(lines)


def respond_node(state: AgentState) -> AgentState:
    """Node: synthesize tool results into a final user-facing response."""
    intent = state.get("intent", "general")
    tool_results = state.get("tool_results", {})
    tool_name = state.get("tool_name", "none")
    error = state.get("error", "")

    if error:
        response = f"I ran into an issue with the {tool_name} tool:\n\n{error}"
    elif intent == "sql":
        response = format_sql_response(tool_results)
    elif intent == "rag":
        response = format_rag_response(tool_results)
    elif intent == "forecast":
        response = format_forecast_response(tool_results)
    elif intent == "general":
        response = (
            "I'm AIDA, your Autonomous Inventory & Demand Agent. I can help with:\n\n"
            "**SQL Queries** — Ask about revenue, inventory, products, suppliers, margins.\n"
            "  e.g. _\"Which store has the highest revenue?\"_\n\n"
            "**Policy Lookup** — Search supplier contracts, SOPs, and return policies.\n"
            "  e.g. _\"What is the return window for dairy products?\"_\n\n"
            "**Demand Forecasts** — Predict future demand per product and store.\n"
            "  e.g. _\"Forecast demand for dairy products for the next 7 days\"_\n\n"
            "What would you like to know?"
        )
    else:
        response = f"I understood your intent as '{intent}' but I'm not sure how to handle it."

    return {
        **state,
        "response": response,
    }


# =============================================================================
# BUILD THE GRAPH
# =============================================================================

def route_by_intent(state: AgentState) -> Literal["sql", "rag", "forecast", "respond"]:
    """Conditional edge: route the state to the appropriate node based on intent."""
    intent = state.get("intent", "general")

    if intent == "sql":
        return "sql"
    elif intent == "rag":
        return "rag"
    elif intent == "forecast":
        return "forecast"
    else:
        return "respond"


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph StateGraph."""
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("classify", classify_node)
    workflow.add_node("sql", sql_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("forecast", forecast_node)
    workflow.add_node("respond", respond_node)

    # Define edges
    workflow.add_edge(START, "classify")

    # Conditional routing: classify → sql | rag | forecast | respond
    workflow.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "sql": "sql",
            "rag": "rag",
            "forecast": "forecast",
            "respond": "respond",
        },
    )

    # All tool nodes converge to the response synthesizer
    workflow.add_edge("sql", "respond")
    workflow.add_edge("rag", "respond")
    workflow.add_edge("forecast", "respond")
    workflow.add_edge("respond", END)

    return workflow.compile()


# =============================================================================
# RUNNABLE ENTRY POINT
# =============================================================================

_graph = None  # module-level cache


def get_graph():
    """Return the compiled graph, creating it lazily."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_agent(user_query: str, history: list[dict] | None = None) -> AgentState:
    """
    Run the agent end-to-end on a single user query.

    Args:
        user_query: The user's natural language question.
        history: Optional conversation history (list of {role, content} dicts).

    Returns:
        The final AgentState with the response.
    """
    graph = get_graph()
    initial_state: AgentState = {
        "user_query": user_query,
        "messages": history or [],
        "intent": "",
        "tool_name": "",
        "tool_results": {},
        "response": "",
        "error": "",
    }
    final_state = graph.invoke(initial_state)
    return final_state
