import pytest

from app.rag.parser import DocumentParseError, parse_document
from tests.conftest import make_pdf


def test_txt() -> None:
    result = parse_document(b"\xef\xbb\xbfHello \xc3\xa9", "notes.txt", "text/plain")
    assert result.pages[0].text == "Hello é"
    assert result.page_count is None
    assert result.pages[0].page_number is None


@pytest.mark.parametrize("data, mime, message", [
    (b"", "text/plain", "empty"),
    (b" \n", "text/plain", "no text"),
    (b"\xff", "text/plain", "UTF-8"),
    (b"garbage", "application/pdf", "valid PDF"),
    (b"%PDF-1.7 broken", "application/pdf", "corrupt"),
    (b"x", "image/png", "Unsupported"),
])
def test_invalid(data: bytes, mime: str, message: str) -> None:
    with pytest.raises(DocumentParseError, match=message):
        parse_document(data, "file", mime)


def test_pdf_pages(pdf_bytes: bytes) -> None:
    document = parse_document(pdf_bytes, "report.pdf", "application/pdf")
    assert document.page_count == 3
    assert [p.page_number for p in document.pages] == [1, 2, 3]
    assert "First page" in document.pages[0].text
    assert "Third page" in document.pages[2].text


@pytest.mark.parametrize("data, message", [
    (make_pdf([""]), "no extractable text"),
    (make_pdf(["Secret"], encrypted=True), "Encrypted"),
])
def test_unreadable_pdf(data: bytes, message: str) -> None:
    with pytest.raises(DocumentParseError, match=message):
        parse_document(data, "file.pdf", "application/pdf")
