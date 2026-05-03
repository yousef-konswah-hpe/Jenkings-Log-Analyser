"""RAG (Retrieval-Augmented Generation) over historical analyses.

Generates embeddings via the OpenAI SDK (GitHub Copilot compatible), stores
them in MongoDB, and retrieves the top-K most similar past analyses.
"""

import re
import time
from typing import Optional

import numpy as np
from openai import OpenAI

from config import (
    embeddings_collection,
    COPILOT_API_URL,
    COPILOT_API_KEY,
    EMBEDDING_MODEL,
    RAG_TOP_K,
    RAG_SIMILARITY_THRESHOLD,
)


#  Embedding helper

def _get_openai_client() -> OpenAI:
    """Return an OpenAI SDK client configured for the Copilot endpoint."""
    return OpenAI(
        api_key=COPILOT_API_KEY,
        base_url=COPILOT_API_URL or None,
        timeout=30.0,
        max_retries=0,
    )


def _get_embedding(text: str, max_chars: int = 8000) -> Optional[list[float]]:
    """Request an embedding vector via the OpenAI embeddings API."""
    truncated = text[:max_chars]
    try:
        client = _get_openai_client()
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=truncated,
        )
        return response.data[0].embedding
    except Exception as exc:
        print(f"[RAG] Embedding error: {exc}")
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(dot / norm) if norm > 0 else 0.0


def _summarise_for_embedding(analysis: str) -> str:
    """Extract a condensed version of an analysis for embedding."""
    # Focus on summary, root cause, and fix sections
    sections = []
    for pattern in [
        r"\*\*Summary\*\*.*?(?=\*\*|$)",
        r"\*\*Root Cause\*\*.*?(?=\*\*|$)",
        r"\*\*Errors.*?\*\*.*?(?=\*\*|$)",
        r"\*\*Fix Suggestions\*\*.*?(?=\*\*|$)",
    ]:
        match = re.search(pattern, analysis, re.DOTALL | re.IGNORECASE)
        if match:
            sections.append(match.group(0).strip())

    return "\n\n".join(sections) if sections else analysis[:4000]


# ── Public API ─────────────────────────────────────────────────────

def store_embedding(analysis_id: str, job_name: str, analysis_text: str) -> bool:
    """Generate and store an embedding for a completed analysis."""
    summary = _summarise_for_embedding(analysis_text)
    embedding = _get_embedding(summary)

    if not embedding:
        print(f"[RAG] Failed to embed analysis {analysis_id}")
        return False

    try:
        embeddings_collection.update_one(
            {"analysis_id": analysis_id},
            {
                "$set": {
                    "analysis_id": analysis_id,
                    "job_name": job_name,
                    "embedding": embedding,
                    "summary_text": summary[:2000],
                    "updated_at": time.time(),
                }
            },
            upsert=True,
        )
        print(f"[RAG] Stored embedding for {analysis_id}")
        return True
    except Exception as exc:
        print(f"[RAG] Store error: {exc}")
        return False


def find_similar_analyses(
    query_text: str,
    job_name: Optional[str] = None,
    top_k: int = RAG_TOP_K,
    threshold: float = RAG_SIMILARITY_THRESHOLD,
    exclude_id: Optional[str] = None,
) -> list[dict]:
    """
    Find the top-K most similar past analyses.

    Returns list of dicts: {analysis_id, job_name, similarity, summary_text}
    """
    query_embedding = _get_embedding(_summarise_for_embedding(query_text))
    if not query_embedding:
        return []

    try:
        # Fetch all stored embeddings (optionally filter by job)
        query = {}
        if job_name:
            query["job_name"] = job_name
        cursor = embeddings_collection.find(query)

        scored = []
        for doc in cursor:
            if exclude_id and doc.get("analysis_id") == exclude_id:
                continue
            stored_emb = doc.get("embedding")
            if not stored_emb:
                continue

            sim = _cosine_similarity(query_embedding, stored_emb)
            if sim >= threshold:
                scored.append({
                    "analysis_id": doc["analysis_id"],
                    "job_name": doc.get("job_name", ""),
                    "similarity": round(sim * 100, 1),
                    "summary_text": doc.get("summary_text", ""),
                })

        # Sort by similarity descending
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    except Exception as exc:
        print(f"[RAG] Search error: {exc}")
        return []


def format_rag_context(similar: list[dict]) -> str:
    """Format similar analyses into a context block for the LLM prompt."""
    if not similar:
        return ""

    lines = ["--- SIMILAR PAST FAILURES (from RAG) ---"]
    for i, item in enumerate(similar, 1):
        lines.append(
            f"\n[Past Failure #{i}] (similarity: {item['similarity']}%, "
            f"job: {item['job_name']})\n{item['summary_text']}"
        )
    lines.append("\n--- END PAST FAILURES ---\n")
    lines.append(
        "Use the above past failures to identify recurring patterns. "
        "If this failure matches a past one, mention it and reference the previous fix."
    )
    return "\n".join(lines)
