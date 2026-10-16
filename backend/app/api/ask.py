from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.documents import get_settings
from app.core.config import Settings
from app.models.rag import AskRequest, AskResponse
from app.rag.llm import LLM
from app.services.indexing import IndexingResources, get_indexing_resources
from app.services.rag_service import ask_question

router = APIRouter(tags=["rag"])


def get_llm(request: Request) -> LLM:
    return request.app.state.llm


@router.post("/ask", response_model=AskResponse, responses={
    409: {"description": "Incompatible Qdrant collection"},
    503: {"description": "LLM, embedding, or Qdrant dependency unavailable"},
})
async def ask(request: AskRequest,
              settings: Annotated[Settings, Depends(get_settings)],
              resources: Annotated[IndexingResources, Depends(get_indexing_resources)],
              llm: Annotated[LLM, Depends(get_llm)]) -> AskResponse:
    return await ask_question(request, settings, resources, llm)
