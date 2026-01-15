"""Advanced document retrieval with multiple strategies."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass

from langchain_core.documents import Document

from .config import RetrieverConfig, RetrievalStrategy
from .vectorstore import get_vectorstore, get_vectorstore_manager
from .embeddings import get_embedding_service
from .exceptions import RAGException


logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Container for retrieval results."""
    documents: List[Document]
    scores: List[float]
    query: str
    strategy: RetrievalStrategy
    metadata: Dict[str, Any]


class BaseRetriever(ABC):
    """Abstract base for retriever implementations."""
    
    def __init__(self, project_id: str, config: RetrieverConfig):
        self.project_id = project_id
        self.config = config
        self.vectorstore = get_vectorstore(project_id)
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """Retrieve relevant documents."""
        pass
    
    def _apply_score_threshold(
        self,
        docs_and_scores: List[Tuple[Document, float]]
    ) -> List[Tuple[Document, float]]:
        """Filter results by score threshold."""
        return [
            (doc, score) for doc, score in docs_and_scores
            if score >= self.config.score_threshold
        ]


class SimilarityRetriever(BaseRetriever):
    """Standard similarity search retriever."""
    
    async def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """Retrieve documents using similarity search."""
        try:
            docs_and_scores = self.vectorstore.similarity_search_with_score(
                query,
                k=self.config.top_k,
                filter=filters
            )
            
            # Apply score threshold
            docs_and_scores = self._apply_score_threshold(docs_and_scores)
            
            documents = [doc for doc, _ in docs_and_scores]
            scores = [score for _, score in docs_and_scores]
            
            return RetrievalResult(
                documents=documents,
                scores=scores,
                query=query,
                strategy=RetrievalStrategy.SIMILARITY,
                metadata={"filter": filters}
            )
            
        except Exception as e:
            logger.error(f"Similarity retrieval failed: {e}")
            raise RAGException(
                "Retrieval failed",
                details={"error": str(e)}
            )


class MMRRetriever(BaseRetriever):
    """Maximal Marginal Relevance retriever for diverse results."""
    
    async def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """Retrieve documents using MMR."""
        try:
            documents = self.vectorstore.max_marginal_relevance_search(
                query,
                k=self.config.top_k,
                fetch_k=self.config.max_rerank_candidates,
                lambda_mult=self.config.mmr_diversity,
                filter=filters
            )
            
            # MMR doesn't return scores, estimate based on position
            scores = [1.0 - (i * 0.1) for i in range(len(documents))]
            
            return RetrievalResult(
                documents=documents,
                scores=scores,
                query=query,
                strategy=RetrievalStrategy.MMR,
                metadata={
                    "filter": filters,
                    "lambda_mult": self.config.mmr_diversity
                }
            )
            
        except Exception as e:
            logger.error(f"MMR retrieval failed: {e}")
            raise RAGException(
                "MMR retrieval failed",
                details={"error": str(e)}
            )


class HybridRetriever(BaseRetriever):
    """Hybrid retriever combining multiple strategies."""
    
    def __init__(self, project_id: str, config: RetrieverConfig):
        super().__init__(project_id, config)
        self.similarity_retriever = SimilarityRetriever(project_id, config)
        self.mmr_retriever = MMRRetriever(project_id, config)
    
    async def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """Retrieve using hybrid approach."""
        try:
            # Get results from both strategies
            similarity_result = await self.similarity_retriever.retrieve(query, filters)
            mmr_result = await self.mmr_retriever.retrieve(query, filters)
            
            # Merge and deduplicate
            seen_ids = set()
            merged_docs = []
            merged_scores = []
            
            # Interleave results
            for i in range(max(len(similarity_result.documents), len(mmr_result.documents))):
                # Add from similarity
                if i < len(similarity_result.documents):
                    doc = similarity_result.documents[i]
                    chunk_id = doc.metadata.get('chunk_id')
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        merged_docs.append(doc)
                        merged_scores.append(similarity_result.scores[i])
                
                # Add from MMR
                if i < len(mmr_result.documents):
                    doc = mmr_result.documents[i]
                    chunk_id = doc.metadata.get('chunk_id')
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        merged_docs.append(doc)
                        merged_scores.append(mmr_result.scores[i])
            
            # Limit to top_k
            merged_docs = merged_docs[:self.config.top_k]
            merged_scores = merged_scores[:self.config.top_k]
            
            return RetrievalResult(
                documents=merged_docs,
                scores=merged_scores,
                query=query,
                strategy=RetrievalStrategy.HYBRID,
                metadata={"filter": filters}
            )
            
        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            raise RAGException(
                "Hybrid retrieval failed",
                details={"error": str(e)}
            )


class DocumentRetriever:
    """
    Main retriever interface with reranking support.
    
    Factory for creating and using different retrieval strategies.
    """
    
    _strategy_map = {
        RetrievalStrategy.SIMILARITY: SimilarityRetriever,
        RetrievalStrategy.MMR: MMRRetriever,
        RetrievalStrategy.HYBRID: HybridRetriever,
    }
    
    def __init__(
        self,
        project_id: str,
        config: Optional[RetrieverConfig] = None
    ):
        self.project_id = project_id
        self.config = config or RetrieverConfig()
        
        retriever_class = self._strategy_map.get(
            self.config.strategy,
            MMRRetriever
        )
        self._retriever = retriever_class(project_id, self.config)
    
    async def retrieve(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        **kwargs
    ) -> RetrievalResult:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: The search query
            document_ids: Optional list of document IDs to filter by
            **kwargs: Additional arguments
            
        Returns:
            RetrievalResult with documents and metadata
        """
        # Build filters
        filters = {}
        if document_ids:
            filters["document_id"] = {"$in": document_ids}
        
        # Perform retrieval
        result = await self._retriever.retrieve(query, filters)
        
        logger.info(
            f"Retrieved {len(result.documents)} documents for query "
            f"using {result.strategy.value} strategy"
        )
        
        return result
    
    async def retrieve_with_context(
        self,
        query: str,
        **kwargs
    ) -> Tuple[List[Document], str]:
        """
        Retrieve documents and format as context string.
        
        Returns:
            Tuple of (documents, formatted_context)
        """
        result = await self.retrieve(query, **kwargs)
        
        context_parts = []
        for doc in result.documents:
            chunk_id = doc.metadata.get('chunk_id', 'unknown')
            context_parts.append(f"[ID: {chunk_id}]\n{doc.page_content}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        return result.documents, context


def create_retriever(
    project_id: str,
    strategy: RetrievalStrategy = RetrievalStrategy.MMR,
    top_k: int = 5,
    **kwargs
) -> DocumentRetriever:
    """Factory function to create a retriever."""
    config = RetrieverConfig(
        strategy=strategy,
        top_k=top_k,
        **kwargs
    )
    return DocumentRetriever(project_id, config)