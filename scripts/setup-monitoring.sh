#!/bin/bash

# Monitoring and Logging Setup Script for Django FAQ/RAG Application
# Sets up comprehensive monitoring, logging, and alerting

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

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --setup-logrotate   Set up log rotation"
    echo "  --setup-monitoring  Set up basic monitoring scripts"
    echo "  --setup-alerts      Set up alerting configuration"
    echo "  --setup-all         Set up all monitoring components"
    echo "  --help              Show this help message"
    echo ""
}

setup_log_directories() {
    log "Setting up log directories..."
    
    # Create log directories
    mkdir -p logs/app
    mkdir -p logs/nginx
    mkdir -p logs/db
    mkdir -p logs/qdrant
    mkdir -p logs/redis
    mkdir -p logs/monitoring
    
    # Set proper permissions
    chmod 755 logs
    chmod 755 logs/*
    
    log "Log directories created successfully"
}

setup_logrotate() {
    log "Setting up log rotation configuration..."
    
    # Create logrotate configuration
    cat > logs/logrotate.conf << 'EOF'
# Log rotation configuration for Django FAQ/RAG Application

logs/app/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose exec app kill -USR1 $(cat /tmp/gunicorn.pid) 2>/dev/null || true
    endscript
}

logs/nginx/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose exec nginx nginx -s reload 2>/dev/null || true
    endscript
}

logs/db/*.log {
    weekly
    missingok
    rotate 12
    compress
    delaycompress
    notifempty
    create 644 root root
}

logs/qdrant/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 root root
}

logs/redis/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 root root
}

logs/monitoring/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 root root
}
EOF
    
    # Create logrotate script
    cat > scripts/rotate-logs.sh << 'EOF'
#!/bin/bash
# Log rotation script

cd "$(dirname "$0")/.."
/usr/sbin/logrotate -s logs/logrotate.state logs/logrotate.conf
EOF
    
    chmod +x scripts/rotate-logs.sh
    
    log "Log rotation configuration created"
    info "Add this to crontab to run daily: 0 2 * * * /path/to/scripts/rotate-logs.sh"
}

setup_monitoring_scripts() {
    log "Setting up monitoring scripts..."
    
    # Create health check script
    cat > scripts/health-check.sh << 'EOF'
#!/bin/bash
# Health check script for all services

set -e

# Configuration
COMPOSE_FILE="docker-compose.yml"
LOG_FILE="logs/monitoring/health-check.log"
ALERT_EMAIL="${ADMIN_EMAIL:-admin@localhost}"

# Load environment variables
if [ -f .env ]; then
    source .env
fi

# Logging function
log_health() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Check service health
check_service_health() {
    local service="$1"
    local health_command="$2"
    
    if docker-compose -f "$COMPOSE_FILE" exec -T "$service" $health_command > /dev/null 2>&1; then
        log_health "✓ $service: Healthy"
        return 0
    else
        log_health "✗ $service: Unhealthy"
        return 1
    fi
}

# Main health check
main() {
    log_health "Starting health check..."
    
    local failed_services=()
    
    # Check application health
    if ! check_service_health "app" "curl -f http://localhost:8000/health/"; then
        failed_services+=("app")
    fi
    
    # Check database health
    if ! check_service_health "db" "pg_isready -U ${DB_USER:-faq_user}"; then
        failed_services+=("db")
    fi
    
    # Check Qdrant health
    if ! check_service_health "qdrant" "curl -f http://localhost:6333/health"; then
        failed_services+=("qdrant")
    fi
    
    # Check Redis health
    if ! check_service_health "redis" "redis-cli ping"; then
        failed_services+=("redis")
    fi
    
    # Check Nginx health
    if ! check_service_health "nginx" "nginx -t"; then
        failed_services+=("nginx")
    fi
    
    # Report results
    if [ ${#failed_services[@]} -eq 0 ]; then
        log_health "All services healthy"
        exit 0
    else
        log_health "Failed services: ${failed_services[*]}"
        
        # Send alert if email is configured
        if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
            echo "Health check failed for services: ${failed_services[*]}" | \
                mail -s "FAQ/RAG Application Health Alert" "$ALERT_EMAIL"
        fi
        
        exit 1
    fi
}

main
EOF
    
    chmod +x scripts/health-check.sh
    
    # Create resource monitoring script
    cat > scripts/monitor-resources.sh << 'EOF'
#!/bin/bash
# Resource monitoring script

set -e

# Configuration
COMPOSE_FILE="docker-compose.yml"
LOG_FILE="logs/monitoring/resources.log"
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=85

# Load environment variables
if [ -f .env ]; then
    source .env
fi

# Logging function
log_resource() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Get container stats
get_container_stats() {
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | \
        grep -E "(app|db|qdrant|redis|nginx)" || true
}

# Check resource usage
check_resources() {
    log_resource "Resource usage check:"
    
    local stats=$(get_container_stats)
    log_resource "$stats"
    
    # Check for high resource usage
    local alerts=()
    
    while IFS=$'\t' read -r container cpu memory mem_perc; do
        if [[ "$container" =~ ^(app|db|qdrant|redis|nginx) ]]; then
            # Extract numeric values
            cpu_num=$(echo "$cpu" | sed 's/%//')
            mem_num=$(echo "$mem_perc" | sed 's/%//')
            
            # Check CPU threshold
            if (( $(echo "$cpu_num > $ALERT_THRESHOLD_CPU" | bc -l) )); then
                alerts+=("$container: High CPU usage ($cpu)")
            fi
            
            # Check memory threshold
            if (( $(echo "$mem_num > $ALERT_THRESHOLD_MEMORY" | bc -l) )); then
                alerts+=("$container: High memory usage ($mem_perc)")
            fi
        fi
    done <<< "$stats"
    
    # Report alerts
    if [ ${#alerts[@]} -gt 0 ]; then
        for alert in "${alerts[@]}"; do
            log_resource "ALERT: $alert"
        done
        
        # Send email alert if configured
        if command -v mail &> /dev/null && [ -n "${ADMIN_EMAIL}" ]; then
            printf "%s\n" "${alerts[@]}" | \
                mail -s "FAQ/RAG Application Resource Alert" "${ADMIN_EMAIL}"
        fi
    fi
}

# Main execution
main() {
    check_resources
}

main
EOF
    
    chmod +x scripts/monitor-resources.sh
    
    # Create log analysis script
    cat > scripts/analyze-logs.sh << 'EOF'
#!/bin/bash
# Log analysis script

set -e

# Configuration
LOG_FILE="logs/monitoring/log-analysis.log"
ANALYSIS_PERIOD="${1:-1}"  # Days to analyze (default: 1)

# Logging function
log_analysis() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Analyze application logs
analyze_app_logs() {
    log_analysis "Analyzing application logs for last $ANALYSIS_PERIOD day(s)..."
    
    # Find log files modified in the last N days
    local log_files=$(find logs/app -name "*.log" -mtime -"$ANALYSIS_PERIOD" 2>/dev/null || true)
    
    if [ -z "$log_files" ]; then
        log_analysis "No recent application log files found"
        return
    fi
    
    # Count error levels
    local errors=$(grep -i "error" $log_files 2>/dev/null | wc -l || echo "0")
    local warnings=$(grep -i "warning" $log_files 2>/dev/null | wc -l || echo "0")
    local criticals=$(grep -i "critical" $log_files 2>/dev/null | wc -l || echo "0")
    
    log_analysis "Application log summary:"
    log_analysis "  Errors: $errors"
    log_analysis "  Warnings: $warnings"
    log_analysis "  Critical: $criticals"
    
    # Top error messages
    if [ "$errors" -gt 0 ]; then
        log_analysis "Top error messages:"
        grep -i "error" $log_files 2>/dev/null | \
            cut -d']' -f2- | \
            sort | uniq -c | sort -nr | head -5 | \
            while read count message; do
                log_analysis "  $count: $message"
            done
    fi
}

# Analyze access patterns
analyze_access_patterns() {
    log_analysis "Analyzing access patterns..."
    
    local nginx_logs=$(find logs/nginx -name "access.log*" -mtime -"$ANALYSIS_PERIOD" 2>/dev/null || true)
    
    if [ -z "$nginx_logs" ]; then
        log_analysis "No recent nginx access logs found"
        return
    fi
    
    # Request count
    local total_requests=$(cat $nginx_logs 2>/dev/null | wc -l || echo "0")
    log_analysis "Total requests: $total_requests"
    
    # Top IPs
    if [ "$total_requests" -gt 0 ]; then
        log_analysis "Top client IPs:"
        awk '{print $1}' $nginx_logs 2>/dev/null | \
            sort | uniq -c | sort -nr | head -5 | \
            while read count ip; do
                log_analysis "  $ip: $count requests"
            done
        
        # Response codes
        log_analysis "Response code distribution:"
        awk '{print $9}' $nginx_logs 2>/dev/null | \
            sort | uniq -c | sort -nr | \
            while read count code; do
                log_analysis "  $code: $count"
            done
    fi
}

# Main execution
main() {
    log_analysis "Starting log analysis for last $ANALYSIS_PERIOD day(s)..."
    
    analyze_app_logs
    analyze_access_patterns
    
    log_analysis "Log analysis completed"
}

main
EOF
    
    chmod +x scripts/analyze-logs.sh
    
    log "Monitoring scripts created successfully"
}

setup_alerting() {
    log "Setting up alerting configuration..."
    
    # Create alerting configuration
    cat > config/alerts.conf << 'EOF'
# Alerting configuration for Django FAQ/RAG Application

# Email settings
ALERT_EMAIL=admin@localhost
SMTP_SERVER=localhost
SMTP_PORT=25

# Thresholds
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=90
RESPONSE_TIME_THRESHOLD=5000

# Check intervals (in minutes)
HEALTH_CHECK_INTERVAL=5
RESOURCE_CHECK_INTERVAL=10
LOG_ANALYSIS_INTERVAL=60

# Alert cooldown (in minutes)
ALERT_COOLDOWN=30
EOF
    
    # Create alert manager script
    cat > scripts/alert-manager.sh << 'EOF'
#!/bin/bash
# Alert manager script

set -e

# Configuration
CONFIG_FILE="config/alerts.conf"
STATE_FILE="logs/monitoring/alert-state.json"

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Load environment variables
if [ -f .env ]; then
    source .env
fi

# Initialize state file
if [ ! -f "$STATE_FILE" ]; then
    echo '{}' > "$STATE_FILE"
fi

# Send alert function
send_alert() {
    local subject="$1"
    local message="$2"
    local alert_key="$3"
    
    # Check cooldown
    local last_alert=$(jq -r ".\"$alert_key\" // 0" "$STATE_FILE" 2>/dev/null || echo "0")
    local current_time=$(date +%s)
    local cooldown_seconds=$((ALERT_COOLDOWN * 60))
    
    if [ $((current_time - last_alert)) -lt $cooldown_seconds ]; then
        echo "Alert $alert_key is in cooldown period"
        return 0
    fi
    
    # Send alert
    if command -v mail &> /dev/null && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
        echo "Alert sent: $subject"
        
        # Update state
        jq ".\"$alert_key\" = $current_time" "$STATE_FILE" > "${STATE_FILE}.tmp" && \
            mv "${STATE_FILE}.tmp" "$STATE_FILE"
    else
        echo "Email not configured, alert not sent: $subject"
    fi
}

# Check disk usage
check_disk_usage() {
    local usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$usage" -gt "${DISK_THRESHOLD:-90}" ]; then
        send_alert "Disk Usage Alert" \
            "Disk usage is at ${usage}% (threshold: ${DISK_THRESHOLD}%)" \
            "disk_usage"
    fi
}

# Check application response time
check_response_time() {
    local start_time=$(date +%s%3N)
    
    if curl -s -f http://localhost/health/ > /dev/null 2>&1; then
        local end_time=$(date +%s%3N)
        local response_time=$((end_time - start_time))
        
        if [ "$response_time" -gt "${RESPONSE_TIME_THRESHOLD:-5000}" ]; then
            send_alert "Response Time Alert" \
                "Application response time is ${response_time}ms (threshold: ${RESPONSE_TIME_THRESHOLD}ms)" \
                "response_time"
        fi
    else
        send_alert "Application Down Alert" \
            "Application health check failed" \
            "app_down"
    fi
}

# Main execution
main() {
    check_disk_usage
    check_response_time
}

main
EOF
    
    chmod +x scripts/alert-manager.sh
    
    log "Alerting configuration created successfully"
}

setup_cron_jobs() {
    log "Setting up cron job examples..."
    
    cat > config/crontab.example << 'EOF'
# Cron jobs for Django FAQ/RAG Application monitoring
# Add these to your system crontab with: crontab -e

# Health checks every 5 minutes
*/5 * * * * /path/to/faq-app/scripts/health-check.sh

# Resource monitoring every 10 minutes
*/10 * * * * /path/to/faq-app/scripts/monitor-resources.sh

# Log analysis every hour
0 * * * * /path/to/faq-app/scripts/analyze-logs.sh

# Alert manager every 5 minutes
*/5 * * * * /path/to/faq-app/scripts/alert-manager.sh

# Log rotation daily at 2 AM
0 2 * * * /path/to/faq-app/scripts/rotate-logs.sh

# Backup daily at 3 AM
0 3 * * * /path/to/faq-app/scripts/backup.sh --full

# Cleanup old backups weekly
0 4 * * 0 find /path/to/faq-app/backups -type d -name "backup_*" -mtime +30 -exec rm -rf {} \;
EOF
    
    log "Cron job examples created in config/crontab.example"
    info "Edit the paths and add to your system crontab"
}

create_monitoring_dashboard() {
    log "Creating monitoring dashboard script..."
    
    cat > scripts/dashboard.sh << 'EOF'
#!/bin/bash
# Simple monitoring dashboard

set -e

# Configuration
COMPOSE_FILE="docker-compose.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Clear screen and show header
clear
echo -e "${BLUE}Django FAQ/RAG Application Dashboard${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# Service status
echo -e "${GREEN}Service Status:${NC}"
docker-compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Resource usage
echo -e "${GREEN}Resource Usage:${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | \
    grep -E "(CONTAINER|app|db|qdrant|redis|nginx)" || echo "No containers running"
echo ""

# Disk usage
echo -e "${GREEN}Disk Usage:${NC}"
df -h / | grep -E "(Filesystem|/dev/)"
echo ""

# Recent logs
echo -e "${GREEN}Recent Application Logs (last 10 lines):${NC}"
if [ -f "logs/app/app.log" ]; then
    tail -n 10 logs/app/app.log
else
    echo "No application logs found"
fi
echo ""

# Health status
echo -e "${GREEN}Health Checks:${NC}"

# Check application
if curl -s -f http://localhost/health/ > /dev/null 2>&1; then
    echo -e "  Application: ${GREEN}✓ Healthy${NC}"
else
    echo -e "  Application: ${RED}✗ Unhealthy${NC}"
fi

# Check database
if docker-compose -f "$COMPOSE_FILE" exec -T db pg_isready > /dev/null 2>&1; then
    echo -e "  Database: ${GREEN}✓ Healthy${NC}"
else
    echo -e "  Database: ${RED}✗ Unhealthy${NC}"
fi

# Check Qdrant
if docker-compose -f "$COMPOSE_FILE" exec -T qdrant curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "  Qdrant: ${GREEN}✓ Healthy${NC}"
else
    echo -e "  Qdrant: ${RED}✗ Unhealthy${NC}"
fi

# Check Redis
if docker-compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "  Redis: ${GREEN}✓ Healthy${NC}"
else
    echo -e "  Redis: ${RED}✗ Unhealthy${NC}"
fi

echo ""
echo -e "${BLUE}Dashboard updated at: $(date)${NC}"
EOF
    
    chmod +x scripts/dashboard.sh
    
    log "Monitoring dashboard created"
    info "Run './scripts/dashboard.sh' to view the dashboard"
}

# Parse command line arguments
SETUP_LOGROTATE=false
SETUP_MONITORING=false
SETUP_ALERTS=false
SETUP_ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --setup-logrotate)
            SETUP_LOGROTATE=true
            shift
            ;;
        --setup-monitoring)
            SETUP_MONITORING=true
            shift
            ;;
        --setup-alerts)
            SETUP_ALERTS=true
            shift
            ;;
        --setup-all)
            SETUP_ALL=true
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
    log "Setting up monitoring and logging..."
    
    # Create necessary directories
    mkdir -p config
    setup_log_directories
    
    if [ "$SETUP_ALL" = true ] || [ "$SETUP_LOGROTATE" = true ]; then
        setup_logrotate
    fi
    
    if [ "$SETUP_ALL" = true ] || [ "$SETUP_MONITORING" = true ]; then
        setup_monitoring_scripts
        create_monitoring_dashboard
    fi
    
    if [ "$SETUP_ALL" = true ] || [ "$SETUP_ALERTS" = true ]; then
        setup_alerting
    fi
    
    if [ "$SETUP_ALL" = true ]; then
        setup_cron_jobs
    fi
    
    log "Monitoring and logging setup completed!"
    echo ""
    echo "Next steps:"
    echo "1. Review and customize config/alerts.conf"
    echo "2. Set up email configuration for alerts"
    echo "3. Add cron jobs from config/crontab.example"
    echo "4. Run './scripts/dashboard.sh' to view the monitoring dashboard"
    echo "5. Test health checks with './scripts/health-check.sh'"
}

# Run main function if no arguments provided
if [ "$SETUP_LOGROTATE" = false ] && [ "$SETUP_MONITORING" = false ] && [ "$SETUP_ALERTS" = false ] && [ "$SETUP_ALL" = false ]; then
    SETUP_ALL=true
fi

main