# app/search.py
"""Hybrid search implementation combining vector and BM25 keyword search.

This module provides:
- BM25Index: BM25 keyword search index with persistence
- HybridSearcher: Combines vector and BM25 search using Reciprocal Rank Fusion (RRF)

Security Note:
    BM25 indexes are persisted using Python pickle format. Pickle is NOT secure
    against maliciously constructed data - loading a tampered pickle file could
    execute arbitrary code. This is acceptable for this application because:

    1. Index files are generated locally by the ingestion pipeline
    2. Files are stored in the local index/ directory with user permissions
    3. Users should not load indexes from untrusted sources

    If deploying in a multi-tenant or networked environment, consider:
    - Using file integrity checks (e.g., HMAC with a local secret)
    - Switching to a safer serialization format (JSON for metadata, numpy for arrays)
    - Restricting file permissions on the index directory
"""

import pickle
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.logging import get_logger

log = get_logger(__name__)

# BM25 index storage directory
BM25_INDEX_DIR = Path("index/bm25")

# Index format version for compatibility checking
BM25_INDEX_VERSION = "1.0"

# Magic bytes to identify valid index files (helps detect corruption)
BM25_INDEX_MAGIC = b"BM25IDX1"


class SearchMode(Enum):
    """Search mode options."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """A single search result with score and metadata."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]
    score: float
    source: str  # "vector", "keyword", or "hybrid"


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 indexing.

    Simple tokenization: lowercase, split on non-alphanumeric characters,
    remove short tokens (length < 2).

    Args:
        text: Text to tokenize.

    Returns:
        List of tokens.
    """
    # Lowercase and split on non-alphanumeric
    tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
    # Filter short tokens
    return [t for t in tokens if len(t) >= 2]


class BM25Index:
    """BM25 keyword search index with persistence.

    Stores document texts and their IDs for BM25 scoring.
    Can be saved to and loaded from disk for persistence across sessions.
    """

    def __init__(self, provider: str) -> None:
        """Initialize BM25 index for a provider.

        Args:
            provider: Provider identifier (e.g., "cme").
        """
        self.provider = provider
        self.chunk_ids: list[str] = []
        self.documents: list[str] = []
        self.tokenized_corpus: list[list[str]] = []
        self.bm25: BM25Okapi | None = None

    def add_documents(
        self,
        chunk_ids: list[str],
        documents: list[str],
    ) -> None:
        """Add documents to the index.

        Args:
            chunk_ids: List of chunk identifiers.
            documents: List of document texts.
        """
        if len(chunk_ids) != len(documents):
            raise ValueError("chunk_ids and documents must have same length")

        self.chunk_ids.extend(chunk_ids)
        self.documents.extend(documents)

        # Tokenize new documents
        new_tokens = [tokenize(doc) for doc in documents]
        self.tokenized_corpus.extend(new_tokens)

        log.debug(
            "bm25_documents_added",
            provider=self.provider,
            count=len(documents),
            total=len(self.chunk_ids),
        )

    def build(self) -> None:
        """Build the BM25 index from added documents.

        Must be called after all documents are added and before querying.
        """
        if not self.tokenized_corpus:
            log.warning("bm25_build_empty", provider=self.provider)
            return

        self.bm25 = BM25Okapi(self.tokenized_corpus)
        log.info(
            "bm25_index_built",
            provider=self.provider,
            document_count=len(self.chunk_ids),
        )

    def query(self, question: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Query the BM25 index.

        Args:
            question: Query text.
            top_k: Number of top results to return.

        Returns:
            List of (chunk_id, score) tuples sorted by score descending.
        """
        if self.bm25 is None:
            log.warning("bm25_query_no_index", provider=self.provider)
            return []

        query_tokens = tokenize(question)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Get top-k indices
        scored_indices = [(i, scores[i]) for i in range(len(scores))]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        top_indices = scored_indices[:top_k]

        return [(self.chunk_ids[i], score) for i, score in top_indices if score > 0]

    def get_index_path(self) -> Path:
        """Get the file path for this provider's BM25 index.

        Returns:
            Path to the index pickle file.
        """
        return BM25_INDEX_DIR / f"{self.provider}_index.pkl"

    def save(self) -> None:
        """Save the BM25 index to disk.

        Saves to index/bm25/{provider}_index.pkl with metadata for validation.
        Includes version info and document count for integrity checking.
        """
        index_path = self.get_index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": BM25_INDEX_VERSION,
            "provider": self.provider,
            "document_count": len(self.chunk_ids),
            "chunk_ids": self.chunk_ids,
            "documents": self.documents,
            "tokenized_corpus": self.tokenized_corpus,
        }

        with open(index_path, "wb") as f:
            # Write magic bytes first for format identification
            f.write(BM25_INDEX_MAGIC)
            pickle.dump(data, f)

        log.info(
            "bm25_index_saved",
            provider=self.provider,
            path=str(index_path),
            document_count=len(self.chunk_ids),
            version=BM25_INDEX_VERSION,
        )

    @classmethod
    def load(cls, provider: str) -> "BM25Index | None":
        """Load a BM25 index from disk.

        Validates magic bytes and version for integrity. See module docstring
        for security considerations regarding pickle deserialization.

        Args:
            provider: Provider identifier.

        Returns:
            BM25Index instance or None if not found or invalid.
        """
        index_path = BM25_INDEX_DIR / f"{provider}_index.pkl"

        if not index_path.exists():
            log.debug("bm25_index_not_found", provider=provider, path=str(index_path))
            return None

        try:
            with open(index_path, "rb") as f:
                # Validate magic bytes
                magic = f.read(len(BM25_INDEX_MAGIC))
                if magic != BM25_INDEX_MAGIC:
                    log.error(
                        "bm25_index_invalid_format",
                        provider=provider,
                        error="Invalid magic bytes - file may be corrupted or tampered",
                    )
                    return None

                data = pickle.load(f)

            # Validate version compatibility
            file_version = data.get("version", "unknown")
            if file_version != BM25_INDEX_VERSION:
                log.warning(
                    "bm25_index_version_mismatch",
                    provider=provider,
                    file_version=file_version,
                    expected_version=BM25_INDEX_VERSION,
                )
                # Continue loading - version mismatch is a warning, not error

            # Validate data integrity
            expected_count = data.get("document_count", 0)
            actual_count = len(data.get("chunk_ids", []))
            if expected_count != actual_count:
                log.error(
                    "bm25_index_integrity_error",
                    provider=provider,
                    expected_count=expected_count,
                    actual_count=actual_count,
                )
                return None

            index = cls(provider)
            index.chunk_ids = data["chunk_ids"]
            index.documents = data["documents"]
            index.tokenized_corpus = data["tokenized_corpus"]
            index.build()

            log.info(
                "bm25_index_loaded",
                provider=provider,
                document_count=len(index.chunk_ids),
                version=file_version,
            )
            return index

        except Exception as e:
            log.error("bm25_index_load_failed", provider=provider, error=str(e))
            return None

    def clear(self) -> None:
        """Clear the index and remove from disk."""
        self.chunk_ids = []
        self.documents = []
        self.tokenized_corpus = []
        self.bm25 = None

        index_path = self.get_index_path()
        if index_path.exists():
            index_path.unlink()
            log.info("bm25_index_deleted", provider=self.provider)


def rrf_score(rank: int, k: int = 60) -> float:
    """Calculate Reciprocal Rank Fusion (RRF) score.

    RRF is a rank aggregation method that combines results from multiple
    ranking systems. It uses the formula: 1 / (k + rank) where k is a
    constant (typically 60) that controls the influence of lower-ranked items.

    Args:
        rank: 1-based rank position (1 = top result).
        k: Constant parameter (default 60 per original RRF paper).

    Returns:
        RRF score for this rank position.
    """
    return 1.0 / (k + rank)


def merge_results_rrf(
    vector_results: list[tuple[str, float]],
    bm25_results: list[tuple[str, float]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Merge vector and BM25 results using Reciprocal Rank Fusion.

    Each result list should be sorted by score descending (best first).
    RRF combines rankings from both sources, favoring items that appear
    in both lists while giving appropriate weight to rank positions.

    Args:
        vector_results: List of (chunk_id, score) from vector search.
        bm25_results: List of (chunk_id, score) from BM25 search.
        k: RRF constant (default 60).

    Returns:
        List of (chunk_id, combined_rrf_score) sorted by score descending.
    """
    combined_scores: dict[str, float] = {}

    # Add RRF scores from vector results
    for rank, (chunk_id, _) in enumerate(vector_results, start=1):
        combined_scores[chunk_id] = combined_scores.get(chunk_id, 0) + rrf_score(
            rank, k
        )

    # Add RRF scores from BM25 results
    for rank, (chunk_id, _) in enumerate(bm25_results, start=1):
        combined_scores[chunk_id] = combined_scores.get(chunk_id, 0) + rrf_score(
            rank, k
        )

    # Sort by combined score
    sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


class HybridSearcher:
    """Combines vector and BM25 search for hybrid retrieval.

    Supports three search modes:
    - vector: Semantic search only (ChromaDB embeddings)
    - keyword: Keyword search only (BM25)
    - hybrid: Combines both using Reciprocal Rank Fusion
    """

    def __init__(
        self,
        provider: str,
        collection: Any,
        bm25_index: BM25Index | None = None,
    ) -> None:
        """Initialize hybrid searcher.

        Args:
            provider: Provider identifier.
            collection: ChromaDB collection for vector search.
            bm25_index: Optional BM25 index for keyword search.
        """
        self.provider = provider
        self.collection = collection
        self.bm25_index = bm25_index

    def search(
        self,
        question: str,
        mode: SearchMode = SearchMode.HYBRID,
        top_k: int = 5,
        retrieval_multiplier: int = 2,
    ) -> list[SearchResult]:
        """Perform search with specified mode.

        Args:
            question: Query text.
            mode: Search mode (vector, keyword, or hybrid).
            top_k: Number of final results to return.
            retrieval_multiplier: Multiplier for initial retrieval count
                (retrieves top_k * multiplier for re-ranking in hybrid mode).

        Returns:
            List of SearchResult objects sorted by relevance.
        """
        if mode == SearchMode.VECTOR:
            return self._vector_search(question, top_k)
        elif mode == SearchMode.KEYWORD:
            return self._keyword_search(question, top_k)
        else:  # HYBRID
            return self._hybrid_search(question, top_k, retrieval_multiplier)

    def _vector_search(self, question: str, top_k: int) -> list[SearchResult]:
        """Perform vector-only search.

        Args:
            question: Query text.
            top_k: Number of results.

        Returns:
            List of SearchResult objects.
        """
        results = self.collection.query(
            query_texts=[question],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]

            for i, chunk_id in enumerate(ids):
                # Convert distance to similarity score (ChromaDB uses L2 distance)
                # Lower distance = more similar, so we invert
                distance = distances[i] if i < len(distances) else 0
                score = 1.0 / (1.0 + distance)

                search_results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        text=docs[i] if i < len(docs) else "",
                        metadata=dict(metas[i]) if i < len(metas) and metas[i] else {},
                        score=score,
                        source="vector",
                    )
                )

        log.debug(
            "vector_search_complete",
            provider=self.provider,
            question=question[:50],
            results=len(search_results),
        )
        return search_results

    def _keyword_search(self, question: str, top_k: int) -> list[SearchResult]:
        """Perform keyword-only search.

        Args:
            question: Query text.
            top_k: Number of results.

        Returns:
            List of SearchResult objects.
        """
        if self.bm25_index is None:
            log.warning("keyword_search_no_index", provider=self.provider)
            return []

        bm25_results = self.bm25_index.query(question, top_k)

        # Need to fetch document text and metadata from ChromaDB
        search_results = []
        for chunk_id, score in bm25_results:
            try:
                result = self.collection.get(
                    ids=[chunk_id],
                    include=["documents", "metadatas"],
                )
                if result and result.get("documents") and result["documents"]:
                    search_results.append(
                        SearchResult(
                            chunk_id=chunk_id,
                            text=result["documents"][0],
                            metadata=(
                                dict(result["metadatas"][0])
                                if result.get("metadatas") and result["metadatas"]
                                else {}
                            ),
                            score=score,
                            source="keyword",
                        )
                    )
            except Exception as e:
                log.warning(
                    "keyword_search_fetch_failed", chunk_id=chunk_id, error=str(e)
                )

        log.debug(
            "keyword_search_complete",
            provider=self.provider,
            question=question[:50],
            results=len(search_results),
        )
        return search_results

    def _hybrid_search(
        self,
        question: str,
        top_k: int,
        retrieval_multiplier: int,
    ) -> list[SearchResult]:
        """Perform hybrid search using RRF.

        Args:
            question: Query text.
            top_k: Number of final results.
            retrieval_multiplier: Multiplier for initial retrieval.

        Returns:
            List of SearchResult objects.
        """
        # Retrieve more candidates for re-ranking
        candidate_count = top_k * retrieval_multiplier

        # Get vector results
        vector_results = self._vector_search(question, candidate_count)
        vector_tuples = [(r.chunk_id, r.score) for r in vector_results]

        # Get BM25 results if available
        bm25_tuples: list[tuple[str, float]] = []
        if self.bm25_index:
            bm25_tuples = self.bm25_index.query(question, candidate_count)

        # If no BM25 index, fall back to vector-only
        if not bm25_tuples:
            log.debug("hybrid_fallback_to_vector", provider=self.provider)
            return vector_results[:top_k]

        # Merge using RRF
        merged = merge_results_rrf(vector_tuples, bm25_tuples)

        # Build final results with document text and metadata
        chunk_to_result: dict[str, SearchResult] = {
            r.chunk_id: r for r in vector_results
        }

        final_results = []
        for chunk_id, rrf_score in merged[:top_k]:
            if chunk_id in chunk_to_result:
                result = chunk_to_result[chunk_id]
                final_results.append(
                    SearchResult(
                        chunk_id=result.chunk_id,
                        text=result.text,
                        metadata=result.metadata,
                        score=rrf_score,
                        source="hybrid",
                    )
                )
            else:
                # Fetch from ChromaDB if not in vector results
                try:
                    fetched = self.collection.get(
                        ids=[chunk_id],
                        include=["documents", "metadatas"],
                    )
                    if fetched and fetched.get("documents") and fetched["documents"]:
                        final_results.append(
                            SearchResult(
                                chunk_id=chunk_id,
                                text=fetched["documents"][0],
                                metadata=(
                                    dict(fetched["metadatas"][0])
                                    if fetched.get("metadatas") and fetched["metadatas"]
                                    else {}
                                ),
                                score=rrf_score,
                                source="hybrid",
                            )
                        )
                except Exception as e:
                    log.warning("hybrid_fetch_failed", chunk_id=chunk_id, error=str(e))

        log.info(
            "hybrid_search_complete",
            provider=self.provider,
            vector_count=len(vector_results),
            bm25_count=len(bm25_tuples),
            final_count=len(final_results),
        )
        return final_results
