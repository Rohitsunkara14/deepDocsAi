import pytest

from app.rag.chunker import chunk_document, clean_text, split_text
from app.rag.parser import parse_document


@pytest.mark.parametrize("text, expected", [("", []), (" \n\t", []), ("Hello.", ["Hello."])])
def test_short_empty(text: str, expected: list[str]) -> None:
    assert split_text(text, 20, 5) == expected


def test_cleaning() -> None:
    assert clean_text(" A  word.\r\n\r\n\r\n B\tword. ") == "A word.\n\nB word."


def test_paragraph_preference() -> None:
    first = "First paragraph is here."
    chunks = split_text(first + "\n\nSecond paragraph is long enough to split.", 40, 5)
    assert chunks[0] == first


def test_overlap_and_reconstruction() -> None:
    text = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    chunks = split_text(text, 20, 5)
    assert all(len(c) <= 20 for c in chunks)
    assert all(a[-5:] == b[:5] for a, b in zip(chunks, chunks[1:]))
    assert chunks[0] + "".join(c[5:] for c in chunks[1:]) == text


@pytest.mark.parametrize("length", [19, 20, 21, 40, 1000])
def test_boundaries(length: int) -> None:
    text = "".join(chr(0x400+i) for i in range(length))
    chunks = split_text(text, 20, 5)
    assert all(0 < len(c) <= 20 for c in chunks)
    assert len(chunks) == len(set(chunks))


def test_repetitions_deduplicated() -> None:
    assert split_text("x" * 100, 20, 5) == ["x" * 20, "x" * 10]


@pytest.mark.parametrize("size, overlap", [(0, 0), (10, 10), (10, -1), (10, 11)])
def test_invalid_configuration(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        split_text("abc", size, overlap)


def test_page_metadata(pdf_bytes: bytes) -> None:
    document = parse_document(pdf_bytes, "report.pdf", "application/pdf")
    chunks = chunk_document(document, 100, 10)
    assert [c.page_number for c in chunks] == [1, 3]
    assert [c.chunk_index for c in chunks] == [0, 1]
    assert all(c.source_filename == "report.pdf" for c in chunks)
    assert len({c.chunk_id for c in chunks}) == 2
