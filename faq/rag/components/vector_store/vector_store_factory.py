"""
Vector Store Factory

Factory for creating vector store instances based on configuration.
Supports both local (pickle-based) and Qdrant vector stores with fallback mechanisms.
"""

import logging
from typing import Optional

from faq.rag.interfaces.base import VectorStoreInterface
from faq.rag.config.settings import rag_config
from .vector_store import VectorStore
from .qdrant_vector_store import QdrantVectorStore, QdrantVectorStoreError, QDRANT_AVAILABLE


logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """Factory for creating vector store instances."""
    
    @staticmethod
    def create_vector_store(
        store_type: Optional[str] = None,
        fallback_enabled: bool = True,
        **kwargs
    ) -> VectorStoreInterface:
        """
        Create a vector store instance based on configuration.
        
        Args:
            store_type: Type of vector store ('local' or 'qdrant'). If None, uses config.
            fallback_enabled: Whether to enable fallback to local store for Qdrant
            **kwargs: Additional arguments for vector store initialization
            
        Returns:
            VectorStoreInterface implementation
            
        Raises:
            ValueError: If store_type is invalid or required dependencies are missing
        """
        config = rag_config.get_vector_config()
        
        # Determine store type
        if store_type is None:
            store_type = config.get('store_type', 'qdrant')  # Default to Qdrant for production
        
        store_type = store_type.lower()
        
        if store_type == 'local':
            return VectorStoreFactory._create_local_store(**kwargs)
        elif store_type == 'qdrant':
            return VectorStoreFactory._create_qdrant_store(
                fallback_enabled=fallback_enabled, 
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported vector store type: {store_type}")
    
    @staticmethod
    def _create_local_store(**kwargs) -> VectorStore:
        """Create a local (pickle-based) vector store."""
        config = rag_config.get_vector_config()
        
        # Set default parameters from config
        storage_path = kwargs.get('storage_path', rag_config.config.vector_store_path)
        
        logger.info(f"Creating local vector store at: {storage_path}")
        
        return VectorStore(
            storage_path=storage_path,
            **kwargs
        )
    
    @staticmethod
    def _create_qdrant_store(fallback_enabled: bool = True, **kwargs) -> QdrantVectorStore:
        """Create a Qdrant vector store with optional fallback."""
        if not QDRANT_AVAILABLE:
            if fallback_enabled:
                logger.warning(
                    "qdrant-client not available, falling back to local vector store. "
                    "Install with: pip install qdrant-client"
                )
                return VectorStoreFactory._create_local_store(**kwargs)
            else:
                raise ValueError(
                    "qdrant-client not available and fallback disabled. "
                    "Install with: pip install qdrant-client"
                )
        
        config = rag_config.get_vector_config()
        
        # Set default parameters from config
        host = kwargs.get('host', config.get('qdrant_host', 'localhost'))
        port = kwargs.get('port', config.get('qdrant_port', 6333))
        collection_name = kwargs.get('collection_name', config.get('qdrant_collection_name', 'faq_embeddings'))
        vector_dimension = kwargs.get('vector_dimension', config.get('dimension', 384))
        timeout = kwargs.get('timeout', config.get('qdrant_timeout', 30))
        
        # Create fallback store if enabled
        fallback_store = None
        if fallback_enabled:
            try:
                fallback_store = VectorStoreFactory._create_local_store()
                logger.info("Created fallback local vector store for Qdrant")
            except Exception as e:
                logger.warning(f"Failed to create fallback store: {e}")
        
        logger.info(f"Creating Qdrant vector store - Host: {host}:{port}, Collection: {collection_name}")
        
        try:
            return QdrantVectorStore(
                host=host,
                port=port,
                collection_name=collection_name,
                vector_dimension=vector_dimension,
                timeout=timeout,
                fallback_store=fallback_store,
                **{k: v for k, v in kwargs.items() if k not in [
                    'host', 'port', 'collection_name', 'vector_dimension', 'timeout'
                ]}
            )
        except QdrantVectorStoreError as e:
            if fallback_enabled and fallback_store:
                logger.error(f"Qdrant initialization failed, using fallback store: {e}")
                return fallback_store
            else:
                raise
    
    @staticmethod
    def create_production_store() -> VectorStoreInterface:
        """
        Create a production-ready vector store.
        
        This method creates a Qdrant store with local fallback for production use.
        
        Returns:
            VectorStoreInterface implementation suitable for production
        """
        return VectorStoreFactory.create_vector_store(
            store_type='qdrant',
            fallback_enabled=True
        )
    
    @staticmethod
    def create_development_store() -> VectorStoreInterface:
        """
        Create a development vector store.
        
        This method creates a local store for development use.
        
        Returns:
            VectorStoreInterface implementation suitable for development
        """
        return VectorStoreFactory.create_vector_store(
            store_type='local',
            fallback_enabled=False
        )
    
    @staticmethod
    def get_available_stores() -> list:
        """
        Get list of available vector store types.
        
        Returns:
            List of available store type strings
        """
        stores = ['local']
        
        if QDRANT_AVAILABLE:
            stores.append('qdrant')
        
        return stores
    
    @staticmethod
    def health_check_all_stores() -> dict:
        """
        Perform health checks on all available store types.
        
        Returns:
            Dictionary with health check results for each store type
        """
        results = {}
        
        # Check local store
        try:
            local_store = VectorStoreFactory._create_local_store()
            results['local'] = {
                'available': True,
                'stats': local_store.get_vector_stats()
            }
        except Exception as e:
            results['local'] = {
                'available': False,
                'error': str(e)
            }
        
        # Check Qdrant store
        if QDRANT_AVAILABLE:
            try:
                qdrant_store = VectorStoreFactory._create_qdrant_store(fallback_enabled=False)
                results['qdrant'] = qdrant_store.health_check()
            except Exception as e:
                results['qdrant'] = {
                    'available': False,
                    'error': str(e)
                }
        else:
            results['qdrant'] = {
                'available': False,
                'error': 'qdrant-client not installed'
            }
        
        return results