# tests/test_gate.py
"""Tests for confidence gating (Phase 6) - Two-tier gating system."""

from app.gate import get_refusal_reason_message
from app.gate import should_refuse


class MockChunk:
    """Mock chunk object with relevance score."""

    def __init__(self, relevance_score: float):
        self.relevance_score = relevance_score


class TestShouldRefuseReranked:
    """Test should_refuse() with reranked scores (0-3 scale)."""

    def test_refuse_when_no_chunks(self):
        """Should refuse when no chunks retrieved."""
        refuse, reason = should_refuse([], scores_are_reranked=True)
        assert refuse is True
        assert reason == "no_chunks_retrieved"

    def test_refuse_when_all_chunks_below_threshold(self):
        """Should refuse when all chunks score below threshold."""
        chunks = [
            MockChunk(0),
            MockChunk(1),
            MockChunk(1.5),
        ]
        refuse, reason = should_refuse(
            chunks, scores_are_reranked=True, relevance_threshold=2
        )
        assert refuse is True
        assert reason == "all_chunks_below_threshold"

    def test_refuse_when_top_score_below_threshold(self):
        """Should refuse when top score is below threshold."""
        chunks = [
            MockChunk(1.9),
            MockChunk(1.5),
            MockChunk(1.0),
        ]
        refuse, reason = should_refuse(
            chunks, scores_are_reranked=True, relevance_threshold=2
        )
        assert refuse is True
        assert reason in ("all_chunks_below_threshold", "top_score_below_threshold")

    def test_accept_when_chunk_above_threshold(self):
        """Should accept when at least one chunk is above threshold."""
        chunks = [
            MockChunk(2.5),
            MockChunk(1.0),
            MockChunk(0.5),
        ]
        refuse, reason = should_refuse(
            chunks, scores_are_reranked=True, relevance_threshold=2
        )
        assert refuse is False
        assert reason is None

    def test_accept_when_chunk_exactly_at_threshold(self):
        """Should accept when chunk score equals threshold."""
        chunks = [
            MockChunk(2.0),
            MockChunk(1.0),
        ]
        refuse, reason = should_refuse(
            chunks, scores_are_reranked=True, relevance_threshold=2
        )
        assert refuse is False
        assert reason is None

    def test_refuse_when_insufficient_chunks_above_threshold(self):
        """Should refuse when not enough chunks above threshold."""
        chunks = [
            MockChunk(2.5),
            MockChunk(1.0),
            MockChunk(0.5),
        ]
        # Require at least 2 chunks above threshold
        refuse, reason = should_refuse(
            chunks, scores_are_reranked=True, relevance_threshold=2, min_chunks=2
        )
        assert refuse is True
        assert reason == "insufficient_chunks_above_threshold"

    def test_accept_when_enough_chunks_above_threshold(self):
        """Should accept when enough chunks above threshold."""
        chunks = [
            MockChunk(3.0),
            MockChunk(2.5),
            MockChunk(1.0),
        ]
        # Require at least 2 chunks above threshold
        refuse, reason = should_refuse(
            chunks, scores_are_reranked=True, relevance_threshold=2, min_chunks=2
        )
        assert refuse is False
        assert reason is None

    def test_custom_threshold(self):
        """Should work with custom threshold values."""
        chunks = [
            MockChunk(1.5),
            MockChunk(1.0),
        ]
        # Lower threshold - should accept
        refuse, reason = should_refuse(
            chunks, scores_are_reranked=True, relevance_threshold=1
        )
        assert refuse is False
        assert reason is None

        # Higher threshold - should refuse
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is True

    def test_handles_dict_chunks(self):
        """Should handle chunks as dictionaries."""
        chunks = [
            {"relevance_score": 2.5},
            {"relevance_score": 1.0},
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is False
        assert reason is None

    def test_handles_metadata_dict_chunks(self):
        """Should handle chunks with metadata dict containing _relevance_score."""

        class ChunkWithMetadata:
            def __init__(self, score: float):
                self.metadata = {"_relevance_score": score}

        chunks = [
            ChunkWithMetadata(2.5),
            ChunkWithMetadata(1.0),
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is False
        assert reason is None

    def test_handles_missing_scores_as_zero(self):
        """Should treat chunks without scores as having score 0."""

        class ChunkNoScore:
            pass

        chunks = [
            ChunkNoScore(),
            ChunkNoScore(),
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is True
        # All chunks treated as score 0, below threshold
        assert reason in ("all_chunks_below_threshold", "top_score_below_threshold")


class TestRefusalMessages:
    """Test refusal reason messages."""

    def test_no_chunks_retrieved_message(self):
        """Should return appropriate message for no chunks."""
        msg = get_refusal_reason_message("no_chunks_retrieved")
        assert "No relevant information" in msg
        assert "found" in msg

    def test_all_chunks_below_threshold_message(self):
        """Should return appropriate message for low scores."""
        msg = get_refusal_reason_message("all_chunks_below_threshold")
        assert "sufficiently relevant" in msg or "relevant" in msg

    def test_insufficient_chunks_message(self):
        """Should return appropriate message for insufficient chunks."""
        msg = get_refusal_reason_message("insufficient_chunks_above_threshold")
        assert "Insufficient" in msg or "insufficient" in msg

    def test_top_score_below_threshold_message(self):
        """Should return appropriate message for top score below threshold."""
        msg = get_refusal_reason_message("top_score_below_threshold")
        assert "relevant" in msg or "confidence" in msg or "threshold" in msg

    def test_unknown_reason_message(self):
        """Should return generic message for unknown reason."""
        msg = get_refusal_reason_message("unknown_reason_code")
        assert "Unable to provide" in msg or "reliable answer" in msg

    def test_none_reason_message(self):
        """Should return generic message for None reason."""
        msg = get_refusal_reason_message(None)
        assert "Unable to provide" in msg or "reliable answer" in msg


class TestGateIntegration:
    """Integration tests for confidence gating."""

    def test_typical_good_reranking_results(self):
        """Should accept typical good reranking results."""
        # Simulate reranked chunks with good scores
        chunks = [
            MockChunk(3),  # HIGHLY RELEVANT
            MockChunk(2),  # RELEVANT
            MockChunk(2),  # RELEVANT
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is False
        assert reason is None

    def test_typical_poor_reranking_results(self):
        """Should refuse typical poor reranking results."""
        # Simulate reranked chunks with poor scores
        chunks = [
            MockChunk(1),  # NOT RELEVANT
            MockChunk(1),  # NOT RELEVANT
            MockChunk(0),  # NOT RELEVANT
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is True
        assert reason is not None

    def test_mixed_reranking_results(self):
        """Should accept mixed results if top chunks are good."""
        chunks = [
            MockChunk(3),  # HIGHLY RELEVANT
            MockChunk(1),  # NOT RELEVANT
            MockChunk(0),  # NOT RELEVANT
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is False
        assert reason is None

    def test_borderline_case_just_above_threshold(self):
        """Should accept borderline case just above threshold."""
        chunks = [
            MockChunk(2.01),  # Just above threshold
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is False
        assert reason is None

    def test_borderline_case_just_below_threshold(self):
        """Should refuse borderline case just below threshold."""
        chunks = [
            MockChunk(1.99),  # Just below threshold
        ]
        refuse, reason = should_refuse(chunks, relevance_threshold=2)
        assert refuse is True
        assert reason is not None


class TestGateConfiguration:
    """Test gating with different configuration values."""

    def test_strict_gating(self):
        """Should work with strict thresholds."""
        chunks = [
            MockChunk(2.5),
            MockChunk(2.0),
        ]
        # Strict: require score >= 3
        refuse, reason = should_refuse(chunks, relevance_threshold=3)
        assert refuse is True

    def test_lenient_gating(self):
        """Should work with lenient thresholds."""
        chunks = [
            MockChunk(1.0),
            MockChunk(0.5),
        ]
        # Lenient: require score >= 0.5
        refuse, reason = should_refuse(chunks, relevance_threshold=0.5)
        assert refuse is False

    def test_require_multiple_good_chunks(self):
        """Should enforce min_chunks requirement."""
        chunks = [
            MockChunk(3.0),
            MockChunk(1.0),
            MockChunk(1.0),
        ]
        # Only 1 chunk above threshold, but require 2
        refuse, reason = should_refuse(chunks, relevance_threshold=2, min_chunks=2)
        assert refuse is True
        assert reason == "insufficient_chunks_above_threshold"

        # If we only require 1, should accept
        refuse, reason = should_refuse(chunks, relevance_threshold=2, min_chunks=1)
        assert refuse is False


class TestShouldRefuseRetrieval:
    """Test should_refuse() with raw retrieval scores (vector/BM25/RRF)."""

    def test_accept_good_retrieval_scores(self):
        """Should accept when top score stands out from others."""
        # Simulates good retrieval: top (0.9) / top2 (0.5) = 1.8 > 1.2 ✓
        chunks = [
            MockChunk(0.9),  # Top-1
            MockChunk(0.5),  # Top-2
            MockChunk(0.3),
            MockChunk(0.2),
            MockChunk(0.1),
        ]
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is False
        assert reason is None

    def test_refuse_when_no_clear_winner(self):
        """Should refuse when all scores are similar (no clear best match)."""
        # All scores close together: ratio = 0.55/0.54 = 1.018 < 1.2 ✗
        chunks = [
            MockChunk(0.55),
            MockChunk(0.54),
            MockChunk(0.53),
            MockChunk(0.52),
            MockChunk(0.51),
        ]
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is True
        assert reason == "retrieval_insufficient_ratio"

    def test_refuse_when_negative_scores(self):
        """Should refuse when all scores are negative (false accept prevention)."""
        # All negative scores - top1 (-0.1) <= min_score (0.05) ✗
        chunks = [
            MockChunk(-0.1),  # Top-1 (negative!)
            MockChunk(-1.0),
            MockChunk(-2.0),
        ]
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is True
        assert reason == "retrieval_top_below_minimum"

    def test_accept_single_chunk_with_positive_score(self):
        """Should accept single chunk if score > 0."""
        chunks = [MockChunk(0.5)]
        refuse, reason = should_refuse(chunks, scores_are_reranked=False)
        assert refuse is False
        assert reason is None

    def test_refuse_single_chunk_with_zero_score(self):
        """Should refuse single chunk with zero or negative score."""
        chunks = [MockChunk(0.0)]
        refuse, reason = should_refuse(chunks, scores_are_reranked=False)
        assert refuse is True
        assert reason == "retrieval_score_too_low"

        chunks = [MockChunk(-0.1)]
        refuse, reason = should_refuse(chunks, scores_are_reranked=False)
        assert refuse is True
        assert reason == "retrieval_score_too_low"

    def test_custom_min_score_threshold(self):
        """Should work with custom minimum score thresholds."""
        chunks = [
            MockChunk(0.9),
            MockChunk(0.5),
            MockChunk(0.4),
            MockChunk(0.3),
        ]
        # Strict: require min score > 0.8, ratio 0.9/0.5 = 1.8 > 1.2 ✓
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.8,
            retrieval_min_ratio=1.2,
        )
        assert refuse is False

    def test_custom_ratio_threshold(self):
        """Should work with custom ratio thresholds."""
        chunks = [
            MockChunk(0.6),  # Top-1
            MockChunk(0.5),  # Top-2
            MockChunk(0.4),
        ]
        # Ratio = 0.6/0.5 = 1.2 exactly

        # Require ratio > 1.2 (strict) - should refuse
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.21,
        )
        assert refuse is True
        assert reason == "retrieval_insufficient_ratio"

        # Require ratio >= 1.2 (default) - should accept
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is False

    def test_handles_zero_top2_score(self):
        """Should handle case where top-2 is zero or negative with strong top-1."""
        chunks = [
            MockChunk(0.8),  # Top-1 is strong (>> 2 * min_score)
            MockChunk(0.0),  # Top-2 is 0
            MockChunk(0.0),
        ]
        # Uses special logic when top2 <= 0
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        # Should accept since top1 (0.8) > 2 * min_score (0.1) and significantly > top2
        assert refuse is False

    def test_refuses_weak_top1_with_negative_top2(self):
        """Should refuse when top-1 is weak and top-2 is negative."""
        chunks = [
            MockChunk(0.06),  # Top-1 barely above min_score
            MockChunk(-0.01),  # Top-2 is negative
            MockChunk(-0.05),
        ]
        # Should refuse: top1 (0.06) < 2 * min_score (0.10)
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is True
        assert reason == "retrieval_top1_too_weak_with_negative_top2"


class TestTwoTierGating:
    """Test two-tier gating: reranked vs retrieval scores."""

    def test_reranked_scores_use_threshold_gating(self):
        """Reranked scores should use 0-3 threshold-based gating."""
        chunks = [MockChunk(2.5), MockChunk(1.0)]

        # With scores_are_reranked=True, uses threshold (2)
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=True,
            relevance_threshold=2,
        )
        assert refuse is False  # 2.5 >= 2
        assert reason is None

    def test_retrieval_scores_use_min_score_gating(self):
        """Retrieval scores should use min_score+ratio gating."""
        chunks = [MockChunk(2.5), MockChunk(1.0)]

        # With scores_are_reranked=False, uses min_score+ratio (not threshold)
        # Ratio = 2.5/1.0 = 2.5 > 1.2, should accept
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is False

    def test_prevents_false_refusal_on_retrieval_fallback(self):
        """Should not falsely refuse retrieval scores using reranked thresholds."""
        # Simulates RRF scores: ratio = 0.9/0.7 = 1.29 > 1.2 ✓
        chunks = [
            MockChunk(0.9),  # Good RRF score
            MockChunk(0.7),
            MockChunk(0.5),
        ]

        # If we mistakenly used reranked threshold (2), this would refuse
        # But with retrieval gating, it should accept
        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is False  # Should NOT refuse

    def test_prevents_false_accept_on_bad_retrieval_scores(self):
        """Should refuse when retrieval scores show no confidence."""
        # All scores very close together: ratio = 0.21/0.20 = 1.05 < 1.2 ✗
        chunks = [
            MockChunk(0.21),
            MockChunk(0.20),
            MockChunk(0.19),
        ]

        refuse, reason = should_refuse(
            chunks,
            scores_are_reranked=False,
            retrieval_min_score=0.05,
            retrieval_min_ratio=1.2,
        )
        assert refuse is True  # Should refuse due to insufficient ratio
        assert reason == "retrieval_insufficient_ratio"


class TestRefusalMessagesExtended:
    """Test new refusal messages for retrieval-score gating."""

    def test_retrieval_score_too_low_message(self):
        """Should return message for low retrieval score."""
        msg = get_refusal_reason_message("retrieval_score_too_low")
        assert "relevance score" in msg.lower() or "insufficient" in msg.lower()

    def test_retrieval_top_below_minimum_message(self):
        """Should return message for low scores."""
        msg = get_refusal_reason_message("retrieval_top_below_minimum")
        assert "confidence" in msg.lower() or "low" in msg.lower()

    def test_retrieval_insufficient_ratio_message(self):
        """Should return message for insufficient ratio."""
        msg = get_refusal_reason_message("retrieval_insufficient_ratio")
        assert (
            "clear" in msg.lower()
            or "similar" in msg.lower()
            or "confidence" in msg.lower()
        )

    def test_empty_context_after_budget_message(self):
        """Should return message for empty context after budget."""
        msg = get_refusal_reason_message("empty_context_after_budget")
        assert (
            "budget" in msg.lower()
            or "token" in msg.lower()
            or "eliminated" in msg.lower()
        )
