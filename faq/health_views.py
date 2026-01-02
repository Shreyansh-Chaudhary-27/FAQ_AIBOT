"""
Health check views for production deployment monitoring.

Provides endpoints for monitoring application health, database connectivity,
vector store status, and overall system health.
"""

import logging
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.db import connection
from django.conf import settings

from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
from faq.rag.components.vector_store.health_monitor import VectorStoreHealthMonitor


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
            'type': 'postgresql' if 'postgresql' in settings.DATABASES['default']['ENGINE'] else 'other'
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        health_data['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
        overall_healthy = False
    
    # Vector store health check
    try:
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
    
    # RAG system configuration check
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
    
    Returns:
        JsonResponse with vector store health details
    """
    try:
        # Create vector store and health monitor
        vector_store = VectorStoreFactory.create_vector_store()
        health_monitor = VectorStoreHealthMonitor()
        
        # Perform comprehensive health check
        health_report = health_monitor.check_health(vector_store)
        
        # Convert health report to JSON-serializable format
        response_data = {
            'status': health_report.overall_status,
            'timestamp': health_report.timestamp.isoformat(),
            'store_type': health_report.store_type,
            'metrics': [
                {
                    'name': metric.name,
                    'value': metric.value,
                    'threshold': metric.threshold,
                    'status': metric.status,
                    'unit': metric.unit,
                    'description': metric.description,
                    'timestamp': metric.timestamp.isoformat()
                }
                for metric in health_report.metrics
            ],
            'errors': health_report.errors,
            'warnings': health_report.warnings,
            'recommendations': health_report.recommendations
        }
        
        # Set HTTP status code based on health
        status_code = 200
        if health_report.overall_status == 'unhealthy':
            status_code = 503
        elif health_report.overall_status == 'degraded':
            status_code = 200  # Still operational but with warnings
        
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
def health_qdrant(request):
    """
    Qdrant-specific health check endpoint.
    
    Returns:
        JsonResponse with detailed Qdrant health information
    """
    try:
        from faq.rag.components.vector_store.qdrant_initializer import QdrantInitializer, QDRANT_AVAILABLE
        from faq.rag.config.settings import rag_config
        
        if not QDRANT_AVAILABLE:
            return JsonResponse({
                'status': 'unavailable',
                'timestamp': datetime.now().isoformat(),
                'error': 'qdrant-client not installed'
            }, status=503)
        
        # Get Qdrant configuration
        config = rag_config.get_vector_config()
        host = config.get('qdrant_host', 'localhost')
        port = config.get('qdrant_port', 6333)
        collection_name = config.get('qdrant_collection_name', 'faq_embeddings')
        
        # Initialize Qdrant client
        initializer = QdrantInitializer(host=host, port=port)
        
        # Perform health check
        health_result = initializer.health_check()
        
        # Get collection statistics if healthy
        collection_stats = {}
        if health_result['status'] == 'healthy':
            try:
                collection_stats = initializer.get_collection_stats(collection_name)
            except Exception as e:
                collection_stats = {'error': str(e)}
        
        # Validate collection configuration
        validation_result = {}
        if health_result['status'] == 'healthy':
            try:
                validation_result = initializer.validate_collection(collection_name)
            except Exception as e:
                validation_result = {'valid': False, 'error': str(e)}
        
        response_data = {
            'status': health_result['status'],
            'timestamp': health_result['timestamp'],
            'server': {
                'host': host,
                'port': port,
                'response_time_ms': health_result.get('response_time_ms', 0),
                'collections_count': health_result.get('collections_count', 0),
                'peer_count': health_result.get('peer_count', 1)
            },
            'collection': {
                'name': collection_name,
                'exists': validation_result.get('valid', False),
                'stats': collection_stats,
                'validation': validation_result
            }
        }
        
        # Add error information if unhealthy
        if health_result['status'] != 'healthy':
            response_data['error'] = health_result.get('error', 'Unknown error')
        
        # Set HTTP status code
        status_code = 200 if health_result['status'] == 'healthy' else 503
        
        return JsonResponse(response_data, status=status_code)
        
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
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
        
        # Vector store readiness (basic check)
        try:
            vector_store = VectorStoreFactory.create_vector_store()
            stats = vector_store.get_vector_stats()
            components['vector_store'] = isinstance(stats, dict)
        except Exception:
            components['vector_store'] = False
            ready = False
        
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


@require_http_methods(["GET"])
@never_cache
def health_embeddings(request):
    """
    Embedding system specific health check.
    
    Returns:
        JsonResponse with embedding system health details
    """
    try:
        from faq.rag.core.factory import rag_factory
        from faq.rag.config.settings import rag_config
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'embedding_config': {
                'type': rag_config.config.embedding_type,
                'model': rag_config.config.local_embedding_model,
                'dimension': rag_config.config.vector_dimension,
                'fallback_enabled': rag_config.config.embedding_fallback_enabled,
                'text_search_fallback': rag_config.config.text_search_fallback_enabled
            },
            'components': {}
        }
        
        overall_healthy = True
        
        # Test vectorizer health
        try:
            rag_system = rag_factory.create_default_system()
            if rag_system.vectorizer:
                vectorizer_health = rag_system.vectorizer.health_check()
                health_data['components']['vectorizer'] = vectorizer_health
                
                if vectorizer_health.get('status') != 'healthy':
                    overall_healthy = False
            else:
                health_data['components']['vectorizer'] = {
                    'status': 'unavailable',
                    'error': 'Vectorizer not initialized'
                }
                overall_healthy = False
                
        except Exception as e:
            logger.error(f"Vectorizer health check failed: {e}")
            health_data['components']['vectorizer'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            overall_healthy = False
        
        # Test embedding generation
        try:
            if rag_system.vectorizer:
                test_text = "This is a test query for embedding generation"
                start_time = datetime.now()
                test_embedding = rag_system.vectorizer.generate_embeddings(test_text)
                generation_time = (datetime.now() - start_time).total_seconds()
                
                health_data['components']['embedding_generation'] = {
                    'status': 'healthy',
                    'test_successful': True,
                    'generation_time_ms': round(generation_time * 1000, 2),
                    'embedding_dimension': len(test_embedding) if test_embedding is not None else 0
                }
            else:
                health_data['components']['embedding_generation'] = {
                    'status': 'unavailable',
                    'test_successful': False,
                    'error': 'Vectorizer not available'
                }
                overall_healthy = False
                
        except Exception as e:
            logger.error(f"Embedding generation test failed: {e}")
            health_data['components']['embedding_generation'] = {
                'status': 'unhealthy',
                'test_successful': False,
                'error': str(e)
            }
            overall_healthy = False
        
        # Test vector store connectivity
        try:
            if rag_system.vector_store:
                vector_health = rag_system.vector_store.health_check()
                health_data['components']['vector_store'] = vector_health
                
                if vector_health.get('status') not in ['healthy', 'degraded']:
                    overall_healthy = False
            else:
                health_data['components']['vector_store'] = {
                    'status': 'unavailable',
                    'error': 'Vector store not initialized'
                }
                overall_healthy = False
                
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            health_data['components']['vector_store'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            overall_healthy = False
        
        # Update overall status
        if not overall_healthy:
            health_data['status'] = 'unhealthy'
        elif any(comp.get('status') == 'degraded' for comp in health_data['components'].values()):
            health_data['status'] = 'degraded'
        
        # Set HTTP status code
        status_code = 200
        if health_data['status'] == 'unhealthy':
            status_code = 503
        elif health_data['status'] == 'degraded':
            status_code = 200  # Still operational but with warnings
        
        return JsonResponse(health_data, status=status_code)
        
    except Exception as e:
        logger.error(f"Embedding health check failed: {e}")
        return JsonResponse({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }, status=503)


@require_http_methods(["POST"])
@never_cache
def regenerate_embeddings(request):
    """
    Endpoint to trigger embedding regeneration for updated FAQs.
    
    Returns:
        JsonResponse with regeneration status
    """
    try:
        from faq.rag.core.factory import rag_factory
        from faq.models import RAGFAQEntry
        import json
        
        # Parse request body for specific FAQ IDs or regenerate all
        request_data = {}
        if request.body:
            try:
                request_data = json.loads(request.body)
            except json.JSONDecodeError:
                pass
        
        faq_ids = request_data.get('faq_ids', [])
        force_regenerate = request_data.get('force', False)
        
        # Initialize RAG system
        rag_system = rag_factory.create_default_system()
        
        if not rag_system.vectorizer or not rag_system.vector_store:
            return JsonResponse({
                'status': 'error',
                'message': 'Embedding system not available'
            }, status=503)
        
        # Get FAQs to regenerate
        if faq_ids:
            faqs_to_regenerate = RAGFAQEntry.objects.filter(rag_id__in=faq_ids)
        else:
            # Regenerate all FAQs if no specific IDs provided
            faqs_to_regenerate = RAGFAQEntry.objects.all()
        
        if not faqs_to_regenerate.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'No FAQs found to regenerate'
            }, status=404)
        
        # Convert Django FAQs to RAG FAQEntry objects
        from faq.rag.interfaces.base import FAQEntry
        
        rag_faqs = []
        for django_faq in faqs_to_regenerate:
            rag_faq = FAQEntry(
                id=django_faq.rag_id,
                question=django_faq.question,
                answer=django_faq.answer,
                category=django_faq.category,
                audience='any',  # Default value
                intent='information',  # Default value
                condition='default',  # Default value
                confidence_score=django_faq.confidence_score,
                keywords=django_faq.keywords.split(', ') if django_faq.keywords else [],
                composite_key=f"{django_faq.category}_{django_faq.rag_id}",
                embedding=None,  # Will be regenerated
                created_at=django_faq.created_at,
                updated_at=django_faq.updated_at
            )
            rag_faqs.append(rag_faq)
        
        # Regenerate embeddings
        start_time = datetime.now()
        regenerated_faqs = rag_system.vectorizer.vectorize_faq_batch(rag_faqs)
        generation_time = (datetime.now() - start_time).total_seconds()
        
        # Store updated embeddings in vector store
        rag_system.vector_store.store_vectors(
            regenerated_faqs,
            document_id='embedding_regeneration',
            document_hash=f"regen_{datetime.now().timestamp()}"
        )
        
        # Update Django models with new embeddings
        updated_count = 0
        for rag_faq in regenerated_faqs:
            if rag_faq.embedding is not None:
                try:
                    django_faq = RAGFAQEntry.objects.get(rag_id=rag_faq.id)
                    django_faq.set_question_embedding_array(rag_faq.embedding)
                    django_faq.save()
                    updated_count += 1
                except RAGFAQEntry.DoesNotExist:
                    logger.warning(f"Django FAQ with rag_id {rag_faq.id} not found")
        
        return JsonResponse({
            'status': 'success',
            'message': f'Successfully regenerated embeddings for {updated_count} FAQs',
            'details': {
                'total_faqs_processed': len(rag_faqs),
                'embeddings_generated': len(regenerated_faqs),
                'django_faqs_updated': updated_count,
                'generation_time_seconds': round(generation_time, 2),
                'force_regenerate': force_regenerate
            }
        })
        
    except Exception as e:
        logger.error(f"Embedding regeneration failed: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Embedding regeneration failed: {str(e)}'
        }, status=500)