"""Document loading and ingestion pipeline."""

import os
import logging
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional, Type
from abc import ABC, abstractmethod

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    TextLoader,
    BSHTMLLoader
)

from .exceptions import DocumentLoadError, UnsupportedFileTypeError
from .normalizers import TextNormalizer, MetadataNormalizer


logger = logging.getLogger(__name__)


class DocumentProcessor(ABC):
    """Abstract base for document processors."""
    
    @abstractmethod
    def load(self, file_path: str) -> List[Document]:
        """Load documents from file."""
        pass
    
    @abstractmethod
    def supports(self, extension: str) -> bool:
        """Check if processor supports file extension."""
        pass


class PDFProcessor(DocumentProcessor):
    """PDF document processor."""
    
    EXTENSIONS = {'.pdf'}
    
    def supports(self, extension: str) -> bool:
        return extension.lower() in self.EXTENSIONS
    
    def load(self, file_path: str) -> List[Document]:
        loader = PyPDFLoader(file_path)
        return loader.load()


class WordProcessor(DocumentProcessor):
    """Word document processor."""
    
    EXTENSIONS = {'.docx', '.doc'}
    
    def supports(self, extension: str) -> bool:
        return extension.lower() in self.EXTENSIONS
    
    def load(self, file_path: str) -> List[Document]:
        loader = UnstructuredWordDocumentLoader(file_path)
        return loader.load()


class PowerPointProcessor(DocumentProcessor):
    """PowerPoint document processor."""
    
    EXTENSIONS = {'.pptx', '.ppt'}
    
    def supports(self, extension: str) -> bool:
        return extension.lower() in self.EXTENSIONS
    
    def load(self, file_path: str) -> List[Document]:
        loader = UnstructuredPowerPointLoader(file_path)
        return loader.load()


class ExcelProcessor(DocumentProcessor):
    """Excel document processor."""
    
    EXTENSIONS = {'.xlsx', '.xls'}
    
    def supports(self, extension: str) -> bool:
        return extension.lower() in self.EXTENSIONS
    
    def load(self, file_path: str) -> List[Document]:
        loader = UnstructuredExcelLoader(file_path)
        return loader.load()


class TextProcessor(DocumentProcessor):
    """Plain text and Markdown processor."""
    
    EXTENSIONS = {'.txt', '.md', '.markdown', '.rst'}
    
    def supports(self, extension: str) -> bool:
        return extension.lower() in self.EXTENSIONS
    
    def load(self, file_path: str) -> List[Document]:
        loader = TextLoader(file_path, encoding='utf-8')
        return loader.load()


class HTMLProcessor(DocumentProcessor):
    """HTML document processor."""
    
    EXTENSIONS = {'.html', '.htm'}
    
    def supports(self, extension: str) -> bool:
        return extension.lower() in self.EXTENSIONS
    
    def load(self, file_path: str) -> List[Document]:
        loader = BSHTMLLoader(file_path)
        return loader.load()


class DocumentLoader:
    """
    Main document loader with support for multiple file types.
    
    Uses a registry of processors for extensibility.
    """
    
    # Default processors
    DEFAULT_PROCESSORS: List[DocumentProcessor] = [
        PDFProcessor(),
        WordProcessor(),
        PowerPointProcessor(),
        ExcelProcessor(),
        TextProcessor(),
        HTMLProcessor(),
    ]
    
    def __init__(
        self,
        processors: Optional[List[DocumentProcessor]] = None,
        normalize_text: bool = True,
        normalize_metadata: bool = True
    ):
        self.processors = processors or self.DEFAULT_PROCESSORS
        self.normalize_text = normalize_text
        self.normalize_metadata = normalize_metadata
        
        # Build extension mapping
        self._extension_map: Dict[str, DocumentProcessor] = {}
        for processor in self.processors:
            for ext in getattr(processor, 'EXTENSIONS', set()):
                self._extension_map[ext] = processor
    
    def get_supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return list(self._extension_map.keys())
    
    def is_supported(self, file_path: str) -> bool:
        """Check if file type is supported."""
        ext = Path(file_path).suffix.lower()
        return ext in self._extension_map
    
    def _get_processor(self, file_path: str) -> DocumentProcessor:
        """Get appropriate processor for file."""
        ext = Path(file_path).suffix.lower()
        
        if ext not in self._extension_map:
            raise UnsupportedFileTypeError(
                f"Unsupported file type: {ext}",
                details={
                    "file_path": file_path,
                    "supported": self.get_supported_extensions()
                }
            )
        
        return self._extension_map[ext]
    
    def _validate_file(self, file_path: str) -> None:
        """Validate file exists and is readable."""
        path = Path(file_path)
        
        if not path.exists():
            raise DocumentLoadError(
                f"File not found: {file_path}",
                details={"file_path": file_path}
            )
        
        if not path.is_file():
            raise DocumentLoadError(
                f"Path is not a file: {file_path}",
                details={"file_path": file_path}
            )
        
        if not os.access(file_path, os.R_OK):
            raise DocumentLoadError(
                f"File is not readable: {file_path}",
                details={"file_path": file_path}
            )
    
    def _enrich_metadata(
        self,
        documents: List[Document],
        file_path: str
    ) -> List[Document]:
        """Enrich document metadata with file information."""
        path = Path(file_path)
        file_stats = path.stat()
        
        base_metadata = {
            "source": str(path),
            "source_file": path.name,
            "file_extension": path.suffix.lower(),
            "file_size_bytes": file_stats.st_size,
        }
        
        for doc in documents:
            doc.metadata.update(base_metadata)
            
            if self.normalize_metadata:
                doc.metadata = MetadataNormalizer.normalize_metadata(doc.metadata)
        
        return documents
    
    def _normalize_documents(self, documents: List[Document]) -> List[Document]:
        """Normalize document content."""
        if not self.normalize_text:
            return documents
        
        for doc in documents:
            doc.page_content = TextNormalizer.normalize(
                doc.page_content,
                normalize_unicode=True,
                remove_control_chars=True,
                normalize_whitespace=True
            )
        
        return documents
    
    def load(self, file_path: str) -> List[Document]:
        """
        Load documents from file with full processing.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            List of processed Document objects
            
        Raises:
            DocumentLoadError: If loading fails
            UnsupportedFileTypeError: If file type is not supported
        """
        logger.info(f"Loading document: {file_path}")
        
        # Validate file
        self._validate_file(file_path)
        
        # Get processor
        processor = self._get_processor(file_path)
        
        try:
            # Load documents
            documents = processor.load(file_path)
            
            if not documents:
                logger.warning(f"No content extracted from: {file_path}")
                return []
            
            # Enrich metadata
            documents = self._enrich_metadata(documents, file_path)
            
            # Normalize content
            documents = self._normalize_documents(documents)
            
            # Filter empty documents
            documents = [
                doc for doc in documents
                if doc.page_content and doc.page_content.strip()
            ]
            
            logger.info(f"Loaded {len(documents)} pages/sections from {file_path}")
            return documents
            
        except UnsupportedFileTypeError:
            raise
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
            raise DocumentLoadError(
                f"Failed to load document: {str(e)}",
                details={"file_path": file_path, "error": str(e)}
            )


# Module-level convenience functions
_loader: Optional[DocumentLoader] = None


def get_document_loader() -> DocumentLoader:
    """Get or create document loader singleton."""
    global _loader
    if _loader is None:
        _loader = DocumentLoader()
    return _loader


def load_document(file_path: str) -> List[Document]:
    """Convenience function to load a document."""
    return get_document_loader().load(file_path)