"""Custom exceptions for the RAG pipeline."""

from typing import Optional


class RAGException(Exception):
    """Base exception for RAG pipeline errors."""
    
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DocumentLoadError(RAGException):
    """Raised when document loading fails."""
    pass


class ChunkingError(RAGException):
    """Raised when document chunking fails."""
    pass


class EmbeddingError(RAGException):
    """Raised when embedding generation fails."""
    pass


class VectorStoreError(RAGException):
    """Raised when vector store operations fail."""
    pass


class QueryError(RAGException):
    """Raised when query processing fails."""
    pass


class UnsupportedFileTypeError(DocumentLoadError):
    """Raised when file type is not supported."""
    pass