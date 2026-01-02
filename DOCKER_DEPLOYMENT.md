# Docker Deployment Guide

This guide explains how to deploy the Django FAQ/RAG application using Docker Compose for both development and production environments with comprehensive monitoring, backup, and maintenance procedures.

## Quick Start

### Development Deployment

```bash
# Clone the repository and navigate to the project directory
git clone <repository-url>
cd faq-rag-application

# Start all services for development
docker-compose up -d

# View logs
docker-compose logs -f
```

### Production Deployment

```bash
# Run the production setup script
./scripts/setup-production.sh

# Edit the .env file with your production values
nano .env

# Start all services for production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Set up monitoring and logging
./scripts/setup-monitoring.sh --setup-all

# View logs
docker-compose logs -f
```

## Architecture Overview

The Docker Compose setup includes the following services:

- **nginx**: Reverse proxy and static file server
- **app**: Django application server (Gunicorn)
- **db**: PostgreSQL database
- **qdrant**: Vector database for embeddings
- **redis**: Cache and session storage

## Configuration Files

### Docker Compose Files

- `docker-compose.yml`: Base configuration for all environments
- `docker-compose.override.yml`: Development overrides (automatically loaded)
- `docker-compose.prod.yml`: Production-specific configuration

### Environment Configuration

- `.env.example`: Template with all available environment variables
- `.env`: Your actual environment configuration (create from template)

### Service Configuration

- `redis/redis.conf`: Redis server configuration
- `postgres/init/`: PostgreSQL initialization scripts
- `qdrant/config/config.yaml`: Qdrant vector database configuration
- `nginx/`: Nginx configuration files

## Environment Variables

### Required Variables

These variables must be set in your `.env` file:

```bash
SECRET_KEY=your-django-secret-key
DB_PASSWORD=your-database-password
GEMINI_API_KEY=your-gemini-api-key
```

### Important Production Variables

```bash
DJANGO_ENV=production
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
```

### Resource Limits

Configure resource limits for production:

```bash
# Database resources
DB_MEMORY_LIMIT=512M
DB_CPU_LIMIT=0.5

# Application resources
APP_MEMORY_LIMIT=1G
APP_CPU_LIMIT=1.0

# Vector database resources
QDRANT_MEMORY_LIMIT=1G
QDRANT_CPU_LIMIT=1.0
```

### Monitoring and Alerting

```bash
# Alert thresholds
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=90
RESPONSE_TIME_THRESHOLD=5000

# Monitoring intervals
HEALTH_CHECK_INTERVAL=300
RESOURCE_CHECK_INTERVAL=600
LOG_ANALYSIS_INTERVAL=3600

# Backup settings
BACKUP_RETENTION_DAYS=30
BACKUP_COMPRESSION=true
```

## Service Dependencies and Startup Order

The services start in the following order:

1. **db** (PostgreSQL) - Database backend
2. **qdrant** - Vector database for embeddings
3. **redis** - Cache and session storage
4. **app** - Django application (waits for db, qdrant, redis)
5. **nginx** - Web server (waits for app)

Each service includes health checks to ensure proper startup order.

## Data Persistence

### Development

Data is stored in Docker volumes:
- `postgres_data`: Database files
- `qdrant_data`: Vector database files
- `redis_data`: Cache data
- `static_files`: Static assets
- `media_files`: User uploads
- `app_logs`: Application logs

### Production

Data is stored in bind-mounted directories:
- `./data/postgres`: Database files
- `./data/qdrant`: Vector database files
- `./data/redis`: Cache data
- `./logs`: Application and web server logs

## Networking

### Development
- All services can communicate internally
- External ports exposed for debugging

### Production
- **Frontend network**: nginx ↔ app communication
- **Backend network**: Internal services (db, qdrant, redis)
- Backend network is isolated from external access

## Deployment Scripts

### Automated Deployment

Use the main deployment script for automated deployment:

```bash
# Full deployment
./deploy.sh deploy

# Update application only
./deploy.sh update

# Check system health
./deploy.sh health

# Test Qdrant connectivity
./deploy.sh test-qdrant

# View logs
./deploy.sh logs

# Stop services
./deploy.sh stop

# Restart services
./deploy.sh restart

# Clean up Docker resources
./deploy.sh cleanup
```

### Backup and Restore

```bash
# Create full backup
./scripts/backup.sh --full

# Create database-only backup
./scripts/backup.sh --database-only

# Create vector database backup
./scripts/backup.sh --vectors-only

# Restore from backup
./scripts/restore.sh backups/backup_20240101_120000

# Restore database only
./scripts/restore.sh --database-only backups/backup_20240101_120000
```

## Monitoring and Logging

### Setup Monitoring

```bash
# Set up all monitoring components
./scripts/setup-monitoring.sh --setup-all

# Set up log rotation only
./scripts/setup-monitoring.sh --setup-logrotate

# Set up monitoring scripts only
./scripts/setup-monitoring.sh --setup-monitoring

# Set up alerting only
./scripts/setup-monitoring.sh --setup-alerts
```

### Monitoring Dashboard

```bash
# View real-time dashboard
./scripts/dashboard.sh
```

### Health Checks

```bash
# Manual health check
./scripts/health-check.sh

# Resource monitoring
./scripts/monitor-resources.sh

# Log analysis
./scripts/analyze-logs.sh
```

### Automated Monitoring

Add these cron jobs for automated monitoring:

```bash
# Health checks every 5 minutes
*/5 * * * * /path/to/faq-app/scripts/health-check.sh

# Resource monitoring every 10 minutes
*/10 * * * * /path/to/faq-app/scripts/monitor-resources.sh

# Log analysis every hour
0 * * * * /path/to/faq-app/scripts/analyze-logs.sh

# Daily backup at 3 AM
0 3 * * * /path/to/faq-app/scripts/backup.sh --full

# Log rotation daily at 2 AM
0 2 * * * /path/to/faq-app/scripts/rotate-logs.sh
```

## Common Commands

### Service Management

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart a specific service
docker-compose restart app

# View service logs
docker-compose logs -f app

# Execute commands in containers
docker-compose exec app python manage.py migrate
docker-compose exec db psql -U faq_user -d faq_production
```

### Database Operations

```bash
# Run Django migrations
docker-compose exec app python manage.py migrate

# Create superuser
docker-compose exec app python manage.py createsuperuser

# Access PostgreSQL shell
docker-compose exec db psql -U faq_user -d faq_production

# Backup database
docker-compose exec db pg_dump -U faq_user faq_production > backup.sql
```

### Vector Database Operations

```bash
# Check Qdrant health
curl http://localhost:6333/health

# Initialize Qdrant collections
docker-compose exec app python manage.py init_qdrant

# Sync FAQs to Qdrant
docker-compose exec app python manage.py sync_faqs_to_qdrant

# Test Qdrant integration
docker-compose exec app python manage.py test_qdrant
```

## Monitoring and Troubleshooting

### Health Checks

All services include health checks:

```bash
# Check service health
docker-compose ps

# View health check logs
docker-compose logs nginx | grep health
```

### Application Health Endpoints

- `http://localhost/health/`: Overall application health
- `http://localhost:6333/health`: Qdrant vector database health

### Log Locations

- Application logs: `./logs/app/` (production) or Docker logs (development)
- Nginx logs: `./logs/nginx/` (production)
- Database logs: Available via `docker-compose logs db`
- Monitoring logs: `./logs/monitoring/`

### Common Issues

1. **Service won't start**: Check environment variables and health checks
2. **Database connection errors**: Verify DB_PASSWORD and database service health
3. **Vector database issues**: Check Qdrant service logs and initialization
4. **Static files not loading**: Verify nginx configuration and volume mounts
5. **High resource usage**: Check monitoring logs and adjust resource limits
6. **Backup failures**: Verify disk space and service connectivity

### Troubleshooting Commands

```bash
# Check all service health
./deploy.sh health

# View detailed service status
docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Check resource usage
docker stats --no-stream

# View recent errors
grep -i error logs/app/*.log | tail -20

# Check disk space
df -h

# Test database connectivity
docker-compose exec app python manage.py dbshell

# Test Qdrant connectivity
curl -v http://localhost:6333/health
```

## Backup and Restore

### Automated Backup Strategy

The backup system provides comprehensive data protection:

1. **Full Backup**: Database + Vector DB + Logs + Configuration
2. **Incremental Backup**: Database only (for frequent backups)
3. **Retention Policy**: Configurable retention period (default: 30 days)
4. **Compression**: Optional compression to save space
5. **Verification**: Backup integrity verification

### Backup Types

```bash
# Full backup (recommended for production)
./scripts/backup.sh --full

# Database only (for frequent backups)
./scripts/backup.sh --database-only

# Vector database only
./scripts/backup.sh --vectors-only

# Logs only
./scripts/backup.sh --logs-only

# Custom retention period
./scripts/backup.sh --retention 60  # 60 days

# Uncompressed backup
./scripts/backup.sh --no-compress
```

### Restore Procedures

```bash
# List available backups
ls -la backups/

# Full restore
./scripts/restore.sh backups/backup_20240101_120000

# Database only restore
./scripts/restore.sh --database-only backups/backup_20240101_120000

# Force restore without confirmation
./scripts/restore.sh --force backups/backup_20240101_120000

# Restore without restarting services
./scripts/restore.sh --no-restart backups/backup_20240101_120000
```

### Disaster Recovery

In case of complete system failure:

1. **Prepare new environment**:
   ```bash
   git clone <repository-url>
   cd faq-rag-application
   cp .env.example .env
   # Edit .env with production values
   ```

2. **Restore from backup**:
   ```bash
   # Copy backup files to new system
   scp -r backups/ user@new-server:/path/to/app/

   # Start services
   docker-compose up -d

   # Restore data
   ./scripts/restore.sh --force backups/backup_YYYYMMDD_HHMMSS
   ```

3. **Verify restoration**:
   ```bash
   ./deploy.sh health
   ./scripts/dashboard.sh
   ```

## Security Considerations

### Production Security

1. **Environment Variables**: Never commit `.env` files to version control
2. **Network Isolation**: Backend services are not exposed externally
3. **Resource Limits**: Prevent resource exhaustion attacks
4. **SSL/HTTPS**: Configure SSL certificates in `nginx/ssl/`
5. **Database Access**: Database port not exposed externally in production
6. **Regular Updates**: Keep Docker images and dependencies updated
7. **Monitoring**: Set up alerting for security events

### SSL Configuration

Place your SSL certificates in `nginx/ssl/`:
- `nginx/ssl/cert.pem`: SSL certificate
- `nginx/ssl/key.pem`: Private key

Update nginx configuration to enable HTTPS.

### Security Monitoring

```bash
# Check for failed login attempts
grep -i "failed" logs/nginx/access.log

# Monitor unusual access patterns
./scripts/analyze-logs.sh

# Check resource usage for anomalies
./scripts/monitor-resources.sh
```

## Performance Tuning

### Resource Allocation

Adjust resource limits based on your server capacity:

```bash
# High-performance server
APP_MEMORY_LIMIT=2G
APP_CPU_LIMIT=2.0
QDRANT_MEMORY_LIMIT=2G
DB_MEMORY_LIMIT=1G

# Low-resource server
APP_MEMORY_LIMIT=512M
APP_CPU_LIMIT=0.5
QDRANT_MEMORY_LIMIT=512M
DB_MEMORY_LIMIT=256M
```

### Gunicorn Workers

Configure Gunicorn workers based on CPU cores:

```bash
# Formula: (2 x CPU cores) + 1
GUNICORN_WORKERS=5  # For 2 CPU cores
```

### Database Optimization

```bash
# Connection pooling
DB_MAX_CONNECTIONS=20
DB_CONN_MAX_AGE=600

# PostgreSQL tuning (add to postgres/init/02-tuning.sql)
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
```

### Vector Database Optimization

```bash
# Qdrant performance settings
QDRANT_MAX_REQUEST_SIZE=32
QDRANT_MAX_SEARCH_THREADS=0  # Auto-detect
```

## Scaling

### Horizontal Scaling

To scale the application:

1. Use a load balancer in front of multiple nginx instances
2. Scale the app service: `docker-compose up -d --scale app=3`
3. Use external PostgreSQL and Redis services
4. Configure shared storage for static files

### Vertical Scaling

Increase resource limits in `.env`:

```bash
APP_MEMORY_LIMIT=4G
APP_CPU_LIMIT=4.0
GUNICORN_WORKERS=9
```

### Load Testing

```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Basic load test
ab -n 1000 -c 10 http://localhost/

# Test with authentication
ab -n 100 -c 5 -H "Authorization: Bearer token" http://localhost/api/
```

## Maintenance Procedures

### Regular Maintenance Tasks

1. **Daily**:
   - Check service health
   - Monitor resource usage
   - Review error logs
   - Verify backups

2. **Weekly**:
   - Analyze access patterns
   - Clean up old logs
   - Update security patches
   - Performance review

3. **Monthly**:
   - Full system backup verification
   - Security audit
   - Capacity planning review
   - Update dependencies

### Maintenance Commands

```bash
# Daily health check
./scripts/health-check.sh

# Weekly log analysis
./scripts/analyze-logs.sh 7

# Monthly backup verification
./scripts/restore.sh --database-only --no-restart backups/latest

# Clean up old Docker resources
./deploy.sh cleanup

# Update application
./deploy.sh update
```

## Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| Configuration | `docker-compose.yml` + `docker-compose.override.yml` | `docker-compose.yml` + `docker-compose.prod.yml` |
| Debug Mode | Enabled | Disabled |
| Port Exposure | All ports exposed | Only HTTP/HTTPS exposed |
| Resource Limits | None | Enforced |
| Data Persistence | Docker volumes | Bind mounts |
| SSL | Optional | Required |
| Networking | Open | Isolated backend |
| Monitoring | Basic | Comprehensive |
| Backups | Manual | Automated |
| Logging | Console | Files + Rotation |

## Support and Troubleshooting

### Getting Help

1. Check the logs: `docker-compose logs -f`
2. Verify health checks: `./deploy.sh health`
3. Review environment configuration
4. Check the troubleshooting section above
5. Run the monitoring dashboard: `./scripts/dashboard.sh`

### Emergency Procedures

#### Service Down

```bash
# Check what's down
./deploy.sh health

# Restart all services
./deploy.sh restart

# Check logs for errors
docker-compose logs --tail=100 app db qdrant
```

#### Database Issues

```bash
# Check database connectivity
docker-compose exec db pg_isready -U faq_user

# Check database logs
docker-compose logs db

# Restore from backup if needed
./scripts/restore.sh --database-only backups/latest
```

#### High Resource Usage

```bash
# Check resource usage
./scripts/monitor-resources.sh

# Scale down if needed
docker-compose up -d --scale app=1

# Clean up resources
./deploy.sh cleanup
```

#### Data Loss

```bash
# Stop services immediately
docker-compose down

# Restore from latest backup
./scripts/restore.sh --force backups/backup_YYYYMMDD_HHMMSS

# Verify restoration
./deploy.sh health
```

For additional support, check the application logs and monitoring data to identify the root cause of issues.