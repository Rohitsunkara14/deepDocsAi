from pathlib import PurePosixPath
from hashlib import sha256
from uuid import UUID, uuid5, NAMESPACE_URL

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.services.indexing import IndexingResources
from app.models.document import IngestionResponse
from app.rag.chunker import chunk_document
from app.rag.token_chunker import chunk_document_tokens
from app.core.errors import IndexingError
from app.rag.parser import DocumentParseError, parse_document


class DocumentProcessingError(ValueError):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def process_document(data: bytes, filename: str, content_type: str,
                     settings: Settings, resources: IndexingResources) -> IngestionResponse:
    try:
        document = parse_document(data, filename, content_type)
    except DocumentParseError as exc:
        raise DocumentProcessingError(422, str(exc)) from exc
    if settings.chunking_strategy == "token":
        if not hasattr(resources.embedder, "tokenization_config"):
            raise IndexingError("Configured embedder does not support token-aware chunking.", 409)
        tokenizer, limit = resources.embedder.tokenization_config()
        chunks = chunk_document_tokens(document, tokenizer, settings.token_chunk_size,
                                       settings.token_chunk_overlap, limit)
    else:
        chunks = chunk_document(document, settings.chunk_size, settings.chunk_overlap)
    document_id = str(uuid5(NAMESPACE_URL, filename + ":" + sha256(data).hexdigest()))
    for chunk in chunks:
        chunk.chunk_id = str(uuid5(UUID(document_id), str(chunk.chunk_index)))
    with resources.lock:
        dimension = resources.embedder.dimension
        resources.store.ensure_collection(dimension)
        try:
            for start in range(0, len(chunks), settings.embedding_batch_size):
                batch = chunks[start:start + settings.embedding_batch_size]
                vectors = resources.embedder.embed_texts([chunk.text for chunk in batch])
                resources.store.upsert(batch, vectors, document_id, dimension)
            resources.store.remove_stale_chunks(document_id, len(chunks))
        finally:
            resources.bm25.invalidate()

    return IngestionResponse(document_id=document_id, filename=filename, content_type=content_type,
        page_count=document.page_count, chunk_count=len(chunks), indexed_chunk_count=len(chunks))



async def process_upload(file: UploadFile, settings: Settings, resources: IndexingResources) -> IngestionResponse:
    try:
        filename = PurePosixPath((file.filename or "").replace("\\", "/")).name
        types = {"application/pdf": ".pdf", "text/plain": ".txt"}
        content_type = file.content_type or ""
        if content_type not in types or PurePosixPath(filename).suffix.lower() != types[content_type]:
            raise DocumentProcessingError(415, "Upload a .pdf (application/pdf) or .txt (text/plain) file.")
        limit = settings.max_upload_size_mb * 1024 * 1024
        if file.size is not None and file.size > limit:
            raise DocumentProcessingError(413, "File exceeds MAX_UPLOAD_SIZE_MB.")
        data = bytearray()
        while block := await file.read(min(65536, limit + 1 - len(data))):
            data.extend(block)
            if len(data) > limit:
                raise DocumentProcessingError(413, "File exceeds MAX_UPLOAD_SIZE_MB.")
        if not data:
            raise DocumentProcessingError(400, "The uploaded file is empty.")
        return await run_in_threadpool(process_document, bytes(data), filename, content_type, settings, resources)
    finally:
        await file.close()
