from typing import List
from langchain_core.documents import Document
import uuid

class Chunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_documents(self, documents: List[Document], document_id: str) -> List[Document]:
        chunks = []
        for doc in documents:
            text = doc.page_content
            # Simple chunking that tracks offsets
            # In a production system, we'd use a more sophisticated splitter
            # that yields offsets. For now, we'll implement a basic one.
            
            start = 0
            while start < len(text):
                end = start + self.chunk_size
                chunk_text = text[start:end]
                
                chunk_doc = Document(
                    page_content=chunk_text,
                    metadata={
                        **doc.metadata,
                        "chunk_id": str(uuid.uuid4()),
                        "document_id": document_id,
                        "char_start": start,
                        "char_end": min(end, len(text))
                    }
                )
                chunks.append(chunk_doc)
                start += (self.chunk_size - self.chunk_overlap)
                
        return chunks
