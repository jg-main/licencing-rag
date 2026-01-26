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
from app.logging import get_logger

log = get_logger(__name__)


class LLMConnectionError(Exception):
    """Raised when LLM connection or generation fails."""

    pass


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

        Raises:
            LLMConnectionError: If generation fails.
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

        Raises:
            LLMConnectionError: If Ollama is not running or generation fails.
        """
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return str(response["message"]["content"])
        except ollama.ResponseError as e:
            log.error("ollama_response_error", model=self.model, error=str(e))
            raise LLMConnectionError(f"Ollama error: {e}") from e
        except Exception as e:
            log.error("ollama_connection_failed", model=self.model, error=str(e))
            raise LLMConnectionError(
                f"Cannot connect to Ollama. Is it running? Error: {e}"
            ) from e


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, model: str = ANTHROPIC_MODEL) -> None:
        """Initialize the Anthropic provider.

        Args:
            model: Model name to use (e.g., 'claude-sonnet-4-5-20250929').

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

        Raises:
            LLMConnectionError: If API call fails.
        """
        try:
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
        except anthropic.APIConnectionError as e:
            log.error("anthropic_connection_error", error=str(e))
            raise LLMConnectionError(f"Cannot connect to Anthropic API: {e}") from e
        except anthropic.RateLimitError as e:
            log.error("anthropic_rate_limit", error=str(e))
            raise LLMConnectionError(f"Anthropic rate limit exceeded: {e}") from e
        except anthropic.APIStatusError as e:
            log.error("anthropic_api_error", status=e.status_code, error=str(e))
            raise LLMConnectionError(
                f"Anthropic API error ({e.status_code}): {e}"
            ) from e


def get_llm() -> LLMProvider:
    """Get the configured LLM provider.

    Returns:
        LLMProvider instance based on LLM_PROVIDER config.

    Raises:
        ValueError: If provider requires missing configuration.
    """
    log.debug("initializing_llm", provider=LLM_PROVIDER)
    if LLM_PROVIDER == "anthropic":
        return AnthropicProvider()
    return OllamaProvider()
