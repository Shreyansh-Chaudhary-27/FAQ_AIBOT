"""
Django management command to sync existing FAQ data to Qdrant vector database.

This command migrates FAQ data from the Django database to Qdrant,
ensuring embeddings are generated and stored properly for production use.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from faq.models import RAGFAQEntry
from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
from faq.rag.components.vector_store.qdrant_initializer import QdrantInitializer, QDRANT_AVAILABLE
from faq.rag.interfaces.base import FAQEntry
from faq.rag.config.settings import rag_config
from datetime import datetime

# Try to import vectorizer, but make it optional
try:
    from faq.rag.components.vectorizer.vectorizer import FAQVectorizer
    VECTORIZER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Vectorizer not available: {e}")
    VECTORIZER_AVAILABLE = False
    FAQVectorizer = None


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync existing FAQ data from Django database to Qdrant vector database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of FAQs to process in each batch (default: 50)'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync even if FAQs already exist in Qdrant'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing'
        )
        
        parser.add_argument(
            '--validate-only',
            action='store_true',
            help='Only validate Qdrant setup without syncing data'
        )
        
        parser.add_argument(
            '--stats-only',
            action='store_true',
            help='Only show statistics about current data'
        )
    
    def handle(self, *args, **options):
        """Execute the sync command."""
        
        # Check dependencies
        if not QDRANT_AVAILABLE:
            raise CommandError(
                "qdrant-client not available. Install with: pip install qdrant-client"
            )
        
        if not VECTORIZER_AVAILABLE:
            raise CommandError(
                "Vectorizer not available. This may be due to missing dependencies like google-generativeai. "
                "Install required dependencies or use a different sync method."
            )
        
        batch_size = options['batch_size']
        force_sync = options['force']
        dry_run = options['dry_run']
        validate_only = options['validate_only']
        stats_only = options['stats_only']
        
        self.stdout.write("FAQ to Qdrant Sync Tool")
        self.stdout.write("=" * 50)
        
        try:
            # Get configuration
            config = rag_config.get_vector_config()
            host = config.get('qdrant_host', 'localhost')
            port = config.get('qdrant_port', 6333)
            collection_name = config.get('qdrant_collection_name', 'faq_embeddings')
            
            self.stdout.write(f"Qdrant server: {host}:{port}")
            self.stdout.write(f"Collection: {collection_name}")
            self.stdout.write(f"Batch size: {batch_size}")
            
            # Initialize Qdrant
            initializer = QdrantInitializer(host=host, port=port)
            
            # Validate Qdrant setup
            self.stdout.write("\nValidating Qdrant setup...")
            health_result = initializer.health_check()
            
            if health_result['status'] != 'healthy':
                raise CommandError(f"Qdrant server is unhealthy: {health_result.get('error', 'Unknown error')}")
            
            self.stdout.write(self.style.SUCCESS("✓ Qdrant server is healthy"))
            
            # Validate collection
            validation_result = initializer.validate_collection(collection_name)
            if not validation_result['valid']:
                self.stdout.write(self.style.WARNING(f"Collection validation failed: {validation_result.get('error')}"))
                self.stdout.write("Attempting to create collection...")
                
                if not initializer.setup_faq_collection(collection_name):
                    raise CommandError("Failed to create FAQ collection")
                
                self.stdout.write(self.style.SUCCESS("✓ FAQ collection created"))
            else:
                self.stdout.write(self.style.SUCCESS("✓ Collection is valid"))
            
            if validate_only:
                self.stdout.write(self.style.SUCCESS("Validation completed successfully"))
                return
            
            # Get FAQ statistics
            django_faq_count = RAGFAQEntry.objects.count()
            
            # Get Qdrant statistics
            qdrant_stats = initializer.get_collection_stats(collection_name)
            qdrant_faq_count = qdrant_stats.get('total_points', 0) if 'error' not in qdrant_stats else 0
            
            self.stdout.write(f"\nData Statistics:")
            self.stdout.write(f"Django FAQs: {django_faq_count}")
            self.stdout.write(f"Qdrant FAQs: {qdrant_faq_count}")
            
            if stats_only:
                if 'error' not in qdrant_stats:
                    self.stdout.write(f"\nQdrant Collection Details:")
                    self.stdout.write(f"Vector dimension: {qdrant_stats.get('vector_dimension')}")
                    self.stdout.write(f"Distance metric: {qdrant_stats.get('distance_metric')}")
                    
                    # Show distribution
                    category_dist = qdrant_stats.get('category_distribution', {})
                    if category_dist:
                        self.stdout.write("Category distribution:")
                        for category, count in category_dist.items():
                            self.stdout.write(f"  {category}: {count}")
                return
            
            if django_faq_count == 0:
                self.stdout.write(self.style.WARNING("No FAQs found in Django database"))
                return
            
            if not force_sync and qdrant_faq_count > 0:
                self.stdout.write(self.style.WARNING(
                    f"Qdrant already contains {qdrant_faq_count} FAQs. Use --force to re-sync."
                ))
                return
            
            if dry_run:
                self.stdout.write(f"\nDRY RUN: Would sync {django_faq_count} FAQs to Qdrant")
                return
            
            # Create vector store and vectorizer
            self.stdout.write("\nInitializing vector store and vectorizer...")
            vector_store = VectorStoreFactory.create_vector_store(store_type='qdrant')
            vectorizer = FAQVectorizer(use_advanced_matching=True)
            
            # Clear existing data if force sync
            if force_sync and qdrant_faq_count > 0:
                self.stdout.write("Clearing existing Qdrant data...")
                if vector_store.clear_all():
                    self.stdout.write(self.style.SUCCESS("✓ Existing data cleared"))
                else:
                    self.stdout.write(self.style.WARNING("⚠ Failed to clear existing data"))
            
            # Sync FAQs in batches
            self.stdout.write(f"\nSyncing {django_faq_count} FAQs to Qdrant...")
            
            synced_count = 0
            failed_count = 0
            total_batches = (django_faq_count + batch_size - 1) // batch_size
            
            for batch_num in range(0, django_faq_count, batch_size):
                batch_faqs = RAGFAQEntry.objects.all()[batch_num:batch_num + batch_size]
                current_batch = (batch_num // batch_size) + 1
                
                self.stdout.write(f"Processing batch {current_batch}/{total_batches} ({len(batch_faqs)} FAQs)...")
                
                # Convert Django models to FAQEntry objects
                faq_entries = []
                for django_faq in batch_faqs:
                    faq_entry = FAQEntry(
                        id=str(django_faq.id),
                        question=django_faq.question,
                        answer=django_faq.answer,
                        category=django_faq.category,
                        audience=django_faq.audience,
                        intent=django_faq.intent,
                        condition=django_faq.condition,
                        confidence_score=django_faq.confidence_score,
                        keywords=django_faq.keywords or [],
                        composite_key=django_faq.composite_key,
                        embedding=None,  # Will be generated
                        created_at=django_faq.created_at,
                        updated_at=django_faq.updated_at
                    )
                    faq_entries.append(faq_entry)
                
                try:
                    # Generate embeddings
                    self.stdout.write(f"  Generating embeddings for batch {current_batch}...")
                    vectorized_faqs = vectorizer.vectorize_faq_batch(faq_entries)
                    
                    # Store in Qdrant
                    self.stdout.write(f"  Storing batch {current_batch} in Qdrant...")
                    vector_store.store_vectors(
                        vectorized_faqs, 
                        document_id=f"django_sync_batch_{current_batch}",
                        document_hash=f"sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    )
                    
                    synced_count += len(vectorized_faqs)
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Batch {current_batch} completed ({len(vectorized_faqs)} FAQs)"))
                    
                except Exception as e:
                    failed_count += len(faq_entries)
                    self.stdout.write(self.style.ERROR(f"  ✗ Batch {current_batch} failed: {e}"))
                    logger.error(f"Batch {current_batch} sync failed: {e}")
            
            # Final statistics
            self.stdout.write(f"\nSync completed!")
            self.stdout.write(f"Successfully synced: {synced_count} FAQs")
            if failed_count > 0:
                self.stdout.write(self.style.WARNING(f"Failed to sync: {failed_count} FAQs"))
            
            # Validate final state
            self.stdout.write("\nValidating final state...")
            final_stats = initializer.get_collection_stats(collection_name)
            final_count = final_stats.get('total_points', 0) if 'error' not in final_stats else 0
            
            self.stdout.write(f"Final Qdrant FAQ count: {final_count}")
            
            if final_count >= synced_count:
                self.stdout.write(self.style.SUCCESS("✓ Sync validation passed"))
            else:
                self.stdout.write(self.style.WARNING("⚠ Sync validation failed - counts don't match"))
            
            # Test vector store functionality
            self.stdout.write("\nTesting vector store functionality...")
            try:
                health_check = vector_store.health_check()
                if health_check.get('status') == 'healthy':
                    self.stdout.write(self.style.SUCCESS("✓ Vector store health check passed"))
                else:
                    self.stdout.write(self.style.WARNING(f"⚠ Vector store health check failed: {health_check.get('error')}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ Vector store health check error: {e}"))
            
        except Exception as e:
            logger.exception("FAQ sync failed")
            raise CommandError(f"Sync failed: {e}")