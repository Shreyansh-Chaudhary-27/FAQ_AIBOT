"""
Development Django settings for faqbackend project.
This module contains development-specific settings with local database and debug mode enabled.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from .base import *

# Load environment variables from .env file for development
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-z@r=*#4*)znd(&xd%*pbok1=1otg1coc@qy0ng2$jj0k)r9m4e')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = [
    'faq-aibot.onrender.com',
    'localhost',
    '127.0.0.1',
    'testserver',
]

# Database - SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Static files configuration for development
STATICFILES_DIRS = [
    BASE_DIR / 'assets',
    BASE_DIR,  # allow serving root-level static like chatbot.js
]

# Gemini AI Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Development logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'admin_security.log',
            'formatter': 'security',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'security',
        },
    },
    'loggers': {
        'admin_security': {
            'handlers': ['security_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# CSRF trusted origins for development
CSRF_TRUSTED_ORIGINS = [
    'https://faq-aibot.onrender.com',
]

# Development-specific settings
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Disable HTTPS enforcement in development
SECURE_SSL_REDIRECT = False