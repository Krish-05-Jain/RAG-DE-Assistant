"""
app/rag/vectorstore.py
──────────────────────
ChromaDB vector store setup and management.

Logical flow:
  1. Initialise a ChromaDB persistent client at `chroma_persist_dir`.
  2. Create (or load) a collection with cosine-similarity distance.
  3. Expose `upsert_documents()` and `query_collection()` helpers used
     by the ingestion and retriever modules.
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings


def get_chroma_client() -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client."""
    return chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_or_create_collection(client: chromadb.PersistentClient):
    """Return the pipeline_docs collection (creates if absent)."""
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_documents(
    collection,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """Upsert a batch of embedded chunks into the collection."""
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query_collection(
    collection,
    query_embeddings: list[list[float]],
    n_results: int = 5,
) -> dict:
    """Query the collection and return top-K results."""
    return collection.query(
        query_embeddings=query_embeddings,
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )