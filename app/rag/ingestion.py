"""
app/rag/ingestion.py
─────────────────────
Document ingestion pipeline.

Logical flow:
  1. Walk `data/pipeline_docs/` and load every Markdown file.
  2. Split each document into overlapping chunks using
     RecursiveCharacterTextSplitter (chunk_size=500, overlap=50).
  3. Embed each chunk with sentence-transformers (all-MiniLM-L6-v2).
  4. Upsert chunks into ChromaDB with source + section metadata.

Run from project root:
    python -m app.rag.ingestion
"""

import os
import hashlib
import logging
from pathlib import Path

from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.rag.vectorstore import (
    get_chroma_client,
    get_or_create_collection,
    upsert_documents,
)

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# ── Embedding model (loaded once) ──────────────────────────────────────────────
_embedder = SentenceTransformer(settings.embedding_model)

# ── Text splitter ─────────────────────────────────────────────────────────────
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _stable_id(source: str, chunk_index: int) -> str:
    """Generate a stable, deterministic chunk ID."""
    raw = f"{source}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_table_names() -> list[str]:
    """Helper to load all known table names from tables.json to use for tagging."""
    try:
        tables_path = settings.catalogue_dir / "tables.json"
        if tables_path.exists():
            tables_data = json.loads(tables_path.read_text())
            return [t["name"] for t in tables_data]
    except Exception as e:
        logger.error(f"Failed to load table names for ingestion tagging: {e}")
    return []

import json
_KNOWN_TABLES = _load_table_names()

def load_markdown_files(docs_dir: Path) -> list[dict]:
    """Backward compatibility shim for tests."""
    return load_all_files(docs_dir, Path("nonexistent"))


def load_all_files(docs_dir: Path, code_dir: Path) -> list[dict]:
    """
    Recursively load .md, .py, and .sql files from docs_dir and code_dir.
    Returns list of {'source': str, 'content': str, 'file_type': str, 'extension': str}
    """
    docs = []
    
    # Load markdown documentation
    if docs_dir.exists():
        for path in sorted(docs_dir.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            docs.append({
                "source": str(path),
                "content": text,
                "file_type": "documentation",
                "extension": ".md"
            })
            logger.info(f"Loaded Doc: {path.name} ({len(text)} chars)")
            
    # Load python and sql source code
    if code_dir.exists():
        for ext in ("*.py", "*.sql"):
            for path in sorted(code_dir.rglob(ext)):
                text = path.read_text(encoding="utf-8")
                docs.append({
                    "source": str(path),
                    "content": text,
                    "file_type": "source_code",
                    "extension": Path(path).suffix
                })
                logger.info(f"Loaded Code: {path.name} ({len(text)} chars)")
                
    return docs


def chunk_documents(docs: list[dict]) -> list[dict]:
    """
    Split documents into overlapping chunks.
    Returns list of {'chunk_id', 'source', 'content', 'file_type', 'extension'} dicts.
    """
    chunks = []
    for doc in docs:
        pieces = _splitter.split_text(doc["content"])
        for i, piece in enumerate(pieces):
            chunks.append(
                {
                    "chunk_id": _stable_id(doc["source"], i),
                    "source": doc["source"],
                    "content": piece,
                    "file_type": doc.get("file_type", "documentation"),
                    "extension": doc.get("extension", ".md"),
                }
            )
    logger.info(f"Total chunks produced: {len(chunks)}")
    return chunks


def embed_and_ingest(chunks: list[dict]) -> int:
    """
    Embed chunks and upsert into ChromaDB with enriched metadata.
    """
    client = get_chroma_client()
    collection = get_or_create_collection(client)

    texts = [c["content"] for c in chunks]
    embeddings = _embedder.encode(texts, show_progress_bar=True).tolist()

    metadatas = []
    for c in chunks:
        # Tag tables referenced in chunk
        mentioned_tables = [t for t in _KNOWN_TABLES if t.lower() in c["content"].lower()]
        tables_str = ",".join(mentioned_tables) if mentioned_tables else "none"
        
        metadatas.append({
            "source": c["source"],
            "file_type": c["file_type"],
            "extension": c["extension"],
            "tables": tables_str
        })

    upsert_documents(
        collection=collection,
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )
    logger.info(f"Ingested {len(chunks)} chunks into ChromaDB with metadata-aware tagging.")
    return len(chunks)


def run_ingestion(docs_dir: Path | None = None, code_dir: Path | None = None) -> int:
    """End-to-end ingestion: load → chunk → embed → upsert."""
    docs_dir = docs_dir or settings.pipeline_docs_dir
    code_dir = code_dir or settings.pipeline_code_dir
    docs = load_all_files(docs_dir, code_dir)
    if not docs:
        logger.warning(f"No files found for ingestion.")
        return 0
    chunks = chunk_documents(docs)
    
    # Invalidate BM25 cache so it rebuilds on next search
    from app.rag.bm25_retriever import invalidate_index
    invalidate_index()
    
    return embed_and_ingest(chunks)


if __name__ == "__main__":
    total = run_ingestion()
    print(f"✅ Ingestion complete — {total} chunks stored.")
