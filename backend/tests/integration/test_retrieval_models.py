"""Explicit opt-in coverage of the actual tokenizer and CPU cross encoder."""
import os

import pytest

from app.core.config import Settings
from app.models.search import SearchResult
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.reranker import CrossEncoderReranker
from app.rag.token_chunker import split_token_text

pytestmark = pytest.mark.skipif(os.getenv("RUN_RETRIEVAL_MODELS") != "1",
    reason="Opt-in real retrieval models; ordinary tests never download models")


def test_real_token_budget() -> None:
    settings = Settings(_env_file=None)
    embedder = SentenceTransformerEmbedder(settings.embedding_model_name)
    tokenizer, limit = embedder.tokenization_config()
    chunks = split_token_text(("Uncharacteristically complex terminology improves testing.\n\n"
                              "Revenue increased in international markets. ") * 100,
                              tokenizer, 200, 32, limit)
    assert len(chunks) > 1
    assert all(len(tokenizer(chunk, truncation=False)["input_ids"]) <= 202 <= limit
               for chunk in chunks)


def test_real_cross_encoder() -> None:
    reranker = CrossEncoderReranker(Settings(_env_file=None).reranker_model_name)
    candidates = [SearchResult(chunk_id=str(index), document_id="document",
        text=text, source_filename="fixture.txt", page_number=None, chunk_index=index, score=0)
        for index, text in enumerate(["Cats like sleeping.", "Revenue grew by twenty percent."])]
    results = reranker.rerank("How much did revenue grow?", candidates, 2)
    assert results[0].chunk_id == "1"
    assert {item.chunk_id for item in results} == {"0", "1"}
    # Exercise the singleton inference shape as well.
    assert reranker.rerank("revenue growth", [candidates[1]], 1)[0].chunk_id == "1"
