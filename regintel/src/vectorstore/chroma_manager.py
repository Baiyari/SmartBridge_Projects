"""
Vector store management for RegIntel.

Wraps a local, persistent ChromaDB instance with two collections:
  - "obligations": embedded obligation clauses extracted from circulars
  - "policies":     embedded internal SOP / policy document chunks

Uses Sentence-Transformers (CPU-only, free) for embeddings, so the entire
pipeline runs without a paid API or GPU.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import chromadb
from chromadb.utils import embedding_functions

from config import Settings
from src.extraction.obligation_extractor import Obligation

OBLIGATIONS_COLLECTION = "obligations"
POLICIES_COLLECTION = "policies"


def _stable_id(*parts: str) -> str:
    """Deterministic ID so re-ingesting the same content doesn't duplicate."""
    digest = hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


@dataclass
class GapMatch:
    """Result of comparing one obligation against the policy vector store."""

    obligation: dict
    best_policy_match: str | None
    similarity_score: float  # 0.0 (no overlap) to 1.0 (identical)
    is_gap: bool


class VectorStore:
    """Thin, typed wrapper around a persistent ChromaDB client."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.load()
        self._client = chromadb.PersistentClient(path=self.settings.chroma_persist_dir)
        self._embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.settings.embedding_model
        )
        self.obligations = self._client.get_or_create_collection(
            OBLIGATIONS_COLLECTION, embedding_function=self._embedder
        )
        self.policies = self._client.get_or_create_collection(
            POLICIES_COLLECTION, embedding_function=self._embedder
        )

    def reset_policies(self) -> None:
        """Clear all policy documents in the collection by deleting and recreating it."""
        try:
            self._client.delete_collection(POLICIES_COLLECTION)
        except Exception:
            pass
        self.policies = self._client.get_or_create_collection(
            POLICIES_COLLECTION, embedding_function=self._embedder
        )

    def add_obligations(self, obligations: list[Obligation]) -> int:
        """Embed and store obligations. Returns count actually added
        (duplicates by content hash are skipped)."""
        if not obligations:
            return 0

        ids, documents, metadatas = [], [], []
        for ob in obligations:
            doc_id = _stable_id(ob.clause_text, ob.circular_number or "")
            ids.append(doc_id)
            documents.append(ob.clause_text)
            metadatas.append(
                {
                    "obligation_type": ob.obligation_type,
                    "deadline_text": ob.deadline_text or "",
                    "applicable_entity": ob.applicable_entity or "",
                    "circular_number": ob.circular_number or "",
                    "regulator": ob.regulator or "",
                    "source_path": ob.source_path or "",
                }
            )

        self.obligations.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def add_policy_chunks(
        self, chunks: list[str], *, policy_name: str
    ) -> int:
        """Embed and store internal policy/SOP text chunks."""
        if not chunks:
            return 0

        ids, documents, metadatas = [], [], []
        for i, chunk in enumerate(chunks):
            doc_id = _stable_id(policy_name, str(i), chunk[:80])
            ids.append(doc_id)
            documents.append(chunk)
            metadatas.append({"policy_name": policy_name, "chunk_index": i})

        self.policies.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def find_gaps(self, obligations: list[Obligation], *, similarity_threshold: float = 0.55) -> list[GapMatch]:
        """For every provided obligation, search the policy collection for the
        closest semantic match. If the best match falls below the similarity
        threshold (or no policies exist at all), the obligation is flagged
        as an uncovered compliance gap.
        """
        results: list[GapMatch] = []
        has_policies = self.policies.count() > 0

        for ob in obligations:
            doc_id = _stable_id(ob.clause_text, ob.circular_number or "")
            meta = {
                "obligation_type": ob.obligation_type,
                "deadline_text": ob.deadline_text or "",
                "applicable_entity": ob.applicable_entity or "",
                "circular_number": ob.circular_number or "",
                "regulator": ob.regulator or "",
                "source_path": ob.source_path or "",
            }

            if not has_policies:
                results.append(
                    GapMatch(
                        obligation={"id": doc_id, "clause_text": ob.clause_text, **meta},
                        best_policy_match=None,
                        similarity_score=0.0,
                        is_gap=True,
                    )
                )
                continue

            query = self.policies.query(query_texts=[ob.clause_text], n_results=1)
            distance = query["distances"][0][0] if query["distances"][0] else 2.0
            # Chroma's default space is L2 on normalized embeddings;
            # convert to an intuitive 0..1 similarity score.
            similarity = max(0.0, 1.0 - (distance / 2.0))
            best_doc = query["documents"][0][0] if query["documents"][0] else None

            results.append(
                GapMatch(
                    obligation={"id": doc_id, "clause_text": ob.clause_text, **meta},
                    best_policy_match=best_doc,
                    similarity_score=round(similarity, 4),
                    is_gap=similarity < similarity_threshold,
                )
            )

        return results
