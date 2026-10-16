from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.models.search import SearchRequest, SearchResponse
from app.services.indexing import IndexingResources, get_indexing_resources
from app.services.search_service import search_documents

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse, responses={
    409: {"description": "Incompatible collection"},
    503: {"description": "Embedding or Qdrant dependency failure"},
})
async def search(request: SearchRequest,
                 resources: Annotated[IndexingResources, Depends(get_indexing_resources)]) -> SearchResponse:
    return await run_in_threadpool(search_documents, request, resources)
