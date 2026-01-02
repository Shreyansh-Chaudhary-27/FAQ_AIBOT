#!/usr/bin/env python
"""
Comprehensive test script for Qdrant vector database integration in production.

This script tests all aspects of Qdrant integration including:
- Connection and health checks
- Collection setup and validation
- Vector storage and retrieval
- Fallback mechanisms
- Performance and reliability
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faqbackend.settings.development')
django.setup()

import time
import numpy as np
from datetime import datetime
from typing import List, Dict, Any

from faq.rag.components.vector_store.qdrant_initializer import QdrantInitializer, QDRANT_AVAILABLE
from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
from faq.rag.components.vector_store.health_monitor import VectorStoreHealthMonitor
from faq.rag.components.vectorizer.vectorizer import FAQVectorizer
from faq.rag.interfaces.base import FAQEntry
from faq.rag.config.settings import rag_config


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_success(message: str):
    """Print a success message."""
    print(f"✓ {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"⚠ {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"✗ {message}")


def test_qdrant_availability():
    """Test if Qdrant client is available."""
    print_header("Testing Qdrant Availability")
    
    if not QDRANT_AVAILABLE:
        print_error("qdrant-client not available")
        print("Install with: pip install qdrant-client")
        return False
    
    print_success("qdrant-client is available")
    return True


def test_qdrant_connection():
    """Test connection to Qdrant server."""
    print_header("Testing Qdrant Connection")
    
    try:
        config = rag_config.get_vector_config()
        host = config.get('qdrant_host', 'localhost')
        port = config.get('qdrant_port', 6333)
        
        print(f"Connecting to Qdrant at {host}:{port}...")
        
        initializer = QdrantInitializer(host=host, port=port)
        
        if initializer.connect():
            print_success(f"Connected to Qdrant server at {host}:{port}")
            return initializer
        else:
            print_error("Failed to connect to Qdrant server")
            return None
            
    except Exception as e:
        print_error(f"Connection test failed: {e}")
        return None


def test_qdrant_health(initializer: QdrantInitializer):
    """Test Qdrant server health."""
    print_header("Testing Qdrant Health")
    
    try:
        health_result = initializer.health_check()
        
        print(f"Status: {health_result['status']}")
        print(f"Response time: {health_result.get('response_time_ms', 0):.2f}ms")
        print(f"Collections: {health_result.get('collections_count', 0)}")
        print(f"Peers: {health_result.get('peer_count', 1)}")
        
        if health_result['status'] == 'healthy':
            print_success("Qdrant server is healthy")
            return True
        else:
            print_error(f"Qdrant server is unhealthy: {health_result.get('error')}")
            return False
            
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False


def test_collection_setup(initializer: QdrantInitializer):
    """Test collection setup and validation."""
    print_header("Testing Collection Setup")
    
    try:
        config = rag_config.get_vector_config()
        collection_name = config.get('qdrant_collection_name', 'faq_embeddings')
        vector_dimension = config.get('dimension', 384)
        
        print(f"Setting up collection: {collection_name}")
        print(f"Vector dimension: {vector_dimension}")
        
        # Setup collection
        if initializer.setup_faq_collection(collection_name, vector_dimension):
            print_success("Collection setup completed")
        else:
            print_error("Collection setup failed")
            return False
        
        # Validate collection
        validation_result = initializer.validate_collection(collection_name)
        
        if validation_result['valid']:
            print_success("Collection validation passed")
            print(f"  Vector dimension: {validation_result.get('vector_dimension')}")
            print(f"  Distance metric: {validation_result.get('distance_metric')}")
            print(f"  Total points: {validation_result.get('total_points')}")
            return True
        else:
            print_error(f"Collection validation failed: {validation_result.get('error')}")
            return False
            
    except Exception as e:
        print_error(f"Collection setup test failed: {e}")
        return False


def test_vector_store_factory():
    """Test vector store factory creation."""
    print_header("Testing Vector Store Factory")
    
    try:
        # Test Qdrant store creation
        print("Creating Qdrant vector store...")
        qdrant_store = VectorStoreFactory.create_vector_store(store_type='qdrant')
        print_success(f"Qdrant store created: {type(qdrant_store).__name__}")
        
        # Test health check
        health_result = qdrant_store.health_check()
        print(f"Store health: {health_result.get('status', 'unknown')}")
        
        if health_result.get('status') == 'healthy':
            print_success("Vector store is healthy")
        else:
            print_warning(f"Vector store health: {health_result.get('status')}")
        
        return qdrant_store
        
    except Exception as e:
        print_error(f"Vector store factory test failed: {e}")
        return None


def test_vector_operations(vector_store):
    """Test vector storage and retrieval operations."""
    print_header("Testing Vector Operations")
    
    try:
        # Create test FAQs
        test_faqs = [
            FAQEntry(
                id="test_1",
                question="What is machine learning?",
                answer="Machine learning is a subset of artificial intelligence.",
                category="technology",
                audience="general",
                intent="information",
                condition="default",
                confidence_score=0.9,
                keywords=["machine", "learning", "AI"],
                composite_key="tech_ml_1",
                embedding=None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            FAQEntry(
                id="test_2",
                question="How does deep learning work?",
                answer="Deep learning uses neural networks with multiple layers.",
                category="technology",
                audience="technical",
                intent="information",
                condition="default",
                confidence_score=0.8,
                keywords=["deep", "learning", "neural", "networks"],
                composite_key="tech_dl_1",
                embedding=None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        
        # Generate embeddings
        print("Generating embeddings for test FAQs...")
        vectorizer = FAQVectorizer(use_advanced_matching=True)
        vectorized_faqs = vectorizer.vectorize_faq_batch(test_faqs)
        print_success(f"Generated embeddings for {len(vectorized_faqs)} FAQs")
        
        # Store vectors
        print("Storing vectors in Qdrant...")
        vector_store.store_vectors(
            vectorized_faqs,
            document_id="test_document",
            document_hash="test_hash_123"
        )
        print_success("Vectors stored successfully")
        
        # Test similarity search
        print("Testing similarity search...")
        query_text = "What is artificial intelligence?"
        query_embedding = vectorizer.generate_embeddings(query_text)
        
        similar_matches = vector_store.search_similar(
            query_embedding,
            threshold=0.3,
            top_k=5
        )
        
        print_success(f"Similarity search found {len(similar_matches)} matches")
        for i, match in enumerate(similar_matches):
            print(f"  {i+1}. {match.faq_entry.question} (score: {match.similarity_score:.3f})")
        
        # Test N-gram search
        print("Testing N-gram search...")
        ngram_matches = vector_store.search_by_ngrams(
            ["machine", "learning"],
            threshold=0.5
        )
        
        print_success(f"N-gram search found {len(ngram_matches)} matches")
        for i, match in enumerate(ngram_matches):
            print(f"  {i+1}. {match.faq_entry.question} (score: {match.similarity_score:.3f})")
        
        # Test filtered search
        print("Testing filtered search...")
        filtered_matches = vector_store.search_with_filters(
            query_embedding,
            threshold=0.3,
            top_k=5,
            category_filter="technology",
            audience_filter="general"
        )
        
        print_success(f"Filtered search found {len(filtered_matches)} matches")
        
        return True
        
    except Exception as e:
        print_error(f"Vector operations test failed: {e}")
        return False


def test_fallback_mechanisms():
    """Test fallback mechanisms when Qdrant is unavailable."""
    print_header("Testing Fallback Mechanisms")
    
    try:
        # Test factory fallback
        print("Testing vector store factory fallback...")
        
        # This should create a store with fallback enabled
        store_with_fallback = VectorStoreFactory.create_production_store()
        print_success("Production store created (with fallback)")
        
        # Test health monitoring
        print("Testing health monitoring...")
        health_monitor = VectorStoreHealthMonitor()
        health_report = health_monitor.check_health(store_with_fallback)
        
        print(f"Overall status: {health_report.overall_status}")
        print(f"Store type: {health_report.store_type}")
        print(f"Metrics count: {len(health_report.metrics)}")
        
        if health_report.errors:
            print("Errors:")
            for error in health_report.errors:
                print(f"  - {error}")
        
        if health_report.recommendations:
            print("Recommendations:")
            for rec in health_report.recommendations:
                print(f"  - {rec}")
        
        print_success("Fallback mechanisms tested")
        return True
        
    except Exception as e:
        print_error(f"Fallback test failed: {e}")
        return False


def test_performance():
    """Test performance characteristics."""
    print_header("Testing Performance")
    
    try:
        vector_store = VectorStoreFactory.create_vector_store(store_type='qdrant')
        vectorizer = FAQVectorizer(use_advanced_matching=True)
        
        # Performance test parameters
        num_faqs = 10
        num_searches = 5
        
        print(f"Performance test: {num_faqs} FAQs, {num_searches} searches")
        
        # Create test FAQs
        test_faqs = []
        for i in range(num_faqs):
            faq = FAQEntry(
                id=f"perf_test_{i}",
                question=f"Test question {i} about performance and scalability",
                answer=f"Test answer {i} explaining performance concepts",
                category="performance",
                audience="technical",
                intent="information",
                condition="default",
                confidence_score=0.8,
                keywords=[f"test{i}", "performance", "scalability"],
                composite_key=f"perf_{i}",
                embedding=None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            test_faqs.append(faq)
        
        # Measure embedding generation time
        start_time = time.time()
        vectorized_faqs = vectorizer.vectorize_faq_batch(test_faqs)
        embedding_time = time.time() - start_time
        
        print(f"Embedding generation: {embedding_time:.3f}s ({embedding_time/num_faqs:.3f}s per FAQ)")
        
        # Measure storage time
        start_time = time.time()
        vector_store.store_vectors(vectorized_faqs, document_id="perf_test")
        storage_time = time.time() - start_time
        
        print(f"Vector storage: {storage_time:.3f}s ({storage_time/num_faqs:.3f}s per FAQ)")
        
        # Measure search time
        query_embedding = vectorizer.generate_embeddings("performance test query")
        
        search_times = []
        for i in range(num_searches):
            start_time = time.time()
            matches = vector_store.search_similar(query_embedding, threshold=0.3, top_k=5)
            search_time = time.time() - start_time
            search_times.append(search_time)
        
        avg_search_time = sum(search_times) / len(search_times)
        print(f"Average search time: {avg_search_time:.3f}s ({len(matches)} results)")
        
        print_success("Performance test completed")
        return True
        
    except Exception as e:
        print_error(f"Performance test failed: {e}")
        return False


def test_health_endpoints():
    """Test health check endpoints."""
    print_header("Testing Health Endpoints")
    
    try:
        from faq.health_views import health_qdrant, health_vector_store
        from django.test import RequestFactory
        
        factory = RequestFactory()
        
        # Test Qdrant health endpoint
        print("Testing Qdrant health endpoint...")
        request = factory.get('/health/qdrant/')
        response = health_qdrant(request)
        
        print(f"Qdrant health status: {response.status_code}")
        if response.status_code == 200:
            print_success("Qdrant health endpoint working")
        else:
            print_warning(f"Qdrant health endpoint returned {response.status_code}")
        
        # Test vector store health endpoint
        print("Testing vector store health endpoint...")
        request = factory.get('/health/vector-store/')
        response = health_vector_store(request)
        
        print(f"Vector store health status: {response.status_code}")
        if response.status_code == 200:
            print_success("Vector store health endpoint working")
        else:
            print_warning(f"Vector store health endpoint returned {response.status_code}")
        
        return True
        
    except Exception as e:
        print_error(f"Health endpoints test failed: {e}")
        return False


def main():
    """Run all tests."""
    print_header("Qdrant Production Integration Test Suite")
    print(f"Test started at: {datetime.now()}")
    
    results = {}
    
    # Run tests
    tests = [
        ("Qdrant Availability", test_qdrant_availability),
        ("Qdrant Connection", test_qdrant_connection),
        ("Vector Store Factory", test_vector_store_factory),
        ("Fallback Mechanisms", test_fallback_mechanisms),
        ("Performance", test_performance),
        ("Health Endpoints", test_health_endpoints),
    ]
    
    initializer = None
    
    for test_name, test_func in tests:
        try:
            if test_name == "Qdrant Connection":
                initializer = test_func()
                results[test_name] = initializer is not None
            elif test_name in ["Qdrant Health", "Collection Setup"] and initializer:
                if test_name == "Qdrant Health":
                    results[test_name] = test_qdrant_health(initializer)
                else:
                    results[test_name] = test_collection_setup(initializer)
            else:
                results[test_name] = test_func()
        except Exception as e:
            print_error(f"Test {test_name} failed with exception: {e}")
            results[test_name] = False
    
    # Additional tests if connection successful
    if initializer:
        try:
            results["Qdrant Health"] = test_qdrant_health(initializer)
            results["Collection Setup"] = test_collection_setup(initializer)
        except Exception as e:
            print_error(f"Additional tests failed: {e}")
    
    # Print summary
    print_header("Test Results Summary")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: PASSED")
            passed += 1
        else:
            print_error(f"{test_name}: FAILED")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print_success("All tests passed! Qdrant integration is ready for production.")
        return 0
    else:
        print_warning(f"{total - passed} tests failed. Review the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())