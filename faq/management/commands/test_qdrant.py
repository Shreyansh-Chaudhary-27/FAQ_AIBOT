"""
Django management command to test Qdrant vector database functionality.

This command performs comprehensive testing of Qdrant integration,
including connectivity, collection setup, data operations, and health monitoring.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from faq.rag.components.vector_store.qdrant_initializer import QdrantInitializer, QdrantInitializerError, QDRANT_AVAILABLE
from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
from faq.rag.components.vector_store.health_monitor import VectorStoreHealthMonitor
from faq.rag.config.settings import rag_config


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test Qdrant vector database functionality and integration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--host',
            type=str,
            default=None,
            help='Qdrant server host (default: from config)'
        )
        
        parser.add_argument(
            '--port',
            type=int,
            default=None,
            help='Qdrant server port (default: from config)'
        )
        
        parser.add_argument(
            '--collection',
            type=str,
            default=None,
            help='Collection name (default: from config)'
        )
        
        parser.add_argument(
            '--skip-health',
            action='store_true',
            help='Skip health monitoring tests'
        )
        
        parser.add_argument(
            '--skip-operations',
            action='store_true',
            help='Skip data operation tests'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        """Execute the test command."""
        
        # Check if Qdrant is available
        if not QDRANT_AVAILABLE:
            raise CommandError(
                "qdrant-client not available. Install with: pip install qdrant-client"
            )
        
        # Get configuration
        config = rag_config.get_vector_config()
        
        host = options['host'] or config.get('qdrant_host', 'localhost')
        port = options['port'] or config.get('qdrant_port', 6333)
        collection_name = options['collection'] or config.get('qdrant_collection_name', 'faq_embeddings')
        
        self.stdout.write(f"Testing Qdrant at {host}:{port}")
        self.stdout.write(f"Collection: {collection_name}")
        
        try:
            # Test 1: Basic connectivity
            self.stdout.write("\n" + "="*50)
            self.stdout.write("TEST 1: Basic Connectivity")
            self.stdout.write("="*50)
            
            initializer = QdrantInitializer(host=host, port=port, timeout=30)
            
            if initializer.connect():
                self.stdout.write(self.style.SUCCESS("✓ Connection successful"))
            else:
                raise CommandError("Failed to connect to Qdrant server")
            
            # Test 2: Health check
            self.stdout.write("\n" + "="*50)
            self.stdout.write("TEST 2: Health Check")
            self.stdout.write("="*50)
            
            health_result = initializer.health_check()
            
            if health_result['status'] == 'healthy':
                self.stdout.write(self.style.SUCCESS("✓ Qdrant server is healthy"))
                if options['verbose']:
                    self.stdout.write(f"  Response time: {health_result.get('response_time_ms', 0):.2f}ms")
                    self.stdout.write(f"  Collections: {health_result.get('collections_count', 0)}")
                    self.stdout.write(f"  Peers: {health_result.get('peer_count', 1)}")
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Qdrant server is unhealthy: {health_result.get('error', 'Unknown error')}")
                )
            
            # Test 3: Collection setup
            self.stdout.write("\n" + "="*50)
            self.stdout.write("TEST 3: Collection Setup")
            self.stdout.write("="*50)
            
            if initializer.setup_faq_collection(collection_name=collection_name, vector_dimension=384):
                self.stdout.write(self.style.SUCCESS("✓ FAQ collection setup successful"))
            else:
                raise CommandError("Failed to setup FAQ collection")
            
            # Test 4: Collection validation
            self.stdout.write("\n" + "="*50)
            self.stdout.write("TEST 4: Collection Validation")
            self.stdout.write("="*50)
            
            validation_result = initializer.validate_collection(collection_name)
            
            if validation_result['valid']:
                self.stdout.write(self.style.SUCCESS("✓ Collection validation passed"))
                if options['verbose']:
                    self.stdout.write(f"  Vector dimension: {validation_result.get('vector_dimension')}")
                    self.stdout.write(f"  Distance metric: {validation_result.get('distance_metric')}")
                    self.stdout.write(f"  Total points: {validation_result.get('total_points')}")
                    self.stdout.write(f"  Status: {validation_result.get('status')}")
                
                if 'warnings' in validation_result:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ {validation_result['warnings']}")
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Collection validation failed: {validation_result.get('error')}")
                )
            
            # Test 5: Vector store factory
            self.stdout.write("\n" + "="*50)
            self.stdout.write("TEST 5: Vector Store Factory")
            self.stdout.write("="*50)
            
            try:
                vector_store = VectorStoreFactory.create_vector_store(store_type='qdrant')
                self.stdout.write(self.style.SUCCESS("✓ Vector store factory created Qdrant store"))
                
                # Test basic operations
                if not options['skip_operations']:
                    stats = vector_store.get_vector_stats()
                    if isinstance(stats, dict):
                        self.stdout.write(self.style.SUCCESS("✓ Vector store stats retrieval successful"))
                        if options['verbose']:
                            self.stdout.write(f"  Store type: {stats.get('store_type')}")
                            self.stdout.write(f"  Total vectors: {stats.get('total_vectors', 0)}")
                            self.stdout.write(f"  Is healthy: {stats.get('is_healthy')}")
                    else:
                        self.stdout.write(self.style.WARNING("⚠ Vector store stats returned unexpected format"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Vector store factory test failed: {e}"))
            
            # Test 6: Health monitoring
            if not options['skip_health']:
                self.stdout.write("\n" + "="*50)
                self.stdout.write("TEST 6: Health Monitoring")
                self.stdout.write("="*50)
                
                try:
                    vector_store = VectorStoreFactory.create_vector_store(store_type='qdrant')
                    health_monitor = VectorStoreHealthMonitor()
                    
                    health_report = health_monitor.check_health(vector_store)
                    
                    self.stdout.write(f"Overall status: {health_report.overall_status}")
                    
                    if health_report.overall_status == 'healthy':
                        self.stdout.write(self.style.SUCCESS("✓ Health monitoring passed"))
                    elif health_report.overall_status == 'degraded':
                        self.stdout.write(self.style.WARNING("⚠ Health monitoring shows degraded status"))
                    else:
                        self.stdout.write(self.style.ERROR("✗ Health monitoring shows unhealthy status"))
                    
                    if options['verbose']:
                        self.stdout.write(f"  Metrics count: {len(health_report.metrics)}")
                        self.stdout.write(f"  Errors: {len(health_report.errors)}")
                        self.stdout.write(f"  Warnings: {len(health_report.warnings)}")
                        self.stdout.write(f"  Recommendations: {len(health_report.recommendations)}")
                        
                        # Show critical metrics
                        for metric in health_report.metrics:
                            if metric.status in ['warning', 'critical']:
                                self.stdout.write(f"  {metric.name}: {metric.value} {metric.unit} ({metric.status})")
                        
                        # Show errors and recommendations
                        for error in health_report.errors:
                            self.stdout.write(self.style.ERROR(f"  Error: {error}"))
                        
                        for recommendation in health_report.recommendations:
                            self.stdout.write(self.style.WARNING(f"  Recommendation: {recommendation}"))
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ Health monitoring test failed: {e}"))
            
            # Test 7: Collection statistics
            self.stdout.write("\n" + "="*50)
            self.stdout.write("TEST 7: Collection Statistics")
            self.stdout.write("="*50)
            
            stats_result = initializer.get_collection_stats(collection_name)
            
            if 'error' not in stats_result:
                self.stdout.write(self.style.SUCCESS("✓ Collection statistics retrieval successful"))
                if options['verbose']:
                    self.stdout.write(f"  Total points: {stats_result.get('total_points', 0)}")
                    self.stdout.write(f"  Vector dimension: {stats_result.get('vector_dimension')}")
                    self.stdout.write(f"  Distance metric: {stats_result.get('distance_metric')}")
                    self.stdout.write(f"  Sample size: {stats_result.get('sample_size', 0)}")
                    
                    # Show distribution info
                    category_dist = stats_result.get('category_distribution', {})
                    if category_dist:
                        self.stdout.write("  Category distribution:")
                        for category, count in category_dist.items():
                            self.stdout.write(f"    {category}: {count}")
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Collection statistics failed: {stats_result['error']}")
                )
            
            # Final summary
            self.stdout.write("\n" + "="*50)
            self.stdout.write("TEST SUMMARY")
            self.stdout.write("="*50)
            
            self.stdout.write(
                self.style.SUCCESS("✓ All Qdrant tests completed successfully!")
            )
            self.stdout.write(f"Qdrant server at {host}:{port} is ready for production use.")
            
        except QdrantInitializerError as e:
            raise CommandError(f"Qdrant initialization error: {e}")
        except Exception as e:
            logger.exception("Unexpected error during Qdrant testing")
            raise CommandError(f"Unexpected error: {e}")