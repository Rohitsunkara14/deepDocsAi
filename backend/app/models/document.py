from pydantic import BaseModel, Field


class ParsedPage(BaseModel):
    page_number: int | None = Field(default=None, ge=1)
    text: str


class ParsedDocument(BaseModel):
    filename: str
    content_type: str
    page_count: int | None = Field(default=None, ge=0)
    pages: list[ParsedPage]


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    source_filename: str
    page_number: int | None
    chunk_index: int = Field(ge=0)


class IngestionResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str
    page_count: int | None
    chunk_count: int
    indexed_chunk_count: int
