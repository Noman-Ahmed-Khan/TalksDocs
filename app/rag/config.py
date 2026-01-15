"""Configuration for RAG pipeline components."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""
    FIXED_SIZE = "fixed_size"
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"


class RetrievalStrategy(str, Enum):
    """Available retrieval strategies."""
    SIMILARITY = "similarity"
    MMR = "mmr"  # Maximal Marginal Relevance
    HYBRID = "hybrid"


@dataclass
class ChunkerConfig:
    """Configuration for document chunking."""
    strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE
    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 100
    separators: List[str] = field(default_factory=lambda: [
        "\n\n\n",
        "\n\n",
        "\n",
        ". ",
        "! ",
        "? ",
        "; ",
        ", ",
        " ",
        ""
    ])
    preserve_paragraphs: bool = True


@dataclass
class RetrieverConfig:
    """Configuration for document retrieval."""
    strategy: RetrievalStrategy = RetrievalStrategy.MMR
    top_k: int = 5
    score_threshold: float = 0.5
    mmr_diversity: float = 0.3  # Lambda for MMR
    rerank_enabled: bool = True
    max_rerank_candidates: int = 20


@dataclass
class QueryConfig:
    """Configuration for query processing."""
    temperature: float = 0.0
    max_tokens: int = 2048
    include_sources: bool = True
    citation_required: bool = True
    fallback_response: str = "I don't have enough information in the provided documents to answer this question."


@dataclass
class RAGConfig:
    """Master configuration for RAG pipeline."""
    chunker: ChunkerConfig = field(default_factory=ChunkerConfig)
    retriever: RetrieverConfig = field(default_factory=RetrieverConfig)
    query: QueryConfig = field(default_factory=QueryConfig)