from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=20, strict=True)
    document_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be empty")
        return value


class Citation(BaseModel):
    source_number: int = Field(ge=1)
    chunk_id: str
    document_id: str
    source_filename: str
    page_number: int | None
    chunk_index: int


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
