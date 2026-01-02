#!/usr/bin/env python
"""
Test health check endpoints for Qdrant integration.
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

from django.test import RequestFactory
import json

def test_health_endpoints():
    """Test all health check endpoints."""
    print("Testing Health Check Endpoints")
    print("=" * 50)
    
    factory = RequestFactory()
    
    # Test basic health check
    print("\n1. Testing basic health check...")
    try:
        from faq.health_views import health_check
        request = factory.get('/health/')
        response = health_check(request)
        
        print(f"Status: {response.status_code}")
        data = json.loads(response.content)
        print(f"Response: {data}")
        
        if response.status_code == 200:
            print("✓ Basic health check passed")
        else:
            print("✗ Basic health check failed")
    except Exception as e:
        print(f"✗ Basic health check error: {e}")
    
    # Test detailed health check
    print("\n2. Testing detailed health check...")
    try:
        from faq.health_views import health_detailed
        request = factory.get('/health/detailed/')
        response = health_detailed(request)
        
        print(f"Status: {response.status_code}")
        data = json.loads(response.content)
        print(f"Overall status: {data.get('status')}")
        print(f"Components: {list(data.get('components', {}).keys())}")
        
        if response.status_code in [200, 503]:  # 503 is acceptable for degraded health
            print("✓ Detailed health check passed")
        else:
            print("✗ Detailed health check failed")
    except Exception as e:
        print(f"✗ Detailed health check error: {e}")
    
    # Test vector store health check
    print("\n3. Testing vector store health check...")
    try:
        from faq.health_views import health_vector_store
        request = factory.get('/health/vector-store/')
        response = health_vector_store(request)
        
        print(f"Status: {response.status_code}")
        data = json.loads(response.content)
        print(f"Store status: {data.get('status')}")
        print(f"Store type: {data.get('store_type')}")
        
        if response.status_code in [200, 503]:  # 503 is acceptable for unhealthy store
            print("✓ Vector store health check passed")
        else:
            print("✗ Vector store health check failed")
    except Exception as e:
        print(f"✗ Vector store health check error: {e}")
    
    # Test Qdrant health check
    print("\n4. Testing Qdrant health check...")
    try:
        from faq.health_views import health_qdrant
        request = factory.get('/health/qdrant/')
        response = health_qdrant(request)
        
        print(f"Status: {response.status_code}")
        data = json.loads(response.content)
        print(f"Qdrant status: {data.get('status')}")
        
        if 'server' in data:
            server_info = data['server']
            print(f"Server: {server_info.get('host')}:{server_info.get('port')}")
        
        if response.status_code in [200, 503]:  # 503 is acceptable for unavailable Qdrant
            print("✓ Qdrant health check passed")
        else:
            print("✗ Qdrant health check failed")
    except Exception as e:
        print(f"✗ Qdrant health check error: {e}")
    
    # Test readiness probe
    print("\n5. Testing readiness probe...")
    try:
        from faq.health_views import health_readiness
        request = factory.get('/health/ready/')
        response = health_readiness(request)
        
        print(f"Status: {response.status_code}")
        data = json.loads(response.content)
        print(f"Ready: {data.get('ready')}")
        print(f"Components: {data.get('components', {})}")
        
        if response.status_code in [200, 503]:  # Both are valid responses
            print("✓ Readiness probe passed")
        else:
            print("✗ Readiness probe failed")
    except Exception as e:
        print(f"✗ Readiness probe error: {e}")
    
    # Test liveness probe
    print("\n6. Testing liveness probe...")
    try:
        from faq.health_views import health_liveness
        request = factory.get('/health/live/')
        response = health_liveness(request)
        
        print(f"Status: {response.status_code}")
        data = json.loads(response.content)
        print(f"Alive: {data.get('alive')}")
        
        if response.status_code == 200:
            print("✓ Liveness probe passed")
        else:
            print("✗ Liveness probe failed")
    except Exception as e:
        print(f"✗ Liveness probe error: {e}")
    
    print("\n" + "=" * 50)
    print("Health endpoint tests completed!")

if __name__ == "__main__":
    test_health_endpoints()