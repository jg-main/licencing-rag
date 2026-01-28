# tests/test_query.py
"""Tests for query pipeline."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from app.prompts import QA_PROMPT
from app.prompts import SYSTEM_PROMPT
from app.prompts import get_refusal_message


class TestPrompts:
    """Tests for prompt templates."""

    def test_system_prompt_has_required_sections(self) -> None:
        """System prompt includes required output format."""
        assert "## Answer" in SYSTEM_PROMPT
        assert "## Supporting Clauses" in SYSTEM_PROMPT
        assert "## Citations" in SYSTEM_PROMPT
        assert "## Notes" in SYSTEM_PROMPT

    def test_system_prompt_requires_provider_in_citations(self) -> None:
        """System prompt requires provider prefix in citations."""
        assert "[PROVIDER]" in SYSTEM_PROMPT

    def test_system_prompt_requires_page_ranges(self) -> None:
        """System prompt mentions page ranges."""
        assert "Pages" in SYSTEM_PROMPT

    def test_qa_prompt_has_placeholders(self) -> None:
        """QA prompt has required placeholders."""
        assert "{provider}" in QA_PROMPT
        assert "{context}" in QA_PROMPT
        assert "{question}" in QA_PROMPT


class TestRefusalMessage:
    """Tests for refusal message generation."""

    def test_single_provider_refusal(self) -> None:
        """Single provider refusal message."""
        msg = get_refusal_message(["cme"])
        assert "CME" in msg
        assert "not addressed" in msg.lower()

    def test_multiple_provider_refusal(self) -> None:
        """Multiple provider refusal message."""
        msg = get_refusal_message(["cme", "ice"])
        assert "CME" in msg
        assert "ICE" in msg

    def test_empty_provider_refusal(self) -> None:
        """Empty provider list doesn't crash."""
        msg = get_refusal_message([])
        assert isinstance(msg, str)


class TestProviderNormalization:
    """Tests for provider list normalization."""

    def test_empty_providers_normalized_to_default(self) -> None:
        """Empty providers list is normalized to DEFAULT_PROVIDERS."""
        from pathlib import Path

        from app.config import DEFAULT_PROVIDERS
        from app.query import query

        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
            patch("app.query.get_llm") as mock_llm,
        ):
            # Mock collection
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["chunk_1"]],
                "documents": [["Test document"]],
                "metadatas": [
                    [
                        {
                            "chunk_id": "chunk_1",
                            "provider": "cme",
                            "document_path": "test.pdf",
                        }
                    ]
                ],
                "distances": [[0.1]],
            }
            mock_collection.metadata = {"embedding_model": "text-embedding-3-large"}
            mock_client.return_value.get_collection.return_value = mock_collection

            # Mock LLM
            mock_llm_instance = MagicMock()
            mock_llm_instance.generate.return_value = "Test answer"
            mock_llm.return_value = mock_llm_instance

            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    # Query with empty list should use DEFAULT_PROVIDERS
                    result = query("test question", providers=[])

            # Should have used default providers (cme)
            assert result["providers"] == DEFAULT_PROVIDERS

            # Should have proper provider label in context
            mock_llm_instance.generate.assert_called_once()
            call_args = mock_llm_instance.generate.call_args
            prompt = call_args.kwargs["prompt"]
            # Should mention CME (from DEFAULT_PROVIDERS)
            assert "CME" in prompt


class TestEffectiveSearchMode:
    """Tests for effective_search_mode tracking."""

    def test_keyword_fallback_to_vector_reported(self) -> None:
        """When keyword mode falls back to vector, effective_search_mode reflects this."""
        from pathlib import Path

        from app.query import query

        # Mock ChromaDB and BM25 to simulate keyword fallback scenario
        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
            patch("app.query.BM25Index.load") as mock_bm25_load,
            patch("app.query.get_llm") as mock_llm,
        ):
            # Setup: BM25 index is missing (returns None)
            mock_bm25_load.return_value = None

            # Mock collection with vector results
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["chunk_1"]],
                "documents": [["Test document about fees"]],
                "metadatas": [
                    [
                        {
                            "chunk_id": "chunk_1",
                            "provider": "cme",
                            "document_path": "test.pdf",
                        }
                    ]
                ],
                "distances": [[0.1]],
            }
            mock_collection.metadata = {"embedding_model": "text-embedding-3-large"}
            mock_client.return_value.get_collection.return_value = mock_collection

            # Mock LLM response
            mock_llm_instance = MagicMock()
            mock_llm_instance.generate.return_value = "Test answer"
            mock_llm.return_value = mock_llm_instance

            # Mock CHROMA_DIR exists
            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    result = query(
                        "test question", providers=["cme"], search_mode="keyword"
                    )

            # Verify response includes both requested and effective mode
            assert result["search_mode"] == "keyword"
            assert result["effective_search_mode"] == "vector"

    def test_vector_mode_no_fallback(self) -> None:
        """When vector mode is used without fallback, modes match."""
        from pathlib import Path

        from app.query import query

        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
            patch("app.query.get_llm") as mock_llm,
        ):
            # Mock collection with vector results
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["chunk_1"]],
                "documents": [["Test document"]],
                "metadatas": [
                    [
                        {
                            "chunk_id": "chunk_1",
                            "provider": "cme",
                            "document_path": "test.pdf",
                        }
                    ]
                ],
                "distances": [[0.1]],
            }
            mock_collection.metadata = {"embedding_model": "text-embedding-3-large"}
            mock_client.return_value.get_collection.return_value = mock_collection

            # Mock LLM
            mock_llm_instance = MagicMock()
            mock_llm_instance.generate.return_value = "Test answer"
            mock_llm.return_value = mock_llm_instance

            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    result = query(
                        "test question", providers=["cme"], search_mode="vector"
                    )

            # Both should be vector
            assert result["search_mode"] == "vector"
            assert result["effective_search_mode"] == "vector"


class TestEmbeddingValidation:
    """Tests for embedding model and dimension validation guards."""

    def test_missing_embedding_metadata_raises_error(self) -> None:
        """Query should fail if collection lacks embedding_model metadata (legacy index)."""
        from pathlib import Path

        from app.query import query

        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
        ):
            # Mock collection with MISSING embedding metadata
            mock_collection = MagicMock()
            mock_collection.metadata = {}  # No embedding_model key
            mock_client.return_value.get_collection.return_value = mock_collection

            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    with pytest.raises(RuntimeError) as exc_info:
                        query("test question", providers=["cme"])

            assert "missing embedding metadata" in str(exc_info.value).lower()
            assert "legacy" in str(exc_info.value).lower()

    def test_embedding_model_mismatch_raises_error(self) -> None:
        """Query should fail if stored embedding model differs from config."""
        from pathlib import Path

        from app.query import query

        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
        ):
            # Mock collection with DIFFERENT embedding model (e.g., old Ollama model)
            mock_collection = MagicMock()
            mock_collection.metadata = {"embedding_model": "nomic-embed-text"}
            mock_client.return_value.get_collection.return_value = mock_collection

            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    with pytest.raises(RuntimeError) as exc_info:
                        query("test question", providers=["cme"])

            assert "mismatch" in str(exc_info.value).lower()
            assert "nomic-embed-text" in str(exc_info.value)

    def test_embedding_dimensions_mismatch_raises_error(self) -> None:
        """Query should fail if stored dimensions differ from config."""
        from pathlib import Path

        from app.query import query

        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
        ):
            # Mock collection with correct model but WRONG dimensions
            mock_collection = MagicMock()
            mock_collection.metadata = {
                "embedding_model": "text-embedding-3-large",
                "embedding_dimensions": 768,  # Wrong! Should be 3072
            }
            mock_client.return_value.get_collection.return_value = mock_collection

            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    with pytest.raises(RuntimeError) as exc_info:
                        query("test question", providers=["cme"])

            assert "dimensions mismatch" in str(exc_info.value).lower()
            assert "768" in str(exc_info.value)

    def test_collection_not_found_skips_provider(self) -> None:
        """Missing collection should skip provider and return refusal (NotFoundError)."""
        from pathlib import Path

        from chromadb.errors import NotFoundError

        from app.query import query

        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
        ):
            # Simulate collection not found
            mock_client.return_value.get_collection.side_effect = NotFoundError(
                "Collection not found"
            )

            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    result = query("test question", providers=["cme"])

            # Should return refusal response (no chunks retrieved)
            assert result["chunks_retrieved"] == 0
            assert "not addressed" in result["answer"].lower()

    def test_collection_not_found_valueerror_skips_provider(self) -> None:
        """Missing collection should skip provider and return refusal (ValueError for legacy ChromaDB)."""
        from pathlib import Path

        from app.query import query

        with (
            patch("app.query.chromadb.PersistentClient") as mock_client,
            patch("app.query.OpenAIEmbeddingFunction"),
        ):
            # Simulate legacy ChromaDB ValueError
            mock_client.return_value.get_collection.side_effect = ValueError(
                "Collection not found"
            )

            with patch("app.query.CHROMA_DIR", Path("/tmp/test_chroma")):
                with patch.object(Path, "exists", return_value=True):
                    result = query("test question", providers=["cme"])

            # Should return refusal response (no chunks retrieved)
            assert result["chunks_retrieved"] == 0
            assert "not addressed" in result["answer"].lower()
