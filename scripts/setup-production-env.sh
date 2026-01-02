#!/bin/bash

# Production Environment Setup Script
# This script helps configure production environment variables and validates the setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Configuration
ENV_FILE=".env"
ENV_PRODUCTION_FILE=".env.production"
ENV_EXAMPLE_FILE=".env.example"

show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  setup           Interactive setup of production environment"
    echo "  validate        Validate current environment configuration"
    echo "  generate-secret Generate a new Django secret key"
    echo "  test-db         Test database connection"
    echo "  test-qdrant     Test Qdrant vector database connection"
    echo "  test-gemini     Test Gemini API connection"
    echo "  create-dirs     Create required data directories"
    echo ""
    echo "Options:"
    echo "  --env-file FILE    Use specific environment file (default: .env)"
    echo "  --force           Overwrite existing configuration"
    echo "  --verbose         Enable verbose output"
    echo ""
}

generate_secret_key() {
    log "Generating new Django secret key..."
    
    # Generate a secure random secret key
    SECRET_KEY=$(python3 -c "
import secrets
import string
alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
secret_key = ''.join(secrets.choice(alphabet) for i in range(50))
print(secret_key)
")
    
    echo "Generated secret key: $SECRET_KEY"
    echo ""
    echo "Add this to your .env file:"
    echo "SECRET_KEY=$SECRET_KEY"
}

create_directories() {
    log "Creating required data directories..."
    
    # Create data directories
    mkdir -p data/postgres
    mkdir -p data/qdrant
    mkdir -p data/redis
    mkdir -p logs
    mkdir -p logs/nginx
    mkdir -p backups
    
    # Set appropriate permissions
    chmod 755 data
    chmod 755 data/postgres
    chmod 755 data/qdrant
    chmod 755 data/redis
    chmod 755 logs
    chmod 755 logs/nginx
    chmod 755 backups
    
    log "Directories created successfully"
}

validate_environment() {
    log "Validating environment configuration..."
    
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file $ENV_FILE not found"
        error "Run 'setup' command first or copy .env.production to .env"
        return 1
    fi
    
    # Source environment file
    source "$ENV_FILE"
    
    # Check required variables
    local errors=0
    
    # Django core settings
    if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "django-insecure-CHANGE-THIS-IN-PRODUCTION-use-djecrety-ir-to-generate" ]; then
        error "SECRET_KEY is not set or using default value"
        errors=$((errors + 1))
    fi
    
    if [ "$DEBUG" = "True" ] || [ "$DEBUG" = "true" ]; then
        error "DEBUG is set to True - this is dangerous in production"
        errors=$((errors + 1))
    fi
    
    if [ -z "$ALLOWED_HOSTS" ] || [[ "$ALLOWED_HOSTS" == *"your-domain.com"* ]]; then
        error "ALLOWED_HOSTS contains default values - update with your actual domain"
        errors=$((errors + 1))
    fi
    
    # Database settings
    if [ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "CHANGE-THIS-SECURE-PASSWORD" ]; then
        error "DB_PASSWORD is not set or using default value"
        errors=$((errors + 1))
    fi
    
    # Gemini API key
    if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "YOUR-GEMINI-API-KEY-HERE" ]; then
        error "GEMINI_API_KEY is not set or using default value"
        errors=$((errors + 1))
    fi
    
    # Security settings
    if [[ "$CSRF_TRUSTED_ORIGINS" == *"your-domain.com"* ]]; then
        warn "CSRF_TRUSTED_ORIGINS contains default values - update with your actual domain"
    fi
    
    if [ $errors -eq 0 ]; then
        log "Environment validation passed"
        return 0
    else
        error "Environment validation failed with $errors errors"
        return 1
    fi
}

test_database_connection() {
    log "Testing database connection..."
    
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file $ENV_FILE not found"
        return 1
    fi
    
    source "$ENV_FILE"
    
    # Test PostgreSQL connection using Docker
    if docker run --rm --network host postgres:15-alpine pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "${DB_USER:-faq_user}" > /dev/null 2>&1; then
        log "Database connection successful"
        return 0
    else
        error "Database connection failed"
        error "Make sure PostgreSQL is running and accessible"
        return 1
    fi
}

test_qdrant_connection() {
    log "Testing Qdrant connection..."
    
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file $ENV_FILE not found"
        return 1
    fi
    
    source "$ENV_FILE"
    
    # Test Qdrant connection
    QDRANT_URL="http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}"
    
    if curl -s "$QDRANT_URL/health" > /dev/null 2>&1; then
        log "Qdrant connection successful"
        return 0
    else
        error "Qdrant connection failed"
        error "Make sure Qdrant is running at $QDRANT_URL"
        return 1
    fi
}

test_gemini_api() {
    log "Testing Gemini API connection..."
    
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file $ENV_FILE not found"
        return 1
    fi
    
    source "$ENV_FILE"
    
    if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "YOUR-GEMINI-API-KEY-HERE" ]; then
        error "GEMINI_API_KEY is not configured"
        return 1
    fi
    
    # Test Gemini API with a simple request
    python3 -c "
import os
import google.generativeai as genai

try:
    genai.configure(api_key='$GEMINI_API_KEY')
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    response = model.generate_content('Hello')
    print('Gemini API connection successful')
    exit(0)
except Exception as e:
    print(f'Gemini API connection failed: {e}')
    exit(1)
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        log "Gemini API connection successful"
        return 0
    else
        error "Gemini API connection failed"
        error "Check your GEMINI_API_KEY and internet connection"
        return 1
    fi
}

interactive_setup() {
    log "Starting interactive production environment setup..."
    
    # Check if .env already exists
    if [ -f "$ENV_FILE" ] && [ "$FORCE" != "true" ]; then
        warn "Environment file $ENV_FILE already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Setup cancelled"
            return 0
        fi
    fi
    
    # Copy production template
    if [ -f "$ENV_PRODUCTION_FILE" ]; then
        cp "$ENV_PRODUCTION_FILE" "$ENV_FILE"
        log "Copied $ENV_PRODUCTION_FILE to $ENV_FILE"
    elif [ -f "$ENV_EXAMPLE_FILE" ]; then
        cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
        log "Copied $ENV_EXAMPLE_FILE to $ENV_FILE"
    else
        error "No template file found (.env.production or .env.example)"
        return 1
    fi
    
    echo ""
    info "Please edit $ENV_FILE and update the following required values:"
    echo ""
    echo "1. SECRET_KEY - Generate a new one with: $0 generate-secret"
    echo "2. DB_PASSWORD - Set a secure database password"
    echo "3. GEMINI_API_KEY - Your Gemini AI API key"
    echo "4. ALLOWED_HOSTS - Your production domain(s)"
    echo "5. CSRF_TRUSTED_ORIGINS - Your production HTTPS URLs"
    echo ""
    
    read -p "Press Enter to open $ENV_FILE in your default editor..."
    ${EDITOR:-nano} "$ENV_FILE"
    
    echo ""
    log "Configuration file updated. Running validation..."
    
    if validate_environment; then
        log "Setup completed successfully!"
        echo ""
        info "Next steps:"
        echo "1. Create data directories: $0 create-dirs"
        echo "2. Test connections: $0 validate"
        echo "3. Deploy application: ./deploy.sh deploy"
    else
        warn "Setup completed but validation failed"
        warn "Please fix the validation errors before deploying"
    fi
}

# Parse command line arguments
COMMAND=""
FORCE="false"
VERBOSE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        setup|validate|generate-secret|test-db|test-qdrant|test-gemini|create-dirs)
            COMMAND="$1"
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --force)
            FORCE="true"
            shift
            ;;
        --verbose)
            VERBOSE="true"
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    case $COMMAND in
        setup)
            interactive_setup
            ;;
        validate)
            validate_environment
            ;;
        generate-secret)
            generate_secret_key
            ;;
        test-db)
            test_database_connection
            ;;
        test-qdrant)
            test_qdrant_connection
            ;;
        test-gemini)
            test_gemini_api
            ;;
        create-dirs)
            create_directories
            ;;
        "")
            error "No command specified"
            show_usage
            exit 1
            ;;
        *)
            error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main