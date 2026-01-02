#!/usr/bin/env python
"""
Simple test script for Qdrant vector database integration.

This script tests basic Qdrant functionality without requiring
the full RAG system dependencies.
"""

import sys
import time
import numpy as np
from datetime import datetime

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

def test_qdrant_client():
    """Test Qdrant client availability and basic functionality."""
    print_header("Testing Qdrant Client")
    
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
        print_success("qdrant-client imported successfully")
        
        # Test connection to localhost (if available)
        try:
            client = QdrantClient(host="localhost", port=6333, timeout=5)
            collections = client.get_collections()
            print_success(f"Connected to Qdrant server (found {len(collections.collections)} collections)")
            return client
        except Exception as e:
            print_warning(f"Could not connect to Qdrant server: {e}")
            print("This is expected if Qdrant is not running locally")
            return None
            
    except ImportError as e:
        print_error(f"qdrant-client not available: {e}")
        print("Install with: pip install qdrant-client")
        return None

def test_collection_operations(client):
    """Test collection creation and management."""
    if not client:
        print_warning("Skipping collection tests - no client available")
        return False
        
    print_header("Testing Collection Operations")
    
    try:
        collection_name = "test_faq_embeddings"
        vector_dimension = 384
        
        # Check if collection exists
        collections = client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if collection_name in collection_names:
            print(f"Collection {collection_name} already exists, deleting...")
            client.delete_collection(collection_name)
        
        # Create collection
        print(f"Creating collection: {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_dimension,
                distance=models.Distance.COSINE
            )
        )
        print_success("Collection created successfully")
        
        # Verify collection
        collection_info = client.get_collection(collection_name)
        print(f"Collection info: {collection_info.points_count} points, "
              f"{collection_info.config.params.vectors.size}D vectors")
        
        return True
        
    except Exception as e:
        print_error(f"Collection operations failed: {e}")
        return False

def test_vector_operations(client):
    """Test vector storage and search operations."""
    if not client:
        print_warning("Skipping vector tests - no client available")
        return False
        
    print_header("Testing Vector Operations")
    
    try:
        collection_name = "test_faq_embeddings"
        
        # Create test vectors
        test_points = []
        for i in range(5):
            vector = np.random.rand(384).astype(float).tolist()
            point = models.PointStruct(
                id=i,
                vector=vector,
                payload={
                    'question': f'Test question {i}',
                    'answer': f'Test answer {i}',
                    'category': 'test',
                    'created_at': datetime.now().isoformat()
                }
            )
            test_points.append(point)
        
        # Insert vectors
        print("Inserting test vectors...")
        client.upsert(
            collection_name=collection_name,
            points=test_points
        )
        print_success(f"Inserted {len(test_points)} vectors")
        
        # Wait a moment for indexing
        time.sleep(1)
        
        # Test search
        print("Testing similarity search...")
        query_vector = np.random.rand(384).astype(float).tolist()
        
        search_result = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3,
            with_payload=True
        )
        
        print_success(f"Search returned {len(search_result)} results")
        for i, result in enumerate(search_result):
            print(f"  {i+1}. {result.payload['question']} (score: {result.score:.3f})")
        
        # Test retrieval by ID
        print("Testing point retrieval...")
        points = client.retrieve(
            collection_name=collection_name,
            ids=[0, 1],
            with_payload=True
        )
        print_success(f"Retrieved {len(points)} points by ID")
        
        # Clean up
        print("Cleaning up test collection...")
        client.delete_collection(collection_name)
        print_success("Test collection deleted")
        
        return True
        
    except Exception as e:
        print_error(f"Vector operations failed: {e}")
        return False

def test_health_check(client):
    """Test health check functionality."""
    if not client:
        print_warning("Skipping health check - no client available")
        return False
        
    print_header("Testing Health Check")
    
    try:
        start_time = time.time()
        collections = client.get_collections()
        response_time = (time.time() - start_time) * 1000
        
        print(f"Response time: {response_time:.2f}ms")
        print(f"Collections found: {len(collections.collections)}")
        
        # Try to get cluster info (may not be available in all versions)
        try:
            cluster_info = client.get_cluster_info()
            print(f"Cluster peers: {len(cluster_info.peers) if cluster_info.peers else 1}")
        except:
            print("Cluster info not available (single node setup)")
        
        print_success("Health check completed")
        return True
        
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False

def main():
    """Run all tests."""
    print_header("Qdrant Simple Integration Test")
    print(f"Test started at: {datetime.now()}")
    
    results = {}
    
    # Test Qdrant client
    client = test_qdrant_client()
    results["Client Import"] = client is not None or "qdrant_client" in sys.modules
    
    if client:
        # Run tests that require a connection
        results["Health Check"] = test_health_check(client)
        results["Collection Operations"] = test_collection_operations(client)
        results["Vector Operations"] = test_vector_operations(client)
    else:
        print_warning("Qdrant server not available - skipping server-dependent tests")
        results["Health Check"] = False
        results["Collection Operations"] = False
        results["Vector Operations"] = False
    
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
    
    if results["Client Import"]:
        print_success("Qdrant client is available and functional")
        if client:
            print_success("Qdrant server connection successful")
        else:
            print_warning("Qdrant server not running (start with Docker Compose)")
    else:
        print_error("Qdrant client not available - install qdrant-client")
    
    return 0 if passed > 0 else 1

if __name__ == "__main__":
    sys.exit(main())