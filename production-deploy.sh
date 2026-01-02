#!/bin/bash

# Production Deployment Configuration Script
# This script sets up and validates the production environment configuration

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

show_usage() {
    echo "Production Deployment Configuration"
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup           Set up production environment configuration"
    echo "  validate        Validate production configuration"
    echo "  deploy          Deploy to production with validation"
    echo "  test-services   Test all service connections"
    echo "  generate-env    Generate production environment file"
    echo ""
}

generate_production_env() {
    log "Generating production environment configuration..."
    
    # Check if .env.production exists
    if [ ! -f "$ENV_PRODUCTION_FILE" ]; then
        error "Production template file $ENV_PRODUCTION_FILE not found"
        return 1
    fi
    
    # Copy production template to .env
    cp "$ENV_PRODUCTION_FILE" "$ENV_FILE"
    log "Copied $ENV_PRODUCTION_FILE to $ENV_FILE"
    
    # Generate a secure secret key
    log "Generating secure Django secret key..."
    SECRET_KEY=$(python3 -c "
import secrets
import string
alphabet = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
secret_key = ''.join(secrets.choice(alphabet) for i in range(50))
print(secret_key)
")
    
    # Replace placeholder values in .env file
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/SECRET_KEY=django-insecure-CHANGE-THIS-IN-PRODUCTION-use-djecrety-ir-to-generate/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
    else
        # Linux
        sed -i "s/SECRET_KEY=django-insecure-CHANGE-THIS-IN-PRODUCTION-use-djecrety-ir-to-generate/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE"
    fi
    
    log "Generated secure secret key"
    
    echo ""
    warn "IMPORTANT: Please update the following values in $ENV_FILE:"
    echo "1. DB_PASSWORD - Set a secure database password"
    echo "2. GEMINI_API_KEY - Your Gemini AI API key"
    echo "3. ALLOWED_HOSTS - Your production domain(s)"
    echo "4. CSRF_TRUSTED_ORIGINS - Your production HTTPS URLs"
    echo ""
}

validate_configuration() {
    log "Validating production configuration..."
    
    # Run the Python validation script
    if python3 validate_production_config.py; then
        log "Configuration validation passed"
        return 0
    else
        error "Configuration validation failed"
        return 1
    fi
}

test_service_connections() {
    log "Testing service connections..."
    
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file $ENV_FILE not found"
        return 1
    fi
    
    # Source environment variables
    source "$ENV_FILE"
    
    local success=true
    
    # Test database connection (if PostgreSQL is running)
    log "Testing database connection..."
    if command -v pg_isready &> /dev/null; then
        if pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "${DB_USER:-faq_user}" > /dev/null 2>&1; then
            log "✅ Database connection successful"
        else
            warn "❌ Database connection failed (service may not be running)"
            success=false
        fi
    else
        warn "pg_isready not available, skipping database test"
    fi
    
    # Test Qdrant connection (if Qdrant is running)
    log "Testing Qdrant connection..."
    QDRANT_URL="http://${QDRANT_HOST:-localhost}:${QDRANT_PORT:-6333}"
    if curl -s "$QDRANT_URL/health" > /dev/null 2>&1; then
        log "✅ Qdrant connection successful"
    else
        warn "❌ Qdrant connection failed (service may not be running)"
        success=false
    fi
    
    # Test Gemini API (if API key is configured)
    if [ -n "$GEMINI_API_KEY" ] && [ "$GEMINI_API_KEY" != "YOUR-GEMINI-API-KEY-HERE" ]; then
        log "Testing Gemini API connection..."
        if python3 -c "
import os
import google.generativeai as genai
try:
    genai.configure(api_key='$GEMINI_API_KEY')
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    response = model.generate_content('Hello')
    print('Gemini API test successful')
    exit(0)
except Exception as e:
    print(f'Gemini API test failed: {e}')
    exit(1)
" 2>/dev/null; then
            log "✅ Gemini API connection successful"
        else
            warn "❌ Gemini API connection failed"
            success=false
        fi
    else
        warn "Gemini API key not configured, skipping test"
    fi
    
    if $success; then
        log "All available service connections tested successfully"
        return 0
    else
        warn "Some service connections failed (services may not be running)"
        return 1
    fi
}

setup_production() {
    log "Setting up production environment..."
    
    # Create required directories
    log "Creating required directories..."
    mkdir -p data/postgres data/qdrant data/redis logs logs/nginx backups
    
    # Generate environment configuration
    generate_production_env
    
    echo ""
    info "Production environment setup completed!"
    echo ""
    info "Next steps:"
    echo "1. Edit $ENV_FILE and update the required values"
    echo "2. Run: $0 validate"
    echo "3. Run: $0 deploy"
    echo ""
}

deploy_production() {
    log "Starting production deployment..."
    
    # Validate configuration first
    if ! validate_configuration; then
        error "Configuration validation failed. Please fix errors before deploying."
        return 1
    fi
    
    # Test service connections (optional, may fail if services aren't running yet)
    test_service_connections || warn "Some service tests failed, continuing with deployment..."
    
    # Run the main deployment script
    log "Running deployment script..."
    if [ -f "deploy.sh" ]; then
        chmod +x deploy.sh
        ./deploy.sh deploy
    else
        error "Deployment script deploy.sh not found"
        return 1
    fi
    
    log "Production deployment completed!"
}

# Parse command line arguments
COMMAND="$1"

case $COMMAND in
    setup)
        setup_production
        ;;
    validate)
        validate_configuration
        ;;
    deploy)
        deploy_production
        ;;
    test-services)
        test_service_connections
        ;;
    generate-env)
        generate_production_env
        ;;
    "")
        show_usage
        ;;
    *)
        error "Unknown command: $COMMAND"
        show_usage
        exit 1
        ;;
esac