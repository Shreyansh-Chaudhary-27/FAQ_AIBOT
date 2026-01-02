"""
Django settings for faqbackend project.

This module automatically loads the appropriate settings based on the DJANGO_ENV environment variable:
- development: Local development settings with SQLite and debug mode
- production: Production settings with PostgreSQL, security, and performance optimizations

Environment variable DJANGO_ENV determines which settings to load:
- If not set or set to 'development': loads development settings
- If set to 'production': loads production settings

For production deployment, ensure all required environment variables are set.
See .env.example for a complete list of configuration options.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file if it exists
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Determine which settings to load based on DJANGO_ENV environment variable
DJANGO_ENV = os.getenv('DJANGO_ENV', 'development').lower()

if DJANGO_ENV == 'production':
    print("Loading production settings...")
    from .production import *
else:
    print(f"Loading development settings (DJANGO_ENV='{DJANGO_ENV}')...")
    from .development import *