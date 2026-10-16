import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.core.errors import LLMError
from app.rag.llm import OpenAICompatibleLLM


def settings(**kwargs) -> Settings:
    return Settings(_env_file=None, llm_model="test-model", llm_api_key="fake-test-key",
                    llm_base_url="https://provider.example/v1", **kwargs)


def run_provider(config: Settings, handler) -> str:
    async def run() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await OpenAICompatibleLLM(config, client).generate("SYSTEM", "USER")
    return asyncio.run(run())


def test_chat_completion_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://provider.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer fake-test-key"
        payload = json.loads(request.content)
        assert payload["messages"] == [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "USER"}]
        assert payload["temperature"] == .1
        assert payload["max_completion_tokens"] == 800
        assert payload["stream"] is False
        return httpx.Response(200, json={"choices": [{"message": {"content": "Answer [1]"}, "finish_reason": "stop"}]})
    assert run_provider(settings(), handler) == "Answer [1]"


@pytest.mark.parametrize("changes", [
    {"llm_model": ""}, {"llm_api_key": ""}, {"llm_provider": "unsupported"},
    {"llm_base_url": "bad-url"}, {"llm_base_url": "https://key:secret@provider.example/v1"},
    {"llm_base_url": "https://provider.example/v1?api_key=secret"},
])
def test_missing_invalid_config_no_network(changes: dict) -> None:
    config = settings().model_copy(update=changes)
    if isinstance(changes.get("llm_api_key"), str):
        from pydantic import SecretStr
        config = config.model_copy(update={"llm_api_key": SecretStr(changes["llm_api_key"])})
    def handler(request):
        pytest.fail("Invalid configuration must not make a request")
    with pytest.raises(LLMError):
        run_provider(config, handler)


@pytest.mark.parametrize("status", [301, 400, 401, 403, 429, 500, 503])
def test_safe_provider_errors(status: int) -> None:
    with pytest.raises(LLMError) as error:
        run_provider(settings(), lambda _: httpx.Response(status, text="SECRET prompt and API key"))
    assert "SECRET" not in str(error.value)
    assert "fake-test-key" not in str(error.value)


@pytest.mark.parametrize("body", [
    b"invalid JSON", b"{}", b'{"choices":[]}',
    b'{"choices":[{"message":{"content":null},"finish_reason":"stop"}]}',
    b'{"choices":[{"message":{"content":" "},"finish_reason":"stop"}]}',
    b'{"choices":[{"message":{"content":"truncated"},"finish_reason":"length"}]}',
    b'{"choices":[{"message":{"content":12},"finish_reason":"stop"}]}',
])
def test_malformed_output(body: bytes) -> None:
    with pytest.raises(LLMError):
        run_provider(settings(), lambda _: httpx.Response(200, content=body))


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_network_failure(error_type) -> None:
    def handler(request):
        raise error_type("secret details", request=request)
    with pytest.raises(LLMError) as error:
        run_provider(settings(), handler)
    assert "secret details" not in str(error.value)


def test_secret_repr() -> None:
    assert "fake-test-key" not in repr(settings())


def test_oversized_response() -> None:
    with pytest.raises(LLMError, match="oversized"):
        run_provider(settings(), lambda _: httpx.Response(200, content=b"x" * 1_048_577))
