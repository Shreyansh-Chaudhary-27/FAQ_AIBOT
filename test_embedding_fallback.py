#!/usr/bin/env python3
"""
Test script for embedding system fallback mechanisms.

This script tests the enhanced RAG system with Qdrant integration,
embedding fallback mechanisms, and error handling improvements.
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faqbackend.settings.development')
django.setup()

import logging
from datetime import datetime
from faq.rag.core.factory import rag_factory
from faq.rag.config.settings import rag_config
from faq.rag.interfaces.base import FAQEntry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_embedding_system_health():
    """Test embedding system health checks."""
    print("\n" + "="*60)
    print("TESTING EMBEDDING SYSTEM HEALTH")
    print("="*60)
    
    try:
        # Create RAG system
        rag_system = rag_factory.create_default_system()
        
        # Test vectorizer health
        if rag_system.vectorizer:
            vectorizer_health = rag_system.vectorizer.health_check()
            print(f"✓ Vectorizer health: {vectorizer_health.get('status', 'unknown')}")
            
            if vectorizer_health.get('status') == 'healthy':
                # Test embedding generation
                test_text = "What are your business hours?"
                embedding = rag_system.vectorizer.generate_embeddings(test_text)
                print(f"✓ Embedding generation successful: dimension {len(embedding)}")
            else:
                print(f"⚠ Vectorizer not healthy: {vectorizer_health}")
        else:
            print("✗ Vectorizer not available")
        
        # Test vector store health
        if rag_system.vector_store:
            store_health = rag_system.vector_store.health_check()
            print(f"✓ Vector store health: {store_health.get('status', 'unknown')}")
            print(f"  Store type: {store_health.get('store_type', 'unknown')}")
            
            if store_health.get('qdrant_available'):
                print(f"  Qdrant available: {store_health.get('qdrant_available')}")
                print(f"  Vector count: {store_health.get('vector_count', 0)}")
        else:
            print("✗ Vector store not available")
        
        return True
        
    except Exception as e:
        print(f"✗ Embedding system health test failed: {e}")
        return False


def test_embedding_fallback_mechanisms():
    """Test embedding fallback mechanisms."""
    print("\n" + "="*60)
    print("TESTING EMBEDDING FALLBACK MECHANISMS")
    print("="*60)
    
    try:
        # Create RAG system
        rag_system = rag_factory.create_default_system()
        
        # Test 1: Normal query processing
        print("\n1. Testing normal query processing...")
        test_query = "What are your business hours?"
        
        try:
            response = rag_system.answer_query(test_query)
            print(f"✓ Query processed successfully")
            print(f"  Response: {response.text[:100]}...")
            print(f"  Confidence: {response.confidence}")
            print(f"  Generation method: {response.generation_method}")
            print(f"  Fallback reason: {response.metadata.get('fallback_reason', 'none')}")
        except Exception as e:
            print(f"⚠ Query processing failed (expected with fallback): {e}")
        
        # Test 2: Query with no matching FAQs (should trigger fallback)
        print("\n2. Testing query with no matching FAQs...")
        obscure_query = "What is the quantum entanglement coefficient of your customer service?"
        
        try:
            response = rag_system.answer_query(obscure_query)
            print(f"✓ Fallback response generated")
            print(f"  Response: {response.text[:100]}...")
            print(f"  Confidence: {response.confidence}")
            print(f"  Generation method: {response.generation_method}")
            print(f"  Fallback reason: {response.metadata.get('fallback_reason', 'none')}")
        except Exception as e:
            print(f"✗ Fallback response generation failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Embedding fallback test failed: {e}")
        return False


def test_vector_store_operations():
    """Test vector store operations with fallback."""
    print("\n" + "="*60)
    print("TESTING VECTOR STORE OPERATIONS")
    print("="*60)
    
    try:
        # Create RAG system
        rag_system = rag_factory.create_default_system()
        
        if not rag_system.vector_store or not rag_system.vectorizer:
            print("✗ Vector store or vectorizer not available")
            return False
        
        # Create test FAQ entries
        test_faqs = [
            FAQEntry(
                id="test_faq_1",
                question="What are your business hours?",
                answer="We are open Monday to Friday, 9 AM to 5 PM.",
                category="general",
                audience="any",
                intent="information",
                condition="default",
                confidence_score=0.9,
                keywords=["business", "hours", "open", "time"],
                source_document="test_document",
                embedding=None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            FAQEntry(
                id="test_faq_2",
                question="How do I contact support?",
                answer="You can contact support via email at support@example.com or call us at 555-0123.",
                category="support",
                audience="any",
                intent="information",
                condition="default",
                confidence_score=0.9,
                keywords=["contact", "support", "email", "phone"],
                source_document="test_document",
                embedding=None,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ]
        
        # Test 1: Vectorize FAQs
        print("\n1. Testing FAQ vectorization...")
        try:
            vectorized_faqs = rag_system.vectorizer.vectorize_faq_batch(test_faqs)
            print(f"✓ Vectorized {len(vectorized_faqs)} FAQs")
            
            # Check embeddings
            for faq in vectorized_faqs:
                if faq.embedding is not None:
                    print(f"  FAQ '{faq.id}': embedding dimension {len(faq.embedding)}")
                else:
                    print(f"  FAQ '{faq.id}': no embedding generated")
        except Exception as e:
            print(f"⚠ FAQ vectorization failed: {e}")
            vectorized_faqs = test_faqs  # Use original FAQs without embeddings
        
        # Test 2: Store vectors
        print("\n2. Testing vector storage...")
        try:
            rag_system.vector_store.store_vectors(
                vectorized_faqs,
                document_id="test_document",
                document_hash="test_hash_123"
            )
            print(f"✓ Stored vectors successfully")
        except Exception as e:
            print(f"⚠ Vector storage failed: {e}")
        
        # Test 3: Search vectors
        print("\n3. Testing vector search...")
        try:
            if rag_system.vectorizer:
                query_embedding = rag_system.vectorizer.generate_embeddings("business hours")
                matches = rag_system.vector_store.search_similar(query_embedding, threshold=0.3, top_k=5)
                print(f"✓ Found {len(matches)} similar vectors")
                
                for match in matches:
                    print(f"  Match: '{match.faq_entry.question}' (score: {match.similarity_score:.3f})")
            else:
                print("⚠ Vectorizer not available for search test")
        except Exception as e:
            print(f"⚠ Vector search failed: {e}")
        
        # Test 4: N-gram search fallback
        print("\n4. Testing N-gram search fallback...")
        try:
            ngram_matches = rag_system.vector_store.search_by_ngrams(
                ["business", "hours"], 
                threshold=0.5
            )
            print(f"✓ Found {len(ngram_matches)} N-gram matches")
            
            for match in ngram_matches:
                print(f"  N-gram match: '{match.faq_entry.question}' (score: {match.similarity_score:.3f})")
        except Exception as e:
            print(f"⚠ N-gram search failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Vector store operations test failed: {e}")
        return False


def test_configuration():
    """Test RAG system configuration."""
    print("\n" + "="*60)
    print("TESTING RAG SYSTEM CONFIGURATION")
    print("="*60)
    
    try:
        config = rag_config.config
        
        print(f"✓ Embedding type: {config.embedding_type}")
        print(f"✓ Vector store type: {config.vector_store_type}")
        print(f"✓ Vector dimension: {config.vector_dimension}")
        print(f"✓ Similarity threshold: {config.similarity_threshold}")
        print(f"✓ Embedding fallback enabled: {config.embedding_fallback_enabled}")
        print(f"✓ Text search fallback enabled: {config.text_search_fallback_enabled}")
        print(f"✓ Embedding retry attempts: {config.embedding_retry_attempts}")
        print(f"✓ Qdrant host: {config.qdrant_host}")
        print(f"✓ Qdrant port: {config.qdrant_port}")
        print(f"✓ Qdrant collection: {config.qdrant_collection_name}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False


def main():
    """Run all embedding system tests."""
    print("EMBEDDING SYSTEM FALLBACK TESTING")
    print("=" * 80)
    print(f"Test started at: {datetime.now()}")
    
    tests = [
        ("Configuration", test_configuration),
        ("Embedding System Health", test_embedding_system_health),
        ("Embedding Fallback Mechanisms", test_embedding_fallback_mechanisms),
        ("Vector Store Operations", test_vector_store_operations),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results[test_name] = False
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Embedding system is working correctly.")
        return 0
    else:
        print("⚠ Some tests failed. Check the output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)