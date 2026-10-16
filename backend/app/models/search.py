from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20, strict=True)
    document_id: UUID | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must not be empty")
        return value


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    source_filename: str
    page_number: int | None
    chunk_index: int
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
