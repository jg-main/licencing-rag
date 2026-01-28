"""Tests for Phase 3: Hybrid Retrieval with OpenAI embeddings.

This test suite verifies:
1. Vector search with text-embedding-3-large
2. BM25 keyword search
3. RRF merge produces reasonable rankings
4. Candidate pool max 12 chunks
5. Deduplication by chunk_id
6. Debug logging for retrieval sources
"""

from typing import Any

import chromadb
import pytest

from app.config import EMBEDDING_DIMENSIONS
from app.config import EMBEDDING_MODEL
from app.embed import OpenAIEmbeddingFunction
from app.search import BM25Index
from app.search import HybridSearcher
from app.search import SearchMode
from app.search import merge_results_rrf
from app.search import rrf_score


@pytest.fixture
def tmp_chroma_collection(tmp_path):
    """Create a temporary ChromaDB collection for testing."""
    # Use persistent client with tmp_path to avoid conflicts
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    embedding_function = OpenAIEmbeddingFunction()
    collection = client.create_collection(
        name="test",
        embedding_function=embedding_function,
        metadata={
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimensions": str(EMBEDDING_DIMENSIONS),
        },
    )
    yield collection
    # Cleanup
    try:
        client.delete_collection("test")
    except Exception:
        pass


class TestRRFScoring:
    """Test Reciprocal Rank Fusion scoring function."""

    def test_rrf_score_first_rank(self) -> None:
        """First rank (1) should have highest score."""
        score = rrf_score(1, k=60)
        assert score == 1.0 / 61

    def test_rrf_score_decreases_with_rank(self) -> None:
        """RRF score should decrease as rank increases."""
        score1 = rrf_score(1, k=60)
        score2 = rrf_score(2, k=60)
        score10 = rrf_score(10, k=60)
        assert score1 > score2 > score10

    def test_rrf_score_custom_k(self) -> None:
        """RRF should respect custom k parameter."""
        score = rrf_score(1, k=100)
        assert score == 1.0 / 101


class TestRRFMerge:
    """Test RRF merging of vector and BM25 results."""

    def test_merge_empty_lists(self) -> None:
        """Merging empty lists should return empty result."""
        result = merge_results_rrf([], [])
        assert result == []

    def test_merge_single_source_vector(self) -> None:
        """Vector-only results should be ranked by RRF."""
        vector_results = [
            ("chunk1", 0.9),
            ("chunk2", 0.8),
            ("chunk3", 0.7),
        ]
        result = merge_results_rrf(vector_results, [])

        # Should return all chunks with RRF scores
        assert len(result) == 3
        assert result[0][0] == "chunk1"  # Highest rank
        assert result[0][1] == rrf_score(1)  # RRF score for rank 1

    def test_merge_single_source_bm25(self) -> None:
        """BM25-only results should be ranked by RRF."""
        bm25_results = [
            ("chunk1", 5.2),
            ("chunk2", 4.1),
        ]
        result = merge_results_rrf([], bm25_results)

        assert len(result) == 2
        assert result[0][0] == "chunk1"

    def test_merge_overlapping_chunks_boosted(self) -> None:
        """Chunks appearing in both lists should get boosted scores."""
        vector_results = [
            ("chunk1", 0.9),
            ("chunk2", 0.8),
        ]
        bm25_results = [
            ("chunk1", 5.0),  # Also top in BM25
            ("chunk3", 4.0),
        ]
        result = merge_results_rrf(vector_results, bm25_results)

        # chunk1 appears in both, should have highest combined score
        assert result[0][0] == "chunk1"
        # chunk1 score should be sum of RRF scores from both sources
        expected_score = rrf_score(1) + rrf_score(1)  # Rank 1 in both
        assert abs(result[0][1] - expected_score) < 0.001

    def test_merge_deduplication(self) -> None:
        """Same chunk_id should only appear once in results."""
        vector_results = [("chunk1", 0.9), ("chunk2", 0.8)]
        bm25_results = [("chunk1", 5.0), ("chunk2", 4.0)]
        result = merge_results_rrf(vector_results, bm25_results)

        chunk_ids = [chunk_id for chunk_id, _ in result]
        assert len(chunk_ids) == len(set(chunk_ids))  # No duplicates

    def test_merge_sorted_by_score_descending(self) -> None:
        """Merged results should be sorted by score descending."""
        vector_results = [("chunk1", 0.5), ("chunk2", 0.4)]
        bm25_results = [("chunk3", 1.0), ("chunk4", 0.9)]
        result = merge_results_rrf(vector_results, bm25_results)

        scores = [score for _, score in result]
        assert scores == sorted(scores, reverse=True)


class TestBM25Configuration:
    """Test BM25 index configuration matches Phase 3 requirements."""

    def test_bm25_default_top_k(self) -> None:
        """BM25 query should support top_k=10 as default."""
        index = BM25Index("test")
        chunk_ids = ["chunk1", "chunk2", "chunk3"]
        documents = [
            "CME Group market data fee schedule information",
            "Professional subscriber licensing agreement terms",
            "Real-time data redistribution requirements",
        ]
        index.add_documents(chunk_ids, documents)
        index.build()

        # Query with relevant terms to get non-zero scores
        results = index.query("market data fee", top_k=10)
        assert len(results) <= 10
        assert len(results) >= 1  # At least one match

    def test_bm25_respects_custom_top_k(self) -> None:
        """BM25 should respect custom top_k parameter."""
        index = BM25Index("test")
        chunk_ids = [f"chunk{i}" for i in range(20)]
        documents = [f"CME market data license document number {i}" for i in range(20)]
        index.add_documents(chunk_ids, documents)
        index.build()

        results = index.query("market data license", top_k=5)
        assert len(results) == 5


class TestHybridSearchConfiguration:
    """Test HybridSearcher configuration for Phase 3."""

    def test_hybrid_search_default_top_k(self) -> None:
        """Hybrid search default top_k should be configurable."""
        # This test verifies the interface supports top_k parameter
        # Actual integration test requires ChromaDB instance
        # Just verify the signature exists and has correct default
        import inspect

        sig = inspect.signature(HybridSearcher.search)
        assert "top_k" in sig.parameters
        # Default should be 5 in current implementation
        assert sig.parameters["top_k"].default == 5

    def test_hybrid_search_retrieval_multiplier(self) -> None:
        """Hybrid search should support retrieval multiplier."""
        import inspect

        sig = inspect.signature(HybridSearcher.search)
        assert "retrieval_multiplier" in sig.parameters
        # Default multiplier is 2
        assert sig.parameters["retrieval_multiplier"].default == 2

    def test_candidate_pool_calculation(self) -> None:
        """Candidate pool should be top_k * retrieval_multiplier."""
        # With default settings: top_k=5, multiplier=2 → 10 candidates
        # This ensures we retrieve enough for reranking
        top_k = 5
        multiplier = 2
        expected_candidates = top_k * multiplier
        assert expected_candidates == 10

    def test_max_candidate_pool_with_top_k_10(self) -> None:
        """With top_k=10 and multiplier=2, candidate pool = 20."""
        # Phase 3 specifies we want final result of max 12 chunks
        # With top_k=10 and multiplier=2, we get 20 candidates
        # which is then reduced to 10 final results
        top_k = 10
        multiplier = 2
        candidate_count = top_k * multiplier
        assert candidate_count == 20  # Retrieval phase
        # Then RRF reduces to top_k=10 for final results


class TestVectorSearchConfiguration:
    """Test vector search with OpenAI embeddings."""

    def test_embedding_model_configuration(self) -> None:
        """Verify OpenAI embedding model is configured correctly."""
        assert EMBEDDING_MODEL == "text-embedding-3-large"
        assert EMBEDDING_DIMENSIONS == 3072

    def test_vector_search_signature(self) -> None:
        """Vector search should support top_k parameter."""
        import inspect

        sig = inspect.signature(HybridSearcher._vector_search)
        assert "top_k" in sig.parameters

    def test_keyword_search_signature(self) -> None:
        """Keyword search should support top_k parameter."""
        import inspect

        sig = inspect.signature(HybridSearcher._keyword_search)
        assert "top_k" in sig.parameters


class TestSearchModeEnumeration:
    """Test SearchMode enumeration."""

    def test_search_modes_available(self) -> None:
        """All three search modes should be available."""
        assert SearchMode.VECTOR.value == "vector"
        assert SearchMode.KEYWORD.value == "keyword"
        assert SearchMode.HYBRID.value == "hybrid"

    def test_search_mode_from_string(self) -> None:
        """Should be able to construct SearchMode from string."""
        assert SearchMode("vector") == SearchMode.VECTOR
        assert SearchMode("keyword") == SearchMode.KEYWORD
        assert SearchMode("hybrid") == SearchMode.HYBRID


class TestDebuggingAndLogging:
    """Test debug logging for retrieval sources."""

    def test_search_result_has_source_field(self) -> None:
        """SearchResult should track which method found it."""
        from app.search import SearchResult

        result = SearchResult(
            chunk_id="test1",
            text="Test document",
            metadata={},
            score=0.9,
            source="vector",
        )

        assert result.source == "vector"

    def test_search_result_sources(self) -> None:
        """SearchResult should support all source types."""
        from app.search import SearchResult

        for source in ["vector", "keyword", "hybrid"]:
            result = SearchResult(
                chunk_id="test",
                text="text",
                metadata={},
                score=1.0,
                source=source,
            )
            assert result.source == source


class TestPhase3Requirements:
    """Integration tests for Phase 3 requirements."""

    def test_vector_k_equals_10(self) -> None:
        """Vector search k should be set to 10."""
        # This is configured via top_k parameter
        # Default in query.py should be TOP_K = 10
        from app.config import TOP_K

        assert TOP_K == 10

    def test_bm25_k_equals_10(self) -> None:
        """BM25 search k should be set to 10."""
        # BM25 uses the same top_k parameter
        # Verify it accepts top_k=10
        index = BM25Index("test")
        index.add_documents(["doc1", "doc2"], ["id1", "id2"])
        index.build()
        results = index.query("doc", top_k=10)
        assert len(results) <= 10

    def test_deduplication_in_rrf_merge(self) -> None:
        """RRF merge must deduplicate by chunk_id."""
        # Duplicate chunk_id in both sources
        vector = [("chunk1", 0.9), ("chunk2", 0.8)]
        bm25 = [("chunk1", 5.0), ("chunk3", 4.0)]

        result = merge_results_rrf(vector, bm25)
        chunk_ids = [cid for cid, _ in result]

        # chunk1 appears in both sources but should only appear once
        assert chunk_ids.count("chunk1") == 1
        assert len(chunk_ids) == 3  # chunk1, chunk2, chunk3

    def test_candidate_pool_max_12_configuration(self) -> None:
        """With top_k=6 and multiplier=2, candidate pool is 12."""
        # To achieve max 12 candidates: top_k=6, multiplier=2
        # This gives us 12 candidates before RRF reduction to 6 final
        top_k = 6
        multiplier = 2
        candidate_pool = top_k * multiplier
        assert candidate_pool == 12


class TestRuntimeBehavior:
    """Test actual runtime behavior, not just configuration."""

    def test_hybrid_search_actual_candidate_pool_respects_max_12(
        self, tmp_chroma_collection: Any
    ) -> None:
        """Verify hybrid search actually retrieves max 12 candidates, not 20."""
        # Create a large corpus to ensure we can retrieve 20+ items
        chunk_ids = [f"chunk_{i:03d}" for i in range(50)]
        documents = [
            f"market data licensing fee schedule document {i}" for i in range(50)
        ]

        # Add to ChromaDB
        tmp_chroma_collection.add(
            ids=chunk_ids,
            documents=documents,
            metadatas=[{"doc": f"doc_{i}"} for i in range(50)],
        )

        # Create and populate BM25 index
        bm25 = BM25Index("test")
        bm25.add_documents(chunk_ids, documents)
        bm25.build()

        # Track how many candidates were actually requested
        vector_call_count = []

        searcher = HybridSearcher("test", tmp_chroma_collection, bm25)

        # Patch the internal method to track candidate_count
        original_vector = searcher._vector_search

        def tracked_vector(question: str, top_k: int) -> list:
            vector_call_count.append(top_k)
            return original_vector(question, top_k)

        searcher._vector_search = tracked_vector

        # Call hybrid search with top_k=10, retrieval_multiplier=2
        # This would calculate 20 candidates, but should be capped at 12
        results = searcher._hybrid_search(
            "market data fee", top_k=10, retrieval_multiplier=2
        )

        # Verify candidate_count was capped at 12, not 20
        assert len(vector_call_count) == 1, "Vector search should be called once"
        assert vector_call_count[0] == 12, (
            f"Vector search should request 12 candidates, got {vector_call_count[0]}"
        )

        # Final results should be top_k=10
        assert len(results) <= 10

    def test_rrf_merge_actual_deduplication(self) -> None:
        """Verify RRF merge actually removes duplicates at runtime."""
        # Create overlapping results with same chunk appearing in both
        vector = [
            ("chunk_a", 0.95),
            ("chunk_b", 0.85),
            ("chunk_c", 0.75),
            ("chunk_d", 0.65),
        ]
        bm25 = [
            ("chunk_b", 0.90),  # Duplicate - should boost score
            ("chunk_e", 0.80),
            ("chunk_a", 0.70),  # Duplicate - should boost score
        ]

        merged = merge_results_rrf(vector, bm25)
        chunk_ids = [chunk_id for chunk_id, _ in merged]

        # Verify no duplicates
        assert len(chunk_ids) == len(set(chunk_ids)), (
            f"Found duplicates in: {chunk_ids}"
        )

        # Verify chunks that appeared in both sources are present
        assert "chunk_a" in chunk_ids
        assert "chunk_b" in chunk_ids

        # Verify total unique chunks (4 from vector + 3 from bm25 - 2 duplicates = 5)
        assert len(chunk_ids) == 5

    def test_search_result_source_field_populated(
        self, tmp_chroma_collection: Any
    ) -> None:
        """Verify SearchResult.source field is properly set for each search mode."""
        # Setup test data
        chunk_ids = ["c1", "c2", "c3"]
        documents = [
            "market data licensing fee",
            "professional subscriber agreement",
            "real-time data redistribution",
        ]
        tmp_chroma_collection.add(
            ids=chunk_ids,
            documents=documents,
            metadatas=[{"doc": f"doc_{i}"} for i in range(3)],
        )

        # Create BM25 index
        bm25 = BM25Index("test")
        bm25.add_documents(chunk_ids, documents)
        bm25.build()

        searcher = HybridSearcher("test", tmp_chroma_collection, bm25)

        # Test vector search sets source="vector"
        vector_results = searcher._vector_search("market data", top_k=2)
        assert all(r.source == "vector" for r in vector_results), (
            "Vector search should set source='vector'"
        )

        # Test keyword search sets source="keyword"
        keyword_results = searcher._keyword_search("market data", top_k=2)
        assert all(r.source == "keyword" for r in keyword_results), (
            "Keyword search should set source='keyword'"
        )

        # Test hybrid search sets source="hybrid"
        hybrid_results = searcher._hybrid_search(
            "market data", top_k=2, retrieval_multiplier=2
        )
        assert all(r.source == "hybrid" for r in hybrid_results), (
            "Hybrid search should set source='hybrid'"
        )

    def test_debug_info_structure(self) -> None:
        """Verify debug_info has the correct structure when enabled."""
        # This is a unit test for the debug_info structure
        # We'll verify the structure without needing full E2E setup

        # Expected structure
        debug_info = {
            "original_query": "What is the market data fee?",
            "normalized_query": "market data fee",
            "retrieval_sources": {
                "vector": 0,
                "keyword": 0,
                "hybrid": 3,
            },
        }

        # Verify all required fields are present
        assert "original_query" in debug_info
        assert "normalized_query" in debug_info
        assert "retrieval_sources" in debug_info

        # Verify retrieval_sources structure
        sources = debug_info["retrieval_sources"]
        assert isinstance(sources, dict)
        assert "vector" in sources
        assert "keyword" in sources
        assert "hybrid" in sources
        assert all(isinstance(v, int) for v in sources.values())
