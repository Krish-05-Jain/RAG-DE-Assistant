"""
app/rag/grader.py
──────────────────
Relevance grader for Corrective RAG.

Logical flow:
  1. For each retrieved chunk, call the LLM with a tight binary-grading prompt.
  2. Parse the response to extract: RELEVANT / AMBIGUOUS / IRRELEVANT.
  3. Return a list of (chunk, grade) pairs for the corrective pipeline.

Design choices:
  - Uses the same Ollama/Groq client as the orchestrator to avoid a second
    model connection.
  - Prompt is deliberately short and deterministic (temperature=0).
  - Falls back to AMBIGUOUS on any parse failure (safe default).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Literal

from app.config import settings

logger = logging.getLogger(__name__)

Grade = Literal["RELEVANT", "AMBIGUOUS", "IRRELEVANT"]

_GRADE_PROMPT = """\
You are a strict relevance grader.
Given a USER QUESTION and a DOCUMENT CHUNK, respond with ONLY a JSON object:
  {{"grade": "RELEVANT"}}      — chunk directly answers the question
  {{"grade": "AMBIGUOUS"}}    — chunk is loosely related but incomplete
  {{"grade": "IRRELEVANT"}}   — chunk is off-topic

USER QUESTION: {question}

DOCUMENT CHUNK:
{chunk}

JSON response (no explanation, no markdown):"""


def grade_chunk(question: str, chunk: str) -> Grade:
    """
    Grade a single chunk against the question.
    Returns 'RELEVANT', 'AMBIGUOUS', or 'IRRELEVANT'.
    """
    from app.agents.llm import call_llm
    prompt = _GRADE_PROMPT.format(
        question=question.strip(),
        chunk=chunk.strip()[:800],  # cap to avoid token waste
    )
    try:
        resp = call_llm(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0,
        )
        raw = resp.content.strip() if resp.content else ""
        # Extract JSON even if model adds surrounding text
        match = re.search(r'\{.*?"grade"\s*:\s*"(\w+)".*?\}', raw, re.DOTALL)
        if match:
            grade = match.group(1).upper()
            if grade in ("RELEVANT", "AMBIGUOUS", "IRRELEVANT"):
                return grade  # type: ignore[return-value]
        logger.debug("Grade parse fallback for raw: %r", raw)
    except Exception as exc:
        logger.warning("Grader error: %s", exc)
    return "AMBIGUOUS"  # safe fallback


def grade_hits(
    question: str,
    hits: list[dict],
) -> list[dict]:
    """
    Grade every hit and attach a 'grade' key.

    Returns same list with added keys:
        hit["grade"]  → 'RELEVANT' | 'AMBIGUOUS' | 'IRRELEVANT'
    """
    graded = []
    for hit in hits:
        g = grade_chunk(question, hit["content"])
        graded.append({**hit, "grade": g})
        logger.debug("Grade: %s | source: %s", g, hit.get("source", "?"))
    return graded
