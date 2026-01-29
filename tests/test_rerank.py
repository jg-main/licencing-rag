"""Tests for LLM reranking module (Phase 4)."""

import pytest

from app.rerank import MAX_CHUNK_LENGTH_FOR_RERANKING
from app.rerank import parse_score_response
from app.rerank import rerank_chunks
from app.rerank import score_chunk
from app.rerank import truncate_chunk


class TestTruncation:
    """Test chunk text truncation for reranking."""

    def test_short_chunk_not_truncated(self):
        """Short chunks should pass through unchanged."""
        text = "This is a short chunk of text."
        result = truncate_chunk(text)
        assert result == text

    def test_long_chunk_truncated(self):
        """Long chunks should be truncated with ellipsis."""
        text = "x" * 3000
        result = truncate_chunk(text, max_length=2000)
        assert len(result) == 2003  # 2000 + "..."
        assert result.endswith("...")

    def test_custom_max_length(self):
        """Custom max length should be respected."""
        text = "x" * 500
        result = truncate_chunk(text, max_length=100)
        assert len(result) == 103  # 100 + "..."


class TestScoreResponseParsing:
    """Test parsing of LLM score responses."""

    def test_parse_valid_score_3(self):
        """Parse valid score 3 response."""
        response = "Score: 3\nExplanation: Directly answers the question about fees."
        score, explanation = parse_score_response(response)
        assert score == 3
        assert "fees" in explanation.lower()

    def test_parse_valid_score_0(self):
        """Parse valid score 0 response."""
        response = "Score: 0\nExplanation: Not relevant to the question."
        score, explanation = parse_score_response(response)
        assert score == 0

    def test_parse_with_extra_whitespace(self):
        """Parse response with extra whitespace."""
        response = "  Score:  2  \n  Explanation:  Contains related info  "
        score, explanation = parse_score_response(response)
        assert score == 2
        assert "related info" in explanation.lower()

    def test_parse_score_out_of_range(self):
        """Score should be clamped to 0-3 range."""
        response = "Score: 5\nExplanation: This is too high."
        score, explanation = parse_score_response(response)
        assert score == 3  # Clamped to max

    def test_parse_malformed_response(self):
        """Malformed response should default to score 1."""
        response = "This is just some random text without proper format."
        score, explanation = parse_score_response(response)
        assert score == 1  # Default
        assert explanation == response.strip()

    def test_parse_missing_explanation(self):
        """Response without explanation should still parse score."""
        response = "Score: 2"
        score, _ = parse_score_response(response)
        assert score == 2

    def test_parse_case_insensitive(self):
        """Parsing should be case-insensitive."""
        response = "score: 2\nexplanation: Some text"
        score, explanation = parse_score_response(response)
        assert score == 2
        assert "some text" in explanation.lower()


class TestChunkScoring:
    """Test individual chunk scoring."""

    @pytest.mark.skipif(True, reason="Requires OpenAI API key and makes real API calls")
    def test_score_chunk_integration(self):
        """Integration test for scoring a chunk (requires API key)."""
        chunk_text = """
        CME Group Market Data Fee Schedule

        Professional User Fee: $105 per month
        Non-Professional User Fee: $10 per month
        """
        question = "What are the CME market data fees?"

        score, explanation = score_chunk(
            chunk_id="test_chunk_1",
            chunk_text=chunk_text,
            question=question,
        )

        # Should score high (2 or 3) since it directly answers the question
        assert score >= 2
        assert len(explanation) > 0

    def test_score_chunk_error_handling(self):
        """Test error handling in score_chunk."""
        # Test with empty text should not crash
        score, explanation = score_chunk(
            chunk_id="test_chunk_error",
            chunk_text="",
            question="What are the fees?",
        )
        # Should return some score (even if default)
        assert 0 <= score <= 3


class TestRerankChunks:
    """Test the main rerank_chunks function."""

    def test_rerank_empty_list(self):
        """Reranking empty list should return empty lists."""
        kept, dropped = rerank_chunks([], "What are the fees?")
        assert kept == []
        assert dropped == []

    @pytest.mark.skipif(True, reason="Requires OpenAI API key and makes real API calls")
    def test_rerank_basic_integration(self):
        """Basic integration test for reranking (requires API key)."""
        chunks = [
            {
                "chunk_id": "chunk_1",
                "text": "CME market data fees are $105/month for professionals.",
                "metadata": {"source": "cme"},
                "score": 0.8,
                "source": "hybrid",
            },
            {
                "chunk_id": "chunk_2",
                "text": "The Exchange reserves the right to modify these terms.",
                "metadata": {"source": "cme"},
                "score": 0.6,
                "source": "hybrid",
            },
            {
                "chunk_id": "chunk_3",
                "text": "Historical data is available through the archive service.",
                "metadata": {"source": "cme"},
                "score": 0.5,
                "source": "hybrid",
            },
        ]

        question = "What are the CME market data fees?"

        kept, dropped = rerank_chunks(chunks, question, top_k=2)

        # Should keep top 2 chunks
        assert len(kept) == 2
        assert len(dropped) == 1

        # First chunk should score highest (directly answers question)
        assert kept[0].chunk_id == "chunk_1"
        assert kept[0].relevance_score >= 2

    def test_rerank_top_k_larger_than_chunks(self):
        """Test when top_k is larger than number of chunks."""
        chunks = [
            {
                "chunk_id": "chunk_1",
                "text": "Some text",
                "metadata": {},
                "score": 0.8,
                "source": "vector",
            },
        ]

        # Mock the scoring to avoid API calls
        import app.rerank

        original_score_chunk = app.rerank.score_chunk

        def mock_score_chunk(
            chunk_id, chunk_text, question, model=None, include_explanations=True
        ):
            return 2, "Mock explanation"

        app.rerank.score_chunk = mock_score_chunk

        try:
            # MAX_CHUNKS_AFTER_RERANKING from config will apply
            kept, dropped = rerank_chunks(chunks, "test question")
            assert len(kept) == 1
            assert len(dropped) == 0
        finally:
            app.rerank.score_chunk = original_score_chunk

    def test_rerank_sequential_mode(self):
        """Test sequential (non-parallel) reranking."""
        chunks = [
            {
                "chunk_id": "chunk_1",
                "text": "Text 1",
                "metadata": {},
                "score": 0.8,
                "source": "vector",
            },
            {
                "chunk_id": "chunk_2",
                "text": "Text 2",
                "metadata": {},
                "score": 0.6,
                "source": "vector",
            },
        ]

        # Mock the scoring to avoid API calls
        import app.rerank

        original_score_chunk = app.rerank.score_chunk

        call_count = [0]

        def mock_score_chunk(
            chunk_id, chunk_text, question, model=None, include_explanations=True
        ):
            call_count[0] += 1
            if chunk_id == "chunk_1":
                return 3, "Highly relevant"
            return 1, "Somewhat relevant"

        app.rerank.score_chunk = mock_score_chunk

        try:
            # Test with sequential processing (mocked scores ensure chunk_1 wins)
            # MIN_RERANKING_SCORE=2 means chunk_2 (score=1) gets dropped
            kept, dropped = rerank_chunks(chunks, "test question")
            assert len(kept) == 1  # Only chunk_1 (score=3 >= 2)
            assert len(dropped) == 1  # chunk_2 (score=1 < 2)
            assert kept[0].chunk_id == "chunk_1"
            assert kept[0].relevance_score == 3
            assert call_count[0] == 2  # Should have called mock twice
        finally:
            app.rerank.score_chunk = original_score_chunk

    def test_rerank_sorting_by_relevance(self):
        """Test that chunks are sorted by relevance score."""
        chunks = [
            {
                "chunk_id": "chunk_1",
                "text": "Low relevance",
                "metadata": {},
                "score": 0.5,
                "source": "vector",
            },
            {
                "chunk_id": "chunk_2",
                "text": "High relevance",
                "metadata": {},
                "score": 0.9,
                "source": "vector",
            },
            {
                "chunk_id": "chunk_3",
                "text": "Medium relevance",
                "metadata": {},
                "score": 0.7,
                "source": "vector",
            },
        ]

        # Mock scoring
        import app.rerank

        original_score_chunk = app.rerank.score_chunk

        def mock_score_chunk(
            chunk_id, chunk_text, question, model=None, include_explanations=True
        ):
            # Give them different scores that all pass threshold
            if chunk_id == "chunk_1":
                return 2, "Relevant"
            if chunk_id == "chunk_2":
                return 3, "Highly relevant"
            return 2, "Relevant"

        app.rerank.score_chunk = mock_score_chunk

        try:
            kept, dropped = rerank_chunks(chunks, "test question")
            # All chunks >= MIN_RERANKING_SCORE (2)
            assert len(kept) == 3
            # Should be sorted by relevance_score descending
            assert kept[0].chunk_id == "chunk_2"  # score=3
            assert kept[0].relevance_score == 3
            # chunk_1 and chunk_3 both have score=2, order preserved from original
        finally:
            app.rerank.score_chunk = original_score_chunk

    def test_rerank_preserves_metadata(self):
        """Test that metadata is preserved through reranking."""
        chunks = [
            {
                "chunk_id": "chunk_1",
                "text": "Text 1",
                "metadata": {"source": "cme", "page_start": 5},
                "score": 0.8,
                "source": "hybrid",
            },
        ]

        # Mock the scoring
        import app.rerank

        original_score_chunk = app.rerank.score_chunk

        def mock_score_chunk(
            chunk_id, chunk_text, question, model=None, include_explanations=True
        ):
            return 2, "Relevant"  # Score >= threshold

        app.rerank.score_chunk = mock_score_chunk

        try:
            kept, dropped = rerank_chunks(chunks, "test question")
            assert len(kept) == 1
            assert kept[0].metadata["source"] == "cme"
            assert kept[0].metadata["page_start"] == 5
            assert kept[0].source == "hybrid"
            assert kept[0].original_score == 0.8
        finally:
            app.rerank.score_chunk = original_score_chunk


class TestRerankingConfiguration:
    """Test reranking configuration constants."""

    def test_max_chunk_length_reasonable(self):
        """Ensure max chunk length is reasonable."""
        assert MAX_CHUNK_LENGTH_FOR_RERANKING > 0
        assert MAX_CHUNK_LENGTH_FOR_RERANKING <= 5000  # Not too large


class TestRerankIntegration:
    """Integration tests with query pipeline."""

    @pytest.mark.skipif(True, reason="Requires full integration setup and API key")
    def test_query_with_reranking_enabled(self):
        """Test query pipeline with reranking enabled."""
        from app.query import query

        result = query(
            "What are the CME market data fees?",
            sources=["cme"],
            enable_reranking=True,
            debug=True,
        )

        # Should have debug info with reranking details
        assert "debug" in result
        assert "reranking" in result["debug"]
        assert result["debug"]["reranking"]["enabled"] is True
        assert "chunks_after_reranking" in result["debug"]["reranking"]

    @pytest.mark.skipif(True, reason="Requires full integration setup and API key")
    def test_query_with_reranking_disabled(self):
        """Test query pipeline with reranking disabled."""
        from app.query import query

        result = query(
            "What are the CME market data fees?",
            sources=["cme"],
            enable_reranking=False,
            debug=True,
        )

        # Should not have reranking info
        if "debug" in result and "reranking" in result["debug"]:
            assert result["debug"]["reranking"]["enabled"] is False
