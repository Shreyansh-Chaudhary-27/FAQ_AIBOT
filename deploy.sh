#!/bin/bash

# Production Deployment Script for Django FAQ/RAG Application
# This script automates the deployment process with Qdrant vector database

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
COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
BACKUP_DIR="backups"
DEPLOYMENT_LOG="deployment.log"

# Functions
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  deploy          Deploy the application stack"
    echo "  update          Update and restart the application"
    echo "  stop            Stop all services"
    echo "  restart         Restart all services"
    echo "  logs            Show application logs"
    echo "  backup          Create backup of databases"
    echo "  restore         Restore from backup"
    echo "  health          Check system health"
    echo "  test-qdrant     Test Qdrant connectivity"
    echo "  cleanup         Clean up unused Docker resources"
    echo ""
    echo "Options:"
    echo "  --env-file FILE    Use specific environment file (default: .env)"
    echo "  --no-backup       Skip backup during deployment"
    echo "  --force           Force deployment without confirmations"
    echo "  --verbose         Enable verbose output"
    echo ""
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file $ENV_FILE not found"
        error "Please copy .env.example to .env and configure it"
        exit 1
    fi
    
    # Check required environment variables
    source "$ENV_FILE"
    
    required_vars=("SECRET_KEY" "DB_PASSWORD" "GEMINI_API_KEY")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            error "Required environment variable $var is not set in $ENV_FILE"
            exit 1
        fi
    done
    
    log "Prerequisites check passed"
}

create_backup() {
    if [ "$SKIP_BACKUP" = "true" ]; then
        info "Skipping backup as requested"
        return 0
    fi
    
    log "Creating backup..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Generate backup filename with timestamp
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
    
    # Check if services are running
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        # Backup PostgreSQL database
        log "Backing up PostgreSQL database..."
        docker-compose -f "$COMPOSE_FILE" exec -T db pg_dump -U "${DB_USER:-faq_user}" "${DB_NAME:-faq_production}" > "$BACKUP_DIR/postgres_$TIMESTAMP.sql"
        
        # Backup Qdrant data (if accessible)
        log "Backing up Qdrant vector data..."
        if docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s http://localhost:6333/collections > /dev/null 2>&1; then
            # Create a snapshot of Qdrant collections
            docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -X POST "http://localhost:6333/collections/${QDRANT_COLLECTION_NAME:-faq_embeddings}/snapshots" > /dev/null 2>&1 || warn "Qdrant snapshot creation failed"
        fi
        
        # Create compressed backup
        tar -czf "$BACKUP_FILE" -C "$BACKUP_DIR" "postgres_$TIMESTAMP.sql" 2>/dev/null || warn "Backup compression failed"
        
        # Clean up temporary files
        rm -f "$BACKUP_DIR/postgres_$TIMESTAMP.sql"
        
        log "Backup created: $BACKUP_FILE"
    else
        warn "Services not running, skipping database backup"
    fi
}

deploy_application() {
    log "Starting deployment..."
    
    # Create backup before deployment
    create_backup
    
    # Pull latest images
    log "Pulling latest Docker images..."
    docker-compose -f "$COMPOSE_FILE" pull
    
    # Build application image
    log "Building application image..."
    docker-compose -f "$COMPOSE_FILE" build app
    
    # Start services
    log "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log "Waiting for services to be healthy..."
    
    # Wait for database
    timeout=60
    while [ $timeout -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" exec -T db pg_isready -U "${DB_USER:-faq_user}" > /dev/null 2>&1; then
            log "Database is ready"
            break
        fi
        sleep 2
        timeout=$((timeout - 2))
    done
    
    if [ $timeout -le 0 ]; then
        error "Database failed to become ready within timeout"
        exit 1
    fi
    
    # Wait for Qdrant
    timeout=60
    while [ $timeout -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s http://localhost:6333/health > /dev/null 2>&1; then
            log "Qdrant is ready"
            break
        fi
        sleep 2
        timeout=$((timeout - 2))
    done
    
    if [ $timeout -le 0 ]; then
        warn "Qdrant failed to become ready within timeout, continuing anyway"
    fi
    
    # Wait for application
    timeout=120
    while [ $timeout -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" exec -T app curl -s http://localhost:8000/health/ > /dev/null 2>&1; then
            log "Application is ready"
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ $timeout -le 0 ]; then
        error "Application failed to become ready within timeout"
        exit 1
    fi
    
    log "Deployment completed successfully!"
    
    # Show service status
    show_status
}

update_application() {
    log "Updating application..."
    
    # Create backup before update
    create_backup
    
    # Pull latest changes and rebuild
    log "Rebuilding application..."
    docker-compose -f "$COMPOSE_FILE" build app
    
    # Restart application service
    log "Restarting application service..."
    docker-compose -f "$COMPOSE_FILE" up -d app
    
    # Wait for application to be ready
    timeout=60
    while [ $timeout -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" exec -T app curl -s http://localhost:8000/health/ > /dev/null 2>&1; then
            log "Application update completed successfully"
            return 0
        fi
        sleep 5
        timeout=$((timeout - 5))
    done
    
    error "Application failed to restart properly after update"
    exit 1
}

show_logs() {
    log "Showing application logs..."
    docker-compose -f "$COMPOSE_FILE" logs -f --tail=100 app
}

show_status() {
    log "Service Status:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log "Health Checks:"
    
    # Check application health
    if docker-compose -f "$COMPOSE_FILE" exec -T app curl -s http://localhost:8000/health/ > /dev/null 2>&1; then
        echo -e "  Application: ${GREEN}✓ Healthy${NC}"
    else
        echo -e "  Application: ${RED}✗ Unhealthy${NC}"
    fi
    
    # Check database health
    if docker-compose -f "$COMPOSE_FILE" exec -T db pg_isready -U "${DB_USER:-faq_user}" > /dev/null 2>&1; then
        echo -e "  Database: ${GREEN}✓ Healthy${NC}"
    else
        echo -e "  Database: ${RED}✗ Unhealthy${NC}"
    fi
    
    # Check Qdrant health
    if docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo -e "  Qdrant: ${GREEN}✓ Healthy${NC}"
    else
        echo -e "  Qdrant: ${RED}✗ Unhealthy${NC}"
    fi
    
    # Check Redis health
    if docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "  Redis: ${GREEN}✓ Healthy${NC}"
    else
        echo -e "  Redis: ${RED}✗ Unhealthy${NC}"
    fi
}

test_qdrant() {
    log "Testing Qdrant connectivity..."
    
    if docker-compose -f "$COMPOSE_FILE" exec -T app python manage.py test_qdrant --verbose; then
        log "Qdrant test completed successfully"
    else
        error "Qdrant test failed"
        exit 1
    fi
}

cleanup_docker() {
    log "Cleaning up Docker resources..."
    
    # Remove unused containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes (be careful with this)
    if [ "$FORCE" = "true" ]; then
        docker volume prune -f
    else
        warn "Skipping volume cleanup (use --force to enable)"
    fi
    
    # Remove unused networks
    docker network prune -f
    
    log "Docker cleanup completed"
}

stop_services() {
    log "Stopping services..."
    docker-compose -f "$COMPOSE_FILE" down
    log "Services stopped"
}

restart_services() {
    log "Restarting services..."
    docker-compose -f "$COMPOSE_FILE" restart
    log "Services restarted"
}

# Parse command line arguments
COMMAND=""
SKIP_BACKUP="false"
FORCE="false"
VERBOSE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        deploy|update|stop|restart|logs|backup|restore|health|test-qdrant|cleanup)
            COMMAND="$1"
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --no-backup)
            SKIP_BACKUP="true"
            shift
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
    # Log deployment start
    echo "$(date): Starting deployment with command: $COMMAND" >> "$DEPLOYMENT_LOG"
    
    # Check prerequisites
    check_prerequisites
    
    # Execute command
    case $COMMAND in
        deploy)
            deploy_application
            ;;
        update)
            update_application
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        logs)
            show_logs
            ;;
        backup)
            create_backup
            ;;
        health)
            show_status
            ;;
        test-qdrant)
            test_qdrant
            ;;
        cleanup)
            cleanup_docker
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
    
    # Log deployment end
    echo "$(date): Completed deployment command: $COMMAND" >> "$DEPLOYMENT_LOG"
}

# Run main function
main