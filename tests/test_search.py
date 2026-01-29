"""Tests for hybrid search implementation."""

from pathlib import Path

import pytest

from app.search import BM25Index
from app.search import SearchMode
from app.search import merge_results_rrf
from app.search import rrf_score
from app.search import tokenize


class TestTokenize:
    """Tests for tokenization function."""

    def test_basic_tokenization(self) -> None:
        """Basic text is tokenized correctly."""
        tokens = tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_removes_short_tokens(self) -> None:
        """Tokens shorter than 2 characters are removed."""
        tokens = tokenize("I am a test")
        assert "am" in tokens
        assert "test" in tokens
        assert "i" not in tokens
        assert "a" not in tokens

    def test_splits_on_punctuation(self) -> None:
        """Splits on non-alphanumeric characters."""
        tokens = tokenize("hello-world, this.is")
        assert "hello" in tokens
        assert "world" in tokens
        assert "this" in tokens
        assert "is" in tokens

    def test_handles_numbers(self) -> None:
        """Numbers are preserved in tokens."""
        tokens = tokenize("Section 123 Article 456")
        assert "section" in tokens
        assert "123" in tokens
        assert "article" in tokens
        assert "456" in tokens

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        tokens = tokenize("")
        assert tokens == []

    def test_only_punctuation(self) -> None:
        """String with only punctuation returns empty list."""
        tokens = tokenize("!@#$%^&*()")
        assert tokens == []


class TestRRFScore:
    """Tests for Reciprocal Rank Fusion scoring."""

    def test_first_rank(self) -> None:
        """Rank 1 has highest score."""
        score = rrf_score(1, k=60)
        assert score == pytest.approx(1.0 / 61)

    def test_lower_ranks_have_lower_scores(self) -> None:
        """Higher ranks have lower scores."""
        score_1 = rrf_score(1, k=60)
        score_5 = rrf_score(5, k=60)
        score_10 = rrf_score(10, k=60)
        assert score_1 > score_5 > score_10

    def test_custom_k_parameter(self) -> None:
        """Custom k parameter affects scores."""
        score_k60 = rrf_score(1, k=60)
        score_k10 = rrf_score(1, k=10)
        # Lower k gives higher score
        assert score_k10 > score_k60

    def test_score_approaches_zero(self) -> None:
        """Very high ranks have very low scores."""
        score = rrf_score(1000, k=60)
        assert score < 0.001


class TestMergeResultsRRF:
    """Tests for RRF merge function."""

    def test_single_source_results(self) -> None:
        """Results from single source are ranked correctly."""
        vector_results = [("doc1", 0.9), ("doc2", 0.8), ("doc3", 0.7)]
        bm25_results: list[tuple[str, float]] = []

        merged = merge_results_rrf(vector_results, bm25_results)

        # Order should be preserved
        assert len(merged) == 3
        assert merged[0][0] == "doc1"
        assert merged[1][0] == "doc2"
        assert merged[2][0] == "doc3"

    def test_overlapping_results_boosted(self) -> None:
        """Documents appearing in both sources get higher scores."""
        vector_results = [("doc1", 0.9), ("doc2", 0.8)]
        bm25_results = [("doc2", 5.0), ("doc3", 4.0)]

        merged = merge_results_rrf(vector_results, bm25_results)

        # doc2 should be ranked first (appears in both)
        assert merged[0][0] == "doc2"

    def test_rrf_scores_sum_correctly(self) -> None:
        """RRF scores are summed for overlapping results."""
        vector_results = [("doc1", 0.9)]  # rank 1
        bm25_results = [("doc1", 5.0)]  # rank 1

        merged = merge_results_rrf(vector_results, bm25_results, k=60)

        # Score should be 2 * 1/(60+1) = 2/61
        expected = 2 * (1.0 / 61)
        assert merged[0][1] == pytest.approx(expected)

    def test_empty_inputs(self) -> None:
        """Empty inputs return empty results."""
        merged = merge_results_rrf([], [])
        assert merged == []

    def test_different_k_values(self) -> None:
        """Different k values produce different rankings."""
        vector_results = [("doc1", 0.9), ("doc2", 0.8)]
        bm25_results = [("doc3", 5.0), ("doc1", 4.0)]

        merged_k60 = merge_results_rrf(vector_results, bm25_results, k=60)
        merged_k10 = merge_results_rrf(vector_results, bm25_results, k=10)

        # With lower k, position matters more
        # doc1 appears in both, but at different positions
        # Results should still have doc1 first in both cases
        assert merged_k60[0][0] == "doc1"
        assert merged_k10[0][0] == "doc1"


class TestBM25Index:
    """Tests for BM25 index class."""

    def test_add_and_build(self) -> None:
        """Documents can be added and index built."""
        index = BM25Index("test")
        index.add_documents(
            ["chunk1", "chunk2"],
            ["The quick brown fox", "The lazy dog sleeps"],
        )
        index.build()

        assert len(index.chunk_ids) == 2
        assert index.bm25 is not None

    def test_query_returns_results(self) -> None:
        """Query returns matching documents."""
        index = BM25Index("test")
        index.add_documents(
            ["chunk1", "chunk2", "chunk3"],
            [
                "The quick brown fox jumps over the lazy dog",
                "The lazy cat sleeps all day",
                "Python programming is fun and powerful",
            ],
        )
        index.build()

        results = index.query("lazy dog", top_k=2)

        assert len(results) <= 2
        # First result should be chunk1 (has both "lazy" and "dog")
        assert results[0][0] == "chunk1"

    def test_query_empty_corpus(self) -> None:
        """Query on empty corpus returns empty results."""
        index = BM25Index("test")
        index.build()  # Build with no documents

        results = index.query("test query")
        assert results == []

    def test_query_no_matches(self) -> None:
        """Query with no matching tokens returns empty results."""
        index = BM25Index("test")
        index.add_documents(["chunk1"], ["apple banana cherry"])
        index.build()

        results = index.query("xyz123")
        assert results == []

    def test_add_documents_length_mismatch(self) -> None:
        """Mismatched lengths raise ValueError."""
        index = BM25Index("test")

        with pytest.raises(ValueError):
            index.add_documents(
                ["chunk1", "chunk2"],
                ["only one document"],
            )

    def test_clear_resets_index(self) -> None:
        """Clear resets the index."""
        index = BM25Index("test")
        index.add_documents(["chunk1"], ["test document"])
        index.build()

        index.clear()

        assert index.chunk_ids == []
        assert index.documents == []
        assert index.bm25 is None

    def test_multiple_add_documents(self) -> None:
        """Multiple add_documents calls accumulate."""
        index = BM25Index("test")
        # Use longer documents to get non-zero BM25 scores
        index.add_documents(
            ["chunk1"],
            ["first document about legal licensing agreements and contracts"],
        )
        index.add_documents(
            ["chunk2"],
            ["second document about market data and redistribution fees"],
        )
        index.add_documents(
            ["chunk3"],
            ["third document about subscriber definitions and terms"],
        )
        index.build()

        assert len(index.chunk_ids) == 3
        # Query for terms unique to chunk1
        results = index.query("first legal licensing", top_k=1)
        assert len(results) > 0
        assert results[0][0] == "chunk1"


class TestSearchMode:
    """Tests for SearchMode enum."""

    def test_valid_modes(self) -> None:
        """All valid modes can be created."""
        assert SearchMode("vector") == SearchMode.VECTOR
        assert SearchMode("keyword") == SearchMode.KEYWORD
        assert SearchMode("hybrid") == SearchMode.HYBRID

    def test_invalid_mode_raises(self) -> None:
        """Invalid mode raises ValueError."""
        with pytest.raises(ValueError):
            SearchMode("invalid")

    def test_mode_values(self) -> None:
        """Mode values are correct strings."""
        assert SearchMode.VECTOR.value == "vector"
        assert SearchMode.KEYWORD.value == "keyword"
        assert SearchMode.HYBRID.value == "hybrid"


class TestBM25IndexPersistence:
    """Tests for BM25 index persistence (save/load)."""

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """Save creates a pickle file."""
        import app.search as search_module

        # Temporarily override index directory
        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = tmp_path

        try:
            index = BM25Index("test_provider")
            index.add_documents(["chunk1"], ["test document"])
            index.build()
            index.save()

            assert (tmp_path / "test_provider_index.pkl").exists()
        finally:
            search_module.BM25_INDEX_DIR = original_dir

    def test_load_restores_index(self, tmp_path: Path) -> None:
        """Load restores a saved index."""
        import app.search as search_module

        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = tmp_path
        search_module.BM25_INDEX_DIR = tmp_path  # type: ignore[assignment]

        try:
            # Create and save index with longer documents
            index = BM25Index("test_provider")
            index.add_documents(
                ["chunk1", "chunk2", "chunk3"],
                [
                    "The quick brown fox jumps over the lazy dog in the forest",
                    "The lazy sleepy dog rests by the warm fireplace all day long",
                    "Python programming language is powerful and easy to learn",
                ],
            )
            index.build()
            index.save()

            # Load and verify
            loaded = BM25Index.load("test_provider")

            assert loaded is not None
            assert len(loaded.chunk_ids) == 3
            assert loaded.bm25 is not None

            # Verify query works with multi-word query for better BM25 match
            results = loaded.query("quick brown fox", top_k=1)
            assert len(results) > 0
            assert results[0][0] == "chunk1"
        finally:
            search_module.BM25_INDEX_DIR = original_dir

    def test_load_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Load returns None for nonexistent index."""
        import app.search as search_module

        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = tmp_path

        try:
            loaded = BM25Index.load("nonexistent_provider")
            assert loaded is None
        finally:
            search_module.BM25_INDEX_DIR = original_dir

    def test_load_validates_magic_bytes(self, tmp_path: Path) -> None:
        """Load rejects files with invalid magic bytes."""
        import app.search as search_module

        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = tmp_path

        try:
            # Create a file with invalid magic bytes
            index_path = tmp_path / "test_provider_index.pkl"
            with open(index_path, "wb") as f:
                f.write(b"INVALID!")
                import pickle

                pickle.dump({"chunk_ids": []}, f)

            loaded = BM25Index.load("test_provider")
            assert loaded is None  # Should reject due to invalid magic
        finally:
            search_module.BM25_INDEX_DIR = original_dir

    def test_load_validates_document_count(self, tmp_path: Path) -> None:
        """Load rejects files with mismatched document count."""
        import app.search as search_module

        original_dir = search_module.BM25_INDEX_DIR
        search_module.BM25_INDEX_DIR = tmp_path

        try:
            # Create index with corrupted document count
            index_path = tmp_path / "test_provider_index.pkl"
            with open(index_path, "wb") as f:
                f.write(search_module.BM25_INDEX_MAGIC)
                import pickle

                pickle.dump(
                    {
                        "version": "1.0",
                        "source": "test_provider",
                        "document_count": 999,  # Intentionally wrong
                        "chunk_ids": ["chunk1"],
                        "documents": ["test"],
                        "tokenized_corpus": [["test"]],
                    },
                    f,
                )

            loaded = BM25Index.load("test_provider")
            assert loaded is None  # Should reject due to count mismatch
        finally:
            search_module.BM25_INDEX_DIR = original_dir
