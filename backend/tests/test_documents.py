import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client(resources):
    with TestClient(create_app(Settings(_env_file=None, max_upload_size_mb=1,
                                       chunk_size=80, chunk_overlap=10), resources=resources)) as client:
        yield client


def test_txt_upload(client: TestClient) -> None:
    response = client.post("/documents/upload", files={"file": ("notes.txt", b"Useful notes.", "text/plain")})
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "notes.txt"
    assert data["content_type"] == "text/plain"
    assert data["page_count"] is None
    assert data["chunk_count"] == 1
    assert data["indexed_chunk_count"] == 1
    assert "chunks" not in data
    assert data["document_id"]


@pytest.mark.parametrize("name, mime, content, status", [
    ("a.png", "image/png", b"image", 415),
    ("a.exe", "text/plain", b"text", 415),
    ("a.pdf", "text/plain", b"text", 415),
    ("a.txt", "text/plain", b"", 400),
    ("a.txt", "text/plain", b" \n", 422),
    ("a.txt", "text/plain", b"\xff", 422),
    ("a.pdf", "application/pdf", b"%PDF-1.7 broken", 422),
    ("a.txt", "text/plain", b"x" * (1024 * 1024 + 1), 413),
    ("a.txt", "text/plain", b"x" * (2 * 1024 * 1024), 413),
])
def test_errors(client: TestClient, name: str, mime: str, content: bytes, status: int) -> None:
    response = client.post("/documents/upload", files={"file": (name, content, mime)})
    assert response.status_code == status
    assert "Traceback" not in response.text


def test_exact_limit(client: TestClient) -> None:
    response = client.post("/documents/upload", files={"file": ("a.txt", b"x" * (1024*1024), "text/plain")})
    assert response.status_code == 200


def test_pdf_upload(client: TestClient, pdf_bytes: bytes) -> None:
    response = client.post("/documents/upload", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})
    assert response.status_code == 200
    assert response.json()["page_count"] == 3
    assert response.json()["indexed_chunk_count"] == 2
    search = client.post("/search", json={"query": "evidence", "document_id": response.json()["document_id"]})
    assert sorted(c["page_number"] for c in search.json()["results"]) == [1, 3]


def test_swagger(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    operation = client.get("/openapi.json").json()["paths"]["/documents/upload"]["post"]
    assert "multipart/form-data" in operation["requestBody"]["content"]


def test_missing_file(client: TestClient) -> None:
    assert client.post("/documents/upload").status_code == 422


def test_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "300")
    monkeypatch.setenv("CHUNK_OVERLAP", "50")
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "2")
    config = Settings(_env_file=None)
    assert (config.chunk_size, config.chunk_overlap, config.max_upload_size_mb) == (300, 50, 2)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chunk_size=10, chunk_overlap=10)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_upload_size_mb=0)


def test_streamed_oversize_without_content_length(client: TestClient) -> None:
    def body():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="a.txt"\r\nContent-Type: text/plain\r\n\r\n'
        for _ in range(20):
            yield b"x" * 65536
        yield b"\r\n--boundary--\r\n"
    response = client.post("/documents/upload", content=body(),
                           headers={"Content-Type": "multipart/form-data; boundary=boundary"})
    assert response.status_code == 413


def test_upload_cors(client: TestClient) -> None:
    response = client.options("/documents/upload", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200
