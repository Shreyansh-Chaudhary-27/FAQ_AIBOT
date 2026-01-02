"""
Qdrant Vector Store Implementation

This module provides a production-ready vector store implementation using Qdrant
for reliable embedding storage, retrieval, and similarity search in production environments.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import numpy as np
from threading import Lock
import time

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    models = None

from faq.rag.interfaces.base import (
    VectorStoreInterface, 
    FAQEntry, 
    SimilarityMatch
)
from faq.rag.utils.ngram_utils import get_ngram_overlap


logger = logging.getLogger(__name__)


class QdrantVectorStoreError(Exception):
    """Custom exception for Qdrant vector store errors."""
    pass


class QdrantVectorStore(VectorStoreInterface):
    """
    Production-ready Qdrant vector store implementation.
    
    Features:
    - Qdrant vector database integration
    - Automatic collection management
    - Health checks and connectivity monitoring
    - Fallback mechanisms for embedding failures
    - Batch operations for efficiency
    - Metadata filtering and search
    """
    
    def __init__(self, 
                 host: str = "localhost", 
                 port: int = 6333,
                 collection_name: str = "faq_embeddings",
                 vector_dimension: int = 384,
                 timeout: int = 30,
                 fallback_store: Optional[VectorStoreInterface] = None):
        """
        Initialize Qdrant vector store.
        
        Args:
            host: Qdrant server host
            port: Qdrant server port
            collection_name: Name of the collection to use
            vector_dimension: Dimension of embedding vectors
            timeout: Connection timeout in seconds
            fallback_store: Optional fallback vector store for when Qdrant is unavailable
        """
        if not QDRANT_AVAILABLE:
            raise QdrantVectorStoreError(
                "qdrant-client not available. Install with: pip install qdrant-client"
            )
        
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.vector_dimension = vector_dimension
        self.timeout = timeout
        self.fallback_store = fallback_store
        self._lock = Lock()
        
        # Connection and health status
        self._client: Optional[QdrantClient] = None
        self._is_healthy = False
        self._last_health_check = None
        self._connection_retries = 0
        self._max_retries = 3
        
        # Statistics
        self._stats = {
            'total_vectors': 0,
            'last_updated': None,
            'search_count': 0,
            'average_search_time': 0.0,
            'connection_errors': 0,
            'fallback_usage': 0
        }
        
        # Document processing tracking
        self._document_hashes: Dict[str, str] = {}
        self._document_faqs: Dict[str, List[str]] = {}
        
        # Initialize connection
        self._initialize_connection()
        
        logger.info(f"QdrantVectorStore initialized - Host: {host}:{port}, Collection: {collection_name}")
    
    def _initialize_connection(self) -> None:
        """Initialize connection to Qdrant server."""
        try:
            self._client = QdrantClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            
            # Test connection
            self._client.get_collections()
            
            # Create collection if it doesn't exist
            self._ensure_collection_exists()
            
            self._is_healthy = True
            self._last_health_check = datetime.now()
            self._connection_retries = 0
            
            logger.info("Successfully connected to Qdrant server")
            
        except Exception as e:
            self._is_healthy = False
            self._connection_retries += 1
            self._stats['connection_errors'] += 1
            
            logger.error(f"Failed to connect to Qdrant server: {e}")
            
            if self.fallback_store:
                logger.info("Qdrant unavailable, will use fallback store")
            else:
                raise QdrantVectorStoreError(f"Qdrant connection failed and no fallback available: {e}")
    
    def _ensure_collection_exists(self) -> None:
        """Ensure the collection exists with proper configuration."""
        if not self._client:
            raise QdrantVectorStoreError("Qdrant client not initialized")
        
        try:
            # Check if collection exists
            collections = self._client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                
                # Create collection with vector configuration
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_dimension,
                        distance=models.Distance.COSINE
                    ),
                    # Enable payload indexing for metadata filtering
                    optimizers_config=models.OptimizersConfig(
                        default_segment_number=2,
                        max_segment_size=20000,
                        memmap_threshold=20000,
                        indexing_threshold=20000,
                        flush_interval_sec=5,
                        max_optimization_threads=1
                    )
                )
                
                logger.info(f"Collection {self.collection_name} created successfully")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                
                # Verify collection configuration
                collection_info = self._client.get_collection(self.collection_name)
                vector_size = collection_info.config.params.vectors.size
                
                if vector_size != self.vector_dimension:
                    logger.warning(
                        f"Collection vector dimension mismatch: expected {self.vector_dimension}, "
                        f"got {vector_size}"
                    )
                
        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise QdrantVectorStoreError(f"Collection setup failed: {e}")
    
    def _reconnect_if_needed(self) -> bool:
        """Attempt to reconnect if connection is unhealthy."""
        if self._is_healthy:
            return True
        
        if self._connection_retries >= self._max_retries:
            logger.error(f"Max connection retries ({self._max_retries}) exceeded")
            return False
        
        try:
            logger.info(f"Attempting to reconnect to Qdrant (attempt {self._connection_retries + 1})")
            self._initialize_connection()
            return self._is_healthy
        except Exception as e:
            logger.error(f"Reconnection attempt failed: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Qdrant connection.
        
        Returns:
            Dictionary containing health status and metrics
        """
        try:
            if not self._client:
                return {
                    'status': 'unhealthy',
                    'error': 'Client not initialized',
                    'qdrant_available': False
                }
            
            # Test basic operations
            start_time = time.time()
            collections = self._client.get_collections()
            response_time = time.time() - start_time
            
            # Check collection exists
            collection_names = [col.name for col in collections.collections]
            collection_exists = self.collection_name in collection_names
            
            if collection_exists:
                # Get collection info
                collection_info = self._client.get_collection(self.collection_name)
                vector_count = collection_info.points_count
                self._stats['total_vectors'] = vector_count
            else:
                vector_count = 0
            
            self._is_healthy = True
            self._last_health_check = datetime.now()
            
            return {
                'status': 'healthy',
                'qdrant_available': True,
                'response_time_ms': response_time * 1000,
                'collection_exists': collection_exists,
                'vector_count': vector_count,
                'host': self.host,
                'port': self.port,
                'collection_name': self.collection_name,
                'last_check': self._last_health_check.isoformat(),
                'stats': self._stats.copy()
            }
            
        except Exception as e:
            self._is_healthy = False
            self._stats['connection_errors'] += 1
            
            logger.error(f"Qdrant health check failed: {e}")
            
            return {
                'status': 'unhealthy',
                'qdrant_available': False,
                'error': str(e),
                'fallback_available': self.fallback_store is not None,
                'stats': self._stats.copy()
            }
    
    def store_vectors(self, vectors: List[FAQEntry], document_id: Optional[str] = None, document_hash: Optional[str] = None) -> None:
        """
        Store FAQ vectors in Qdrant with fallback support.
        
        Args:
            vectors: List of FAQ entries with embeddings
            document_id: Optional document identifier for tracking
            document_hash: Optional document hash for incremental updates
        """
        with self._lock:
            # Try Qdrant first
            if self._is_healthy or self._reconnect_if_needed():
                try:
                    self._store_vectors_qdrant(vectors, document_id, document_hash)
                    return
                except Exception as e:
                    logger.error(f"Qdrant storage failed: {e}")
                    self._is_healthy = False
                    self._stats['connection_errors'] += 1
            
            # Fallback to local store if available
            if self.fallback_store:
                logger.info("Using fallback store for vector storage")
                self._stats['fallback_usage'] += 1
                self.fallback_store.store_vectors(vectors, document_id, document_hash)
            else:
                raise QdrantVectorStoreError("Qdrant unavailable and no fallback store configured")
    
    def _store_vectors_qdrant(self, vectors: List[FAQEntry], document_id: Optional[str] = None, document_hash: Optional[str] = None) -> None:
        """Store vectors directly in Qdrant."""
        if not self._client:
            raise QdrantVectorStoreError("Qdrant client not initialized")
        
        stored_count = 0
        faq_ids_for_document = []
        
        # If document_id provided, remove existing FAQs from this document first
        if document_id and document_id in self._document_faqs:
            old_faq_ids = self._document_faqs[document_id]
            if old_faq_ids:
                try:
                    self._client.delete(
                        collection_name=self.collection_name,
                        points_selector=models.PointIdsList(
                            points=[faq_id for faq_id in old_faq_ids]
                        )
                    )
                    logger.info(f"Removed {len(old_faq_ids)} existing FAQs for document {document_id}")
                except Exception as e:
                    logger.warning(f"Failed to remove old FAQs: {e}")
        
        # Prepare points for batch insertion
        points = []
        
        for faq_entry in vectors:
            if faq_entry.embedding is None:
                logger.warning(f"FAQ entry {faq_entry.id} has no embedding, skipping")
                continue
            
            # Create point with metadata
            point = models.PointStruct(
                id=faq_entry.id,
                vector=faq_entry.embedding.tolist(),
                payload={
                    'question': faq_entry.question,
                    'answer': faq_entry.answer,
                    'category': faq_entry.category,
                    'audience': faq_entry.audience,
                    'intent': faq_entry.intent,
                    'condition': faq_entry.condition,
                    'confidence_score': faq_entry.confidence_score,
                    'keywords': faq_entry.keywords,
                    'composite_key': faq_entry.composite_key,
                    'document_id': document_id,
                    'created_at': faq_entry.created_at.isoformat() if faq_entry.created_at else None,
                    'updated_at': faq_entry.updated_at.isoformat() if faq_entry.updated_at else None
                }
            )
            
            points.append(point)
            stored_count += 1
            
            if document_id:
                faq_ids_for_document.append(faq_entry.id)
        
        # Batch insert points
        if points:
            try:
                self._client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                
                # Update document tracking
                if document_id:
                    self._document_hashes[document_id] = document_hash or ""
                    self._document_faqs[document_id] = faq_ids_for_document
                    logger.info(f"Tracked {len(faq_ids_for_document)} FAQs for document {document_id}")
                
                self._stats['last_updated'] = datetime.now()
                
                logger.info(f"Stored {stored_count} vectors in Qdrant")
                
            except Exception as e:
                logger.error(f"Failed to upsert points to Qdrant: {e}")
                raise QdrantVectorStoreError(f"Qdrant upsert failed: {e}")
    
    def search_similar(self, query_vector: np.ndarray, threshold: float = 0.7, top_k: int = 10) -> List[SimilarityMatch]:
        """
        Search for similar vectors with fallback support.
        
        Args:
            query_vector: Query embedding vector
            threshold: Minimum similarity threshold (0.0 to 1.0)
            top_k: Maximum number of results to return
            
        Returns:
            List of similarity matches sorted by score (descending)
        """
        start_time = time.time()
        
        with self._lock:
            # Try Qdrant first
            if self._is_healthy or self._reconnect_if_needed():
                try:
                    matches = self._search_similar_qdrant(query_vector, threshold, top_k)
                    self._update_search_stats(time.time() - start_time)
                    return matches
                except Exception as e:
                    logger.error(f"Qdrant search failed: {e}")
                    self._is_healthy = False
                    self._stats['connection_errors'] += 1
            
            # Fallback to local store if available
            if self.fallback_store:
                logger.info("Using fallback store for similarity search")
                self._stats['fallback_usage'] += 1
                matches = self.fallback_store.search_similar(query_vector, threshold, top_k)
                self._update_search_stats(time.time() - start_time)
                return matches
            else:
                raise QdrantVectorStoreError("Qdrant unavailable and no fallback store configured")
    
    def _search_similar_qdrant(self, query_vector: np.ndarray, threshold: float, top_k: int) -> List[SimilarityMatch]:
        """Search for similar vectors directly in Qdrant."""
        if not self._client:
            raise QdrantVectorStoreError("Qdrant client not initialized")
        
        try:
            # Perform similarity search
            search_result = self._client.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                limit=top_k,
                score_threshold=threshold,
                with_payload=True
            )
            
            # Convert results to SimilarityMatch objects
            matches = []
            for scored_point in search_result:
                payload = scored_point.payload
                
                # Reconstruct FAQEntry from payload
                faq_entry = FAQEntry(
                    id=str(scored_point.id),
                    question=payload.get('question', ''),
                    answer=payload.get('answer', ''),
                    category=payload.get('category', 'general'),
                    audience=payload.get('audience', 'any'),
                    intent=payload.get('intent', 'information'),
                    condition=payload.get('condition', 'default'),
                    confidence_score=payload.get('confidence_score', 0.0),
                    keywords=payload.get('keywords', []),
                    composite_key=payload.get('composite_key', ''),
                    embedding=query_vector,  # We don't store the original embedding in payload
                    created_at=datetime.fromisoformat(payload['created_at']) if payload.get('created_at') else datetime.now(),
                    updated_at=datetime.fromisoformat(payload['updated_at']) if payload.get('updated_at') else datetime.now()
                )
                
                match = SimilarityMatch(
                    faq_entry=faq_entry,
                    similarity_score=scored_point.score,
                    match_type='semantic',
                    matched_components=['embedding']
                )
                matches.append(match)
            
            logger.debug(f"Qdrant search found {len(matches)} matches")
            return matches
            
        except Exception as e:
            logger.error(f"Qdrant search operation failed: {e}")
            raise QdrantVectorStoreError(f"Qdrant search failed: {e}")
    
    def search_by_ngrams(self, query_ngrams: List[str], threshold: float = 0.9) -> List[SimilarityMatch]:
        """
        Search for FAQs based on N-gram keyword overlap with fallback support.
        
        Args:
            query_ngrams: List of N-grams from the query
            threshold: Minimum overlap percentage (default: 0.9)
            
        Returns:
            List of similarity matches meeting the threshold
        """
        # Try Qdrant first with keyword filtering
        if self._is_healthy or self._reconnect_if_needed():
            try:
                return self._search_by_ngrams_qdrant(query_ngrams, threshold)
            except Exception as e:
                logger.error(f"Qdrant N-gram search failed: {e}")
                self._is_healthy = False
                self._stats['connection_errors'] += 1
        
        # Fallback to local store if available
        if self.fallback_store:
            logger.info("Using fallback store for N-gram search")
            self._stats['fallback_usage'] += 1
            return self.fallback_store.search_by_ngrams(query_ngrams, threshold)
        else:
            logger.warning("Qdrant unavailable and no fallback store configured for N-gram search")
            return []
    
    def _search_by_ngrams_qdrant(self, query_ngrams: List[str], threshold: float) -> List[SimilarityMatch]:
        """Search by N-grams directly in Qdrant using keyword filtering."""
        if not self._client or not query_ngrams:
            return []
        
        try:
            query_ngram_set = set(query_ngrams)
            
            # Use scroll to get all points and filter by keywords
            # This is not the most efficient approach, but works for moderate datasets
            # For large datasets, consider using Qdrant's full-text search capabilities
            
            scroll_result = self._client.scroll(
                collection_name=self.collection_name,
                limit=1000,  # Adjust based on your dataset size
                with_payload=True
            )
            
            matches = []
            
            for point in scroll_result[0]:
                payload = point.payload
                faq_keywords = payload.get('keywords', [])
                
                if not faq_keywords:
                    continue
                
                faq_ngram_set = set(faq_keywords)
                overlap = get_ngram_overlap(faq_ngram_set, query_ngram_set)
                
                if overlap >= threshold:
                    # Reconstruct FAQEntry
                    faq_entry = FAQEntry(
                        id=str(point.id),
                        question=payload.get('question', ''),
                        answer=payload.get('answer', ''),
                        category=payload.get('category', 'general'),
                        audience=payload.get('audience', 'any'),
                        intent=payload.get('intent', 'information'),
                        condition=payload.get('condition', 'default'),
                        confidence_score=payload.get('confidence_score', 0.0),
                        keywords=faq_keywords,
                        composite_key=payload.get('composite_key', ''),
                        embedding=None,
                        created_at=datetime.fromisoformat(payload['created_at']) if payload.get('created_at') else datetime.now(),
                        updated_at=datetime.fromisoformat(payload['updated_at']) if payload.get('updated_at') else datetime.now()
                    )
                    
                    match = SimilarityMatch(
                        faq_entry=faq_entry,
                        similarity_score=overlap,
                        match_type='keyword_ngram',
                        matched_components=['keywords']
                    )
                    matches.append(match)
            
            # Sort by overlap score descending
            matches.sort(key=lambda x: x.similarity_score, reverse=True)
            
            if matches:
                logger.info(f"Qdrant N-Gram search found {len(matches)} matches (>= {threshold*100}%)")
            
            return matches
            
        except Exception as e:
            logger.error(f"Qdrant N-gram search operation failed: {e}")
            raise QdrantVectorStoreError(f"Qdrant N-gram search failed: {e}")
    
    def search_with_filters(self, query_vector: np.ndarray, threshold: float = 0.7, top_k: int = 10,
                           category_filter: Optional[str] = None, 
                           audience_filter: Optional[str] = None,
                           intent_filter: Optional[str] = None,
                           condition_filter: Optional[str] = None,
                           confidence_filter: Optional[float] = None,
                           keyword_filter: Optional[List[str]] = None) -> List[SimilarityMatch]:
        """
        Search for similar vectors with metadata filtering.
        
        Args:
            query_vector: Query embedding vector
            threshold: Minimum similarity threshold (0.0 to 1.0)
            top_k: Maximum number of results to return
            category_filter: Filter by category
            audience_filter: Filter by audience
            intent_filter: Filter by intent
            condition_filter: Filter by condition (supports '*' for any)
            confidence_filter: Minimum extraction confidence score
            keyword_filter: List of keywords that must be present
            
        Returns:
            List of similarity matches meeting all criteria
        """
        start_time = time.time()
        
        with self._lock:
            # Try Qdrant first
            if self._is_healthy or self._reconnect_if_needed():
                try:
                    matches = self._search_with_filters_qdrant(
                        query_vector, threshold, top_k, category_filter, 
                        audience_filter, intent_filter, condition_filter,
                        confidence_filter, keyword_filter
                    )
                    self._update_search_stats(time.time() - start_time)
                    return matches
                except Exception as e:
                    logger.error(f"Qdrant filtered search failed: {e}")
                    self._is_healthy = False
                    self._stats['connection_errors'] += 1
            
            # Fallback to local store if available
            if self.fallback_store:
                logger.info("Using fallback store for filtered search")
                self._stats['fallback_usage'] += 1
                matches = self.fallback_store.search_with_filters(
                    query_vector, threshold, top_k, category_filter,
                    audience_filter, intent_filter, condition_filter,
                    confidence_filter, keyword_filter
                )
                self._update_search_stats(time.time() - start_time)
                return matches
            else:
                raise QdrantVectorStoreError("Qdrant unavailable and no fallback store configured")
    
    def _search_with_filters_qdrant(self, query_vector: np.ndarray, threshold: float, top_k: int,
                                   category_filter: Optional[str], audience_filter: Optional[str],
                                   intent_filter: Optional[str], condition_filter: Optional[str],
                                   confidence_filter: Optional[float], keyword_filter: Optional[List[str]]) -> List[SimilarityMatch]:
        """Search with filters directly in Qdrant."""
        if not self._client:
            raise QdrantVectorStoreError("Qdrant client not initialized")
        
        try:
            # Build filter conditions
            filter_conditions = []
            
            if audience_filter and audience_filter != 'any':
                filter_conditions.append(
                    models.FieldCondition(
                        key="audience",
                        match=models.MatchValue(value=audience_filter)
                    )
                )
            
            if category_filter and category_filter != 'general':
                filter_conditions.append(
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(value=category_filter)
                    )
                )
            
            if intent_filter and intent_filter not in ['information', 'any', 'all']:
                filter_conditions.append(
                    models.FieldCondition(
                        key="intent",
                        match=models.MatchValue(value=intent_filter)
                    )
                )
            
            if condition_filter and condition_filter not in ['*', 'default']:
                filter_conditions.append(
                    models.FieldCondition(
                        key="condition",
                        match=models.MatchValue(value=condition_filter)
                    )
                )
            
            if confidence_filter is not None:
                filter_conditions.append(
                    models.FieldCondition(
                        key="confidence_score",
                        range=models.Range(gte=confidence_filter)
                    )
                )
            
            # Build filter object
            search_filter = None
            if filter_conditions:
                search_filter = models.Filter(
                    must=filter_conditions
                )
            
            # Perform filtered search
            search_result = self._client.search(
                collection_name=self.collection_name,
                query_vector=query_vector.tolist(),
                query_filter=search_filter,
                limit=top_k,
                score_threshold=threshold,
                with_payload=True
            )
            
            # Convert results to SimilarityMatch objects
            matches = []
            for scored_point in search_result:
                payload = scored_point.payload
                
                # Apply keyword filter if specified
                if keyword_filter:
                    faq_keywords = [kw.lower() for kw in payload.get('keywords', [])]
                    filter_keywords = [kw.lower() for kw in keyword_filter]
                    if not any(kw in faq_keywords for kw in filter_keywords):
                        continue
                
                # Reconstruct FAQEntry from payload
                faq_entry = FAQEntry(
                    id=str(scored_point.id),
                    question=payload.get('question', ''),
                    answer=payload.get('answer', ''),
                    category=payload.get('category', 'general'),
                    audience=payload.get('audience', 'any'),
                    intent=payload.get('intent', 'information'),
                    condition=payload.get('condition', 'default'),
                    confidence_score=payload.get('confidence_score', 0.0),
                    keywords=payload.get('keywords', []),
                    composite_key=payload.get('composite_key', ''),
                    embedding=query_vector,
                    created_at=datetime.fromisoformat(payload['created_at']) if payload.get('created_at') else datetime.now(),
                    updated_at=datetime.fromisoformat(payload['updated_at']) if payload.get('updated_at') else datetime.now()
                )
                
                match = SimilarityMatch(
                    faq_entry=faq_entry,
                    similarity_score=scored_point.score,
                    match_type='semantic',
                    matched_components=['embedding']
                )
                matches.append(match)
            
            logger.debug(f"Qdrant filtered search found {len(matches)} matches")
            return matches
            
        except Exception as e:
            logger.error(f"Qdrant filtered search operation failed: {e}")
            raise QdrantVectorStoreError(f"Qdrant filtered search failed: {e}")
    
    def clear_all(self) -> bool:
        """
        Clear all data from the vector store.
        
        Returns:
            True if cleared successfully
        """
        logger.info("Clearing all data from Qdrant vector store")
        
        with self._lock:
            # Try Qdrant first
            if self._is_healthy or self._reconnect_if_needed():
                try:
                    # Delete and recreate collection
                    self._client.delete_collection(self.collection_name)
                    self._ensure_collection_exists()
                    
                    # Clear tracking data
                    self._document_hashes = {}
                    self._document_faqs = {}
                    
                    # Reset statistics
                    self._stats.update({
                        'total_vectors': 0,
                        'last_updated': datetime.now(),
                        'search_count': 0,
                        'average_search_time': 0.0
                    })
                    
                    logger.info("Successfully cleared Qdrant vector store")
                    return True
                    
                except Exception as e:
                    logger.error(f"Failed to clear Qdrant store: {e}")
                    self._is_healthy = False
                    self._stats['connection_errors'] += 1
            
            # Fallback to local store if available
            if self.fallback_store:
                logger.info("Using fallback store for clear operation")
                self._stats['fallback_usage'] += 1
                return self.fallback_store.clear_all()
            else:
                logger.error("Qdrant unavailable and no fallback store configured")
                return False
    
    def get_vector_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        
        Returns:
            Dictionary containing store statistics
        """
        with self._lock:
            stats = self._stats.copy()
            
            # Add Qdrant-specific metrics
            stats.update({
                'store_type': 'qdrant',
                'host': self.host,
                'port': self.port,
                'collection_name': self.collection_name,
                'vector_dimension': self.vector_dimension,
                'is_healthy': self._is_healthy,
                'last_health_check': self._last_health_check.isoformat() if self._last_health_check else None,
                'connection_retries': self._connection_retries,
                'fallback_available': self.fallback_store is not None
            })
            
            # Try to get current collection info
            if self._is_healthy and self._client:
                try:
                    collection_info = self._client.get_collection(self.collection_name)
                    stats['total_vectors'] = collection_info.points_count
                    stats['collection_status'] = collection_info.status
                except Exception as e:
                    stats['collection_error'] = str(e)
            
            return stats
    
    def _update_search_stats(self, search_time: float) -> None:
        """Update search performance statistics."""
        self._stats['search_count'] += 1
        
        # Update average search time using exponential moving average
        alpha = 0.1  # Smoothing factor
        if self._stats['average_search_time'] == 0.0:
            self._stats['average_search_time'] = search_time
        else:
            self._stats['average_search_time'] = (
                alpha * search_time + 
                (1 - alpha) * self._stats['average_search_time']
            )
    
    # Additional methods for compatibility with VectorStoreInterface
    def batch_search_similar(self, query_vectors: List[np.ndarray], threshold: float = 0.7, top_k: int = 10) -> List[List[SimilarityMatch]]:
        """Perform batch similarity search for multiple query vectors."""
        results = []
        for query_vector in query_vectors:
            matches = self.search_similar(query_vector, threshold, top_k)
            results.append(matches)
        return results
    
    def update_vector(self, faq_id: str, new_vector: np.ndarray) -> None:
        """Update a specific vector in the store."""
        # This would require getting the existing point, updating the vector, and upserting
        # For now, we'll raise NotImplementedError as it's complex with Qdrant
        raise NotImplementedError("Vector update not implemented for Qdrant store")
    
    def delete_vector(self, faq_id: str) -> bool:
        """Delete a vector from the store."""
        if not self._is_healthy or not self._client:
            if self.fallback_store:
                return self.fallback_store.delete_vector(faq_id)
            return False
        
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=[faq_id])
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete vector {faq_id}: {e}")
            return False
    
    def is_document_processed(self, document_id: str, document_hash: str) -> bool:
        """Check if a document has already been processed with the same hash."""
        with self._lock:
            if document_id not in self._document_hashes:
                return False
            
            stored_hash = self._document_hashes[document_id]
            return stored_hash == document_hash
    
    def get_faq_entries(self, faq_ids: List[str]) -> List[FAQEntry]:
        """Get FAQEntry objects for the given IDs."""
        if not self._is_healthy or not self._client:
            if self.fallback_store:
                return self.fallback_store.get_faq_entries(faq_ids)
            return []
        
        try:
            # Retrieve points by IDs
            points = self._client.retrieve(
                collection_name=self.collection_name,
                ids=faq_ids,
                with_payload=True
            )
            
            faq_entries = []
            for point in points:
                payload = point.payload
                faq_entry = FAQEntry(
                    id=str(point.id),
                    question=payload.get('question', ''),
                    answer=payload.get('answer', ''),
                    category=payload.get('category', 'general'),
                    audience=payload.get('audience', 'any'),
                    intent=payload.get('intent', 'information'),
                    condition=payload.get('condition', 'default'),
                    confidence_score=payload.get('confidence_score', 0.0),
                    keywords=payload.get('keywords', []),
                    composite_key=payload.get('composite_key', ''),
                    embedding=None,
                    created_at=datetime.fromisoformat(payload['created_at']) if payload.get('created_at') else datetime.now(),
                    updated_at=datetime.fromisoformat(payload['updated_at']) if payload.get('updated_at') else datetime.now()
                )
                faq_entries.append(faq_entry)
            
            return faq_entries
            
        except Exception as e:
            logger.error(f"Failed to retrieve FAQ entries: {e}")
            return []
    
    def get_document_faqs(self, document_id: str) -> List[str]:
        """Get FAQ IDs associated with a document."""
        with self._lock:
            return self._document_faqs.get(document_id, []).copy()
    
    def remove_document(self, document_id: str) -> int:
        """Remove all FAQs associated with a document."""
        with self._lock:
            if document_id not in self._document_faqs:
                return 0
            
            faq_ids = self._document_faqs[document_id]
            removed_count = 0
            
            if self._is_healthy and self._client:
                try:
                    self._client.delete(
                        collection_name=self.collection_name,
                        points_selector=models.PointIdsList(points=faq_ids)
                    )
                    removed_count = len(faq_ids)
                except Exception as e:
                    logger.error(f"Failed to remove document FAQs from Qdrant: {e}")
            
            # Remove document tracking
            del self._document_faqs[document_id]
            if document_id in self._document_hashes:
                del self._document_hashes[document_id]
            
            if removed_count > 0:
                self._stats['last_updated'] = datetime.now()
            
            logger.info(f"Removed {removed_count} FAQs for document {document_id}")
            return removed_count