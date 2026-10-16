import re
from uuid import uuid4

from app.models.document import DocumentChunk, ParsedDocument


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= chunk_overlap < chunk_size")
    text = clean_text(text)
    chunks: list[str] = []
    seen: set[str] = set()
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Search the latter half to avoid tiny chunks; always advance past overlap.
            minimum = max(chunk_size // 2, chunk_overlap + 1)
            window = text[start:end]
            for pattern in (r"\n\n", r"\n", r"[.!?](?=\s)", r" "):
                boundaries = [match.end() for match in re.finditer(pattern, window)
                              if match.end() >= minimum]
                if boundaries:
                    end = start + boundaries[-1]
                    break
        chunk = text[start:end].strip()
        if chunk and chunk not in seen:
            chunks.append(chunk)
            seen.add(chunk)
        if end == len(text):
            break
        start = end - chunk_overlap
    return chunks


def chunk_document(document: ParsedDocument, chunk_size: int,
                   chunk_overlap: int) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    # Never cross pages: each chunk keeps one unambiguous citation source.
    for page in document.pages:
        for text in split_text(page.text, chunk_size, chunk_overlap):
            chunks.append(DocumentChunk(chunk_id=str(uuid4()), text=text,
                source_filename=document.filename, page_number=page.page_number,
                chunk_index=len(chunks)))
    return chunks
