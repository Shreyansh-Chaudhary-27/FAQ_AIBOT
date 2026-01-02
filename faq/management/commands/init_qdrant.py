"""
Django management command to initialize Qdrant vector database.

This command sets up Qdrant collections, performs health checks,
and optionally migrates data from local vector stores.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from faq.rag.components.vector_store.qdrant_initializer import QdrantInitializer, QdrantInitializerError, QDRANT_AVAILABLE
from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
from faq.rag.config.settings import rag_config


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Initialize Qdrant vector database for production deployment'
    
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
            '--dimension',
            type=int,
            default=None,
            help='Vector dimension (default: from config)'
        )
        
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Recreate collection if it already exists'
        )
        
        parser.add_argument(
            '--migrate',
            action='store_true',
            help='Migrate data from local vector store'
        )
        
        parser.add_argument(
            '--local-store-path',
            type=str,
            default=None,
            help='Path to local vector store data (default: from config)'
        )
        
        parser.add_argument(
            '--health-check-only',
            action='store_true',
            help='Only perform health check, do not initialize'
        )
        
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate existing collection configuration'
        )
        
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show collection statistics'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        
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
        vector_dimension = options['dimension'] or config.get('dimension', 384)
        local_store_path = options['local_store_path'] or rag_config.config.vector_store_path
        
        self.stdout.write(f"Initializing Qdrant at {host}:{port}")
        self.stdout.write(f"Collection: {collection_name}")
        self.stdout.write(f"Vector dimension: {vector_dimension}")
        
        try:
            # Initialize Qdrant
            initializer = QdrantInitializer(
                host=host,
                port=port,
                timeout=30
            )
            
            # Perform health check
            self.stdout.write("Performing health check...")
            health_result = initializer.health_check()
            
            if health_result['status'] == 'healthy':
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Qdrant server is healthy")
                )
                self.stdout.write(f"  Response time: {health_result.get('response_time_ms', 0):.2f}ms")
                self.stdout.write(f"  Collections: {health_result.get('collections_count', 0)}")
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Qdrant server is unhealthy: {health_result.get('error', 'Unknown error')}")
                )
                if not options['health_check_only']:
                    raise CommandError("Cannot proceed with unhealthy Qdrant server")
            
            # If only health check requested, stop here
            if options['health_check_only']:
                return
            
            # Validate existing collection if requested
            if options['validate']:
                self.stdout.write(f"Validating collection: {collection_name}")
                validation_result = initializer.validate_collection(collection_name)
                
                if validation_result['valid']:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Collection {collection_name} is valid")
                    )
                    self.stdout.write(f"  Vector dimension: {validation_result.get('vector_dimension')}")
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
            
            # Show collection statistics if requested
            if options['stats']:
                self.stdout.write(f"Getting statistics for collection: {collection_name}")
                stats_result = initializer.get_collection_stats(collection_name)
                
                if 'error' not in stats_result:
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Collection statistics:")
                    )
                    self.stdout.write(f"  Total points: {stats_result.get('total_points', 0)}")
                    self.stdout.write(f"  Vector dimension: {stats_result.get('vector_dimension')}")
                    self.stdout.write(f"  Distance metric: {stats_result.get('distance_metric')}")
                    self.stdout.write(f"  Status: {stats_result.get('status')}")
                    
                    # Show distribution info
                    category_dist = stats_result.get('category_distribution', {})
                    if category_dist:
                        self.stdout.write("  Category distribution:")
                        for category, count in category_dist.items():
                            self.stdout.write(f"    {category}: {count}")
                    
                    audience_dist = stats_result.get('audience_distribution', {})
                    if audience_dist:
                        self.stdout.write("  Audience distribution:")
                        for audience, count in audience_dist.items():
                            self.stdout.write(f"    {audience}: {count}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Failed to get statistics: {stats_result['error']}")
                    )
            
            # Setup FAQ collection
            self.stdout.write(f"Setting up FAQ collection: {collection_name}")
            
            if initializer.setup_faq_collection(
                collection_name=collection_name,
                vector_dimension=vector_dimension
            ):
                self.stdout.write(
                    self.style.SUCCESS(f"✓ FAQ collection setup completed")
                )
            else:
                raise CommandError("Failed to setup FAQ collection")
            
            # Migrate data if requested
            if options['migrate']:
                self.stdout.write(f"Migrating data from local store: {local_store_path}")
                
                migration_result = initializer.migrate_from_local_store(
                    local_store_path=local_store_path,
                    collection_name=collection_name,
                    batch_size=100
                )
                
                if migration_result['success']:
                    migrated_count = migration_result['migrated_count']
                    total_found = migration_result.get('total_found', migrated_count)
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ Migration completed")
                    )
                    self.stdout.write(f"  Migrated: {migrated_count}/{total_found} vectors")
                    
                    if migrated_count != total_found:
                        self.stdout.write(
                            self.style.WARNING(f"⚠ Some vectors were skipped (missing embeddings)")
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Migration failed: {migration_result.get('error')}")
                    )
                    raise CommandError("Data migration failed")
            
            # Final validation
            self.stdout.write("Performing final validation...")
            final_validation = initializer.validate_collection(collection_name)
            
            if final_validation['valid']:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Qdrant initialization completed successfully")
                )
                self.stdout.write(f"  Collection: {collection_name}")
                self.stdout.write(f"  Total points: {final_validation.get('total_points', 0)}")
                self.stdout.write(f"  Vector dimension: {final_validation.get('vector_dimension')}")
                
                # Test vector store factory
                self.stdout.write("Testing vector store factory...")
                try:
                    store = VectorStoreFactory.create_vector_store(store_type='qdrant')
                    store_health = store.health_check()
                    
                    if store_health.get('status') == 'healthy':
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ Vector store factory test passed")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"⚠ Vector store factory test failed: {store_health.get('error')}")
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ Vector store factory test failed: {e}")
                    )
                
            else:
                raise CommandError(f"Final validation failed: {final_validation.get('error')}")
            
        except QdrantInitializerError as e:
            raise CommandError(f"Qdrant initialization error: {e}")
        except Exception as e:
            logger.exception("Unexpected error during Qdrant initialization")
            raise CommandError(f"Unexpected error: {e}")