"""Thin, provider-agnostic LLM client (OpenAI-compatible & Ollama)."""

import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


# Exceptions and config

class LLMClientError(Exception):
    """Raised when the LLM request fails after all retries."""


@dataclass
class LLMClientConfig:
    """Connection parameters for a single LLM endpoint."""

    api_url: str
    auth_token: str
    default_model: str
    provider: str = "openai"
    timeout_seconds: int = 600
    verify_tls: bool = True
    max_retries: int = 3


# Client

class LLMClient:
    """Send chat-completion requests with automatic retry & back-off."""

    def __init__(self, config: LLMClientConfig):
        self.config = config

    def is_configured(self) -> bool:
        """Return *True* when the minimum required env vars are present."""
        if self.config.provider.lower() == "ollama":
            return bool(self.config.api_url and self.config.default_model)
        return bool(self.config.api_url and self.config.auth_token and self.config.default_model)

    #  Public API                                         
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
        headers, payload = self._build_request(
            selected_model, messages, max_tokens, temperature,
            frequency_penalty, presence_penalty,
        )

        last_error: Optional[str] = None

        for attempt in range(self.config.max_retries):
            try:
                content, usage = self._call(headers, payload)
                if content and content.strip():
                    return content, usage
                last_error = "LLM returned empty content."
            except _RetryableError as exc:
                last_error = str(exc)

            if attempt < self.config.max_retries - 1:
                wait = (2 ** attempt) + random.uniform(1, 3)
                time.sleep(wait)

        raise LLMClientError(last_error or "Failed to call LLM API.")
    
    #  Internals                                      
    def _build_request(self, model, messages, max_tokens, temperature,
                       frequency_penalty, presence_penalty):
        """Return *(headers, payload)* for the configured provider."""
        is_ollama = self.config.provider.lower() == "ollama"

        headers = {"Content-Type": "application/json"}
        if not is_ollama and self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        if is_ollama:
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            }
        else:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty,
            }

        return headers, payload

    def _call(self, headers, payload):
        """Execute one HTTP round-trip; raise *_RetryableError* on failure."""
        try:
            resp = requests.post(
                self.config.api_url,
                headers=headers,
                json=payload,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_tls,
            )
        except requests.exceptions.Timeout:
            raise _RetryableError("Request timeout while calling LLM API.")
        except requests.exceptions.ConnectionError as exc:
            raise _RetryableError(f"Connection error: {exc}")
        except Exception as exc:
            raise _RetryableError(f"Unexpected LLM API error: {exc}")

        if resp.status_code != 200:
            raise _RetryableError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()

        if self.config.provider.lower() == "ollama":
            content = data.get("message", {}).get("content", "")
            eval_count = data.get("eval_count")
            usage = {"total_tokens": eval_count} if eval_count is not None else {}
        else:
            choices = data.get("choices", [])
            if not choices:
                raise _RetryableError("No choices returned by LLM API.")
            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})

        return content, usage


class _RetryableError(Exception):
    """Internal sentinel — not exposed outside this module."""


# Helpers

def env_bool(name: str, default: bool = True) -> bool:
    """Read a boolean from the environment (supports 1/true/yes/y/on)."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
