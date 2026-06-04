"""
app/rag/compressor.py
───────────────────────
Sentence-level context compressor.
Uses the sentence-transformer embedding model to filter out sentences in
retrieved chunks that are not relevant to the user query.
"""

import re
import numpy as np
from numpy.linalg import norm
from sentence_transformers import SentenceTransformer
from app.config import settings

# Load the same sentence transformer model (reuses library cache)
_compress_embedder = SentenceTransformer(settings.embedding_model)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = norm(a) * norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compress_chunk(query: str, content: str, threshold: float = 0.35) -> str:
    """
    Splits content into sentences and keeps only those semantically relevant to the query.
    Always preserves at least the top-1 sentence to avoid returning empty text.
    """
    # Split content by sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content) if s.strip()]
    if not sentences:
        return content

    # Embed query and sentences
    query_emb = _compress_embedder.encode([query])[0]
    sent_embs = _compress_embedder.encode(sentences)

    scored_sentences = []
    for idx, (sentence, emb) in enumerate(zip(sentences, sent_embs)):
        score = _cosine_similarity(query_emb, emb)
        scored_sentences.append((idx, sentence, score))

    # Keep sentences meeting threshold OR the highest scoring sentence
    highest_score = max(scored_sentences, key=lambda x: x[2])
    kept = []
    for idx, sentence, score in scored_sentences:
        if score >= threshold or idx == highest_score[0]:
            kept.append(sentence)

    return " ".join(kept)


def compress_hits(query: str, hits: list[dict], threshold: float = 0.35) -> list[dict]:
    """
    Compresses the 'content' of each hit in a list of retrieved documents.
    """
    compressed = []
    for hit in hits:
        new_content = compress_chunk(query, hit["content"], threshold)
        compressed.append({**hit, "content": new_content})
    return compressed
