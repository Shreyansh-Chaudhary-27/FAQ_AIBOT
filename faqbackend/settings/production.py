"""
Production Django settings for faqbackend project.
This module contains production-optimized settings with environment variable validation,
PostgreSQL database configuration, security settings, and WhiteNoise static file serving.

Requirements addressed:
- 2.1: PostgreSQL database backend
- 2.2: WhiteNoise static file serving
- 2.3: Production error handling (DEBUG=False)
- 2.4: Environment variable validation
- 2.5: HTTPS enforcement
- 4.1, 4.2, 4.3, 4.4: Environment configuration management
- 8.1, 8.2, 8.3, 8.4, 8.5: Security configuration
"""

print("=== LOADING PRODUCTION SETTINGS ===")

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from .base import *

# Load environment variables from .env file if it exists
# This ensures environment variables are available when production settings are loaded
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Try alternative paths
    alt_paths = [
        Path.cwd() / '.env',
        Path(__file__).parent.parent / '.env',
    ]
    for alt_path in alt_paths:
        if alt_path.exists():
            load_dotenv(dotenv_path=alt_path)
            break

# Environment variable validation
class EnvironmentError(Exception):
    """Raised when required environment variables are missing or invalid."""
    pass

def get_env_variable(var_name, default=None, required=True, var_type=str):
    """
    Get environment variable with validation.
    
    Args:
        var_name (str): Name of the environment variable
        default: Default value if variable is not set
        required (bool): Whether the variable is required
        var_type (type): Type to convert the variable to
    
    Returns:
        The environment variable value converted to the specified type
    
    Raises:
        EnvironmentError: If required variable is missing or conversion fails
    """
    value = os.getenv(var_name)
    
    # If value is None and we have a default, use the default
    if value is None:
        if default is not None:
            return default
        elif required:
            raise EnvironmentError(
                f"Required environment variable '{var_name}' is not set. "
                f"Please set this variable in your environment or .env file."
            )
        else:
            return None
    
    # Type conversion with validation
    try:
        if var_type == bool:
            # Handle boolean conversion for common string representations
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        elif var_type == list:
            # Handle comma-separated lists
            if isinstance(value, str):
                # Handle empty string case
                if not value.strip():
                    return default if default is not None else []
                return [item.strip() for item in value.split(',') if item.strip()]
            return value if value is not None else (default if default is not None else [])
        else:
            return var_type(value)
    except (ValueError, TypeError) as e:
        raise EnvironmentError(
            f"Environment variable '{var_name}' has invalid value '{value}'. "
            f"Expected type: {var_type.__name__}. Error: {e}"
        )

# Validate required environment variables at startup
def validate_environment():
    """Validate all required environment variables for production."""
    required_vars = [
        ('SECRET_KEY', str),
        ('GEMINI_API_KEY', str),
    ]
    
    # Database validation - only if using PostgreSQL
    use_sqlite = get_env_variable('USE_SQLITE', default=False, required=False, var_type=bool)
    database_url = get_env_variable('DATABASE_URL', required=False)
    
    if not use_sqlite and not database_url:
        required_vars.extend([
            ('DB_NAME', str),
            ('DB_USER', str),
            ('DB_PASSWORD', str),
        ])
    
    errors = []
    for var_name, var_type in required_vars:
        try:
            get_env_variable(var_name, required=True, var_type=var_type)
        except EnvironmentError as e:
            errors.append(str(e))
    
    if errors:
        error_message = "Environment validation failed:\n" + "\n".join(f"- {error}" for error in errors)
        raise EnvironmentError(error_message)

# Validate environment on import
validate_environment()

# SECURITY WARNING: keep the secret key used in production secret!
# Requirements 4.2, 8.4: Load secrets from environment variables
SECRET_KEY = get_env_variable('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
# Requirements 2.3, 8.1: Disable debug mode in production
DEBUG = False

# Requirements 2.5, 8.3: HTTPS enforcement and security headers
SECURE_SSL_REDIRECT = get_env_variable('SECURE_SSL_REDIRECT', default=True, required=False, var_type=bool)
SECURE_HSTS_SECONDS = get_env_variable('SECURE_HSTS_SECONDS', default=31536000, required=False, var_type=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Requirements 8.2: CSRF protection
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = get_env_variable('CSRF_TRUSTED_ORIGINS', default=[], required=False, var_type=list)

# Session security
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Requirements 2.1, 3.1, 3.2: Database configuration with PostgreSQL and SQLite support
USE_SQLITE = get_env_variable('USE_SQLITE', default=False, required=False, var_type=bool)

if USE_SQLITE:
    # SQLite configuration for cloud deployments (Render, etc.)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 20,
                'check_same_thread': False,
            },
        }
    }
    print("Using SQLite database for production deployment")
else:
    # PostgreSQL configuration with connection pooling
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': get_env_variable('DB_NAME'),
            'USER': get_env_variable('DB_USER'),
            'PASSWORD': get_env_variable('DB_PASSWORD'),
            'HOST': get_env_variable('DB_HOST', default='localhost'),
            'PORT': get_env_variable('DB_PORT', default=5432, required=False, var_type=int),
            'CONN_MAX_AGE': get_env_variable('DB_CONN_MAX_AGE', default=600, required=False, var_type=int),  # 10 minutes
        }
    }
    
    # Alternative: Support DATABASE_URL for easier deployment (Heroku-style)
    DATABASE_URL = get_env_variable('DATABASE_URL', required=False)
    if DATABASE_URL:
        import dj_database_url
        DATABASES['default'] = dj_database_url.parse(DATABASE_URL)
        # Add connection pooling options
        DATABASES['default']['CONN_MAX_AGE'] = 600
    
    print("Using PostgreSQL database for production deployment")

# Requirements 2.2: WhiteNoise static file serving configuration
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# WhiteNoise configuration for production optimization
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = False  # Disable in production for performance
WHITENOISE_MAX_AGE = 31536000  # 1 year cache for static files

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Gemini AI Configuration - Requirements 4.2, 8.4: Load API key from environment
GEMINI_API_KEY = get_env_variable('GEMINI_API_KEY')

# RAG Configuration from environment variables
RAG_EMBEDDING_TYPE = get_env_variable('RAG_EMBEDDING_TYPE', default='local', required=False)
RAG_LOCAL_EMBEDDING_MODEL = get_env_variable('RAG_LOCAL_EMBEDDING_MODEL', default='all-MiniLM-L6-v2', required=False)
RAG_VECTOR_DIMENSION = get_env_variable('RAG_VECTOR_DIMENSION', default=384, required=False, var_type=int)
RAG_SIMILARITY_THRESHOLD = get_env_variable('RAG_SIMILARITY_THRESHOLD', default=0.5, required=False, var_type=float)

# Vector Store Configuration - Use Qdrant in production
RAG_VECTOR_STORE_TYPE = get_env_variable('RAG_VECTOR_STORE_TYPE', default='qdrant', required=False)

# Vector Database Configuration (Qdrant)
QDRANT_HOST = get_env_variable('QDRANT_HOST', default='qdrant', required=False)
QDRANT_PORT = get_env_variable('QDRANT_PORT', default=6333, required=False, var_type=int)
QDRANT_COLLECTION_NAME = get_env_variable('QDRANT_COLLECTION_NAME', default='faq_embeddings', required=False)
QDRANT_TIMEOUT = get_env_variable('QDRANT_TIMEOUT', default=30, required=False, var_type=int)
VECTOR_DB_URL = get_env_variable('VECTOR_DB_URL', required=False)

# Cache Configuration (Redis)
REDIS_URL = get_env_variable('REDIS_URL', required=False)
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': 'faq_prod',
            'TIMEOUT': get_env_variable('CACHE_TTL', default=3600, required=False, var_type=int),
        }
    }
else:
    # Fallback to database cache if Redis is not available
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'cache_table',
        }
    }

# Requirements 2.3, 8.1: Production logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'security': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'security',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['security_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'admin_security': {
            'handlers': ['security_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'faq': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
logs_dir = BASE_DIR / 'logs'
logs_dir.mkdir(exist_ok=True)

# Email configuration for error reporting (optional)
EMAIL_BACKEND = get_env_variable('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend', required=False)
if EMAIL_BACKEND != 'django.core.mail.backends.console.EmailBackend':
    EMAIL_HOST = get_env_variable('EMAIL_HOST', required=False)
    EMAIL_PORT = get_env_variable('EMAIL_PORT', default=587, required=False, var_type=int)
    EMAIL_USE_TLS = get_env_variable('EMAIL_USE_TLS', default=True, required=False, var_type=bool)
    EMAIL_HOST_USER = get_env_variable('EMAIL_HOST_USER', required=False)
    EMAIL_HOST_PASSWORD = get_env_variable('EMAIL_HOST_PASSWORD', required=False)
    DEFAULT_FROM_EMAIL = get_env_variable('DEFAULT_FROM_EMAIL', required=False)
    
    # Admin email for error notifications
    ADMINS = [
        ('Admin', get_env_variable('ADMIN_EMAIL', required=False)),
    ] if get_env_variable('ADMIN_EMAIL', required=False) else []

# Performance optimizations
DATA_UPLOAD_MAX_MEMORY_SIZE = get_env_variable('DATA_UPLOAD_MAX_MEMORY_SIZE', default=5242880, required=False, var_type=int)  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = get_env_variable('FILE_UPLOAD_MAX_MEMORY_SIZE', default=2621440, required=False, var_type=int)  # 2.5MB

# Requirements 8.3: Additional security headers
X_FRAME_OPTIONS = 'DENY'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Disable server tokens for security
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# CRITICAL: Set ALLOWED_HOSTS at the very end to prevent Django from overriding it
# Load from environment or use safe defaults
allowed_hosts_env = os.getenv('ALLOWED_HOSTS')
if allowed_hosts_env:
    try:
        ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]
    except Exception:
        ALLOWED_HOSTS = ['localhost', '127.0.0.1']
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Ensure ALLOWED_HOSTS is never empty
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Add a unique marker to verify this settings file is being used
PRODUCTION_SETTINGS_LOADED = True
PRODUCTION_SETTINGS_MARKER = "PRODUCTION_SETTINGS_ACTIVE"

# Environment validation summary
print("Production settings loaded successfully:")
print(f"- Database: {'SQLite' if USE_SQLITE else 'PostgreSQL'} ({'URL-based' if not USE_SQLITE and 'DATABASE_URL' in locals() and DATABASE_URL else 'individual settings' if not USE_SQLITE else 'file-based'})")
print(f"- Static files: WhiteNoise with compression")
print(f"- Cache: {'Redis' if 'REDIS_URL' in locals() and REDIS_URL else 'Database'}")
print(f"- Debug mode: {DEBUG}")
print(f"- Allowed hosts: {len(ALLOWED_HOSTS)} configured")
print(f"- HTTPS enforcement: {SECURE_SSL_REDIRECT}")

