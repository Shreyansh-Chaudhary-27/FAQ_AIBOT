"""
Base Django settings for faqbackend project.
This contains common settings shared across all environments.
"""

import os
from pathlib import Path
import warnings

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Suppress deprecation warning for google.generativeai package
# The package still works but Google recommends migrating to google.genai
# This suppresses the warning until we migrate
warnings.filterwarnings('ignore', message='.*google.generativeai.*')
warnings.filterwarnings('ignore', message='.*deprecated-generative-ai-python.*')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'faq',
    'captcha',
]

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Add WhiteNoise for static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'faqbackend.middleware.SimpleCORS',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'faq.audit_middleware.AdminAuditMiddleware',  # Add audit logging middleware
    'faqbackend.middleware.AdminAuthMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'faqbackend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'faqbackend.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'  # Indian Standard Time (IST, UTC+5:30)
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'assets',
    BASE_DIR,  # allow serving root-level static like chatbot.js
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CAPTCHA settings for admin dashboard authentication
CAPTCHA_IMAGE_SIZE = (120, 50)
CAPTCHA_LENGTH = 4
CAPTCHA_TIMEOUT = 5  # minutes
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.math_challenge'
CAPTCHA_NOISE_FUNCTIONS = ('captcha.helpers.noise_arcs', 'captcha.helpers.noise_dots')
CAPTCHA_FILTER_FUNCTIONS = ('captcha.helpers.post_smooth',)
CAPTCHA_WORDS_DICTIONARY = '/usr/share/dict/words'
CAPTCHA_FLITE_PATH = None

# Encryption settings for admin dashboard data protection
# Encryption service uses Django's SECRET_KEY for key derivation
# Additional security settings for encryption operations
ENCRYPTION_SETTINGS = {
    'ALGORITHM': 'Fernet',  # Using Fernet encryption from cryptography library
    'KEY_DERIVATION': {
        'ALGORITHM': 'PBKDF2HMAC',
        'HASH_ALGORITHM': 'SHA256',
        'ITERATIONS': 100000,
        'SALT': b'faq_admin_dashboard_salt',  # Static salt for consistency
    },
    'AUDIT_LOGGING': True,  # Enable audit logging for encryption operations
}

# Admin dashboard security settings
ADMIN_DASHBOARD_SETTINGS = {
    'SESSION_TIMEOUT_MINUTES': 30,  # Session timeout for admin users
    'MAX_SESSION_DURATION_HOURS': 8,  # Maximum session duration
    'LOGIN_URL': '/admin-dashboard/login/',  # Admin login URL
    'LOGOUT_URL': '/admin-dashboard/logout/',  # Admin logout URL
    'REQUIRE_STAFF_STATUS': True,  # Require staff status for admin access
    'AUDIT_ALL_ACTIONS': True,  # Enable comprehensive audit logging
    'READ_ONLY_ACCESS': True,  # Enforce read-only access to data
}

# AI-Enhanced FAQ Settings
AI_FAQ_SETTINGS = {
    'ENABLE_GEMINI': True,  # Enable/disable Gemini AI integration
    'FALLBACK_TO_TRADITIONAL': True,  # Use traditional search if Gemini fails
    'MIN_SEMANTIC_CONFIDENCE': 0.3,  # Minimum confidence for semantic matches
    'MAX_AI_RESULTS': 5,  # Maximum results from AI search
    'CONTEXT_RESPONSE_LENGTH': 200,  # Max length for contextual responses
}