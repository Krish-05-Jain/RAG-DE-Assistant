"""
app/agents/tools/pipeline_qa.py
────────────────────────────────
Pipeline Q&A Tool — now powered by Hybrid + Corrective RAG.

Logical flow:
  1. Accept a natural-language question about DE pipelines.
  2. Run the CRAG pipeline:
       a. Hybrid retrieve (Dense ChromaDB + BM25 sparse → RRF fusion)
       b. Grade each chunk: RELEVANT / AMBIGUOUS / IRRELEVANT
       c. If insufficient relevant chunks → rewrite query + re-retrieve
  3. Build a RAG prompt with the corrected context.
  4. Call the configured LLM (Ollama or Groq) for the answer.
  5. Return the answer, sources, and retrieval trace.
"""
from __future__ import annotations

import logging
from app.config import settings
from app.rag.corrective_rag import corrective_retrieve

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency
from app.agents.llm import call_llm


SYSTEM_PROMPT = """You are a senior Data Engineering assistant specialising in
pipeline architecture, ETL design, and operational runbooks.
Answer questions using ONLY the context provided below.
If the context doesn't contain the answer, say so honestly.
Always cite the source document in your answer using [source: filename]."""


def pipeline_qa(question: str) -> dict:
    """
    Answer a pipeline-related question using Hybrid + Corrective RAG.

    Args:
        question: Natural-language question about the DE pipeline.

    Returns:
        dict with:
          - 'answer'          (str)
          - 'sources'         (list[str])
          - 'rewritten_query' (str | None)  — set if query was rewritten
          - 'fallback_used'   (bool)         — True if no relevant docs found
          - 'retrieval_trace' (list[dict])   — graded hits for observability
    """
    # ── 1. CRAG retrieval ─────────────────────────────────────────────────────
    crag = corrective_retrieve(question, top_k=settings.retrieval_top_k)

    logger.info(
        "CRAG: %d graded hits | rewrite=%s | fallback=%s",
        len(crag.graded_hits),
        crag.rewritten_query is not None,
        crag.fallback_used,
    )

    # ── 2. Build LLM prompt ───────────────────────────────────────────────────
    effective_q = crag.rewritten_query or question
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Context:\n{crag.context}\n\n"
                f"Question: {question}"
                + (
                    f"\n\n(Note: query was internally rewritten to: '{effective_q}')"
                    if crag.rewritten_query else ""
                )
            ),
        },
    ]

    # ── 3. LLM call ────────────────────────────────────────────────────────────
    max_tok = 1024 if settings.llm_backend == "ollama" else 512

    response = call_llm(
        messages=messages,
        temperature=0.2,
        max_tokens=max_tok,
    )
    answer = response.content.strip() if response.content else ""
    logger.info("Pipeline QA answered. Sources: %s", crag.sources)

    return {
        "answer":          answer,
        "sources":         crag.sources,
        "rewritten_query": crag.rewritten_query,
        "fallback_used":   crag.fallback_used,
        "retrieval_trace": [
            {
                "source": h.get("source", ""),
                "grade":  h.get("grade", "?"),
                "rrf":    h.get("rrf_score", 0),
            }
            for h in crag.graded_hits
        ],
    }