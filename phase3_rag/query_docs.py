"""
Phase 3: RAG Query Tool (Standalone Test & Agent Tool)
========================================================
Loads the persisted ChromaDB vector store and provides:
  1. A standalone CLI test:     python phase3_rag/query_docs.py "your question"
  2. The query_policy() function that the LangGraph agent will import
     in Phase 5 as the Policy_RAG_Tool.

Usage:
  python phase3_rag/query_docs.py "What is the return window for dairy products?"
  python phase3_rag/query_docs.py "What temperature must frozen products be kept at?"
  python phase3_rag/query_docs.py                # interactive test mode
"""

import sys
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

BASE = Path(__file__).resolve().parent
CHROMA_DIR = BASE / "chroma_db"


def load_vectordb() -> Chroma:
    """Load the persisted Chroma vector store."""
    if not CHROMA_DIR.exists():
        raise FileNotFoundError(
            f"ChromaDB not found at {CHROMA_DIR}. "
            "Run 'python phase3_rag/embed_docs.py' first."
        )
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    return Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
        collection_name="aida_policies",
    )


def query_policy(question: str, k: int = 4) -> list[dict]:
    """
    Search the policy/knowledge base for the most relevant chunks.

    This is the function the LangGraph agent's Policy_RAG_Tool will call.
    It returns a list of dicts with source, content, and metadata so the
    agent can cite the source in its response.

    Args:
        question: Natural language query about SOPs, contracts, or policies.
        k: Number of chunks to retrieve (default 4).

    Returns:
        List of dicts, each with keys: source, doc_type, content, score
    """
    vectordb = load_vectordb()
    results = vectordb.similarity_search_with_relevance_scores(question, k=k)

    output = []
    for doc, score in results:
        output.append({
            "source": doc.metadata.get("source", "unknown"),
            "doc_type": doc.metadata.get("doc_type", "unknown"),
            "chunk_id": doc.metadata.get("chunk_id", -1),
            "content": doc.page_content.strip(),
            "relevance": round(score, 4),
        })
    return output


def format_results(question: str, results: list[dict]) -> str:
    """Pretty-print search results for CLI."""
    lines = [f"\nQuery: \"{question}\"", "=" * 60]
    if not results:
        lines.append("  No results found.")
        return "\n".join(lines)

    for i, r in enumerate(results, 1):
        lines.append(f"\n--- Result {i}  (relevance: {r['relevance']:.4f}) ---")
        lines.append(f"  Source:   {r['source']} ({r['doc_type']})")
        lines.append(f"  Chunk ID: {r['chunk_id']}")
        # Truncate content for display
        content = r["content"]
        if len(content) > 350:
            content = content[:350] + "..."
        lines.append(f"  Content:  \"{content}\"")
    return "\n".join(lines)


# =============================================================================
# Pre-canned test queries that exercise different retrieval patterns
# =============================================================================
TEST_QUERIES = [
    "What is the return window for perishable dairy products?",
    "What temperature must frozen products be stored at?",
    "What is the penalty for late delivery from Amul?",
    "How much marketing fund does PepsiCo provide for promotions?",
    "What is the reorder point formula and safety stock calculation?",
    "How long does a delivery rider have to complete last-mile delivery?",
    "What happens if a supplier scores below 70 for two consecutive months?",
    "What is the wastage sharing agreement for fruits and vegetables?",
    "What are the different quality grades for produce from LocalPro?",
    "What is the fraud prevention threshold for customer returns?",
]


def main():
    vectordb = load_vectordb()

    # If the user passed a query, answer it and exit
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        results = query_policy(question)
        print(format_results(question, results))
        return

    # Otherwise, run the interactive test suite
    print("=" * 60)
    print("AIDA Phase 3 — Policy RAG Query Test Suite")
    print("=" * 60)
    print(f"Vector store: {CHROMA_DIR}")
    print(f"Collection:   aida_policies")
    print(f"\nRunning {len(TEST_QUERIES)} test queries ...")

    for q in TEST_QUERIES:
        results = query_policy(q, k=2)
        print(format_results(q, results))

    print("\n" + "=" * 60)
    print("Test suite complete.")
    print("Usage: python phase3_rag/query_docs.py \"your custom question\"")


if __name__ == "__main__":
    main()
