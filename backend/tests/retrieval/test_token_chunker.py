import re

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import IndexingError
from app.models.document import ParsedDocument, ParsedPage
from app.rag.token_chunker import split_token_text, chunk_document_tokens


class FakeTokenizer:
    is_fast = True

    def num_special_tokens_to_add(self, pair=False):
        return 2

    def __call__(self, text, **kwargs):
        offsets = [match.span() for match in re.finditer(r"\w+|[^\w\s]", text)]
        return {"input_ids": list(range(len(offsets))), "offset_mapping": offsets}


def test_token_limits_and_overlap() -> None:
    tokenizer = FakeTokenizer()
    text = "zero one two three four five six seven eight nine ten eleven"
    chunks = split_token_text(text, tokenizer, 5, 2, 8)
    assert all(len(tokenizer(chunk)["input_ids"]) <= 5 for chunk in chunks)
    assert all(left.split()[-2:] == right.split()[:2] for left, right in zip(chunks, chunks[1:]))
    assert chunks[0].split() + [word for chunk in chunks[1:] for word in chunk.split()[2:]] == text.split()


def test_character_count_is_not_token_count() -> None:
    chunks = split_token_text("extraordinarily lengthy terminology", FakeTokenizer(), 3, 1, 5)
    assert len(chunks) == 1
    assert len(chunks[0]) > 3


def test_paragraph_boundaries() -> None:
    chunks = split_token_text("one two three\n\nfour five six seven eight nine ten", FakeTokenizer(), 6, 1, 10)
    assert chunks[0] == "one two three"


@pytest.mark.parametrize("text", ["", " \n\t"])
def test_empty(text) -> None:
    assert split_token_text(text, FakeTokenizer(), 5, 1, 8) == []


@pytest.mark.parametrize("size, overlap, limit", [(5, 5, 10), (5, -1, 10), (5, 1, 6), (0, 0, 10)])
def test_invalid_budget(size, overlap, limit) -> None:
    with pytest.raises(IndexingError):
        split_token_text("some text", FakeTokenizer(), size, overlap, limit)


def test_page_metadata_and_blank_page() -> None:
    doc = ParsedDocument(filename="paper.pdf", content_type="application/pdf", page_count=3,
        pages=[ParsedPage(page_number=1, text="one two three four five six"),
               ParsedPage(page_number=2, text=" "), ParsedPage(page_number=3, text="seven eight")])
    chunks = chunk_document_tokens(doc, FakeTokenizer(), 4, 1, 8)
    assert [chunk.page_number for chunk in chunks] == [1, 1, 3]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.source_filename == "paper.pdf" for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == 3


def test_configuration_validation() -> None:
    assert Settings(_env_file=None).chunking_strategy == "character"
    with pytest.raises(ValidationError):
        Settings(_env_file=None, token_chunk_size=10, token_chunk_overlap=10)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, retrieval_strategy="unknown")
