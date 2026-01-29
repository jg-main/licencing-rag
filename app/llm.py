# app/llm.py
"""LLM client for OpenAI GPT-4.1.

This module provides a simple OpenAI client for answer generation.
Single source architecture: OpenAI only (no Ollama, no Claude).
"""

import os

import httpx
from openai import APITimeoutError
from openai import OpenAI

from app.config import LLM_MODEL
from app.logging import get_logger

log = get_logger(__name__)


class LLMConnectionError(Exception):
    """Raised when LLM connection or generation fails."""

    pass


def get_openai_client() -> OpenAI:
    """Get configured OpenAI client.

    Returns:
        OpenAI client instance.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Get your key at https://platform.openai.com/api-keys"
        )
    return OpenAI(api_key=api_key)


def generate(
    system: str,
    prompt: str,
    model: str = LLM_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    timeout: float | None = None,
) -> str:
    """Generate a response using OpenAI GPT-4.1.

    Args:
        system: System prompt with instructions.
        prompt: User prompt with context and question.
        model: OpenAI model to use (default: gpt-4.1).
        max_tokens: Maximum tokens in response.
        temperature: Sampling temperature (0.0 for deterministic).
        timeout: Request timeout in seconds (None for no timeout).

    Returns:
        Generated response text.

    Raises:
        LLMConnectionError: If API call fails or times out.
    """
    log.debug("llm_generate", model=model, prompt_length=len(prompt), timeout=timeout)

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
        )
        content = response.choices[0].message.content
        if content is None:
            raise LLMConnectionError("OpenAI returned empty response")
        return content
    except ValueError:
        # Re-raise ValueError (missing API key)
        raise
    except (APITimeoutError, httpx.TimeoutException) as e:
        log.error("llm_timeout", model=model, timeout=timeout)
        raise LLMConnectionError(f"OpenAI API timeout after {timeout}s") from e
    except Exception as e:
        log.error("llm_generation_failed", model=model, error=str(e))
        raise LLMConnectionError(f"OpenAI API error: {e}") from e


# Legacy compatibility: get_llm returns a simple wrapper
# This maintains backward compatibility with existing query.py code
class _OpenAIWrapper:
    """Simple wrapper for backward compatibility with query.py."""

    def generate(self, system: str, prompt: str) -> str:
        """Generate response using OpenAI."""
        return generate(system=system, prompt=prompt)


def get_llm() -> _OpenAIWrapper:
    """Get the LLM client.

    Returns:
        OpenAI wrapper with generate() method.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    # Validate API key early
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Get your key at https://platform.openai.com/api-keys"
        )
    log.debug("initializing_llm", source="openai", model=LLM_MODEL)
    return _OpenAIWrapper()
