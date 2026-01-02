#!/bin/bash

# Backup Script for Django FAQ/RAG Application
# Creates comprehensive backups of all application data

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
BACKUP_BASE_DIR="backups"
RETENTION_DAYS=30

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    error "Environment file $ENV_FILE not found"
    exit 1
fi

# Set defaults for database variables
DB_NAME=${DB_NAME:-faq_production}
DB_USER=${DB_USER:-faq_user}
QDRANT_COLLECTION_NAME=${QDRANT_COLLECTION_NAME:-faq_embeddings}

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --full              Create full backup (default)"
    echo "  --database-only     Backup only PostgreSQL database"
    echo "  --vectors-only      Backup only Qdrant vector database"
    echo "  --logs-only         Backup only application logs"
    echo "  --retention DAYS    Set backup retention period (default: 30 days)"
    echo "  --output DIR        Set backup output directory (default: backups)"
    echo "  --compress          Compress backup files (default: enabled)"
    echo "  --no-compress       Disable compression"
    echo "  --verbose           Enable verbose output"
    echo "  --help              Show this help message"
    echo ""
}

check_services() {
    log "Checking service availability..."
    
    # Check if Docker Compose services are running
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        error "No services are running. Please start the application first."
        exit 1
    fi
    
    # Check database connectivity
    if ! docker-compose -f "$COMPOSE_FILE" exec -T db pg_isready -U "$DB_USER" > /dev/null 2>&1; then
        error "Database is not ready"
        exit 1
    fi
    
    # Check Qdrant connectivity
    if ! docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s http://localhost:6333/health > /dev/null 2>&1; then
        warn "Qdrant is not accessible, vector backup will be skipped"
        SKIP_QDRANT=true
    fi
    
    log "Service availability check completed"
}

create_backup_directory() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    BACKUP_DIR="$BACKUP_BASE_DIR/backup_$timestamp"
    
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
    
    # Create metadata file
    cat > "$BACKUP_DIR/backup_metadata.json" << EOF
{
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "backup_type": "$BACKUP_TYPE",
    "application_version": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "database_name": "$DB_NAME",
    "database_user": "$DB_USER",
    "qdrant_collection": "$QDRANT_COLLECTION_NAME",
    "compression_enabled": $COMPRESS_ENABLED
}
EOF
}

backup_database() {
    if [ "$BACKUP_TYPE" != "database-only" ] && [ "$BACKUP_TYPE" != "full" ]; then
        return 0
    fi
    
    log "Backing up PostgreSQL database..."
    
    local db_backup_file="$BACKUP_DIR/postgres_backup.sql"
    
    # Create database backup
    if docker-compose -f "$COMPOSE_FILE" exec -T db pg_dump \
        -U "$DB_USER" \
        -h localhost \
        --verbose \
        --clean \
        --if-exists \
        --create \
        "$DB_NAME" > "$db_backup_file" 2>/dev/null; then
        
        log "Database backup completed: $(du -h "$db_backup_file" | cut -f1)"
        
        # Compress if enabled
        if [ "$COMPRESS_ENABLED" = true ]; then
            log "Compressing database backup..."
            gzip "$db_backup_file"
            db_backup_file="${db_backup_file}.gz"
        fi
        
        # Verify backup integrity
        if [ "$COMPRESS_ENABLED" = true ]; then
            if ! gzip -t "$db_backup_file" 2>/dev/null; then
                error "Database backup compression verification failed"
                return 1
            fi
        else
            if ! head -n 1 "$db_backup_file" | grep -q "PostgreSQL database dump" 2>/dev/null; then
                error "Database backup verification failed"
                return 1
            fi
        fi
        
        log "Database backup verified successfully"
    else
        error "Database backup failed"
        return 1
    fi
}

backup_vectors() {
    if [ "$BACKUP_TYPE" != "vectors-only" ] && [ "$BACKUP_TYPE" != "full" ]; then
        return 0
    fi
    
    if [ "$SKIP_QDRANT" = true ]; then
        warn "Skipping vector database backup (Qdrant not accessible)"
        return 0
    fi
    
    log "Backing up Qdrant vector database..."
    
    local qdrant_backup_file="$BACKUP_DIR/qdrant_backup.tar"
    
    # Create Qdrant snapshot
    local snapshot_name="backup_$(date +%s)"
    if docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s -X POST \
        "http://localhost:6333/collections/$QDRANT_COLLECTION_NAME/snapshots" \
        -H "Content-Type: application/json" \
        -d "{\"snapshot_name\": \"$snapshot_name\"}" > /dev/null 2>&1; then
        
        log "Qdrant snapshot created: $snapshot_name"
        
        # Wait for snapshot to be ready
        sleep 5
        
        # Export Qdrant data directory
        if docker-compose -f "$COMPOSE_FILE" exec -T qdrant tar cf - /qdrant/storage > "$qdrant_backup_file" 2>/dev/null; then
            log "Vector database backup completed: $(du -h "$qdrant_backup_file" | cut -f1)"
            
            # Compress if enabled
            if [ "$COMPRESS_ENABLED" = true ]; then
                log "Compressing vector database backup..."
                gzip "$qdrant_backup_file"
                qdrant_backup_file="${qdrant_backup_file}.gz"
            fi
            
            log "Vector database backup verified successfully"
        else
            error "Vector database backup failed"
            return 1
        fi
    else
        warn "Failed to create Qdrant snapshot, attempting direct backup..."
        
        # Fallback: direct backup without snapshot
        if docker-compose -f "$COMPOSE_FILE" exec -T qdrant tar cf - /qdrant/storage > "$qdrant_backup_file" 2>/dev/null; then
            log "Vector database backup completed (without snapshot): $(du -h "$qdrant_backup_file" | cut -f1)"
            
            if [ "$COMPRESS_ENABLED" = true ]; then
                gzip "$qdrant_backup_file"
            fi
        else
            error "Vector database backup failed"
            return 1
        fi
    fi
}

backup_logs() {
    if [ "$BACKUP_TYPE" != "logs-only" ] && [ "$BACKUP_TYPE" != "full" ]; then
        return 0
    fi
    
    log "Backing up application logs..."
    
    local logs_backup_file="$BACKUP_DIR/logs_backup.tar"
    
    # Check if logs directory exists
    if [ -d "logs" ]; then
        if tar cf "$logs_backup_file" logs/ 2>/dev/null; then
            log "Logs backup completed: $(du -h "$logs_backup_file" | cut -f1)"
            
            # Compress if enabled
            if [ "$COMPRESS_ENABLED" = true ]; then
                log "Compressing logs backup..."
                gzip "$logs_backup_file"
            fi
        else
            warn "Logs backup failed or no logs found"
        fi
    else
        warn "Logs directory not found, skipping logs backup"
    fi
}

backup_configuration() {
    if [ "$BACKUP_TYPE" != "full" ]; then
        return 0
    fi
    
    log "Backing up configuration files..."
    
    local config_backup_file="$BACKUP_DIR/config_backup.tar"
    
    # Backup configuration files (excluding sensitive .env)
    local config_files=(
        "docker-compose.yml"
        "docker-compose.prod.yml"
        "docker-compose.override.yml"
        "nginx/"
        "redis/"
        "postgres/"
        "qdrant/"
        "gunicorn.conf.py"
        "requirements.txt"
        "Dockerfile"
        ".dockerignore"
    )
    
    local existing_files=()
    for file in "${config_files[@]}"; do
        if [ -e "$file" ]; then
            existing_files+=("$file")
        fi
    done
    
    if [ ${#existing_files[@]} -gt 0 ]; then
        if tar cf "$config_backup_file" "${existing_files[@]}" 2>/dev/null; then
            log "Configuration backup completed: $(du -h "$config_backup_file" | cut -f1)"
            
            # Compress if enabled
            if [ "$COMPRESS_ENABLED" = true ]; then
                gzip "$config_backup_file"
            fi
        else
            warn "Configuration backup failed"
        fi
    else
        warn "No configuration files found to backup"
    fi
}

cleanup_old_backups() {
    log "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
    
    if [ -d "$BACKUP_BASE_DIR" ]; then
        # Find and remove backups older than retention period
        local deleted_count=0
        while IFS= read -r -d '' backup_dir; do
            if [ -d "$backup_dir" ]; then
                rm -rf "$backup_dir"
                deleted_count=$((deleted_count + 1))
            fi
        done < <(find "$BACKUP_BASE_DIR" -maxdepth 1 -type d -name "backup_*" -mtime +$RETENTION_DAYS -print0 2>/dev/null)
        
        if [ $deleted_count -gt 0 ]; then
            log "Removed $deleted_count old backup(s)"
        else
            log "No old backups to remove"
        fi
    fi
}

create_backup_summary() {
    log "Creating backup summary..."
    
    local summary_file="$BACKUP_DIR/backup_summary.txt"
    
    cat > "$summary_file" << EOF
Django FAQ/RAG Application Backup Summary
========================================

Backup Date: $(date)
Backup Type: $BACKUP_TYPE
Backup Directory: $BACKUP_DIR
Compression: $([ "$COMPRESS_ENABLED" = true ] && echo "Enabled" || echo "Disabled")

Files Created:
EOF
    
    # List all files in backup directory with sizes
    if command -v ls &> /dev/null; then
        ls -lh "$BACKUP_DIR" >> "$summary_file"
    fi
    
    echo "" >> "$summary_file"
    echo "Total Backup Size: $(du -sh "$BACKUP_DIR" | cut -f1)" >> "$summary_file"
    
    log "Backup summary created: $summary_file"
}

# Parse command line arguments
BACKUP_TYPE="full"
COMPRESS_ENABLED=true
VERBOSE=false
SKIP_QDRANT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            BACKUP_TYPE="full"
            shift
            ;;
        --database-only)
            BACKUP_TYPE="database-only"
            shift
            ;;
        --vectors-only)
            BACKUP_TYPE="vectors-only"
            shift
            ;;
        --logs-only)
            BACKUP_TYPE="logs-only"
            shift
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --output)
            BACKUP_BASE_DIR="$2"
            shift 2
            ;;
        --compress)
            COMPRESS_ENABLED=true
            shift
            ;;
        --no-compress)
            COMPRESS_ENABLED=false
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
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
    log "Starting backup process (type: $BACKUP_TYPE)"
    
    # Check prerequisites
    check_services
    
    # Create backup directory
    create_backup_directory
    
    # Perform backups based on type
    case $BACKUP_TYPE in
        full)
            backup_database
            backup_vectors
            backup_logs
            backup_configuration
            ;;
        database-only)
            backup_database
            ;;
        vectors-only)
            backup_vectors
            ;;
        logs-only)
            backup_logs
            ;;
    esac
    
    # Create backup summary
    create_backup_summary
    
    # Cleanup old backups
    cleanup_old_backups
    
    log "Backup process completed successfully!"
    log "Backup location: $BACKUP_DIR"
    log "Total backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
}

# Run main function
main