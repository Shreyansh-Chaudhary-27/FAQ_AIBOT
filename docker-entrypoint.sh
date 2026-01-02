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

# Function to wait for database (REMOVED - using Pinecone only)
wait_for_db() {
    log "Using Pinecone vector database - no database connection wait needed"
    return 0
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

# Function to initialize Pinecone vector database
init_pinecone() {
    log "Initializing Pinecone vector database..."
    if python manage.py shell -c "
from faq.rag.components.vector_store.vector_store_factory import VectorStoreFactory
try:
    store = VectorStoreFactory.create_production_store()
    health = store.health_check()
    print(f'Pinecone health check: {health.get(\"status\", \"unknown\")}')
    if health.get('status') == 'healthy':
        print('Pinecone connection successful')
    else:
        print('Pinecone connection degraded but functional')
except Exception as e:
    print(f'Pinecone initialization failed: {e}')
    raise
" > /dev/null 2>&1; then
        log "Pinecone vector database initialized successfully"
    else
        warn "Pinecone initialization failed, continuing anyway"
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
    
    if [ -z "$PINECONE_API_KEY" ]; then
        error "PINECONE_API_KEY environment variable is required"
        exit 1
    fi
    
    # No database waiting needed - using Pinecone vector database
    log "Using Pinecone vector database - no external database dependencies"
    
    # Run initialization steps
    run_migrations
    collect_static
    create_superuser
    init_pinecone
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