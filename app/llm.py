# app/llm.py
"""LLM provider abstraction for answer generation."""

import os
from abc import ABC
from abc import abstractmethod

import anthropic
import ollama

from app.config import ANTHROPIC_MODEL
from app.config import LLM_MODEL
from app.config import LLM_PROVIDER


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, system: str, prompt: str) -> str:
        """Generate a response given system prompt and user prompt.

        Args:
            system: System prompt with instructions.
            prompt: User prompt with context and question.

        Returns:
            Generated response text.
        """
        pass


class OllamaProvider(LLMProvider):
    """Ollama-based LLM provider for local inference."""

    def __init__(self, model: str = LLM_MODEL) -> None:
        """Initialize the Ollama provider.

        Args:
            model: Model name to use (e.g., 'llama3.2:3b').
        """
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        """Generate response using Ollama.

        Args:
            system: System prompt.
            prompt: User prompt.

        Returns:
            Generated text.
        """
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return str(response["message"]["content"])


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, model: str = ANTHROPIC_MODEL) -> None:
        """Initialize the Anthropic provider.

        Args:
            model: Model name to use (e.g., 'claude-sonnet-4-20250514').

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set.
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Get your key at https://console.anthropic.com/"
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        """Generate response using Claude API.

        Args:
            system: System prompt.
            prompt: User prompt.

        Returns:
            Generated text.
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        # Extract text from response
        content = response.content[0]
        if hasattr(content, "text"):
            return str(content.text)
        return str(content)


def get_llm() -> LLMProvider:
    """Get the configured LLM provider.

    Returns:
        LLMProvider instance based on LLM_PROVIDER config.
    """
    if LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    return OllamaProvider()
