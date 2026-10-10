"""Errors raised by the ingestion side."""

from pathlib import Path


class IngestionError(Exception):
    """Ingestion must stop (spec 01 "fail loudly").

    The message always names the offending file or folder.
    """

    def __init__(self, path: Path | str, reason: str):
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"{self.path}: {reason}")


class RetrievalError(Exception):
    """open_retrieval() startup check failed (spec 03, "fail loudly")."""
