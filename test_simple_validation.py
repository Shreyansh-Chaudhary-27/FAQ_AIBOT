#!/usr/bin/env python3
"""
Simple deployment validation without Unicode characters.
"""

import os
import sys
from pathlib import Path

def test_files_exist():
    """Test that all required files exist."""
    print("Testing file existence...")
    
    required_files = [
        "Dockerfile",
        "docker-compose.yml", 
        ".env.example",
        "gunicorn.conf.py",
        "docker-entrypoint.sh",
        "nginx/nginx.conf",
        "nginx/conf.d/django.conf",
        "faqbackend/settings/production.py",
        "requirements.txt"
    ]
    
    missing_files = []
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  [OK] {file_path}")
        else:
            print(f"  [MISSING] {file_path}")
            missing_files.append(file_path)
    
    return len(missing_files) == 0

def test_django_settings():
    """Test Django settings can be loaded."""
    print("Testing Django settings...")
    
    try:
        # Set minimal environment
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faqbackend.settings.production')
        os.environ.setdefault('SECRET_KEY', 'test-key')
        os.environ.setdefault('DB_NAME', 'test')
        os.environ.setdefault('DB_USER', 'test')
        os.environ.setdefault('DB_PASSWORD', 'test')
        os.environ.setdefault('GEMINI_API_KEY', 'test')
        os.environ.setdefault('DEBUG', 'False')
        os.environ.setdefault('ALLOWED_HOSTS', 'localhost')
        
        import django
        from django.conf import settings
        django.setup()
        
        print(f"  [OK] Django settings loaded")
        print(f"  [OK] DEBUG = {settings.DEBUG}")
        print(f"  [OK] Database engine: {settings.DATABASES['default']['ENGINE']}")
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] Django settings failed: {e}")
        return False

def test_basic_imports():
    """Test basic imports work."""
    print("Testing basic imports...")
    
    try:
        import django
        print(f"  [OK] Django {django.get_version()}")
        
        import sentence_transformers
        print(f"  [OK] sentence-transformers available")
        
        return True
        
    except ImportError as e:
        print(f"  [ERROR] Import failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=== Deployment Validation ===")
    
    tests = [
        ("File Existence", test_files_exist),
        ("Django Settings", test_django_settings),
        ("Basic Imports", test_basic_imports),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append(result)
            print(f"Result: {'PASS' if result else 'FAIL'}")
        except Exception as e:
            print(f"Result: ERROR - {e}")
            results.append(False)
    
    print(f"\n=== Summary ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("Status: READY FOR DEPLOYMENT")
        return 0
    else:
        print("Status: NOT READY - Fix issues above")
        return 1

if __name__ == "__main__":
    sys.exit(main())