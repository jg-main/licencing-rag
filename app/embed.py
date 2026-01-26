# app/embed.py
"""Embedding function for ChromaDB using Ollama."""

from typing import Any

import ollama
from chromadb import EmbeddingFunction
from chromadb import Embeddings

from app.config import EMBED_MODEL


class OllamaEmbeddingFunction(EmbeddingFunction):  # type: ignore[type-arg]
    """ChromaDB-compatible embedding function using Ollama.

    This class wraps the Ollama embedding API to provide embeddings
    for both document ingestion and query-time embedding.
    """

    def __init__(self, model: str = EMBED_MODEL) -> None:
        """Initialize the embedding function.

        Args:
            model: The Ollama embedding model to use.
        """
        self.model = model

    def __call__(self, input: Any) -> Embeddings:
        """Embed a list of texts.

        Args:
            input: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        embeddings: Embeddings = []
        for text in input:
            response = ollama.embed(model=self.model, input=text)
            embeddings.append(response["embeddings"][0])
        return embeddings
