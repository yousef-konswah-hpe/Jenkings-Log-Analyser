"""Thin LLM client backed by the OpenAI SDK (GitHub Copilot compatible)."""

import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError


# Exceptions and config

class LLMClientError(Exception):
    """Raised when the LLM request fails after all retries."""


@dataclass
class LLMClientConfig:
    """Connection parameters for the OpenAI-compatible endpoint."""

    api_url: str          # base URL, e.g. https://api.githubcopilot.com
    auth_token: str       # GitHub token or OpenAI API key
    default_model: str
    provider: str = "copilot"   # informational only
    timeout_seconds: int = 600
    verify_tls: bool = True     # kept for API compatibility; SDK always verifies
    max_retries: int = 3


# Client

class LLMClient:
    """Send chat-completion requests via the OpenAI SDK with retry & back-off."""

    def __init__(self, config: LLMClientConfig):
        self.config = config
        self._openai: Optional[OpenAI] = None

    def _client(self) -> OpenAI:
        """Lazily initialise the OpenAI SDK client."""
        if self._openai is None:
            self._openai = OpenAI(
                api_key=self.config.auth_token,
                base_url=self.config.api_url or None,
                timeout=float(self.config.timeout_seconds),
                max_retries=0,   # we handle retries ourselves
            )
        return self._openai

    def is_configured(self) -> bool:
        """Return *True* when the minimum required env vars are present."""
        return bool(self.config.auth_token and self.config.default_model)

    # Public API
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        model: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Send a chat-completion request and return *(content, usage_dict)*.

        Raises:
            LLMClientError: after all retries are exhausted.
        """
        if not self.is_configured():
            raise LLMClientError("LLM client is not configured. Check environment variables.")

        selected_model = model or self.config.default_model
        last_error: Optional[str] = None

        for attempt in range(self.config.max_retries):
            try:
                response = self._client().chat.completions.create(
                    model=selected_model,
                    messages=messages,  # type: ignore[arg-type]
                    max_tokens=max_tokens,
                    temperature=temperature,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                )
                content = response.choices[0].message.content or ""
                if content.strip():
                    usage = {}
                    if response.usage:
                        usage = {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                        }
                    return content, usage
                last_error = "LLM returned empty content."
            except APITimeoutError:
                last_error = "Request timeout while calling LLM API."
            except APIConnectionError as exc:
                last_error = f"Connection error: {exc}"
            except APIStatusError as exc:
                last_error = f"HTTP {exc.status_code}: {str(exc.message)[:300]}"
            except Exception as exc:
                last_error = f"Unexpected LLM API error: {exc}"

            if attempt < self.config.max_retries - 1:
                wait = (2 ** attempt) + random.uniform(1, 3)
                time.sleep(wait)

        raise LLMClientError(last_error or "Failed to call LLM API.")


# Helpers

def env_bool(name: str, default: bool = True) -> bool:
    """Read a boolean from the environment (supports 1/true/yes/y/on)."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
