import json
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings
from app.core.errors import LLMError


class LLM(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str) -> str: ...


class OpenAICompatibleLLM:
    """Chat Completions adapter; credentials are checked only when generating."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.client = client

    def _configuration(self) -> tuple[str, str]:
        config = self.settings
        if config.llm_provider != "openai_compatible" or not config.llm_model.strip():
            raise LLMError("LLM generation is not configured. Set LLM_PROVIDER and LLM_MODEL.")
        key = config.llm_api_key.get_secret_value().strip() if config.llm_api_key else ""
        if not key:
            raise LLMError("LLM generation is not configured. Set LLM_API_KEY.")
        try:
            url = urlsplit(config.llm_base_url)
            valid = (url.scheme in {"http", "https"} and bool(url.hostname)
                     and not url.username and not url.password and not url.query and not url.fragment)
        except ValueError:
            valid = False
        if not valid:
            raise LLMError("LLM_BASE_URL must be a valid HTTP(S) API base URL without credentials or query parameters.")
        return config.llm_base_url.rstrip("/") + "/chat/completions", key

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        url, key = self._configuration()
        try:
            # Never follow redirects with a credential-bearing request or retry paid calls.
            async with self.client.stream("POST", url,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": self.settings.llm_model,
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user", "content": user_prompt}],
                      "temperature": self.settings.llm_temperature,
                      "max_completion_tokens": self.settings.llm_max_output_tokens,
                      "stream": False},
                timeout=self.settings.llm_timeout_seconds, follow_redirects=False) as response:
                if response.status_code in {401, 403}:
                    raise LLMError("LLM authentication failed. Check the configured API key and model access.")
                if response.status_code >= 300:
                    raise LLMError("LLM provider request failed. Check provider availability and model configuration.")
                body = bytearray()
                async for block in response.aiter_bytes():
                    body.extend(block)
                    if len(body) > 1_048_576:
                        raise LLMError("LLM provider returned an oversized response.")
            payload = json.loads(body)
            choice = payload["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
                raise LLMError("LLM provider returned an incomplete or malformed response.")
            return content.strip()
        except LLMError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMError("LLM request timed out. Try again later.") from exc
        except httpx.HTTPError as exc:
            raise LLMError("LLM provider is unavailable. Try again later.") from exc
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise LLMError("LLM provider returned a malformed response.") from exc
