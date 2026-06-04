"""
app/rag/bm25_retriever.py
──────────────────────────
Sparse BM25 retriever.

Logical flow:
  1. On first call, fetch all documents from ChromaDB.
  2. Tokenise each document and build a BM25Plus index.
  3. For a given query, score every document and return top-K hits.
  4. Cache the index in memory for the process lifetime.
"""
from __future__ import annotations

import re
import logging
from rank_bm25 import BM25Plus

from app.rag.vectorstore import get_chroma_client, get_or_create_collection

logger = logging.getLogger(__name__)

# ── In-process index cache ────────────────────────────────────────────────────
_bm25: BM25Plus | None = None
_corpus: list[str] = []
_sources: list[str] = []
_metas: list[dict] = []


def _tokenise(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _build_index() -> None:
    """Load all docs from ChromaDB and build the BM25Plus index."""
    global _bm25, _corpus, _sources, _metas

    client = get_chroma_client()
    collection = get_or_create_collection(client)
    total = collection.count()

    if total == 0:
        logger.warning("BM25: ChromaDB collection is empty — no index built.")
        _bm25 = None
        return

    result = collection.get(include=["documents", "metadatas"])
    _corpus = result.get("documents", [])
    _metas = result.get("metadatas", [])
    _sources = [m.get("source", "unknown") for m in _metas]

    tokenised = [_tokenise(doc) for doc in _corpus]
    _bm25 = BM25Plus(tokenised)
    logger.info("BM25 index built: %d documents", len(_corpus))


def bm25_retrieve(query: str, top_k: int = 10) -> list[dict]:
    """
    Return top-K BM25 hits for *query*.

    Returns:
        [{"content": str, "source": str, "bm25_score": float, "rank": int, "metadata": dict}]
    """
    global _bm25

    if _bm25 is None:
        _build_index()

    if _bm25 is None or not _corpus:
        return []

    tokens = _tokenise(query)
    scores = _bm25.get_scores(tokens)

    ranked = sorted(
        enumerate(scores), key=lambda x: x[1], reverse=True
    )[:top_k]

    hits = []
    for rank, (idx, score) in enumerate(ranked, 1):
        hits.append({
            "content":    _corpus[idx],
            "source":     _sources[idx],
            "bm25_score": round(float(score), 4),
            "rank":       rank,
            "metadata":   _metas[idx] if idx < len(_metas) else {},
        })

    logger.debug("BM25 top-%d hits for %r", top_k, query)
    return hits


def invalidate_index() -> None:
    """Force a rebuild on the next call (e.g. after re-ingestion)."""
    global _bm25
    _bm25 = None
