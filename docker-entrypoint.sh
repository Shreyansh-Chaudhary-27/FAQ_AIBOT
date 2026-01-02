#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Function to wait for database
wait_for_db() {
    log "Waiting for database connection..."
    
    # Extract database connection details from DATABASE_URL or individual env vars
    if [ -n "$DATABASE_URL" ]; then
        # Parse DATABASE_URL (format: postgres://user:pass@host:port/dbname)
        DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    else
        DB_HOST=${DB_HOST:-localhost}
        DB_PORT=${DB_PORT:-5432}
    fi
    
    # Wait for database to be ready
    until python -c "
import psycopg2
import sys
import os
from urllib.parse import urlparse

try:
    if os.environ.get('DATABASE_URL'):
        # Parse DATABASE_URL
        url = urlparse(os.environ['DATABASE_URL'])
        conn = psycopg2.connect(
            host=url.hostname,
            port=url.port,
            user=url.username,
            password=url.password,
            database=url.path[1:]
        )
    else:
        # Use individual environment variables
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=os.environ.get('DB_PORT', '5432'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', ''),
            database=os.environ.get('DB_NAME', 'postgres')
        )
    conn.close()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(1)
"; do
        warn "Database is unavailable - sleeping for 2 seconds"
        sleep 2
    done
    
    log "Database is ready!"
}

# Function to run Django migrations
run_migrations() {
    log "Running Django migrations..."
    
    if python manage.py migrate --check > /dev/null 2>&1; then
        log "No migrations needed"
    else
        log "Applying migrations..."
        python manage.py migrate --noinput
        if [ $? -eq 0 ]; then
            log "Migrations completed successfully"
        else
            error "Migration failed"
            exit 1
        fi
    fi
}

# Function to collect static files
collect_static() {
    log "Collecting static files..."
    python manage.py collectstatic --noinput --clear
    if [ $? -eq 0 ]; then
        log "Static files collected successfully"
    else
        warn "Static file collection failed, continuing anyway"
    fi
}

# Function to create superuser if needed
create_superuser() {
    if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ] && [ "$DJANGO_SUPERUSER_EMAIL" ]; then
        log "Creating superuser if it doesn't exist..."
        python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"
    fi
}

# Function to initialize RAG system
init_rag_system() {
    log "Initializing RAG system..."
    if python manage.py init_rag_system > /dev/null 2>&1; then
        log "RAG system initialized successfully"
    else
        warn "RAG system initialization failed, continuing anyway"
    fi
}

# Function to initialize Qdrant vector database
init_qdrant() {
    log "Initializing Qdrant vector database..."
    if python manage.py init_qdrant --health-check-only > /dev/null 2>&1; then
        log "Qdrant health check passed"
        
        # Initialize collection if needed
        if python manage.py init_qdrant > /dev/null 2>&1; then
            log "Qdrant initialization completed successfully"
        else
            warn "Qdrant initialization failed, continuing anyway"
        fi
    else
        warn "Qdrant health check failed, continuing anyway"
    fi
}

# Graceful shutdown handler
shutdown_handler() {
    log "Received shutdown signal, performing graceful shutdown..."
    
    # If gunicorn is running, send SIGTERM to allow graceful shutdown
    if [ -n "$GUNICORN_PID" ]; then
        log "Stopping Gunicorn gracefully..."
        kill -TERM "$GUNICORN_PID"
        wait "$GUNICORN_PID"
    fi
    
    log "Shutdown complete"
    exit 0
}

# Set up signal handlers for graceful shutdown
trap shutdown_handler SIGTERM SIGINT

# Main execution
main() {
    log "Starting Django application initialization..."
    
    # Validate required environment variables
    if [ -z "$SECRET_KEY" ]; then
        error "SECRET_KEY environment variable is required"
        exit 1
    fi
    
    # Wait for database if not in development mode
    if [ "$DJANGO_SETTINGS_MODULE" != "faqbackend.settings.development" ]; then
        wait_for_db
    fi
    
    # Run initialization steps
    run_migrations
    collect_static
    create_superuser
    init_qdrant
    init_rag_system
    
    log "Initialization complete, starting application..."
    
    # Execute the main command
    if [ "$1" = "gunicorn" ]; then
        log "Starting Gunicorn server..."
        exec "$@" &
        GUNICORN_PID=$!
        wait "$GUNICORN_PID"
    else
        log "Executing command: $@"
        exec "$@"
    fi
}

# Run main function with all arguments
main "$@"