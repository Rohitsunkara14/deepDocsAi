from threading import RLock

from fastapi import Request
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.rag.embeddings import Embedder, SentenceTransformerEmbedder
from app.rag.bm25 import BM25Retriever
from app.rag.reranker import CrossEncoderReranker, Reranker
from app.rag.retrieval import Retriever
from app.rag.vector_store import QdrantVectorStore


class IndexingResources:
    """One application-owned model/client; serialize local ingestion and search."""

    def __init__(self, embedder: Embedder, store: QdrantVectorStore, settings: Settings | None = None,
                 reranker: Reranker | None = None) -> None:
        self.embedder = embedder
        self.store = store
        self.lock = RLock()
        self.settings = settings if settings is not None else Settings(_env_file=None)
        self.bm25 = BM25Retriever(store.list_chunks)
        self.reranker = reranker if reranker is not None else CrossEncoderReranker(
            self.settings.reranker_model_name, self.settings.reranker_batch_size)
        self.retriever = Retriever(embedder, store, self.bm25, self.reranker, self.settings)

    def close(self) -> None:
        self.store.close()


def create_resources(settings: Settings) -> IndexingResources:
    client = (QdrantClient(path=settings.qdrant_local_path) if settings.qdrant_local_path
              else QdrantClient(url=settings.qdrant_url, timeout=10, check_compatibility=False,
                                api_key=(settings.qdrant_api_key.get_secret_value().strip() or None)
                                if settings.qdrant_api_key else None, follow_redirects=False))
    return IndexingResources(
        SentenceTransformerEmbedder(settings.embedding_model_name, settings.embedding_batch_size),
        QdrantVectorStore(client, settings.qdrant_collection_name), settings)


def get_indexing_resources(request: Request) -> IndexingResources:
    return request.app.state.indexing
