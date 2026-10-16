from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_pdf(texts: list[str], encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
            DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("secret")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def pdf_bytes() -> bytes:
    return make_pdf(["First page evidence.", "", "Third page evidence."])


from qdrant_client import QdrantClient
from app.rag.vector_store import QdrantVectorStore
from app.services.indexing import IndexingResources


class FakeEmbedder:
    dimension = 3

    def __init__(self) -> None:
        self.batches: list[int] = []

    def embed_text(self, text: str) -> list[float]:
        lower = text.lower()
        return [float("revenue" in lower or "sales" in lower),
                float("cat" in lower or "pet" in lower), 0.1]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(len(texts))
        return [self.embed_text(t) for t in texts]


@pytest.fixture
def resources():
    resource = IndexingResources(FakeEmbedder(),
        QdrantVectorStore(QdrantClient(":memory:"), "test_chunks"))
    yield resource
    resource.close()
