"""
app/rag/retriever.py
─────────────────────
Hybrid retriever combining vector similarity + keyword matching.

Logical flow:
  1. Embed the user query with the same sentence-transformer model.
  2. Run a vector similarity search against ChromaDB (top-K).
  3. Apply a keyword post-filter to boost relevance.
  4. Format results into a plain-text context block for the LLM.
"""

import re
import logging
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.rag.vectorstore import (
    get_chroma_client,
    get_or_create_collection,
    query_collection,
)

logger = logging.getLogger(__name__)

# Shared embedder instance (loaded once per process)
_embedder = SentenceTransformer(settings.embedding_model)


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """
    Retrieve the most relevant chunks for `query`.

    Returns:
        List of dicts: [{'content': str, 'source': str, 'score': float}]
    """
    top_k = top_k or settings.retrieval_top_k
    query_embedding = _embedder.encode([query]).tolist()

    client = get_chroma_client()
    collection = get_or_create_collection(client)

    results = query_collection(
        collection=collection,
        query_embeddings=query_embedding,
        n_results=top_k,
    )

    hits = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        hits.append(
            {
                "content": doc,
                "source": meta.get("source", "unknown"),
                "score": round(1 - dist, 4),  # cosine similarity
                "metadata": meta,
            }
        )

    # Keyword boost: move exact query-term matches to top
    query_terms = set(re.findall(r"\w+", query.lower()))
    hits.sort(
        key=lambda h: sum(
            1 for t in query_terms if t in h["content"].lower()
        ),
        reverse=True,
    )

    logger.debug(f"Retrieved {len(hits)} chunks for query: {query!r}")
    return hits


def format_context(hits: list[dict]) -> str:
    """Format retrieved chunks into a numbered context block."""
    if not hits:
        return "No relevant documentation found."
    lines = []
    for i, hit in enumerate(hits, 1):
        src = hit["source"].split("/")[-1]
        lines.append(f"[{i}] (source: {src}, score: {hit['score']})")
        lines.append(hit["content"])
        lines.append("")
    return "\n".join(lines)
