"""
Pinecone Vector Store Implementation

This module provides a Pinecone-based vector store for the RAG system.
Pinecone is a managed vector database service that provides high-performance
similarity search without requiring local database infrastructure.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Union
import numpy as np
from dataclasses import asdict

from faq.rag.interfaces.base import VectorStoreInterface, FAQEntry, SimilarityMatch

logger = logging.getLogger(__name__)

# Lazy import Pinecone to avoid memory issues during startup
PINECONE_AVAILABLE = False
_pinecone_client = None
_serverless_spec = None

def _import_pinecone():
    """Lazy import Pinecone modules to avoid startup memory issues."""
    global PINECONE_AVAILABLE, _pinecone_client, _serverless_spec
    
    if _pinecone_client is not None:
        return _pinecone_client, _serverless_spec
    
    try:
        from pinecone import Pinecone, ServerlessSpec
        _pinecone_client = Pinecone
        _serverless_spec = ServerlessSpec
        PINECONE_AVAILABLE = True
        logger.info("Pinecone client imported successfully")
        return _pinecone_client, _serverless_spec
    except ImportError as e:
        logger.warning(f"pinecone-client not available: {e}. Install with: pip install pinecone-client")
        PINECONE_AVAILABLE = False
        return None, None
    except Exception as e:
        logger.error(f"Failed to import Pinecone: {e}")
        PINECONE_AVAILABLE = False
        return None, None

# Check availability without importing
try:
    import importlib.util
    spec = importlib.util.find_spec("pinecone")
    PINECONE_AVAILABLE = spec is not None
except Exception:
    PINECONE_AVAILABLE = False


class PineconeVectorStoreError(Exception):
    """Custom exception for Pinecone vector store errors."""
    pass


class PineconeVectorStore(VectorStoreInterface):
    """
    Pinecone-based vector store implementation.
    
    This implementation uses Pinecone's managed vector database service
    to store and search FAQ embeddings without requiring local database infrastructure.
    """
    
    def __init__(self,
                 api_key: str,
                 index_name: str = "faq-embeddings",
                 environment: str = "us-east-1-aws",
                 vector_dimension: int = 384,
                 metric: str = "cosine",
                 timeout: int = 30,
                 fallback_store: Optional[VectorStoreInterface] = None):
        """
        Initialize Pinecone vector store.
        
        Args:
            api_key: Pinecone API key
            index_name: Name of the Pinecone index
            environment: Pinecone environment (e.g., 'us-east-1-aws')
            vector_dimension: Dimension of vectors to store
            metric: Distance metric ('cosine', 'euclidean', 'dotproduct')
            timeout: Request timeout in seconds
            fallback_store: Optional fallback store for error cases
        """
        # Lazy import Pinecone
        Pinecone, ServerlessSpec = _import_pinecone()
        
        if not PINECONE_AVAILABLE or Pinecone is None:
            raise PineconeVectorStoreError(
                "pinecone-client not available. Install with: pip install pinecone-client"
            )
        
        self.api_key = api_key
        self.index_name = index_name
        self.environment = environment
        self.vector_dimension = vector_dimension
        self.metric = metric
        self.timeout = timeout
        self.fallback_store = fallback_store
        self._Pinecone = Pinecone
        self._ServerlessSpec = ServerlessSpec
        
        # Initialize Pinecone client
        try:
            self.pc = self._Pinecone(api_key=api_key)
            self._initialize_index()
            logger.info(f"Pinecone vector store initialized - Index: {index_name}")
        except Exception as e:
            error_msg = f"Failed to initialize Pinecone: {e}"
            logger.error(error_msg)
            if fallback_store:
                logger.warning("Using fallback store due to Pinecone initialization failure")
                self._use_fallback = True
            else:
                raise PineconeVectorStoreError(error_msg)
    
    def _initialize_index(self):
        """Initialize or connect to Pinecone index."""
        try:
            # Check if index exists
            existing_indexes = [index.name for index in self.pc.list_indexes()]
            
            if self.index_name not in existing_indexes:
                logger.info(f"Creating new Pinecone index: {self.index_name}")
                
                # Create index with serverless spec
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.vector_dimension,
                    metric=self.metric,
                    spec=self._ServerlessSpec(
                        cloud='aws',
                        region=self.environment.split('-')[0] + '-' + self.environment.split('-')[1] + '-' + self.environment.split('-')[2]
                    )
                )
                
                # Wait for index to be ready
                while not self.pc.describe_index(self.index_name).status['ready']:
                    logger.info("Waiting for index to be ready...")
                    time.sleep(1)
            
            # Connect to index
            self.index = self.pc.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")
            
        except Exception as e:
            raise PineconeVectorStoreError(f"Failed to initialize index: {e}")
    
    def store_vectors(self, vectors: List[FAQEntry], document_id: str = None, document_hash: str = None):
        """
        Store FAQ vectors in Pinecone.
        
        Args:
            vectors: List of FAQ entries with embeddings
            document_id: Optional document identifier
            document_hash: Optional document hash for change detection
        """
        if hasattr(self, '_use_fallback') and self.fallback_store:
            return self.fallback_store.store_vectors(vectors, document_id, document_hash)
        
        try:
            # Prepare vectors for Pinecone
            pinecone_vectors = []
            
            for i, faq in enumerate(vectors):
                if faq.embedding is None:
                    logger.warning(f"FAQ entry {i} has no embedding, skipping")
                    continue
                
                # Create unique ID
                vector_id = f"{document_id}_{i}" if document_id else f"faq_{i}_{int(time.time())}"
                
                # Prepare metadata
                metadata = {
                    'question': faq.question[:1000],  # Pinecone has metadata size limits
                    'answer': faq.answer[:1000] if faq.answer else "",
                    'category': faq.category or "general",
                    'document_id': document_id or "unknown",
                    'document_hash': document_hash or "",
                    'confidence': float(faq.confidence) if faq.confidence else 1.0,
                    'timestamp': int(time.time())
                }
                
                pinecone_vectors.append({
                    'id': vector_id,
                    'values': faq.embedding.tolist(),
                    'metadata': metadata
                })
            
            if not pinecone_vectors:
                logger.warning("No valid vectors to store")
                return
            
            # Upsert vectors to Pinecone
            logger.info(f"Storing {len(pinecone_vectors)} vectors in Pinecone")
            self.index.upsert(vectors=pinecone_vectors)
            
            logger.info(f"Successfully stored {len(pinecone_vectors)} vectors")
            
        except Exception as e:
            error_msg = f"Failed to store vectors in Pinecone: {e}"
            logger.error(error_msg)
            if self.fallback_store:
                logger.warning("Using fallback store for vector storage")
                return self.fallback_store.store_vectors(vectors, document_id, document_hash)
            raise PineconeVectorStoreError(error_msg)
    
    def search_similar(self, query_vector: np.ndarray, threshold: float = 0.7, top_k: int = 10) -> List[SimilarityMatch]:
        """
        Search for similar vectors in Pinecone.
        
        Args:
            query_vector: Query embedding vector
            threshold: Minimum similarity threshold
            top_k: Maximum number of results to return
            
        Returns:
            List of similarity matches
        """
        if hasattr(self, '_use_fallback') and self.fallback_store:
            return self.fallback_store.search_similar(query_vector, threshold, top_k)
        
        try:
            # Query Pinecone
            results = self.index.query(
                vector=query_vector.tolist(),
                top_k=top_k,
                include_metadata=True,
                include_values=False
            )
            
            # Convert results to SimilarityMatch objects
            matches = []
            for match in results.matches:
                # Pinecone returns cosine similarity, convert to similarity score
                similarity = float(match.score)
                
                if similarity >= threshold:
                    metadata = match.metadata
                    
                    # Create FAQ entry from metadata
                    faq_entry = FAQEntry(
                        question=metadata.get('question', ''),
                        answer=metadata.get('answer', ''),
                        category=metadata.get('category', 'general'),
                        confidence=metadata.get('confidence', 1.0),
                        embedding=None  # Don't include embedding in results
                    )
                    
                    similarity_match = SimilarityMatch(
                        faq_entry=faq_entry,
                        similarity_score=similarity,
                        match_type="vector_similarity",
                        metadata={
                            'pinecone_id': match.id,
                            'document_id': metadata.get('document_id', ''),
                            'timestamp': metadata.get('timestamp', 0)
                        }
                    )
                    
                    matches.append(similarity_match)
            
            logger.info(f"Found {len(matches)} similar vectors above threshold {threshold}")
            return matches
            
        except Exception as e:
            error_msg = f"Failed to search vectors in Pinecone: {e}"
            logger.error(error_msg)
            if self.fallback_store:
                logger.warning("Using fallback store for vector search")
                return self.fallback_store.search_similar(query_vector, threshold, top_k)
            raise PineconeVectorStoreError(error_msg)
    
    def search_by_ngrams(self, query_ngrams: List[str], threshold: float = 0.9) -> List[SimilarityMatch]:
        """
        Search by n-grams using metadata filtering.
        
        Note: Pinecone doesn't have built-in n-gram search, so this uses text matching
        on stored metadata.
        
        Args:
            query_ngrams: List of n-gram strings
            threshold: Minimum similarity threshold
            
        Returns:
            List of similarity matches
        """
        if hasattr(self, '_use_fallback') and self.fallback_store:
            return self.fallback_store.search_by_ngrams(query_ngrams, threshold)
        
        try:
            # For n-gram search, we'll do a broader vector search and then filter
            # This is a limitation of Pinecone's text search capabilities
            logger.warning("N-gram search in Pinecone is limited - using fallback if available")
            
            if self.fallback_store:
                return self.fallback_store.search_by_ngrams(query_ngrams, threshold)
            
            # Return empty results if no fallback available
            return []
            
        except Exception as e:
            logger.error(f"N-gram search failed: {e}")
            return []
    
    def search_with_filters(self, query_vector: np.ndarray, threshold: float = 0.7, 
                          top_k: int = 10, **filters) -> List[SimilarityMatch]:
        """
        Search with metadata filters.
        
        Args:
            query_vector: Query embedding vector
            threshold: Minimum similarity threshold
            top_k: Maximum number of results
            **filters: Metadata filters (category, document_id, etc.)
            
        Returns:
            List of similarity matches
        """
        if hasattr(self, '_use_fallback') and self.fallback_store:
            return self.fallback_store.search_with_filters(query_vector, threshold, top_k, **filters)
        
        try:
            # Build Pinecone filter
            pinecone_filter = {}
            for key, value in filters.items():
                if key in ['category', 'document_id']:
                    pinecone_filter[key] = {"$eq": value}
            
            # Query with filters
            results = self.index.query(
                vector=query_vector.tolist(),
                top_k=top_k,
                include_metadata=True,
                include_values=False,
                filter=pinecone_filter if pinecone_filter else None
            )
            
            # Convert results (same as search_similar)
            matches = []
            for match in results.matches:
                similarity = float(match.score)
                
                if similarity >= threshold:
                    metadata = match.metadata
                    
                    faq_entry = FAQEntry(
                        question=metadata.get('question', ''),
                        answer=metadata.get('answer', ''),
                        category=metadata.get('category', 'general'),
                        confidence=metadata.get('confidence', 1.0),
                        embedding=None
                    )
                    
                    similarity_match = SimilarityMatch(
                        faq_entry=faq_entry,
                        similarity_score=similarity,
                        match_type="filtered_vector_similarity",
                        metadata={
                            'pinecone_id': match.id,
                            'document_id': metadata.get('document_id', ''),
                            'timestamp': metadata.get('timestamp', 0)
                        }
                    )
                    
                    matches.append(similarity_match)
            
            logger.info(f"Found {len(matches)} filtered results above threshold {threshold}")
            return matches
            
        except Exception as e:
            error_msg = f"Failed to search with filters in Pinecone: {e}"
            logger.error(error_msg)
            if self.fallback_store:
                logger.warning("Using fallback store for filtered search")
                return self.fallback_store.search_with_filters(query_vector, threshold, top_k, **filters)
            raise PineconeVectorStoreError(error_msg)
    
    def clear_all(self) -> bool:
        """
        Clear all vectors from Pinecone index.
        
        Returns:
            True if successful
        """
        if hasattr(self, '_use_fallback') and self.fallback_store:
            return self.fallback_store.clear_all()
        
        try:
            # Delete all vectors by deleting and recreating the index
            logger.warning("Clearing all vectors by recreating Pinecone index")
            
            # Delete existing index
            self.pc.delete_index(self.index_name)
            
            # Wait for deletion to complete
            time.sleep(5)
            
            # Recreate index
            self._initialize_index()
            
            logger.info("Successfully cleared all vectors from Pinecone")
            return True
            
        except Exception as e:
            error_msg = f"Failed to clear vectors from Pinecone: {e}"
            logger.error(error_msg)
            if self.fallback_store:
                logger.warning("Using fallback store to clear vectors")
                return self.fallback_store.clear_all()
            return False
    
    def get_vector_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored vectors.
        
        Returns:
            Dictionary with vector statistics
        """
        if hasattr(self, '_use_fallback') and self.fallback_store:
            return self.fallback_store.get_vector_stats()
        
        try:
            # Get index stats
            stats = self.index.describe_index_stats()
            
            return {
                'total_vectors': stats.total_vector_count,
                'index_fullness': stats.index_fullness,
                'dimension': self.vector_dimension,
                'store_type': 'pinecone',
                'index_name': self.index_name,
                'environment': self.environment,
                'metric': self.metric
            }
            
        except Exception as e:
            logger.error(f"Failed to get Pinecone stats: {e}")
            return {
                'total_vectors': 0,
                'store_type': 'pinecone_error',
                'error': str(e)
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Pinecone connection.
        
        Returns:
            Dictionary with health check results
        """
        try:
            # Try to get index stats as a health check
            stats = self.index.describe_index_stats()
            
            return {
                'status': 'healthy',
                'store_type': 'pinecone',
                'index_name': self.index_name,
                'total_vectors': stats.total_vector_count,
                'index_fullness': stats.index_fullness,
                'connection': 'active'
            }
            
        except Exception as e:
            health_result = {
                'status': 'unhealthy',
                'store_type': 'pinecone',
                'index_name': self.index_name,
                'error': str(e),
                'connection': 'failed'
            }
            
            if self.fallback_store:
                fallback_health = self.fallback_store.health_check()
                health_result['fallback'] = fallback_health
                if fallback_health.get('status') == 'healthy':
                    health_result['status'] = 'degraded'
            
            return health_result