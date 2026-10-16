from math import isfinite

from qdrant_client import QdrantClient, models

from app.core.errors import IndexingError
from app.models.document import DocumentChunk
from app.models.search import SearchResult


class QdrantVectorStore:
    def __init__(self, client: QdrantClient, collection_name: str) -> None:
        self.client = client
        self.collection_name = collection_name

    def ensure_collection(self, dimension: int) -> None:
        try:
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(self.collection_name,
                    vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE))
            config = self.client.get_collection(self.collection_name).config.params.vectors
            if not isinstance(config, models.VectorParams) or config.size != dimension or config.distance != models.Distance.COSINE:
                raise IndexingError("Qdrant collection dimension or distance does not match the embedding model. Use a new collection and re-ingest; existing data was not deleted.", 409)
        except IndexingError:
            raise
        except Exception as exc:
            raise IndexingError("Qdrant collection is unavailable. Check QDRANT_URL and the Qdrant service.") from exc

    @staticmethod
    def validate_vectors(vectors: list[list[float]], count: int, dimension: int) -> None:
        if len(vectors) != count or any(len(v) != dimension or not all(isfinite(x) for x in v) for v in vectors):
            raise IndexingError("Embedding dimension mismatch or invalid vector values.", 409)

    def upsert(self, chunks: list[DocumentChunk], vectors: list[list[float]],
               document_id: str, dimension: int) -> None:
        self.validate_vectors(vectors, len(chunks), dimension)
        points = [models.PointStruct(id=chunk.chunk_id, vector=vector,
            payload={**chunk.model_dump(), "document_id": document_id})
            for chunk, vector in zip(chunks, vectors, strict=True)]
        try:
            self.client.upsert(self.collection_name, points=points, wait=True)
        except Exception as exc:
            raise IndexingError("Qdrant write failed. The document may be partially indexed; retry the same upload.") from exc

    def remove_stale_chunks(self, document_id: str, chunk_count: int) -> None:
        # IDs use sequential indexes, so a shorter re-ingestion must remove the old tail.
        try:
            self.client.delete(self.collection_name, points_selector=models.FilterSelector(
                filter=models.Filter(must=[
                    models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)),
                    models.FieldCondition(key="chunk_index", range=models.Range(gte=chunk_count)),
                ])), wait=True)
        except Exception as exc:
            raise IndexingError("Qdrant indexing cleanup failed. Retry the same upload to finish indexing.") from exc

    def search(self, vector: list[float], top_k: int, document_id: str | None,
               dimension: int) -> list[SearchResult]:
        self.validate_vectors([vector], 1, dimension)
        query_filter = None
        if document_id is not None:
            query_filter = models.Filter(must=[models.FieldCondition(
                key="document_id", match=models.MatchValue(value=document_id))])
        try:
            hits = self.client.query_points(self.collection_name, query=vector,
                query_filter=query_filter, limit=top_k, with_payload=True, with_vectors=False).points
            return [SearchResult(**(hit.payload or {}), score=hit.score) for hit in hits]
        except Exception as exc:
            raise IndexingError("Qdrant search failed. Check the service and collection payload schema.") from exc

    def list_chunks(self) -> list[SearchResult]:
        try:
            if not self.client.collection_exists(self.collection_name):
                return []
            chunks: list[SearchResult] = []
            offset = None
            while True:
                points, offset = self.client.scroll(self.collection_name, limit=256,
                    offset=offset, with_payload=True, with_vectors=False)
                chunks.extend(SearchResult(**(point.payload or {}), score=0.0) for point in points)
                if offset is None:
                    return chunks
        except Exception as exc:
            raise IndexingError("Chunk corpus is unavailable for lexical retrieval. Check Qdrant.") from exc

    def check_ready(self) -> None:
        """Read collection metadata only; never create collections or load models."""
        self.client.get_collection(self.collection_name)

    def close(self) -> None:
        self.client.close()
