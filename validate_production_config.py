#!/usr/bin/env python3
"""
Production Configuration Validation Script

This script validates the production environment configuration to ensure
all required settings are properly configured before deployment.

Requirements addressed:
- 4.1: Environment variable configuration validation
- 4.2: Secret management validation
- 4.3: Startup validation
- 4.4: Configuration error handling
- 8.4: Environment variable secret loading validation
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file if it exists
env_file = project_root / '.env'
if env_file.exists():
    print(f"Loading environment variables from {env_file}")
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faqbackend.settings.production')

try:
    import django
    django.setup()
except Exception as e:
    print(f"ERROR: Failed to setup Django: {e}")
    sys.exit(1)

from django.conf import settings
from django.core.management import execute_from_command_line
from django.db import connection
from django.core.exceptions import ImproperlyConfigured

class ProductionConfigValidator:
    """Validates production configuration settings."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        
    def log_error(self, message: str):
        """Log an error message."""
        self.errors.append(message)
        print(f"❌ ERROR: {message}")
    
    def log_warning(self, message: str):
        """Log a warning message."""
        self.warnings.append(message)
        print(f"⚠️  WARNING: {message}")
    
    def log_info(self, message: str):
        """Log an info message."""
        self.info.append(message)
        print(f"ℹ️  INFO: {message}")
    
    def log_success(self, message: str):
        """Log a success message."""
        print(f"✅ SUCCESS: {message}")
    
    def validate_django_settings(self) -> bool:
        """Validate core Django settings."""
        print("\n🔍 Validating Django Settings...")
        
        success = True
        
        # Check DEBUG setting
        if getattr(settings, 'DEBUG', True):
            self.log_error("DEBUG is enabled in production - this is a security risk")
            success = False
        else:
            self.log_success("DEBUG is disabled")
        
        # Check SECRET_KEY
        secret_key = getattr(settings, 'SECRET_KEY', '')
        if not secret_key:
            self.log_error("SECRET_KEY is not set")
            success = False
        elif secret_key.startswith('django-insecure-'):
            self.log_error("SECRET_KEY appears to be using Django's insecure default")
            success = False
        elif len(secret_key) < 50:
            self.log_warning("SECRET_KEY is shorter than recommended (50+ characters)")
        else:
            self.log_success("SECRET_KEY is properly configured")
        
        # Check ALLOWED_HOSTS
        allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
        if not allowed_hosts:
            self.log_error("ALLOWED_HOSTS is empty")
            success = False
        elif 'your-domain.com' in str(allowed_hosts):
            self.log_error("ALLOWED_HOSTS contains placeholder values")
            success = False
        else:
            self.log_success(f"ALLOWED_HOSTS configured with {len(allowed_hosts)} hosts")
        
        return success
    
    def validate_database_config(self) -> bool:
        """Validate database configuration."""
        print("\n🗄️  Validating Database Configuration...")
        
        success = True
        
        # Check database engine
        db_config = settings.DATABASES.get('default', {})
        engine = db_config.get('ENGINE', '')
        
        if 'postgresql' not in engine:
            self.log_error(f"Database engine is {engine}, should be PostgreSQL for production")
            success = False
        else:
            self.log_success("Using PostgreSQL database engine")
        
        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                self.log_success(f"Database connection successful: {version}")
        except Exception as e:
            self.log_error(f"Database connection failed: {e}")
            success = False
        
        # Check connection pooling
        conn_max_age = db_config.get('CONN_MAX_AGE', 0)
        if conn_max_age > 0:
            self.log_success(f"Connection pooling enabled (CONN_MAX_AGE: {conn_max_age})")
        else:
            self.log_warning("Connection pooling not configured")
        
        return success
    
    def validate_security_settings(self) -> bool:
        """Validate security settings."""
        print("\n🔒 Validating Security Settings...")
        
        success = True
        
        # Check HTTPS settings
        if getattr(settings, 'SECURE_SSL_REDIRECT', False):
            self.log_success("HTTPS redirect is enabled")
        else:
            self.log_warning("HTTPS redirect is disabled")
        
        # Check HSTS
        hsts_seconds = getattr(settings, 'SECURE_HSTS_SECONDS', 0)
        if hsts_seconds > 0:
            self.log_success(f"HSTS enabled for {hsts_seconds} seconds")
        else:
            self.log_warning("HSTS not configured")
        
        # Check CSRF settings
        csrf_origins = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])
        if csrf_origins:
            if 'your-domain.com' in str(csrf_origins):
                self.log_error("CSRF_TRUSTED_ORIGINS contains placeholder values")
                success = False
            else:
                self.log_success(f"CSRF trusted origins configured: {len(csrf_origins)} origins")
        else:
            self.log_warning("CSRF_TRUSTED_ORIGINS not configured")
        
        # Check session security
        if getattr(settings, 'SESSION_COOKIE_SECURE', False):
            self.log_success("Secure session cookies enabled")
        else:
            self.log_warning("Secure session cookies not enabled")
        
        return success
    
    def validate_static_files(self) -> bool:
        """Validate static files configuration."""
        print("\n📁 Validating Static Files Configuration...")
        
        success = True
        
        # Check WhiteNoise
        middleware = getattr(settings, 'MIDDLEWARE', [])
        whitenoise_middleware = 'whitenoise.middleware.WhiteNoiseMiddleware'
        
        if whitenoise_middleware in middleware:
            self.log_success("WhiteNoise middleware is configured")
        else:
            self.log_error("WhiteNoise middleware not found in MIDDLEWARE")
            success = False
        
        # Check static files storage
        storage = getattr(settings, 'STATICFILES_STORAGE', '')
        if 'whitenoise' in storage.lower():
            self.log_success("WhiteNoise static files storage configured")
        else:
            self.log_warning("WhiteNoise storage not configured")
        
        # Check static root
        static_root = getattr(settings, 'STATIC_ROOT', '')
        if static_root:
            self.log_success(f"STATIC_ROOT configured: {static_root}")
        else:
            self.log_error("STATIC_ROOT not configured")
            success = False
        
        return success
    
    def validate_external_services(self) -> bool:
        """Validate external service configurations."""
        print("\n🌐 Validating External Services...")
        
        success = True
        
        # Check Gemini API key
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not gemini_key:
            self.log_error("GEMINI_API_KEY is not configured")
            success = False
        elif gemini_key == 'YOUR-GEMINI-API-KEY-HERE':
            self.log_error("GEMINI_API_KEY contains placeholder value")
            success = False
        else:
            self.log_success("Gemini API key is configured")
        
        return success
    
    def validate_rag_configuration(self) -> bool:
        """Validate RAG system configuration."""
        print("\n🤖 Validating RAG Configuration...")
        
        success = True
        
        # Check embedding configuration
        embedding_type = getattr(settings, 'RAG_EMBEDDING_TYPE', '')
        if embedding_type == 'local':
            self.log_success("Using local embedding model")
            
            model_name = getattr(settings, 'RAG_LOCAL_EMBEDDING_MODEL', '')
            if model_name:
                self.log_success(f"Embedding model: {model_name}")
            else:
                self.log_warning("Local embedding model not specified")
        else:
            self.log_warning(f"Embedding type: {embedding_type}")
        
        # Check vector store configuration
        vector_store = getattr(settings, 'RAG_VECTOR_STORE_TYPE', '')
        if vector_store == 'qdrant':
            self.log_success("Using Qdrant vector store")
            
            # Check Qdrant settings
            qdrant_host = getattr(settings, 'QDRANT_HOST', '')
            qdrant_port = getattr(settings, 'QDRANT_PORT', 0)
            
            if qdrant_host and qdrant_port:
                self.log_success(f"Qdrant configured: {qdrant_host}:{qdrant_port}")
            else:
                self.log_error("Qdrant connection settings incomplete")
                success = False
        else:
            self.log_warning(f"Vector store type: {vector_store}")
        
        return success
    
    def validate_caching(self) -> bool:
        """Validate caching configuration."""
        print("\n💾 Validating Cache Configuration...")
        
        success = True
        
        cache_config = settings.CACHES.get('default', {})
        backend = cache_config.get('BACKEND', '')
        
        if 'redis' in backend.lower():
            self.log_success("Using Redis cache backend")
            
            location = cache_config.get('LOCATION', '')
            if location:
                self.log_success(f"Redis location: {location}")
            else:
                self.log_warning("Redis location not configured")
        elif 'database' in backend.lower():
            self.log_warning("Using database cache backend (Redis recommended for production)")
        else:
            self.log_warning(f"Cache backend: {backend}")
        
        return success
    
    def validate_logging(self) -> bool:
        """Validate logging configuration."""
        print("\n📝 Validating Logging Configuration...")
        
        success = True
        
        logging_config = getattr(settings, 'LOGGING', {})
        if logging_config:
            self.log_success("Logging configuration found")
            
            # Check handlers
            handlers = logging_config.get('handlers', {})
            if 'file' in handlers:
                self.log_success("File logging handler configured")
            else:
                self.log_warning("File logging handler not configured")
            
            if 'console' in handlers:
                self.log_success("Console logging handler configured")
        else:
            self.log_warning("No logging configuration found")
        
        return success
    
    def validate_environment_variables(self) -> bool:
        """Validate required environment variables."""
        print("\n🔧 Validating Environment Variables...")
        
        success = True
        
        required_vars = [
            'SECRET_KEY',
            'DB_NAME',
            'DB_USER', 
            'DB_PASSWORD',
            'GEMINI_API_KEY',
            'ALLOWED_HOSTS'
        ]
        
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                self.log_error(f"Required environment variable {var} is not set")
                success = False
            elif var in ['SECRET_KEY', 'DB_PASSWORD', 'GEMINI_API_KEY'] and len(value) < 10:
                self.log_warning(f"Environment variable {var} appears to be too short")
            else:
                self.log_success(f"Environment variable {var} is set")
        
        return success
    
    def test_qdrant_connection(self) -> bool:
        """Test Qdrant vector database connection."""
        print("\n🔍 Testing Qdrant Connection...")
        
        try:
            import requests
            
            qdrant_host = getattr(settings, 'QDRANT_HOST', 'localhost')
            qdrant_port = getattr(settings, 'QDRANT_PORT', 6333)
            
            url = f"http://{qdrant_host}:{qdrant_port}/health"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                self.log_success("Qdrant connection successful")
                return True
            else:
                self.log_error(f"Qdrant health check failed: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_error(f"Qdrant connection failed: {e}")
            return False
    
    def run_validation(self) -> bool:
        """Run all validation checks."""
        print("🚀 Starting Production Configuration Validation...\n")
        
        all_success = True
        
        # Run all validation checks
        checks = [
            self.validate_environment_variables,
            self.validate_django_settings,
            self.validate_database_config,
            self.validate_security_settings,
            self.validate_static_files,
            self.validate_external_services,
            self.validate_rag_configuration,
            self.validate_caching,
            self.validate_logging,
            self.test_qdrant_connection,
        ]
        
        for check in checks:
            try:
                if not check():
                    all_success = False
            except Exception as e:
                self.log_error(f"Validation check failed: {e}")
                all_success = False
        
        # Print summary
        print("\n" + "="*60)
        print("📊 VALIDATION SUMMARY")
        print("="*60)
        
        if self.errors:
            print(f"❌ Errors: {len(self.errors)}")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print(f"⚠️  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.info:
            print(f"ℹ️  Info: {len(self.info)}")
            for info in self.info:
                print(f"   • {info}")
        
        print("\n" + "="*60)
        
        if all_success and not self.errors:
            print("🎉 VALIDATION PASSED - Configuration is ready for production!")
            return True
        else:
            print("❌ VALIDATION FAILED - Please fix the errors before deploying")
            return False

def main():
    """Main function."""
    validator = ProductionConfigValidator()
    
    try:
        success = validator.run_validation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()