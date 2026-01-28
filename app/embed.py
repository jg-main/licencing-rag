# app/embed.py
"""Embedding function for ChromaDB using OpenAI.

This module provides OpenAI embeddings using text-embedding-3-large model
with 3072 dimensions. This is a breaking change from the previous Ollama-based
embeddings (768 dimensions) - all documents must be re-indexed.
"""

import os
from typing import Any

import tiktoken
from chromadb import EmbeddingFunction
from chromadb.api.types import Embeddings
from openai import OpenAI

from app.config import EMBEDDING_DIMENSIONS
from app.config import EMBEDDING_MODEL
from app.config import MAX_CHUNK_CHARS
from app.logging import get_logger

log = get_logger(__name__)

# OpenAI embeddings API limits
# - Max 2048 texts per request
# - Max ~8191 tokens per text (model limit)
# - Practical total token limit per batch: ~1M tokens, but we stay conservative
MAX_BATCH_TOKENS = 500_000  # Stay well under API limits
MAX_TEXTS_PER_BATCH = 100  # Reasonable number of texts per batch


class OpenAIEmbeddingFunction(EmbeddingFunction):  # type: ignore[type-arg]
    """ChromaDB-compatible embedding function using OpenAI.

    This class wraps the OpenAI embedding API to provide embeddings
    for both document ingestion and query-time embedding.

    Uses text-embedding-3-large model which produces 3072-dimensional vectors.
    """

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
    ) -> None:
        """Initialize the embedding function.

        Args:
            model: The OpenAI embedding model to use.
            dimensions: The output dimensions for embeddings.

        Raises:
            ValueError: If OPENAI_API_KEY environment variable is not set.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required. "
                "Get your key at https://platform.openai.com/api-keys"
            )
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions
        # Use cl100k_base tokenizer (same as text-embedding-3-* models)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    @staticmethod
    def name() -> str:
        """Return the name of the embedding function for ChromaDB compatibility."""
        return EMBEDDING_MODEL

    def get_config(self) -> dict[str, Any]:
        """Return the configuration for ChromaDB compatibility."""
        return {
            "model": self.model,
            "dimensions": self.dimensions,
        }

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "OpenAIEmbeddingFunction":
        """Build an instance from configuration for ChromaDB compatibility."""
        return OpenAIEmbeddingFunction(
            model=config.get("model", EMBEDDING_MODEL),
            dimensions=config.get("dimensions", EMBEDDING_DIMENSIONS),
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        return len(self._tokenizer.encode(text))

    def _create_token_aware_batches(self, texts: list[str]) -> list[list[str]]:
        """Create batches that respect token limits.

        Ensures each batch stays under MAX_BATCH_TOKENS total tokens
        and MAX_TEXTS_PER_BATCH texts.

        Args:
            texts: List of text strings to batch.

        Returns:
            List of batches, where each batch is a list of texts.
        """
        batches: list[list[str]] = []
        current_batch: list[str] = []
        current_tokens = 0

        for text in texts:
            text_tokens = self._count_tokens(text)

            # If single text exceeds limit, it goes in its own batch
            # (OpenAI will handle the truncation or error)
            if text_tokens > MAX_BATCH_TOKENS:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0
                batches.append([text])
                continue

            # Check if adding this text would exceed limits
            would_exceed_tokens = current_tokens + text_tokens > MAX_BATCH_TOKENS
            would_exceed_count = len(current_batch) >= MAX_TEXTS_PER_BATCH

            if would_exceed_tokens or would_exceed_count:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [text]
                current_tokens = text_tokens
            else:
                current_batch.append(text)
                current_tokens += text_tokens

        if current_batch:
            batches.append(current_batch)

        return batches

    def __call__(self, input: Any) -> Embeddings:
        """Embed a list of texts.

        Args:
            input: List of text strings to embed.

        Returns:
            List of embedding vectors (3072 dimensions each).
        """
        if not input:
            return []

        # Truncate texts that exceed character limit
        texts = []
        for text in input:
            truncated = text[:MAX_CHUNK_CHARS] if len(text) > MAX_CHUNK_CHARS else text
            texts.append(truncated)

        embeddings: Embeddings = []

        # Create token-aware batches to avoid API limits
        batches = self._create_token_aware_batches(texts)
        log.debug(
            "embedding_batches_created",
            total_texts=len(texts),
            num_batches=len(batches),
        )

        for batch in batches:
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dimensions,
                )
                for embedding_data in response.data:
                    embeddings.append(embedding_data.embedding)  # type: ignore[arg-type]
            except Exception as e:
                log.error(
                    "embedding_failed",
                    model=self.model,
                    batch_size=len(batch),
                    error=str(e),
                )
                raise

        return embeddings  # type: ignore[return-value]

    def embed_query(self, input: Any) -> Embeddings:  # type: ignore[override]
        """Embed a query or list of queries.

        ChromaDB calls this with either a string or list of strings.

        Args:
            input: Query text (string) or list of query texts.

        Returns:
            Embedding vector(s).
        """
        # ChromaDB 1.4+ passes a list even for single queries
        if isinstance(input, list):
            return self.__call__(input)
        # Handle single string for direct calls
        result = self.__call__([input])
        return result[0]  # type: ignore[return-value]

    @property
    def embedding_model(self) -> str:
        """Return the embedding model name for metadata tracking."""
        return self.model

    @property
    def embedding_dimensions(self) -> int:
        """Return the embedding dimensions for metadata tracking."""
        return self.dimensions
