"""Document chunking with multiple strategies and offset tracking."""

import uuid
import logging
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from dataclasses import dataclass

from langchain_core.documents import Document

from .config import ChunkerConfig, ChunkingStrategy
from .normalizers import TextNormalizer
from .exceptions import ChunkingError


logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""
    chunk_id: str
    document_id: str
    char_start: int
    char_end: int
    chunk_index: int
    total_chunks: int
    page: Optional[int] = None
    source: Optional[str] = None


class BaseChunker(ABC):
    """Abstract base class for chunking strategies."""
    
    def __init__(self, config: ChunkerConfig):
        self.config = config
    
    @abstractmethod
    def chunk_text(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Split text into chunks with offset tracking.
        
        Returns:
            List of tuples: (chunk_text, start_offset, end_offset)
        """
        pass
    
    def split_documents(
        self,
        documents: List[Document],
        document_id: str
    ) -> List[Document]:
        """Split multiple documents into chunks with metadata."""
        all_chunks = []
        
        for doc in documents:
            try:
                chunks = self._process_document(doc, document_id)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"Error chunking document: {e}")
                raise ChunkingError(
                    f"Failed to chunk document",
                    details={"document_id": document_id, "error": str(e)}
                )
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(documents)} documents")
        return all_chunks
    
    def _process_document(
        self,
        doc: Document,
        document_id: str
    ) -> List[Document]:
        """Process a single document into chunks."""
        text = doc.page_content
        
        if not text or not text.strip():
            logger.warning(f"Empty document content for document_id: {document_id}")
            return []
        
        # Normalize text before chunking
        normalized_text = TextNormalizer.normalize(text, normalize_whitespace=True)
        
        # Get chunks with offsets
        text_chunks = self.chunk_text(normalized_text)
        total_chunks = len(text_chunks)
        
        chunks = []
        for idx, (chunk_text, start, end) in enumerate(text_chunks):
            # Skip chunks that are too small
            if len(chunk_text.strip()) < self.config.min_chunk_size:
                continue
            
            chunk_metadata = ChunkMetadata(
                chunk_id=str(uuid.uuid4()),
                document_id=document_id,
                char_start=start,
                char_end=end,
                chunk_index=idx,
                total_chunks=total_chunks,
                page=doc.metadata.get('page'),
                source=doc.metadata.get('source')
            )
            
            chunk_doc = Document(
                page_content=chunk_text,
                metadata={
                    **doc.metadata,
                    **vars(chunk_metadata)
                }
            )
            chunks.append(chunk_doc)
        
        return chunks


class FixedSizeChunker(BaseChunker):
    """Fixed-size chunking with overlap."""
    
    def chunk_text(self, text: str) -> List[Tuple[str, int, int]]:
        chunks = []
        text_length = len(text)
        start = 0
        
        while start < text_length:
            end = min(start + self.config.chunk_size, text_length)
            chunk_text = text[start:end]
            chunks.append((chunk_text, start, end))
            
            # Move start position considering overlap
            start += self.config.chunk_size - self.config.chunk_overlap
            
            # Prevent infinite loop
            if start >= text_length:
                break
        
        return chunks


class RecursiveChunker(BaseChunker):
    """Recursive text splitting that respects natural boundaries."""
    
    def chunk_text(self, text: str) -> List[Tuple[str, int, int]]:
        return self._split_recursive(text, 0, self.config.separators)
    
    def _split_recursive(
        self,
        text: str,
        offset: int,
        separators: List[str]
    ) -> List[Tuple[str, int, int]]:
        """Recursively split text using separators."""
        if len(text) <= self.config.chunk_size:
            return [(text, offset, offset + len(text))]
        
        # Find the best separator to use
        separator = self._find_separator(text, separators)
        
        if separator == "":
            # No separator found, fall back to fixed size
            return self._split_fixed(text, offset)
        
        # Split by separator
        chunks = []
        current_chunk = ""
        current_start = offset
        
        parts = text.split(separator)
        
        for i, part in enumerate(parts):
            # Add separator back except for the last part
            part_with_sep = part + separator if i < len(parts) - 1 else part
            
            if len(current_chunk) + len(part_with_sep) <= self.config.chunk_size:
                current_chunk += part_with_sep
            else:
                if current_chunk:
                    chunks.append((
                        current_chunk.strip(),
                        current_start,
                        current_start + len(current_chunk)
                    ))
                
                # Handle overlap
                if self.config.chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-self.config.chunk_overlap:]
                    current_chunk = overlap_text + part_with_sep
                    current_start = current_start + len(current_chunk) - len(overlap_text) - len(part_with_sep)
                else:
                    current_chunk = part_with_sep
                    current_start = current_start + len(current_chunk) - len(part_with_sep)
        
        if current_chunk.strip():
            chunks.append((
                current_chunk.strip(),
                current_start,
                current_start + len(current_chunk)
            ))
        
        return chunks
    
    def _find_separator(self, text: str, separators: List[str]) -> str:
        """Find the best separator present in the text."""
        for sep in separators:
            if sep in text:
                return sep
        return ""
    
    def _split_fixed(
        self,
        text: str,
        offset: int
    ) -> List[Tuple[str, int, int]]:
        """Fallback to fixed-size splitting."""
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.config.chunk_size, len(text))
            chunks.append((text[start:end], offset + start, offset + end))
            start += self.config.chunk_size - self.config.chunk_overlap
        
        return chunks


class SentenceChunker(BaseChunker):
    """Sentence-aware chunking."""
    
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')
    
    def chunk_text(self, text: str) -> List[Tuple[str, int, int]]:
        import re
        sentences = self.SENTENCE_ENDINGS.split(text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        running_offset = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk) + len(sentence) + 1 <= self.config.chunk_size:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                    current_start = running_offset
            else:
                if current_chunk:
                    chunks.append((
                        current_chunk,
                        current_start,
                        current_start + len(current_chunk)
                    ))
                current_chunk = sentence
                current_start = running_offset
            
            running_offset += len(sentence) + 1
        
        if current_chunk:
            chunks.append((
                current_chunk,
                current_start,
                current_start + len(current_chunk)
            ))
        
        return chunks


class Chunker(RecursiveChunker):
    """Default chunker implementation using recursive splitting."""
    def __init__(self, config: Optional[ChunkerConfig] = None):
        super().__init__(config or ChunkerConfig())


class ChunkerFactory:
    """Factory for creating chunker instances."""
    
    _chunkers = {
        ChunkingStrategy.FIXED_SIZE: FixedSizeChunker,
        ChunkingStrategy.RECURSIVE: RecursiveChunker,
        ChunkingStrategy.SENTENCE: SentenceChunker,
    }
    
    @classmethod
    def create(cls, config: Optional[ChunkerConfig] = None) -> BaseChunker:
        """Create a chunker based on configuration."""
        config = config or ChunkerConfig()
        
        chunker_class = cls._chunkers.get(config.strategy, RecursiveChunker)
        return chunker_class(config)


# Convenience function for backward compatibility
def create_chunker(
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
) -> BaseChunker:
    """Create a chunker with specified parameters."""
    config = ChunkerConfig(
        strategy=strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return ChunkerFactory.create(config)