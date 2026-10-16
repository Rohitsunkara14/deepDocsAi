class IndexingError(RuntimeError):
    """An expected indexing dependency or configuration failure, safe for clients."""

    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMError(RuntimeError):
    """A client-safe generation configuration, provider, or output failure."""
