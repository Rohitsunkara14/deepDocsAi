from io import BytesIO

from pypdf import PdfReader

from app.models.document import ParsedDocument, ParsedPage


class DocumentParseError(ValueError):
    """A document cannot be converted to usable text."""


def parse_document(data: bytes, filename: str, content_type: str) -> ParsedDocument:
    if not data:
        raise DocumentParseError("The uploaded file is empty.")
    if content_type == "text/plain":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentParseError("TXT files must contain valid UTF-8 text.") from exc
        pages = [ParsedPage(text=text)]
        page_count = None
    elif content_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentParseError("The file is not a valid PDF.")
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise DocumentParseError("Encrypted PDFs are not supported.")
            pages = [ParsedPage(page_number=i, text=page.extract_text() or "")
                     for i, page in enumerate(reader.pages, start=1)]
            page_count = len(pages)
        except DocumentParseError:
            raise
        except Exception as exc:
            # Third-party parsers can raise several errors for malformed objects.
            raise DocumentParseError("The PDF is corrupt or could not be parsed.") from exc
    else:
        raise DocumentParseError("Unsupported document content type.")
    if not any(page.text.strip() for page in pages):
        message = ("The PDF has no extractable text; scanned PDFs require OCR."
                   if content_type == "application/pdf" else "The document contains no text.")
        raise DocumentParseError(message)
    return ParsedDocument(filename=filename, content_type=content_type,
                          page_count=page_count, pages=pages)
