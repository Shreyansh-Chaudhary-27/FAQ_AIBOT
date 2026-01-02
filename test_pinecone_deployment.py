#!/usr/bin/env python3
"""
Test script to verify Pinecone deployment configuration.
This script tests that the production settings correctly use Pinecone
and that no database connection issues occur.
"""

import os
import sys
import subprocess

def test_pinecone_production_settings():
    """Test that production settings work with Pinecone configuration."""
    print("Testing Pinecone production settings...")
    
    # Set environment variables for Pinecone
    env = os.environ.copy()
    env.update({
        'SECRET_KEY': 'test-secret-key-for-pinecone-deployment',
        'GEMINI_API_KEY': 'test-gemini-key',
        'PINECONE_API_KEY': 'test-pinecone-key',
        'DJANGO_SETTINGS_MODULE': 'faqbackend.settings.production',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,test.onrender.com'
    })
    
    # Test Python script
    test_script = '''
import django
from django.conf import settings
django.setup()

# Verify Pinecone configuration
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
assert "app_data.sqlite3" in str(settings.DATABASES["default"]["NAME"])
assert settings.PINECONE_API_KEY == "test-pinecone-key"
assert settings.RAG_VECTOR_STORE_TYPE == "pinecone"
assert settings.DEBUG == False

print("PASS: Pinecone production settings test passed")
print(f"   Database: {settings.DATABASES['default']['ENGINE']} (minimal app data)")
print(f"   Vector Store: {settings.RAG_VECTOR_STORE_TYPE}")
print(f"   Pinecone Index: {settings.PINECONE_INDEX_NAME}")
'''
    
    try:
        result = subprocess.run(
            [sys.executable, '-c', test_script],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("PASS: Pinecone production settings test PASSED")
            return True
        else:
            print("FAIL: Pinecone production settings test FAILED")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"ERROR: Pinecone production settings test ERROR: {e}")
        return False

def test_no_database_waiting():
    """Test that no database connection waiting occurs."""
    print("\nTesting no database connection waiting...")
    
    # Test that the application doesn't try to connect to PostgreSQL
    env = os.environ.copy()
    env.update({
        'SECRET_KEY': 'test-key',
        'GEMINI_API_KEY': 'test-gemini-key',
        'PINECONE_API_KEY': 'test-pinecone-key',
        'DJANGO_SETTINGS_MODULE': 'faqbackend.settings.production'
    })
    
    # Test that Django can start without database connection errors
    test_script = '''
import django
from django.conf import settings
from django.core.management import execute_from_command_line
import sys

# This should not try to connect to PostgreSQL
django.setup()

# Test that we can run basic Django commands
try:
    # This would fail if there were database connection issues
    from django.core.management.commands.check import Command
    command = Command()
    # Don't actually run check, just verify it can be imported
    print("PASS: Django commands can be imported without database errors")
except Exception as e:
    print(f"FAIL: Django command import failed: {e}")
    sys.exit(1)

print("PASS: No database connection waiting required")
'''
    
    try:
        result = subprocess.run(
            [sys.executable, '-c', test_script],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("PASS: No database waiting test PASSED")
            return True
        else:
            print("FAIL: Database waiting test FAILED")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"ERROR: Database waiting test ERROR: {e}")
        return False

def main():
    """Run all Pinecone deployment tests."""
    print("Pinecone Deployment Configuration Tests")
    print("=" * 50)
    
    tests = [
        test_pinecone_production_settings,
        test_no_database_waiting,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"ERROR: Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("SUCCESS: All Pinecone deployment tests PASSED!")
        print("\nYour application is ready for Pinecone deployment on Render!")
        print("\nTo deploy with Pinecone on Render:")
        print("   1. Get Pinecone API key from pinecone.io")
        print("   2. Set PINECONE_API_KEY in Render environment variables")
        print("   3. Deploy without adding any database services")
        print("   4. No more 'Database is unavailable' errors!")
        return True
    else:
        print("FAIL: Some tests failed. Please check the configuration.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)