from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from pydantic import SecretStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    app_name: str = Field(default="deepdocs-ai", min_length=1)
    app_env: str = "development"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173"])

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_origins(cls, origins: list[str]) -> list[str]:
        if any("*" in origin for origin in origins):
            raise ValueError("CORS origins must be explicit; wildcards are not allowed")
        return origins

    max_upload_size_mb: int = Field(default=10, ge=1)
    chunk_size: int = Field(default=1000, ge=1)
    chunk_overlap: int = Field(default=150, ge=0)

    @model_validator(mode="after")
    def validate_chunk_overlap(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be less than CHUNK_SIZE")
        return self

    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", min_length=1)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection_name: str = Field(default="deepdocs_chunks", min_length=1)
    qdrant_local_path: str | None = None

    # LLM strings may be unset: health, ingestion and search must still work.
    llm_provider: str = "openai_compatible"
    llm_model: str = ""
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_temperature: float = Field(default=0.1, ge=0, le=2)
    llm_max_output_tokens: int = Field(default=800, ge=1, le=8192)
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    rag_top_k_default: int = Field(default=5, ge=1, le=20)
    rag_max_context_chars: int = Field(default=12000, ge=256, le=100000)

    chunking_strategy: Literal["character", "token"] = "character"
    token_chunk_size: int = Field(default=200, ge=1)
    token_chunk_overlap: int = Field(default=32, ge=0)
    retrieval_strategy: Literal["dense", "bm25", "hybrid", "hybrid_rerank"] = "dense"
    retrieval_candidate_count: int = Field(default=20, ge=1, le=200)
    rrf_constant: int = Field(default=60, ge=1)
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    rerank_candidate_count: int = Field(default=20, ge=1, le=200)
    reranker_batch_size: int = Field(default=16, ge=1, le=128)

    @model_validator(mode="after")
    def validate_token_overlap(self) -> "Settings":
        if self.token_chunk_overlap >= self.token_chunk_size:
            raise ValueError("TOKEN_CHUNK_OVERLAP must be less than TOKEN_CHUNK_SIZE")
        return self

    @field_validator("qdrant_url")
    @classmethod
    def validate_qdrant_url(cls, value: str) -> str:
        try:
            url = urlsplit(value)
            valid = (url.scheme in {"http", "https"} and bool(url.hostname)
                     and url.username is None and url.password is None
                     and not url.query and not url.fragment)
            _ = url.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("QDRANT_URL must be HTTP(S) without credentials, query or fragment")
        return value

    @model_validator(mode="after")
    def deployment_safety(self) -> "Settings":
        if self.app_env.lower() == "production" and self.debug:
            raise ValueError("DEBUG must be false in production")
        if self.qdrant_api_key and self.qdrant_api_key.get_secret_value().strip() and not self.qdrant_local_path:
            if urlsplit(self.qdrant_url).scheme != "https":
                raise ValueError("Authenticated external Qdrant requires HTTPS")
        for origin in self.cors_origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment):
                raise ValueError("CORS_ORIGINS must contain exact HTTP(S) origins without paths or credentials")
        return self
