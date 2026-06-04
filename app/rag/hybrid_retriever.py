"""
app/rag/hybrid_retriever.py
────────────────────────────
Hybrid retriever: Dense (vector) + Sparse (BM25) fused with
Reciprocal Rank Fusion (RRF).

Logical flow:
  1. Run dense retrieval (ChromaDB cosine similarity).
  2. Run sparse retrieval (BM25Plus keyword matching) in parallel.
  3. Merge both ranked lists with RRF:
       RRF_score(d) = Σ  1 / (k + rank_i(d))
  4. Return top-K de-duplicated hits ordered by RRF score.

Why RRF?
  - No normalisation required (scores from different systems are incomparable).
  - Simple, robust, empirically beats naive score averaging.
"""
from __future__ import annotations

import logging
from app.rag.retriever import retrieve as dense_retrieve
from app.rag.bm25_retriever import bm25_retrieve

logger = logging.getLogger(__name__)

# RRF constant — 60 is the standard recommended value
_RRF_K = 60


def _rrf_score(rank: int, k: int = _RRF_K) -> float:
    return 1.0 / (k + rank)


def hybrid_retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve and fuse dense + sparse results using Reciprocal Rank Fusion.

    Returns:
        [{"content": str, "source": str, "rrf_score": float,
          "dense_rank": int|None, "bm25_rank": int|None}]
    """
    fetch_k = top_k * 3  # over-fetch so fusion has more candidates

    # ── 1. Dense results ────────────────────────────────────────────────────
    dense_hits = dense_retrieve(query, top_k=fetch_k)
    dense_rank_map: dict[str, int] = {}
    for rank, hit in enumerate(dense_hits, 1):
        key = hit["content"][:120]  # use prefix as dedup key
        dense_rank_map[key] = rank

    # ── 2. Sparse results ───────────────────────────────────────────────────
    bm25_hits = bm25_retrieve(query, top_k=fetch_k)
    bm25_rank_map: dict[str, tuple[int, dict]] = {}
    for rank, hit in enumerate(bm25_hits, 1):
        key = hit["content"][:120]
        bm25_rank_map[key] = (rank, hit)

    # ── 3. RRF fusion ────────────────────────────────────────────────────────
    all_keys: set[str] = set(dense_rank_map) | set(bm25_rank_map)
    scored: list[dict] = []

    for key in all_keys:
        d_rank = dense_rank_map.get(key)
        b_rank, b_hit = bm25_rank_map.get(key, (None, None))

        rrf = 0.0
        if d_rank is not None:
            rrf += _rrf_score(d_rank)
        if b_rank is not None:
            rrf += _rrf_score(b_rank)

        # Recover full content/source/metadata
        if b_hit:
            content = b_hit["content"]
            source  = b_hit["source"]
            metadata = b_hit.get("metadata", {})
        else:
            # find from dense hits
            match = next((h for h in dense_hits if h["content"][:120] == key), None)
            content = match["content"] if match else key
            source  = match["source"]  if match else "unknown"
            metadata = match.get("metadata", {}) if match else {}

        scored.append({
            "content":    content,
            "source":     source,
            "rrf_score":  round(rrf, 6),
            "dense_rank": d_rank,
            "bm25_rank":  b_rank,
            "metadata":   metadata,
        })

    # ── 4. Sort and return top-K ─────────────────────────────────────────────
    scored.sort(key=lambda x: x["rrf_score"], reverse=True)
    result = scored[:top_k]

    logger.info(
        "Hybrid retrieve: %d dense + %d sparse → %d fused (top %d)",
        len(dense_hits), len(bm25_hits), len(scored), top_k,
    )
    return result


def format_context(hits: list[dict]) -> str:
    """Format hybrid hits into a numbered context block for the LLM."""
    if not hits:
        return "No relevant documentation found."
    lines = []
    for i, hit in enumerate(hits, 1):
        src   = hit["source"].split("/")[-1]
        score = hit.get("rrf_score", 0)
        d_r   = hit.get("dense_rank", "-")
        b_r   = hit.get("bm25_rank", "-")
        lines.append(
            f"[{i}] source={src}  rrf={score:.4f}  dense_rank={d_r}  bm25_rank={b_r}"
        )
        lines.append(hit["content"])
        lines.append("")
    return "\n".join(lines)
