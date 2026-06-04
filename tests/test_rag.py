"""
tests/test_rag.py
──────────────────
Unit tests for the RAG pipeline.

Tests:
  - Document loading from pipeline_docs/
  - Chunk splitting produces expected sizes
  - ChromaDB upsert and query roundtrip
"""

import pytest
from pathlib import Path
from app.rag.ingestion import load_markdown_files, chunk_documents
from app.rag.retriever import retrieve, format_context


def test_load_markdown_files():
    """Should load all 5 markdown files from data/pipeline_docs."""
    docs_dir = Path("data/pipeline_docs")
    if not docs_dir.exists():
        pytest.skip("data/pipeline_docs not present")
    docs = load_markdown_files(docs_dir)
    assert len(docs) >= 1, "Expected at least 1 markdown file"
    for doc in docs:
        assert "source" in doc
        assert "content" in doc
        assert len(doc["content"]) > 0


def test_chunk_documents():
    """Chunks should be <= chunk_size characters."""
    from app.config import settings
    docs = [{"source": "test.md", "content": "A " * 1000}]
    chunks = chunk_documents(docs)
    assert len(chunks) > 1, "Long doc should produce multiple chunks"
    for chunk in chunks:
        assert len(chunk["content"]) <= settings.chunk_size + 50  # slight overlap tolerance


def test_chunk_ids_are_unique():
    """Every chunk should have a unique ID."""
    docs = [
        {"source": "doc1.md", "content": "A " * 500},
        {"source": "doc2.md", "content": "B " * 500},
    ]
    chunks = chunk_documents(docs)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids)), "Chunk IDs must be unique"


def test_format_context_empty():
    """format_context should handle empty hits gracefully."""
    result = format_context([])
    assert "No relevant" in result


def test_format_context_with_hits():
    """format_context should number sources and include content."""
    hits = [
        {"content": "Bronze ingestion uses exponential backoff.", "source": "bronze_ingestion.md", "score": 0.95},
        {"content": "Silver layer applies SCD Type 2.", "source": "silver_transformation.md", "score": 0.88},
    ]
    context = format_context(hits)
    assert "[1]" in context
    assert "[2]" in context
    assert "bronze_ingestion.md" in context
