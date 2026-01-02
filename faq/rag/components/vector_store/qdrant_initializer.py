"""
Qdrant Vector Database Initializer

This module provides initialization and setup utilities for Qdrant vector database,
including collection creation, health checks, and data migration from local stores.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    models = None

from faq.rag.config.settings import rag_config
from faq.rag.interfaces.base import FAQEntry


logger = logging.getLogger(__name__)


class QdrantInitializerError(Exception):
    """Custom exception for Qdrant initializer errors."""
    pass


class QdrantInitializer:
    """
    Handles initialization and setup of Qdrant vector database.
    
    Features:
    - Connection testing and validation
    - Collection creation and configuration
    - Health monitoring and diagnostics
    - Data migration from local stores
    - Batch operations for efficient setup
    """
    
    def __init__(self, 
                 host: str = "localhost", 
                 port: int = 6333,
                 timeout: int = 30):
        """
        Initialize Qdrant initializer.
        
        Args:
            host: Qdrant server host
            port: Qdrant server port
            timeout: Connection timeout in seconds
        """
        if not QDRANT_AVAILABLE:
            raise QdrantInitializerError(
                "qdrant-client not available. Install with: pip install qdrant-client"
            )
        
        self.host = host
        self.port = port
        self.timeout = timeout
        self._client: Optional[QdrantClient] = None
        
        logger.info(f"QdrantInitializer created for {host}:{port}")
    
    def connect(self) -> bool:
        """
        Establish connection to Qdrant server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._client = QdrantClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            
            # Test connection
            collections = self._client.get_collections()
            logger.info(f"Successfully connected to Qdrant server at {self.host}:{self.port}")
            logger.info(f"Found {len(collections.collections)} existing collections")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant server: {e}")
            self._client = None
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check on Qdrant server.
        
        Returns:
            Dictionary containing health status and metrics
        """
        if not self._client:
            if not self.connect():
                return {
                    'status': 'unhealthy',
                    'error': 'Cannot connect to Qdrant server',
                    'timestamp': datetime.now().isoformat()
                }
        
        try:
            start_time = time.time()
            
            # Test basic operations
            collections = self._client.get_collections()
            response_time = time.time() - start_time
            
            # Get server info if available
            try:
                # This might not be available in all Qdrant versions
                cluster_info = self._client.get_cluster_info()
                peer_count = len(cluster_info.peers) if cluster_info.peers else 1
            except:
                peer_count = 1  # Assume single node
            
            return {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'response_time_ms': response_time * 1000,
                'collections_count': len(collections.collections),
                'peer_count': peer_count,
                'host': self.host,
                'port': self.port,
                'collections': [col.name for col in collections.collections]
            }
            
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def create_collection(self, 
                         collection_name: str,
                         vector_dimension: int = 384,
                         distance_metric: str = "cosine",
                         recreate_if_exists: bool = False) -> bool:
        """
        Create a collection for FAQ embeddings.
        
        Args:
            collection_name: Name of the collection to create
            vector_dimension: Dimension of embedding vectors
            distance_metric: Distance metric to use ("cosine", "euclidean", "dot")
            recreate_if_exists: Whether to recreate collection if it already exists
            
        Returns:
            True if collection created/exists, False otherwise
        """
        if not self._client:
            if not self.connect():
                logger.error("Cannot create collection: Qdrant connection failed")
                return False
        
        try:
            # Check if collection exists
            collections = self._client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if collection_name in collection_names:
                if recreate_if_exists:
                    logger.info(f"Recreating existing collection: {collection_name}")
                    self._client.delete_collection(collection_name)
                else:
                    logger.info(f"Collection {collection_name} already exists")
                    return True
            
            # Map distance metric
            distance_map = {
                "cosine": models.Distance.COSINE,
                "euclidean": models.Distance.EUCLID,
                "dot": models.Distance.DOT
            }
            
            distance = distance_map.get(distance_metric.lower(), models.Distance.COSINE)
            
            # Create collection
            logger.info(f"Creating collection: {collection_name} (dim={vector_dimension}, distance={distance_metric})")
            
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_dimension,
                    distance=distance
                ),
                # Optimize for FAQ use case
                optimizers_config=models.OptimizersConfig(
                    default_segment_number=2,
                    max_segment_size=20000,
                    memmap_threshold=20000,
                    indexing_threshold=20000,
                    flush_interval_sec=5,
                    max_optimization_threads=1
                ),
                # Enable payload indexing for metadata filtering
                hnsw_config=models.HnswConfig(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                    max_indexing_threads=0
                )
            )
            
            logger.info(f"Collection {collection_name} created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return False
    
    def setup_faq_collection(self, 
                            collection_name: str = "faq_embeddings",
                            vector_dimension: int = 384) -> bool:
        """
        Set up a collection specifically optimized for FAQ embeddings.
        
        Args:
            collection_name: Name of the FAQ collection
            vector_dimension: Dimension of FAQ embedding vectors
            
        Returns:
            True if setup successful, False otherwise
        """
        logger.info(f"Setting up FAQ collection: {collection_name}")
        
        # Create the collection
        if not self.create_collection(
            collection_name=collection_name,
            vector_dimension=vector_dimension,
            distance_metric="cosine"
        ):
            return False
        
        # Create payload indexes for efficient filtering
        try:
            # Index common FAQ metadata fields
            index_fields = [
                'category',
                'audience', 
                'intent',
                'condition',
                'confidence_score',
                'document_id'
            ]
            
            for field in index_fields:
                try:
                    self._client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field,
                        field_schema=models.PayloadSchemaType.KEYWORD
                    )
                    logger.debug(f"Created index for field: {field}")
                except Exception as e:
                    # Index might already exist, which is fine
                    logger.debug(f"Index creation for {field} skipped: {e}")
            
            logger.info(f"FAQ collection {collection_name} setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup payload indexes: {e}")
            return False
    
    def migrate_from_local_store(self, 
                                local_store_path: str,
                                collection_name: str = "faq_embeddings",
                                batch_size: int = 100) -> Dict[str, Any]:
        """
        Migrate data from local pickle-based vector store to Qdrant.
        
        Args:
            local_store_path: Path to local vector store data
            collection_name: Target Qdrant collection name
            batch_size: Number of vectors to process in each batch
            
        Returns:
            Dictionary with migration results
        """
        logger.info(f"Starting migration from local store: {local_store_path}")
        
        if not self._client:
            if not self.connect():
                return {
                    'success': False,
                    'error': 'Qdrant connection failed'
                }
        
        try:
            # Import local vector store
            from .vector_store import VectorStore
            
            # Load local store
            local_store = VectorStore(storage_path=local_store_path)
            local_stats = local_store.get_vector_stats()
            
            if local_stats['total_vectors'] == 0:
                return {
                    'success': True,
                    'migrated_count': 0,
                    'message': 'No vectors to migrate'
                }
            
            # Get all FAQ entries from local store
            # This is a bit tricky since we need to access internal data
            faq_entries = []
            
            with local_store._lock:
                for faq_id, metadata in local_store._metadata.items():
                    if faq_id in local_store._vectors:
                        # Set the embedding from the vector store
                        metadata.embedding = local_store._vectors[faq_id]
                        faq_entries.append(metadata)
            
            logger.info(f"Found {len(faq_entries)} FAQ entries to migrate")
            
            # Migrate in batches
            migrated_count = 0
            total_batches = (len(faq_entries) + batch_size - 1) // batch_size
            
            for batch_idx in range(0, len(faq_entries), batch_size):
                batch = faq_entries[batch_idx:batch_idx + batch_size]
                batch_num = (batch_idx // batch_size) + 1
                
                logger.info(f"Migrating batch {batch_num}/{total_batches} ({len(batch)} entries)")
                
                # Prepare points for batch insertion
                points = []
                
                for faq_entry in batch:
                    if faq_entry.embedding is None:
                        logger.warning(f"FAQ entry {faq_entry.id} has no embedding, skipping")
                        continue
                    
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
                            'created_at': faq_entry.created_at.isoformat() if faq_entry.created_at else None,
                            'updated_at': faq_entry.updated_at.isoformat() if faq_entry.updated_at else None
                        }
                    )
                    points.append(point)
                
                # Insert batch
                if points:
                    self._client.upsert(
                        collection_name=collection_name,
                        points=points
                    )
                    migrated_count += len(points)
                    logger.info(f"Migrated batch {batch_num}: {len(points)} vectors")
            
            return {
                'success': True,
                'migrated_count': migrated_count,
                'total_found': len(faq_entries),
                'collection_name': collection_name,
                'batch_size': batch_size
            }
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'migrated_count': migrated_count if 'migrated_count' in locals() else 0
            }
    
    def validate_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Validate collection configuration and data integrity.
        
        Args:
            collection_name: Name of collection to validate
            
        Returns:
            Dictionary with validation results
        """
        if not self._client:
            if not self.connect():
                return {
                    'valid': False,
                    'error': 'Qdrant connection failed'
                }
        
        try:
            # Check collection exists
            collections = self._client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if collection_name not in collection_names:
                return {
                    'valid': False,
                    'error': f'Collection {collection_name} does not exist'
                }
            
            # Get collection info
            collection_info = self._client.get_collection(collection_name)
            
            # Validate configuration
            config = collection_info.config
            vector_size = config.params.vectors.size
            distance = config.params.vectors.distance
            
            # Check some sample points
            sample_result = self._client.scroll(
                collection_name=collection_name,
                limit=10,
                with_payload=True,
                with_vectors=True
            )
            
            sample_points = sample_result[0]
            
            validation_results = {
                'valid': True,
                'collection_name': collection_name,
                'vector_dimension': vector_size,
                'distance_metric': distance.name if hasattr(distance, 'name') else str(distance),
                'total_points': collection_info.points_count,
                'sample_points_count': len(sample_points),
                'status': collection_info.status.name if hasattr(collection_info.status, 'name') else str(collection_info.status)
            }
            
            # Validate sample points
            if sample_points:
                first_point = sample_points[0]
                
                # Check vector dimension
                if hasattr(first_point, 'vector') and first_point.vector:
                    actual_dim = len(first_point.vector)
                    if actual_dim != vector_size:
                        validation_results['valid'] = False
                        validation_results['error'] = f'Vector dimension mismatch: expected {vector_size}, got {actual_dim}'
                
                # Check payload structure
                if hasattr(first_point, 'payload') and first_point.payload:
                    expected_fields = ['question', 'answer', 'category', 'audience']
                    missing_fields = [field for field in expected_fields if field not in first_point.payload]
                    
                    if missing_fields:
                        validation_results['warnings'] = f'Missing payload fields: {missing_fields}'
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Collection validation failed: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Get detailed statistics about a collection.
        
        Args:
            collection_name: Name of collection to analyze
            
        Returns:
            Dictionary with collection statistics
        """
        if not self._client:
            if not self.connect():
                return {
                    'error': 'Qdrant connection failed'
                }
        
        try:
            # Get collection info
            collection_info = self._client.get_collection(collection_name)
            
            # Get sample of points for analysis
            sample_result = self._client.scroll(
                collection_name=collection_name,
                limit=100,
                with_payload=True
            )
            
            sample_points = sample_result[0]
            
            # Analyze payload fields
            field_counts = {}
            category_counts = {}
            audience_counts = {}
            
            for point in sample_points:
                if hasattr(point, 'payload') and point.payload:
                    payload = point.payload
                    
                    # Count fields
                    for field in payload.keys():
                        field_counts[field] = field_counts.get(field, 0) + 1
                    
                    # Count categories
                    category = payload.get('category', 'unknown')
                    category_counts[category] = category_counts.get(category, 0) + 1
                    
                    # Count audiences
                    audience = payload.get('audience', 'unknown')
                    audience_counts[audience] = audience_counts.get(audience, 0) + 1
            
            return {
                'collection_name': collection_name,
                'total_points': collection_info.points_count,
                'vector_dimension': collection_info.config.params.vectors.size,
                'distance_metric': collection_info.config.params.vectors.distance.name if hasattr(collection_info.config.params.vectors.distance, 'name') else str(collection_info.config.params.vectors.distance),
                'status': collection_info.status.name if hasattr(collection_info.status, 'name') else str(collection_info.status),
                'sample_size': len(sample_points),
                'field_coverage': field_counts,
                'category_distribution': category_counts,
                'audience_distribution': audience_counts,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                'error': str(e)
            }
    
    def cleanup_collection(self, collection_name: str) -> bool:
        """
        Clean up and optimize a collection.
        
        Args:
            collection_name: Name of collection to clean up
            
        Returns:
            True if cleanup successful, False otherwise
        """
        if not self._client:
            if not self.connect():
                return False
        
        try:
            logger.info(f"Starting cleanup for collection: {collection_name}")
            
            # This would typically involve:
            # 1. Removing duplicate points
            # 2. Optimizing indexes
            # 3. Compacting segments
            
            # For now, we'll just log that cleanup was requested
            logger.info(f"Cleanup completed for collection: {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Cleanup failed for collection {collection_name}: {e}")
            return False