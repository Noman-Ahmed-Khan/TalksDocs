"""Vector store management with Pinecone."""

import logging
from typing import List, Dict, Any, Optional
from functools import lru_cache

from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_core.documents import Document
from tenacity import retry, stop_after_attempt, wait_exponential

from app.settings import settings
from .embeddings import get_embeddings, get_embedding_service
from .exceptions import VectorStoreError


logger = logging.getLogger(__name__)


class VectorStoreManager:
    """
    Manages Pinecone vector store operations.
    
    Handles connection pooling, namespace management, and CRUD operations.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None
    ):
        self.api_key = api_key or settings.PINECONE_API_KEY
        self.index_name = index_name or settings.PINECONE_INDEX_NAME
        self._client: Optional[Pinecone] = None
        self._index = None
        self._vectorstores: Dict[str, PineconeVectorStore] = {}
    
    @property
    def client(self) -> Pinecone:
        """Lazy initialization of Pinecone client."""
        if self._client is None:
            self._client = Pinecone(api_key=self.api_key)
        return self._client
    
    @property
    def index(self):
        """Get or create index connection."""
        if self._index is None:
            self._index = self.client.Index(self.index_name)
        return self._index
    
    def get_vectorstore(self, namespace: str) -> PineconeVectorStore:
        """
        Get or create a vector store for a namespace (project).
        
        Args:
            namespace: The namespace (typically project_id)
            
        Returns:
            PineconeVectorStore instance
        """
        if namespace not in self._vectorstores:
            embeddings = get_embeddings()
            
            self._vectorstores[namespace] = PineconeVectorStore(
                index=self.index,
                embedding=embeddings,
                text_key="text",
                namespace=namespace
            )
            logger.debug(f"Created vectorstore for namespace: {namespace}")
        
        return self._vectorstores[namespace]
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def add_documents(
        self,
        documents: List[Document],
        namespace: str
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of documents to add
            namespace: Target namespace
            
        Returns:
            List of document IDs
        """
        try:
            if not documents:
                logger.warning("No documents to add")
                return []
            
            vectorstore = self.get_vectorstore(namespace)
            
            # Extract IDs from metadata
            ids = [doc.metadata.get('chunk_id') for doc in documents]
            
            # Add documents
            added_ids = vectorstore.add_documents(
                documents=documents,
                ids=ids
            )
            
            logger.info(f"Added {len(added_ids)} documents to namespace: {namespace}")
            return added_ids
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise VectorStoreError(
                "Failed to add documents to vector store",
                details={"namespace": namespace, "error": str(e)}
            )
    
    def delete_by_document_id(
        self,
        document_id: str,
        namespace: str
    ) -> bool:
        """
        Delete all chunks for a document.
        
        Args:
            document_id: The document ID to delete chunks for
            namespace: The namespace
            
        Returns:
            True if successful
        """
        try:
            # Query for all chunks with this document_id
            # Then delete by IDs
            self.index.delete(
                filter={"document_id": document_id},
                namespace=namespace
            )
            logger.info(f"Deleted chunks for document: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document chunks: {e}")
            raise VectorStoreError(
                "Failed to delete document chunks",
                details={"document_id": document_id, "error": str(e)}
            )
    
    def delete_namespace(self, namespace: str) -> bool:
        """Delete all vectors in a namespace."""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            
            # Clear cached vectorstore
            if namespace in self._vectorstores:
                del self._vectorstores[namespace]
            
            logger.info(f"Deleted namespace: {namespace}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete namespace: {e}")
            raise VectorStoreError(
                "Failed to delete namespace",
                details={"namespace": namespace, "error": str(e)}
            )
    
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get index statistics."""
        try:
            stats = self.index.describe_index_stats()
            
            if namespace:
                return {
                    "namespace": namespace,
                    "vector_count": stats.namespaces.get(namespace, {}).get('vector_count', 0)
                }
            
            return {
                "total_vector_count": stats.total_vector_count,
                "namespaces": dict(stats.namespaces)
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            raise VectorStoreError(
                "Failed to get index stats",
                details={"error": str(e)}
            )


# Module-level singleton
_manager: Optional[VectorStoreManager] = None


def get_vectorstore_manager() -> VectorStoreManager:
    """Get or create vector store manager singleton."""
    global _manager
    if _manager is None:
        _manager = VectorStoreManager()
    return _manager


def get_vectorstore(project_id: str) -> PineconeVectorStore:
    """
    Get vectorstore for a project.
    
    Maintains backward compatibility.
    """
    return get_vectorstore_manager().get_vectorstore(project_id)