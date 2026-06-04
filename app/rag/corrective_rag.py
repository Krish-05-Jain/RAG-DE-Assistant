"""
app/rag/corrective_rag.py
──────────────────────────
Corrective RAG (CRAG) pipeline.

Full logical flow:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Query                                                          │
  │   │                                                             │
  │   ▼                                                             │
  │  [1] Hybrid Retrieve  (Dense + BM25 via RRF)                   │
  │   │                                                             │
  │   ▼                                                             │
  │  [2] Grade each chunk (LLM relevance grader)                   │
  │   │                                                             │
  │   ├─ ALL IRRELEVANT ────► [3a] Rewrite query + re-retrieve     │
  │   │                            → grade again                   │
  │   │                            → return best available         │
  │   │                                                             │
  │   ├─ SOME AMBIGUOUS ───► [3b] Keep RELEVANT, discard rest      │
  │   │                            (optionally supplement with      │
  │   │                             re-retrieved on rewritten q)   │
  │   │                                                             │
  │   └─ HAS RELEVANT ─────► [4] Format context for LLM           │
  │                                                                 │
  │   ▼                                                             │
  │  Return: { context, sources, retrieval_trace }                  │
  └─────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.rag.hybrid_retriever import hybrid_retrieve, format_context
from app.rag.grader import grade_hits
from app.rag.compressor import compress_hits

logger = logging.getLogger(__name__)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CRAGResult:
    """Output of the CRAG pipeline."""
    context: str                         # Formatted text for the LLM prompt
    sources: list[str]                   # Deduplicated source file names
    graded_hits: list[dict]              # All hits with their grade attached
    rewritten_query: Optional[str] = None  # Set if query was rewritten
    fallback_used: bool = False          # True if no relevant docs were found


# ── Query rewriter ────────────────────────────────────────────────────────────

_REWRITE_PROMPT = """\
Rewrite the following question to improve document retrieval.
Make it more specific and use different keywords.
Return ONLY the rewritten question, nothing else.

Original question: {question}
Rewritten question:"""


def _rewrite_query(question: str) -> str:
    """Ask the LLM to rewrite the query for better retrieval coverage."""
    try:
        from app.agents.llm import call_llm
        resp = call_llm(
            messages=[{
                "role": "user",
                "content": _REWRITE_PROMPT.format(question=question),
            }],
            max_tokens=80,
            temperature=0.3,
        )
        rewritten = resp.content.strip()
        logger.info("Query rewritten: %r → %r", question, rewritten)
        return rewritten
    except Exception as exc:
        logger.warning("Query rewrite failed: %s — using original", exc)
        return question


# ── Main CRAG pipeline ────────────────────────────────────────────────────────

def corrective_retrieve(
    query: str,
    top_k: int = 5,
    grade_threshold_relevant: int = 1,   # min RELEVANT hits before accepting
    enable_rewrite: bool = True,
) -> CRAGResult:
    """
    Run the full Hybrid + Corrective RAG pipeline.
    Implements metadata-aware search/boosting, context compression, and reranking.
    """
    rewritten_query: Optional[str] = None
    fallback_used = False

    # ── Metadata Extraction & Structured Context Generation ─────────────────
    from app.agents.tools.catalog_explorer import get_all_tables, get_table_by_name, get_lineage
    
    # Find any tables from the catalog mentioned in the query
    try:
        all_tables_meta = get_all_tables()
        table_names = [t["name"] for t in all_tables_meta]
    except Exception:
        table_names = []
    
    mentioned_tables = [t for t in table_names if t.lower() in query.lower()]
    
    metadata_context_parts = []
    for t_name in mentioned_tables:
        t_info = get_table_by_name(t_name)
        if t_info:
            cols_str = ", ".join([f"{c['name']} ({c['type']}{' - PII' if c.get('pii') else ''})" for c in t_info.get("columns", [])])
            metadata_context_parts.append(
                f"STRUCTURED CATALOG METADATA FOR TABLE '{t_name}':\n"
                f"- Description: {t_info.get('description', '')}\n"
                f"- Owner: {t_info.get('owner', '')}\n"
                f"- Schema: [{cols_str}]\n"
                f"- Update Frequency: {t_info.get('update_frequency', '')}\n"
                f"- Expected Row Count: {t_info.get('expected_row_count', 0)}"
            )
            # Add lineage details
            lin = get_lineage(t_name, direction="both")
            if lin.get("upstream"):
                metadata_context_parts.append(f"- Upstream sources: {', '.join(lin['upstream'])}")
            if lin.get("downstream"):
                metadata_context_parts.append(f"- Downstream targets: {', '.join(lin['downstream'])}")
            metadata_context_parts.append("")
            
    metadata_context_str = "\n".join(metadata_context_parts) if metadata_context_parts else ""

    # ── Step 1: Hybrid retrieve with metadata-aware boosting ──────────────────
    # Fetch double top_k to allow boosting chunks that match the catalog metadata
    hits = hybrid_retrieve(query, top_k=top_k * 2)
    logger.info("CRAG step 1 — hybrid retrieved %d hits", len(hits))

    if not hits:
        logger.warning("CRAG: no documents in vector store")
        return CRAGResult(
            context=metadata_context_str if metadata_context_str else "No relevant documentation found.",
            sources=[],
            graded_hits=[],
            fallback_used=True,
        )

    # Prioritize and boost chunks that are tagged with the mentioned tables
    if mentioned_tables:
        for h in hits:
            meta = h.get("metadata", {})
            tables_meta = meta.get("tables", "") if isinstance(meta, dict) else ""
            if any(t.lower() in tables_meta.lower() for t in mentioned_tables):
                h["rrf_score"] = h.get("rrf_score", 0.0) + 0.15  # Semantic boost
        # Re-sort by boosted RRF score
        hits.sort(key=lambda x: x.get("rrf_score", 0.0), reverse=True)

    # Slice back to target top_k
    hits = hits[:top_k]

    # ── Step 2: Grade each hit ────────────────────────────────────────────────
    graded = grade_hits(query, hits)
    relevant  = [h for h in graded if h["grade"] == "RELEVANT"]
    ambiguous = [h for h in graded if h["grade"] == "AMBIGUOUS"]
    irrelevant = [h for h in graded if h["grade"] == "IRRELEVANT"]

    logger.info(
        "CRAG step 2 — grades: %d relevant, %d ambiguous, %d irrelevant",
        len(relevant), len(ambiguous), len(irrelevant),
    )

    # ── Step 3: Corrective actions ────────────────────────────────────────────
    if len(relevant) < grade_threshold_relevant and enable_rewrite:
        # 3a: All/mostly irrelevant → rewrite and re-retrieve
        rewritten_query = _rewrite_query(query)
        new_hits = hybrid_retrieve(rewritten_query, top_k=top_k)
        new_graded = grade_hits(rewritten_query, new_hits)
        new_relevant = [h for h in new_graded if h["grade"] == "RELEVANT"]

        if new_relevant:
            logger.info(
                "CRAG step 3a — re-retrieve found %d relevant hits", len(new_relevant)
            )
            # Merge: prefer new relevant, supplement with original relevant
            final_hits = new_relevant + relevant
        else:
            # Last resort: use ambiguous from both rounds
            logger.warning("CRAG step 3a — still no relevant hits after rewrite")
            final_hits = new_graded + ambiguous
            fallback_used = True

        graded = new_graded  # update trace with new grading
    else:
        # 3b: We have enough relevant hits — keep them (discard IRRELEVANT)
        final_hits = relevant if relevant else ambiguous

    # Deduplicate by content prefix
    seen: set[str] = set()
    deduped: list[dict] = []
    for h in final_hits:
        key = h["content"][:120]
        if key not in seen:
            seen.add(key)
            deduped.append(h)

    final_hits = deduped[:top_k]

    # ── Context Compression ───────────────────────────────────────────────────
    compressed_hits = compress_hits(query, final_hits)

    # ── Step 4: Format output ─────────────────────────────────────────────────
    context = format_context(compressed_hits) if compressed_hits else "No relevant documentation found."
    if metadata_context_str:
        context = f"{metadata_context_str}\n\nRELEVANT DOCUMENTATION & CODE CHUNKS:\n{context}"
        
    sources = list({h["source"].split("/")[-1] for h in final_hits})

    return CRAGResult(
        context=context,
        sources=sources,
        graded_hits=graded,
        rewritten_query=rewritten_query,
        fallback_used=fallback_used,
    )
