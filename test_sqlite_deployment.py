#!/usr/bin/env python3
"""
Test script to verify SQLite deployment configuration.
This script tests that the production settings and Docker entrypoint
correctly handle SQLite deployment for Render.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def test_sqlite_production_settings():
    """Test that production settings work with SQLite configuration."""
    print("Testing SQLite production settings...")
    
    # Set environment variables for SQLite
    env = os.environ.copy()
    env.update({
        'USE_SQLITE': 'True',
        'SECRET_KEY': 'test-secret-key-for-sqlite-deployment',
        'GEMINI_API_KEY': 'test-gemini-key',
        'DJANGO_SETTINGS_MODULE': 'faqbackend.settings.production',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,test.onrender.com'
    })
    
    # Test Python script
    test_script = '''
import django
from django.conf import settings
django.setup()

# Verify SQLite configuration
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
assert "sqlite3" in str(settings.DATABASES["default"]["NAME"])
assert settings.USE_SQLITE == True
assert settings.DEBUG == False

print("PASS: SQLite production settings test passed")
print(f"   Database: {settings.DATABASES['default']['ENGINE']}")
print(f"   File: {settings.DATABASES['default']['NAME']}")
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
            print("PASS: SQLite production settings test PASSED")
            return True
        else:
            print("FAIL: SQLite production settings test FAILED")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"ERROR: SQLite production settings test ERROR: {e}")
        return False

def test_postgresql_production_settings():
    """Test that production settings still work with PostgreSQL configuration."""
    print("\nTesting PostgreSQL production settings...")
    
    # Set environment variables for PostgreSQL
    env = os.environ.copy()
    env.update({
        'SECRET_KEY': 'test-secret-key-for-postgresql-deployment',
        'GEMINI_API_KEY': 'test-gemini-key',
        'DJANGO_SETTINGS_MODULE': 'faqbackend.settings.production',
        'DB_NAME': 'test_faq_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_password',
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,test.onrender.com'
    })
    
    # Remove USE_SQLITE to test PostgreSQL path
    env.pop('USE_SQLITE', None)
    
    # Test Python script
    test_script = '''
import django
from django.conf import settings
django.setup()

# Verify PostgreSQL configuration
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
assert settings.DATABASES["default"]["NAME"] == "test_faq_db"
assert settings.USE_SQLITE == False
assert settings.DEBUG == False

print("PASS: PostgreSQL production settings test passed")
print(f"   Database: {settings.DATABASES['default']['ENGINE']}")
print(f"   Name: {settings.DATABASES['default']['NAME']}")
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
            print("PASS: PostgreSQL production settings test PASSED")
            return True
        else:
            print("FAIL: PostgreSQL production settings test FAILED")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"ERROR: PostgreSQL production settings test ERROR: {e}")
        return False

def main():
    """Run all SQLite deployment tests."""
    print("SQLite Deployment Configuration Tests")
    print("=" * 50)
    
    tests = [
        test_sqlite_production_settings,
        test_postgresql_production_settings,
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
        print("SUCCESS: All SQLite deployment tests PASSED!")
        print("\nYour application is ready for SQLite deployment on Render!")
        print("\nTo deploy with SQLite on Render:")
        print("   1. Set USE_SQLITE=True in environment variables")
        print("   2. Set other required variables (SECRET_KEY, GEMINI_API_KEY, etc.)")
        print("   3. Deploy without adding a PostgreSQL database service")
        return True
    else:
        print("FAIL: Some tests failed. Please check the configuration.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)