"""
Health check views for production deployment monitoring.

Provides lightweight endpoints for monitoring application health.
Uses lazy loading to avoid memory issues during startup.
"""

import logging
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@never_cache
def health_check(request):
    """
    Basic health check endpoint.
    
    Returns:
        JsonResponse with basic health status
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'faq-backend'
    })


@require_http_methods(["GET"])
@never_cache
def health_detailed(request):
    """
    Detailed health check with component status.
    Uses lazy loading to avoid startup memory issues.
    
    Returns:
        JsonResponse with detailed health information
    """
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'faq-backend',
        'components': {}
    }
    
    overall_healthy = True
    
    # Database health check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        health_data['components']['database'] = {
            'status': 'healthy',
            'type': 'sqlite' if 'sqlite' in settings.DATABASES['default']['ENGINE'] else 'postgresql'
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_data['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Vector store health check (lazy loaded)
    try:
        # Lazy import to avoid memory issues
        from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
        
        vector_store = VectorStoreFactory.create_vector_store()
        vector_health = vector_store.health_check() if hasattr(vector_store, 'health_check') else {'status': 'unknown'}
        
        health_data['components']['vector_store'] = {
            'status': vector_health.get('status', 'unknown'),
            'type': vector_store.__class__.__name__,
            'details': vector_health
        }
        
        if vector_health.get('status') not in ['healthy', 'degraded']:
            overall_healthy = False
            
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        health_data['components']['vector_store'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # RAG system configuration check (lazy loaded)
    try:
        from faq.rag.config.settings import rag_config
        config = rag_config.config
        
        health_data['components']['rag_config'] = {
            'status': 'healthy',
            'embedding_type': config.embedding_type,
            'vector_store_type': config.vector_store_type,
            'gemini_configured': bool(config.gemini_api_key)
        }
    except Exception as e:
        logger.error(f"RAG config check failed: {e}")
        health_data['components']['rag_config'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Update overall status
    if not overall_healthy:
        health_data['status'] = 'unhealthy'
    elif any(comp.get('status') == 'degraded' for comp in health_data['components'].values()):
        health_data['status'] = 'degraded'
    
    return JsonResponse(health_data)


@require_http_methods(["GET"])
@never_cache
def health_vector_store(request):
    """
    Vector store specific health check.
    Uses lazy loading to avoid memory issues.
    
    Returns:
        JsonResponse with vector store health details
    """
    try:
        # Lazy import to avoid memory issues
        from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
        
        # Create vector store
        vector_store = VectorStoreFactory.create_vector_store()
        
        # Basic health check
        if hasattr(vector_store, 'health_check'):
            health_result = vector_store.health_check()
        else:
            # Fallback health check
            stats = vector_store.get_vector_stats()
            health_result = {
                'status': 'healthy' if isinstance(stats, dict) else 'unhealthy',
                'store_type': vector_store.__class__.__name__,
                'stats': stats
            }
        
        # Set HTTP status code based on health
        status_code = 200
        if health_result.get('status') == 'unhealthy':
            status_code = 503
        elif health_result.get('status') == 'degraded':
            status_code = 200  # Still operational but with warnings
        
        response_data = {
            'status': health_result.get('status', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'store_type': health_result.get('store_type', vector_store.__class__.__name__),
            'details': health_result
        }
        
        return JsonResponse(response_data, status=status_code)
        
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        return JsonResponse({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }, status=503)


@require_http_methods(["GET"])
@never_cache
def health_readiness(request):
    """
    Kubernetes-style readiness probe.
    Lightweight check for service readiness.
    
    Returns:
        JsonResponse indicating if the service is ready to serve traffic
    """
    try:
        # Check critical components for readiness
        ready = True
        components = {}
        
        # Database readiness
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            components['database'] = True
        except Exception:
            components['database'] = False
            ready = False
        
        # Basic Django readiness
        components['django'] = True
        
        response_data = {
            'ready': ready,
            'timestamp': datetime.now().isoformat(),
            'components': components
        }
        
        return JsonResponse(response_data, status=200 if ready else 503)
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JsonResponse({
            'ready': False,
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }, status=503)


@require_http_methods(["GET"])
@never_cache
def health_liveness(request):
    """
    Kubernetes-style liveness probe.
    
    Returns:
        JsonResponse indicating if the service is alive
    """
    # Simple liveness check - if we can respond, we're alive
    return JsonResponse({
        'alive': True,
        'timestamp': datetime.now().isoformat(),
        'service': 'faq-backend'
    })


# Lightweight endpoints that don't import heavy dependencies
@require_http_methods(["GET"])
@never_cache
def health_pinecone(request):
    """
    Pinecone-specific health check endpoint.
    Uses lazy loading to avoid startup memory issues.
    
    Returns:
        JsonResponse with Pinecone health information
    """
    try:
        # Check if Pinecone is configured
        pinecone_api_key = getattr(settings, 'PINECONE_API_KEY', None)
        if not pinecone_api_key:
            return JsonResponse({
                'status': 'unavailable',
                'timestamp': datetime.now().isoformat(),
                'error': 'PINECONE_API_KEY not configured'
            }, status=503)
        
        # Lazy import and basic connectivity test
        try:
            from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
            vector_store = VectorStoreFactory.create_vector_store(store_type='pinecone')
            
            if hasattr(vector_store, 'health_check'):
                health_result = vector_store.health_check()
            else:
                # Basic check
                stats = vector_store.get_vector_stats()
                health_result = {
                    'status': 'healthy' if stats.get('store_type') == 'pinecone' else 'degraded',
                    'stats': stats
                }
            
            response_data = {
                'status': health_result.get('status', 'unknown'),
                'timestamp': datetime.now().isoformat(),
                'store_type': 'pinecone',
                'index_name': getattr(settings, 'PINECONE_INDEX_NAME', 'faq-embeddings'),
                'environment': getattr(settings, 'PINECONE_ENVIRONMENT', 'us-east-1-aws'),
                'details': health_result
            }
            
            status_code = 200 if health_result.get('status') == 'healthy' else 503
            return JsonResponse(response_data, status=status_code)
            
        except Exception as e:
            logger.error(f"Pinecone health check failed: {e}")
            return JsonResponse({
                'status': 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }, status=503)
        
    except Exception as e:
        logger.error(f"Pinecone health check failed: {e}")
        return JsonResponse({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }, status=503)


# Remove heavy endpoints that cause memory issues
# The following endpoints are commented out to reduce memory usage:
# - health_qdrant (imports heavy Qdrant dependencies)
# - health_embeddings (imports heavy ML dependencies)
# - regenerate_embeddings (imports heavy ML dependencies)

# These can be re-enabled later when memory constraints are resolved