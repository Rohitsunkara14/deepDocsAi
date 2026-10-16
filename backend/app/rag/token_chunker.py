import re
from typing import Any
from uuid import uuid4

from app.core.errors import IndexingError
from app.models.document import DocumentChunk, ParsedDocument
from app.rag.chunker import clean_text


def split_token_text(text: str, tokenizer: Any, chunk_size: int, overlap: int,
                     model_max_tokens: int) -> list[str]:
    special = tokenizer.num_special_tokens_to_add(pair=False)
    if chunk_size < 1 or not 0 <= overlap < chunk_size or chunk_size + special > model_max_tokens:
        raise IndexingError("Token chunk size/overlap is incompatible with the embedding model input budget.", 409)
    if not tokenizer.is_fast:
        raise IndexingError("Token chunking requires a fast tokenizer with character offsets.", 409)
    text = clean_text(text)
    if not text:
        return []
    offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                        truncation=False, verbose=False)["offset_mapping"]
    if not offsets:
        raise IndexingError("The embedding tokenizer produced no usable tokens for this text.", 409)
    chunks: list[str] = []
    seen: set[str] = set()
    start = 0
    while start < len(offsets):
        end = min(start + chunk_size, len(offsets))
        left = offsets[start][0]
        if end < len(offsets):
            window = text[left:offsets[end][0]]
            minimum = start + max(chunk_size // 2, overlap + 1)
            for pattern in (r"\n\n", r"\n", r"[.!?](?=\s)", r" "):
                boundaries = [left + match.end() for match in re.finditer(pattern, window)]
                candidates = [index for index in range(minimum, end + 1)
                              if any(offsets[index - 1][1] <= boundary <= offsets[index][0]
                                     for boundary in boundaries)]
                if candidates:
                    end = candidates[-1]
                    break
        # Re-tokenization protects against WordPiece boundary effects on substrings.
        while end > start:
            chunk = text[left:offsets[end - 1][1]].strip()
            count = len(tokenizer(chunk, add_special_tokens=False, truncation=False)["input_ids"])
            if count <= chunk_size:
                break
            end -= 1
        if end <= start or (end < len(offsets) and end - start <= overlap):
            raise IndexingError("Token chunking cannot make progress with this overlap; reduce TOKEN_CHUNK_OVERLAP.", 409)
        if chunk and chunk not in seen:
            chunks.append(chunk)
            seen.add(chunk)
        if end == len(offsets):
            break
        start = end - overlap
    return chunks


def chunk_document_tokens(document: ParsedDocument, tokenizer: Any, chunk_size: int,
                          overlap: int, model_max_tokens: int) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for page in document.pages:
        for text in split_token_text(page.text, tokenizer, chunk_size, overlap, model_max_tokens):
            chunks.append(DocumentChunk(chunk_id=str(uuid4()), text=text,
                source_filename=document.filename, page_number=page.page_number, chunk_index=len(chunks)))
    return chunks
