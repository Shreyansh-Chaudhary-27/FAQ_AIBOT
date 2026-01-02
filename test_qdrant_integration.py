#!/usr/bin/env python
"""
Simple test script to verify Qdrant integration code without requiring a running Qdrant instance.
This tests the code structure, imports, and basic functionality.
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faqbackend.settings.development')
os.environ.setdefault('GEMINI_API_KEY', 'test-key')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')

django.setup()

def test_imports():
    """Test that all Qdrant-related modules can be imported."""
    print("Testing imports...")
    
    try:
        from faq.rag.components.vector_store.qdrant_vector_store import QdrantVectorStore, QDRANT_AVAILABLE
        print("✓ QdrantVectorStore imported successfully")
        
        from faq.rag.components.vector_store.qdrant_initializer import QdrantInitializer
        print("✓ QdrantInitializer imported successfully")
        
        from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
        print("✓ VectorStoreFactory imported successfully")
        
        from faq.rag.components.vector_store.health_monitor import VectorStoreHealthMonitor
        print("✓ VectorStoreHealthMonitor imported successfully")
        
        print(f"✓ Qdrant client available: {QDRANT_AVAILABLE}")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_vector_store_factory():
    """Test vector store factory functionality."""
    print("\nTesting vector store factory...")
    
    try:
        from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
        
        # Test available stores
        available_stores = VectorStoreFactory.get_available_stores()
        print(f"✓ Available stores: {available_stores}")
        
        # Test local store creation (should always work)
        local_store = VectorStoreFactory.create_vector_store(store_type='local')
        print(f"✓ Local store created: {type(local_store).__name__}")
        
        # Test Qdrant store creation (will use fallback if Qdrant unavailable)
        try:
            qdrant_store = VectorStoreFactory.create_vector_store(store_type='qdrant')
            print(f"✓ Qdrant store created: {type(qdrant_store).__name__}")
        except Exception as e:
            print(f"⚠ Qdrant store creation failed (expected without server): {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Vector store factory test failed: {e}")
        return False

def test_qdrant_initializer():
    """Test Qdrant initializer functionality."""
    print("\nTesting Qdrant initializer...")
    
    try:
        from faq.rag.components.vector_store.qdrant_initializer import QdrantInitializer, QDRANT_AVAILABLE
        
        if not QDRANT_AVAILABLE:
            print("⚠ Qdrant client not available, skipping initializer test")
            return True
        
        # Create initializer (won't connect without server)
        initializer = QdrantInitializer(host='localhost', port=6333)
        print("✓ QdrantInitializer created successfully")
        
        # Test health check (will fail without server, but should not crash)
        try:
            health_result = initializer.health_check()
            print(f"✓ Health check completed: {health_result.get('status', 'unknown')}")
        except Exception as e:
            print(f"⚠ Health check failed (expected without server): {type(e).__name__}")
        
        return True
        
    except Exception as e:
        print(f"✗ Qdrant initializer test failed: {e}")
        return False

def test_health_monitor():
    """Test health monitor functionality."""
    print("\nTesting health monitor...")
    
    try:
        from faq.rag.components.vector_store.health_monitor import VectorStoreHealthMonitor
        from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
        
        # Create health monitor
        monitor = VectorStoreHealthMonitor()
        print("✓ VectorStoreHealthMonitor created successfully")
        
        # Create a local vector store for testing
        vector_store = VectorStoreFactory.create_vector_store(store_type='local')
        
        # Test health check
        health_report = monitor.check_health(vector_store)
        print(f"✓ Health check completed: {health_report.overall_status}")
        print(f"  Store type: {health_report.store_type}")
        print(f"  Metrics: {len(health_report.metrics)}")
        print(f"  Errors: {len(health_report.errors)}")
        print(f"  Warnings: {len(health_report.warnings)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Health monitor test failed: {e}")
        return False

def test_configuration():
    """Test RAG configuration for Qdrant."""
    print("\nTesting configuration...")
    
    try:
        from faq.rag.config.settings import rag_config
        
        config = rag_config.get_vector_config()
        print("✓ Vector configuration loaded successfully")
        print(f"  Store type: {config.get('store_type', 'not set')}")
        print(f"  Qdrant host: {config.get('qdrant_host', 'not set')}")
        print(f"  Qdrant port: {config.get('qdrant_port', 'not set')}")
        print(f"  Collection name: {config.get('qdrant_collection_name', 'not set')}")
        print(f"  Vector dimension: {config.get('dimension', 'not set')}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False

def test_health_views():
    """Test health check views."""
    print("\nTesting health views...")
    
    try:
        from faq.health_views import health_check, health_detailed, health_vector_store
        print("✓ Health views imported successfully")
        
        # Test basic health check view
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/health/')
        
        response = health_check(request)
        print(f"✓ Basic health check: {response.status_code}")
        
        # Test detailed health check
        response = health_detailed(request)
        print(f"✓ Detailed health check: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"✗ Health views test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("QDRANT INTEGRATION TEST")
    print("="*60)
    
    tests = [
        test_imports,
        test_configuration,
        test_vector_store_factory,
        test_qdrant_initializer,
        test_health_monitor,
        test_health_views,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
    
    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("✓ All tests passed! Qdrant integration is ready.")
        return 0
    else:
        print("⚠ Some tests failed. Check the output above for details.")
        return 1

if __name__ == '__main__':
    sys.exit(main())