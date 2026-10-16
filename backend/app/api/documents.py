from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.config import Settings
from app.services.indexing import IndexingResources, get_indexing_resources
from app.models.document import IngestionResponse
from app.services.document_service import DocumentProcessingError, process_upload

router = APIRouter(prefix="/documents", tags=["documents"])


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


@router.post("/upload", response_model=IngestionResponse, responses={
    409: {"description": "Incompatible collection"},
    503: {"description": "Embedding or Qdrant dependency failure"},
    400: {"description": "Empty file"},
    413: {"description": "Upload too large"},
    415: {"description": "Unsupported file type or extension"},
    422: {"description": "Invalid document or missing file"},
})
async def upload_document(file: Annotated[UploadFile, File()],
                          settings: Annotated[Settings, Depends(get_settings)],
                          resources: Annotated[IndexingResources, Depends(get_indexing_resources)]) -> IngestionResponse:
    try:
        return await process_upload(file, settings, resources)
    except DocumentProcessingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
