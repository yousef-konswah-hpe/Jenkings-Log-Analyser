import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


class LLMClientError(Exception):
    pass


@dataclass
class LLMClientConfig:
    api_url: str
    auth_token: str
    default_model: str
    provider: str = "openai"
    timeout_seconds: int = 600
    verify_tls: bool = True
    max_retries: int = 3


class LLMClient:
    def __init__(self, config: LLMClientConfig):
        self.config = config

    def is_configured(self) -> bool:
        if self.config.provider.lower() == "ollama":
            return bool(self.config.api_url and self.config.default_model)
        return bool(self.config.api_url and self.config.auth_token and self.config.default_model)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        model: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        if not self.is_configured():
            raise LLMClientError("LLM client is not configured. Check environment variables.")

        selected_model = model or self.config.default_model
        provider = self.config.provider.lower()

        if provider == "ollama":
            payload: Dict[str, Any] = {
                "model": selected_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                },
            }
            headers = {
                "Content-Type": "application/json",
            }
        else:
            payload = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty,
            }
            headers = {
                "Content-Type": "application/json",
            }
            if self.config.auth_token:
                headers["Authorization"] = f"Bearer {self.config.auth_token}"

        last_error: Optional[str] = None

        for attempt in range(self.config.max_retries):
            try:
                response = requests.post(
                    self.config.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout_seconds,
                    verify=self.config.verify_tls,
                )

                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                else:
                    response_json = response.json()

                    if provider == "ollama":
                        message = response_json.get("message", {})
                        content = message.get("content", "")
                        if content and content.strip():
                            usage = response_json.get("eval_count")
                            usage_payload = {"total_tokens": usage} if usage is not None else {}
                            return content, usage_payload
                        last_error = "Ollama returned empty content."
                    else:
                        choices = response_json.get("choices", [])
                        if not choices:
                            last_error = "No choices returned by LLM API."
                        else:
                            message = choices[0].get("message", {})
                            content = message.get("content", "")
                            if content and content.strip():
                                return content, response_json.get("usage", {})
                            last_error = "LLM returned empty content."

            except requests.exceptions.Timeout:
                last_error = "Request timeout while calling LLM API."
            except requests.exceptions.ConnectionError as exc:
                last_error = f"Connection error while calling LLM API: {exc}"
            except Exception as exc:
                last_error = f"Unexpected LLM API error: {exc}"

            if attempt < self.config.max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                time.sleep(wait_time)

        raise LLMClientError(last_error or "Failed to call LLM API.")


def env_bool(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
