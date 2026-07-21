"""
Phase 3: Document Embedding & ChromaDB Indexing
================================================
Loads the 10 synthetic business documents, splits them into semantic
chunks, generates embeddings with sentence-transformers, and stores
everything in a persistent ChromaDB vector store.

This is the indexing half of the Policy_RAG_Tool. The search half is
in query_docs.py.

Run:  python phase3_rag/embed_docs.py

Requirements (install when prompted):
  pip install langchain langchain-community chromadb sentence-transformers
"""

import os
from pathlib import Path

# --- LangChain imports (v1.3+ paths) ---
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document as LCDocument

# --- Paths ---
BASE = Path(__file__).resolve().parent
DOCS_DIR = BASE / "documents"
CHROMA_DIR = BASE / "chroma_db"

# --- Chunking config ---
CHUNK_SIZE = 400       # characters per chunk
CHUNK_OVERLAP = 60     # overlap between consecutive chunks


def load_documents(docs_dir: Path) -> list[LCDocument]:
    """
    Read all .txt files and wrap them as LangChain Document objects.
    Metadata is derived from the filename:
      - doc_type: 'supplier_contract', 'sop', or 'policy'
      - doc_name: human-readable title
    """
    docs = []
    for txt_path in sorted(docs_dir.glob("*.txt")):
        raw = txt_path.read_text(encoding="utf-8")
        fname = txt_path.stem  # e.g. "SUPPLIER_CONTRACT_Amul_Dairy_Products"

        # Derive document type from filename prefix
        if fname.startswith("SUPPLIER_CONTRACT"):
            doc_type = "supplier_contract"
        elif fname.startswith("SOP"):
            doc_type = "sop"
        elif fname.startswith("POLICY"):
            doc_type = "policy"
        else:
            doc_type = "unknown"

        doc = LCDocument(
            page_content=raw,
            metadata={
                "source": txt_path.name,
                "doc_type": doc_type,
                "doc_name": fname.replace("_", " ").title(),
            },
        )
        docs.append(doc)
    return docs


def chunk_documents(docs: list[LCDocument]) -> list[LCDocument]:
    """
    Split each document into overlapping chunks. The RecursiveCharacterTextSplitter
    tries to break on natural boundaries (double-newline → single-newline → space)
    before falling back to character-level splits.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    # Carry metadata forward (LangChain does this, but we add a chunk index)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
        # Keep a truncated preview for debugging
        chunk.metadata["preview"] = chunk.page_content[:80].replace("\n", " ")
    return chunks


def build_vectorstore(chunks: list[LCDocument], chroma_dir: Path) -> Chroma:
    """
    Embed all chunks and persist to ChromaDB using the
    all-MiniLM-L6-v2 model (384-dim, fast, local, no API key needed).
    """
    print("  Loading embedding model all-MiniLM-L6-v2 (first run downloads ~80 MB) ...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # Delete existing Chroma collection if present
    if chroma_dir.exists():
        import shutil
        shutil.rmtree(str(chroma_dir))

    print(f"  Embedding {len(chunks)} chunks ...")
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(chroma_dir),
        collection_name="aida_policies",
    )
    # Chroma auto-persists with persist_directory in recent versions.
    # Explicit persist is a no-op for the new client, but keep for compat.
    return vectordb


def main():
    print("=" * 60)
    print("AIDA Phase 3 — Document Embedding & Vector Store")
    print("=" * 60)

    # 1. Load
    print("\n[1/3] Loading documents ...")
    docs = load_documents(DOCS_DIR)
    print(f"  Loaded {len(docs)} documents")
    for d in docs:
        print(f"    {d.metadata['doc_type']:20s} | {d.metadata['source']}")

    # 2. Chunk
    print(f"\n[2/3] Chunking (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}) ...")
    chunks = chunk_documents(docs)
    print(f"  Created {len(chunks)} chunks from {len(docs)} documents")
    # Show a sample chunk
    if chunks:
        sample = chunks[len(chunks) // 2]
        print(f"  Sample chunk #{sample.metadata['chunk_id']}:")
        print(f"    Preview: {sample.metadata['preview']}...")

    # 3. Embed & Store
    print(f"\n[3/3] Embedding & storing to {CHROMA_DIR} ...")
    vectordb = build_vectorstore(chunks, CHROMA_DIR)

    # Quick sanity check
    print("\nVerification:")
    results = vectordb.similarity_search("cold chain temperature requirements", k=3)
    for i, r in enumerate(results):
        print(f"  [{i+1}] {r.metadata['source']} (chunk {r.metadata['chunk_id']})")
        print(f"      \"{r.page_content[:100].strip()}...\"")

    print(f"\nVector store ready: {CHROMA_DIR}")
    print(f"Documents: {len(docs)} -> Chunks: {len(chunks)}")
    print("Next: python phase3_rag/query_docs.py")


if __name__ == "__main__":
    main()
