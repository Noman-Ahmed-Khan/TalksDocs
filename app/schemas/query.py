"""Query-related Pydantic schemas."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Represents a citation to a source document chunk."""
    
    chunk_id: str = Field(..., description="Unique identifier for the chunk")
    document_id: Optional[str] = Field(None, description="Parent document ID")
    source_file: str = Field(default="unknown", description="Source filename")
    page: Optional[int] = Field(None, description="Page number (if applicable)")
    char_start: Optional[int] = Field(None, description="Character start position")
    char_end: Optional[int] = Field(None, description="Character end position")
    text_snippet: Optional[str] = Field(
        None, 
        description="Preview of the cited text"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "abc123",
                "document_id": "doc456",
                "source_file": "report.pdf",
                "page": 5,
                "char_start": 1000,
                "char_end": 2000,
                "text_snippet": "The quarterly results show..."
            }
        }


class QueryRequest(BaseModel):
    """Request schema for document queries."""
    
    question: str = Field(
        ..., 
        min_length=1, 
        max_length=2000,
        description="The question to ask"
    )
    document_ids: Optional[List[str]] = Field(
        None,
        description="Filter to specific documents"
    )
    include_all_sources: bool = Field(
        default=False,
        description="Include all retrieved sources in citations"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the key findings in the report?",
                "document_ids": None,
                "include_all_sources": False
            }
        }


class QueryResponse(BaseModel):
    """Response schema for document queries."""
    
    answer: str = Field(..., description="The generated answer")
    citations: List[Citation] = Field(
        default_factory=list,
        description="Citations for the answer"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "The key findings include... [abc123]",
                "citations": [
                    {
                        "chunk_id": "abc123",
                        "document_id": "doc456",
                        "source_file": "report.pdf",
                        "page": 5
                    }
                ],
                "metadata": {
                    "retrieval_strategy": "mmr",
                    "documents_retrieved": 5
                }
            }
        }