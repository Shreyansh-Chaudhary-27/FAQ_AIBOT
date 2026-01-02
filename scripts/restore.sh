#!/bin/bash

# Restore Script for Django FAQ/RAG Application
# Restores application data from backups created by backup.sh

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
    echo "Usage: $0 [OPTIONS] BACKUP_DIRECTORY"
    echo ""
    echo "Arguments:"
    echo "  BACKUP_DIRECTORY    Path to backup directory to restore from"
    echo ""
    echo "Options:"
    echo "  --database-only     Restore only PostgreSQL database"
    echo "  --vectors-only      Restore only Qdrant vector database"
    echo "  --logs-only         Restore only application logs"
    echo "  --config-only       Restore only configuration files"
    echo "  --force             Skip confirmation prompts"
    echo "  --no-restart        Don't restart services after restore"
    echo "  --verbose           Enable verbose output"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backups/backup_20240101_120000"
    echo "  $0 --database-only backups/backup_20240101_120000"
    echo "  $0 --force --no-restart backups/backup_20240101_120000"
    echo ""
}

list_available_backups() {
    log "Available backups:"
    
    if [ -d "$BACKUP_BASE_DIR" ]; then
        local backup_count=0
        for backup_dir in "$BACKUP_BASE_DIR"/backup_*; do
            if [ -d "$backup_dir" ]; then
                local backup_name=$(basename "$backup_dir")
                local backup_date=$(echo "$backup_name" | sed 's/backup_//' | sed 's/_/ /')
                local backup_size=$(du -sh "$backup_dir" 2>/dev/null | cut -f1)
                
                echo "  - $backup_name (Size: $backup_size, Date: $backup_date)"
                backup_count=$((backup_count + 1))
            fi
        done
        
        if [ $backup_count -eq 0 ]; then
            warn "No backups found in $BACKUP_BASE_DIR"
        fi
    else
        warn "Backup directory $BACKUP_BASE_DIR does not exist"
    fi
}

validate_backup_directory() {
    local backup_dir="$1"
    
    if [ ! -d "$backup_dir" ]; then
        error "Backup directory does not exist: $backup_dir"
        return 1
    fi
    
    # Check for backup metadata
    if [ -f "$backup_dir/backup_metadata.json" ]; then
        log "Found backup metadata:"
        if command -v jq &> /dev/null; then
            jq . "$backup_dir/backup_metadata.json"
        else
            cat "$backup_dir/backup_metadata.json"
        fi
    else
        warn "No backup metadata found, proceeding anyway"
    fi
    
    # Check for backup files
    local has_database=false
    local has_vectors=false
    local has_logs=false
    local has_config=false
    
    if [ -f "$backup_dir/postgres_backup.sql" ] || [ -f "$backup_dir/postgres_backup.sql.gz" ]; then
        has_database=true
        info "Database backup found"
    fi
    
    if [ -f "$backup_dir/qdrant_backup.tar" ] || [ -f "$backup_dir/qdrant_backup.tar.gz" ]; then
        has_vectors=true
        info "Vector database backup found"
    fi
    
    if [ -f "$backup_dir/logs_backup.tar" ] || [ -f "$backup_dir/logs_backup.tar.gz" ]; then
        has_logs=true
        info "Logs backup found"
    fi
    
    if [ -f "$backup_dir/config_backup.tar" ] || [ -f "$backup_dir/config_backup.tar.gz" ]; then
        has_config=true
        info "Configuration backup found"
    fi
    
    if [ "$has_database" = false ] && [ "$has_vectors" = false ] && [ "$has_logs" = false ] && [ "$has_config" = false ]; then
        error "No valid backup files found in $backup_dir"
        return 1
    fi
    
    return 0
}

check_services() {
    log "Checking service availability..."
    
    # Check if Docker Compose services are running
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        warn "Services are not running. Starting services..."
        docker-compose -f "$COMPOSE_FILE" up -d
        
        # Wait for services to be ready
        sleep 30
    fi
    
    # Check database connectivity
    local timeout=60
    while [ $timeout -gt 0 ]; do
        if docker-compose -f "$COMPOSE_FILE" exec -T db pg_isready -U "$DB_USER" > /dev/null 2>&1; then
            log "Database is ready"
            break
        fi
        sleep 2
        timeout=$((timeout - 2))
    done
    
    if [ $timeout -le 0 ]; then
        error "Database is not ready"
        return 1
    fi
    
    # Check Qdrant connectivity
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
        warn "Qdrant is not ready, vector restore will be skipped"
        SKIP_QDRANT=true
    fi
    
    log "Service availability check completed"
}

restore_database() {
    if [ "$RESTORE_TYPE" != "database-only" ] && [ "$RESTORE_TYPE" != "full" ]; then
        return 0
    fi
    
    local backup_file=""
    if [ -f "$BACKUP_DIR/postgres_backup.sql.gz" ]; then
        backup_file="$BACKUP_DIR/postgres_backup.sql.gz"
    elif [ -f "$BACKUP_DIR/postgres_backup.sql" ]; then
        backup_file="$BACKUP_DIR/postgres_backup.sql"
    else
        warn "No database backup found, skipping database restore"
        return 0
    fi
    
    log "Restoring PostgreSQL database from: $backup_file"
    
    # Create a pre-restore backup
    if [ "$FORCE" != true ]; then
        log "Creating pre-restore backup..."
        local pre_restore_backup="$BACKUP_BASE_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).sql"
        docker-compose -f "$COMPOSE_FILE" exec -T db pg_dump -U "$DB_USER" "$DB_NAME" > "$pre_restore_backup" 2>/dev/null || warn "Pre-restore backup failed"
    fi
    
    # Stop application to prevent database access during restore
    log "Stopping application service..."
    docker-compose -f "$COMPOSE_FILE" stop app
    
    # Restore database
    if [[ "$backup_file" == *.gz ]]; then
        log "Decompressing and restoring database..."
        if gunzip -c "$backup_file" | docker-compose -f "$COMPOSE_FILE" exec -T db psql -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
            log "Database restore completed successfully"
        else
            error "Database restore failed"
            return 1
        fi
    else
        log "Restoring database..."
        if docker-compose -f "$COMPOSE_FILE" exec -T db psql -U "$DB_USER" -d "$DB_NAME" < "$backup_file" > /dev/null 2>&1; then
            log "Database restore completed successfully"
        else
            error "Database restore failed"
            return 1
        fi
    fi
    
    # Restart application
    if [ "$NO_RESTART" != true ]; then
        log "Restarting application service..."
        docker-compose -f "$COMPOSE_FILE" start app
    fi
}

restore_vectors() {
    if [ "$RESTORE_TYPE" != "vectors-only" ] && [ "$RESTORE_TYPE" != "full" ]; then
        return 0
    fi
    
    if [ "$SKIP_QDRANT" = true ]; then
        warn "Skipping vector database restore (Qdrant not accessible)"
        return 0
    fi
    
    local backup_file=""
    if [ -f "$BACKUP_DIR/qdrant_backup.tar.gz" ]; then
        backup_file="$BACKUP_DIR/qdrant_backup.tar.gz"
    elif [ -f "$BACKUP_DIR/qdrant_backup.tar" ]; then
        backup_file="$BACKUP_DIR/qdrant_backup.tar"
    else
        warn "No vector database backup found, skipping vector restore"
        return 0
    fi
    
    log "Restoring Qdrant vector database from: $backup_file"
    
    # Stop Qdrant service
    log "Stopping Qdrant service..."
    docker-compose -f "$COMPOSE_FILE" stop qdrant
    
    # Clear existing Qdrant data
    log "Clearing existing Qdrant data..."
    docker-compose -f "$COMPOSE_FILE" run --rm --entrypoint="" qdrant rm -rf /qdrant/storage/* || warn "Failed to clear Qdrant data"
    
    # Restore Qdrant data
    if [[ "$backup_file" == *.gz ]]; then
        log "Decompressing and restoring vector database..."
        if gunzip -c "$backup_file" | docker-compose -f "$COMPOSE_FILE" run --rm --entrypoint="" -T qdrant tar xf - -C / > /dev/null 2>&1; then
            log "Vector database restore completed successfully"
        else
            error "Vector database restore failed"
            return 1
        fi
    else
        log "Restoring vector database..."
        if docker-compose -f "$COMPOSE_FILE" run --rm --entrypoint="" -T qdrant tar xf - -C / < "$backup_file" > /dev/null 2>&1; then
            log "Vector database restore completed successfully"
        else
            error "Vector database restore failed"
            return 1
        fi
    fi
    
    # Restart Qdrant service
    if [ "$NO_RESTART" != true ]; then
        log "Restarting Qdrant service..."
        docker-compose -f "$COMPOSE_FILE" start qdrant
        
        # Wait for Qdrant to be ready
        local timeout=60
        while [ $timeout -gt 0 ]; do
            if docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s http://localhost:6333/health > /dev/null 2>&1; then
                log "Qdrant is ready after restore"
                break
            fi
            sleep 2
            timeout=$((timeout - 2))
        done
    fi
}

restore_logs() {
    if [ "$RESTORE_TYPE" != "logs-only" ] && [ "$RESTORE_TYPE" != "full" ]; then
        return 0
    fi
    
    local backup_file=""
    if [ -f "$BACKUP_DIR/logs_backup.tar.gz" ]; then
        backup_file="$BACKUP_DIR/logs_backup.tar.gz"
    elif [ -f "$BACKUP_DIR/logs_backup.tar" ]; then
        backup_file="$BACKUP_DIR/logs_backup.tar"
    else
        warn "No logs backup found, skipping logs restore"
        return 0
    fi
    
    log "Restoring application logs from: $backup_file"
    
    # Backup existing logs
    if [ -d "logs" ] && [ "$FORCE" != true ]; then
        log "Backing up existing logs..."
        mv logs "logs_backup_$(date +%Y%m%d_%H%M%S)" || warn "Failed to backup existing logs"
    fi
    
    # Restore logs
    if [[ "$backup_file" == *.gz ]]; then
        log "Decompressing and restoring logs..."
        if gunzip -c "$backup_file" | tar xf - > /dev/null 2>&1; then
            log "Logs restore completed successfully"
        else
            error "Logs restore failed"
            return 1
        fi
    else
        log "Restoring logs..."
        if tar xf "$backup_file" > /dev/null 2>&1; then
            log "Logs restore completed successfully"
        else
            error "Logs restore failed"
            return 1
        fi
    fi
}

restore_configuration() {
    if [ "$RESTORE_TYPE" != "config-only" ] && [ "$RESTORE_TYPE" != "full" ]; then
        return 0
    fi
    
    local backup_file=""
    if [ -f "$BACKUP_DIR/config_backup.tar.gz" ]; then
        backup_file="$BACKUP_DIR/config_backup.tar.gz"
    elif [ -f "$BACKUP_DIR/config_backup.tar" ]; then
        backup_file="$BACKUP_DIR/config_backup.tar"
    else
        warn "No configuration backup found, skipping configuration restore"
        return 0
    fi
    
    log "Restoring configuration files from: $backup_file"
    
    if [ "$FORCE" != true ]; then
        warn "Configuration restore will overwrite existing files!"
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "Configuration restore cancelled"
            return 0
        fi
    fi
    
    # Restore configuration
    if [[ "$backup_file" == *.gz ]]; then
        log "Decompressing and restoring configuration..."
        if gunzip -c "$backup_file" | tar xf - > /dev/null 2>&1; then
            log "Configuration restore completed successfully"
        else
            error "Configuration restore failed"
            return 1
        fi
    else
        log "Restoring configuration..."
        if tar xf "$backup_file" > /dev/null 2>&1; then
            log "Configuration restore completed successfully"
        else
            error "Configuration restore failed"
            return 1
        fi
    fi
}

verify_restore() {
    log "Verifying restore..."
    
    # Check database
    if docker-compose -f "$COMPOSE_FILE" exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM django_migrations;" > /dev/null 2>&1; then
        log "Database verification: OK"
    else
        warn "Database verification: FAILED"
    fi
    
    # Check Qdrant
    if [ "$SKIP_QDRANT" != true ]; then
        if docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s http://localhost:6333/collections > /dev/null 2>&1; then
            log "Vector database verification: OK"
        else
            warn "Vector database verification: FAILED"
        fi
    fi
    
    # Check application health
    if [ "$NO_RESTART" != true ]; then
        local timeout=60
        while [ $timeout -gt 0 ]; do
            if docker-compose -f "$COMPOSE_FILE" exec -T app curl -s http://localhost:8000/health/ > /dev/null 2>&1; then
                log "Application health verification: OK"
                break
            fi
            sleep 5
            timeout=$((timeout - 5))
        done
        
        if [ $timeout -le 0 ]; then
            warn "Application health verification: TIMEOUT"
        fi
    fi
}

# Parse command line arguments
RESTORE_TYPE="full"
FORCE=false
NO_RESTART=false
VERBOSE=false
SKIP_QDRANT=false
BACKUP_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --database-only)
            RESTORE_TYPE="database-only"
            shift
            ;;
        --vectors-only)
            RESTORE_TYPE="vectors-only"
            shift
            ;;
        --logs-only)
            RESTORE_TYPE="logs-only"
            shift
            ;;
        --config-only)
            RESTORE_TYPE="config-only"
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --no-restart)
            NO_RESTART=true
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
        -*)
            error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [ -z "$BACKUP_DIR" ]; then
                BACKUP_DIR="$1"
            else
                error "Multiple backup directories specified"
                show_usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Main execution
main() {
    if [ -z "$BACKUP_DIR" ]; then
        error "No backup directory specified"
        echo ""
        list_available_backups
        echo ""
        show_usage
        exit 1
    fi
    
    log "Starting restore process (type: $RESTORE_TYPE)"
    log "Backup directory: $BACKUP_DIR"
    
    # Validate backup directory
    if ! validate_backup_directory "$BACKUP_DIR"; then
        exit 1
    fi
    
    # Confirmation prompt
    if [ "$FORCE" != true ]; then
        warn "This will restore data from backup and may overwrite existing data!"
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log "Restore cancelled"
            exit 0
        fi
    fi
    
    # Check services
    check_services
    
    # Perform restore based on type
    case $RESTORE_TYPE in
        full)
            restore_database
            restore_vectors
            restore_logs
            restore_configuration
            ;;
        database-only)
            restore_database
            ;;
        vectors-only)
            restore_vectors
            ;;
        logs-only)
            restore_logs
            ;;
        config-only)
            restore_configuration
            ;;
    esac
    
    # Verify restore
    verify_restore
    
    log "Restore process completed successfully!"
    
    if [ "$NO_RESTART" != true ]; then
        log "All services should be running. Check status with: docker-compose ps"
    else
        log "Services were not restarted. You may need to restart them manually."
    fi
}

# Run main function
main