import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_health() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "deepdocs-ai"}


@pytest.mark.parametrize("origin, allowed", [
    ("https://portfolio.example", True),
    ("https://untrusted.example", False),
])
def test_cors(origin: str, allowed: bool) -> None:
    settings = Settings(_env_file=None, cors_origins=["https://portfolio.example"])
    with TestClient(create_app(settings)) as client:
        response = client.options("/health", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        })
    assert response.status_code == (200 if allowed else 400)
    assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)


def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "DeepDocs Test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", '["https://portfolio.example"]')
    settings = Settings(_env_file=None)
    assert settings.app_name == "DeepDocs Test"
    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.cors_origins == ["https://portfolio.example"]


def test_wildcard_cors_is_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcards are not allowed"):
        Settings(_env_file=None, cors_origins=["*"])
