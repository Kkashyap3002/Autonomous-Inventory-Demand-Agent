"""
Phase 5: AIDA Agent — Interactive CLI
=======================================
Run the full LangGraph agent in interactive mode. Type your questions
and the agent will route them to the right tool automatically.

Usage:
  python phase5_agent/run_agent.py                        (interactive mode)
  python phase5_agent/run_agent.py "revenue by store"     (single query)
  python phase5_agent/run_agent.py --demo                 (demo tour)

Dependencies:
  pip install langgraph
"""

import sys
from pathlib import Path

# Ensure project root is importable
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from phase5_agent.graph import run_agent


# =============================================================================
# DEMO QUERIES — exercises all 3 tools + classifier
# =============================================================================
DEMO_QUERIES = [
    # SQL tool
    ("SQL: Revenue Dashboard", "Which store has the highest revenue?"),
    ("SQL: Low Stock Alert", "Show me all products that are low in stock"),
    ("SQL: Category Margin", "What is the margin by category?"),
    ("SQL: Supplier Scorecard", "How are my suppliers performing on fill rate?"),
    ("SQL: Peak Hours", "What are the peak order hours?"),
    ("SQL: Product Ranking", "What are the top selling products?"),
    ("SQL: Sales Trend", "How have sales been trending over the last 14 days?"),

    # RAG tool
    ("RAG: Return Policy", "What is the return window for perishable dairy products?"),
    ("RAG: Cold Chain", "What temperature must frozen products be kept at?"),
    ("RAG: Penalty Clause", "What is the penalty for late delivery from Amul?"),
    ("RAG: Wastage Sharing", "What is the wastage sharing agreement for fruits and vegetables?"),
    ("RAG: Fraud Policy", "What is the fraud prevention threshold for customer returns?"),
    ("RAG: Supplier PIP", "What happens if a supplier scores below 70 for two months?"),

    # Forecast tool
    ("Forecast: All", "Show me the demand forecast for the next 7 days"),
    ("Forecast: Dairy", "Forecast demand for dairy products for the next 7 days"),
    ("Forecast: At Risk", "Which products are at risk of stockout based on forecasts?"),

    # General / edge cases
    ("General: Help", "What can you do?"),
    ("General: Greeting", "Hello, who are you?"),
]


def run_demo():
    """Run through all demo queries with pauses."""
    print("\n" + "=" * 60)
    print("  AIDA AGENT — DEMO TOUR")
    print("=" * 60)
    print("  Running 17 queries across all 3 tools ...\n")

    for i, (label, query) in enumerate(DEMO_QUERIES, 1):
        print(f"[{i}/{len(DEMO_QUERIES)}] {label}")
        print(f"Q: {query}")
        print("-" * 40)
        result = run_agent(query)
        # Print first 500 chars of response for brevity
        resp = result.get("response", "No response")
        if len(resp) > 500:
            resp = resp[:500] + "..."
        print(resp)
        print()


def run_interactive():
    """Run the agent in an interactive chat loop."""
    print("\n" + "=" * 60)
    print("  AIDA — Autonomous Inventory & Demand Agent")
    print("=" * 60)
    print("  Type your questions. Type 'demo' for a tour, 'quit' to exit.")
    print("  I can answer SQL queries, policy questions, and forecasts.\n")

    history = []
    while True:
        try:
            query = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if query.lower() == "demo":
            run_demo()
            continue

        result = run_agent(query, history)
        response = result.get("response", "I couldn't process that.")
        intent = result.get("intent", "?")
        tool = result.get("tool_name", "?")

        print(f"\nAIDA [{intent}/{tool}] >")
        print(response)
        print()

        # Keep history
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": response})


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo()
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        # Single query mode
        query = " ".join(sys.argv[1:])
        result = run_agent(query)
        print(f"\nAIDA [{result.get('intent', '?')}/{result.get('tool_name', '?')}] >")
        print(result.get("response", "No response"))
    else:
        run_interactive()


if __name__ == "__main__":
    main()
