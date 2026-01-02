# Production Deployment Guide

This document provides step-by-step instructions for deploying the Django FAQ/RAG application to production environments with comprehensive monitoring, backup, and maintenance procedures.

## Prerequisites

Before starting the deployment, ensure you have:

- Docker Engine 20.10+ installed
- Docker Compose 2.0+ installed
- At least 4GB RAM and 20GB disk space
- A domain name (for production SSL)
- SMTP server access (for alerts)
- Gemini API key

## Quick Production Deployment

### 1. Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd faq-rag-application

# Run the production setup script
./scripts/setup-production.sh

# Set up monitoring and logging
./scripts/setup-monitoring.sh --setup-all
```

### 2. Configure Environment

```bash
# Copy and edit the environment file
cp .env.example .env
nano .env
```

**Required environment variables:**
```bash
SECRET_KEY=your-django-secret-key-here
DB_PASSWORD=your-secure-database-password
GEMINI_API_KEY=your-gemini-api-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 3. Deploy Application

```bash
# Deploy the full stack
./deploy.sh deploy

# Check deployment status
./deploy.sh health

# View the monitoring dashboard
./scripts/dashboard.sh
```

### 4. Set Up Automated Monitoring

```bash
# Add cron jobs for monitoring
crontab -e

# Add these lines:
*/5 * * * * /path/to/faq-app/scripts/health-check.sh
*/10 * * * * /path/to/faq-app/scripts/monitor-resources.sh
0 * * * * /path/to/faq-app/scripts/analyze-logs.sh
0 3 * * * /path/to/faq-app/scripts/backup.sh --full
0 2 * * * /path/to/faq-app/scripts/rotate-logs.sh
```

## Detailed Deployment Steps

### Step 1: Environment Preparation

1. **Create production directories:**
   ```bash
   ./scripts/setup-production.sh
   ```

2. **Configure SSL certificates (if using HTTPS):**
   ```bash
   mkdir -p nginx/ssl
   # Copy your SSL certificates:
   # nginx/ssl/cert.pem - SSL certificate
   # nginx/ssl/key.pem - Private key
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your production values. Key variables:
   - `SECRET_KEY`: Generate a new Django secret key
   - `DB_PASSWORD`: Strong database password
   - `GEMINI_API_KEY`: Your Gemini AI API key
   - `ALLOWED_HOSTS`: Your domain names
   - `DJANGO_ENV=production`
   - `DEBUG=False`

### Step 2: Service Configuration

1. **Database configuration:**
   - PostgreSQL 15+ will be automatically configured
   - Data persisted in `./data/postgres`
   - Connection pooling enabled

2. **Vector database configuration:**
   - Qdrant vector database for embeddings
   - Data persisted in `./data/qdrant`
   - Automatic collection initialization

3. **Web server configuration:**
   - Nginx reverse proxy
   - Static file serving
   - SSL termination (if certificates provided)

### Step 3: Deployment Execution

1. **Deploy the application:**
   ```bash
   ./deploy.sh deploy
   ```

   This will:
   - Pull/build Docker images
   - Start all services in correct order
   - Run database migrations
   - Initialize vector database
   - Verify service health

2. **Verify deployment:**
   ```bash
   # Check service status
   ./deploy.sh health

   # View logs
   ./deploy.sh logs

   # Test Qdrant integration
   ./deploy.sh test-qdrant
   ```

### Step 4: Monitoring Setup

1. **Set up monitoring infrastructure:**
   ```bash
   ./scripts/setup-monitoring.sh --setup-all
   ```

2. **Configure alerting:**
   Edit `config/alerts.conf`:
   ```bash
   ALERT_EMAIL=admin@yourdomain.com
   CPU_THRESHOLD=80
   MEMORY_THRESHOLD=85
   DISK_THRESHOLD=90
   ```

3. **Set up automated monitoring:**
   ```bash
   # Copy cron job examples
   cp config/crontab.example /tmp/crontab.tmp
   # Edit paths in /tmp/crontab.tmp
   crontab /tmp/crontab.tmp
   ```

### Step 5: Backup Configuration

1. **Test backup system:**
   ```bash
   # Create test backup
   ./scripts/backup.sh --full

   # Verify backup
   ls -la backups/
   ```

2. **Configure automated backups:**
   ```bash
   # Daily backup at 3 AM
   echo "0 3 * * * /path/to/faq-app/scripts/backup.sh --full" | crontab -
   ```

## Post-Deployment Tasks

### 1. Application Configuration

```bash
# Create Django superuser
docker-compose exec app python manage.py createsuperuser

# Initialize FAQ data (if needed)
docker-compose exec app python manage.py sync_faqs_to_qdrant

# Test application functionality
curl http://localhost/health/
```

### 2. Security Hardening

1. **Firewall configuration:**
   ```bash
   # Allow only necessary ports
   ufw allow 22    # SSH
   ufw allow 80    # HTTP
   ufw allow 443   # HTTPS
   ufw enable
   ```

2. **SSL certificate setup:**
   - Use Let's Encrypt or commercial certificates
   - Update nginx configuration for HTTPS
   - Test SSL configuration

3. **Regular security updates:**
   ```bash
   # Update system packages
   apt update && apt upgrade -y

   # Update Docker images
   ./deploy.sh update
   ```

### 3. Performance Optimization

1. **Resource tuning:**
   Edit `.env` based on server capacity:
   ```bash
   # For 4GB RAM server
   APP_MEMORY_LIMIT=1G
   DB_MEMORY_LIMIT=512M
   QDRANT_MEMORY_LIMIT=1G
   GUNICORN_WORKERS=5
   ```

2. **Database optimization:**
   ```bash
   # Monitor database performance
   docker-compose exec db psql -U faq_user -d faq_production -c "
   SELECT query, calls, total_time, mean_time 
   FROM pg_stat_statements 
   ORDER BY total_time DESC LIMIT 10;"
   ```

## Maintenance Procedures

### Daily Tasks

```bash
# Check system health
./scripts/health-check.sh

# Monitor resource usage
./scripts/monitor-resources.sh

# Review error logs
grep -i error logs/app/*.log | tail -20
```

### Weekly Tasks

```bash
# Analyze access patterns
./scripts/analyze-logs.sh 7

# Clean up old logs
./scripts/rotate-logs.sh

# Update security patches
apt update && apt upgrade -y
```

### Monthly Tasks

```bash
# Full backup verification
./scripts/restore.sh --database-only --no-restart backups/latest

# Performance review
./scripts/dashboard.sh

# Capacity planning
df -h
docker stats --no-stream
```

## Troubleshooting

### Common Issues

1. **Service won't start:**
   ```bash
   # Check logs
   docker-compose logs service_name

   # Check environment variables
   docker-compose config

   # Restart service
   docker-compose restart service_name
   ```

2. **Database connection errors:**
   ```bash
   # Check database status
   docker-compose exec db pg_isready -U faq_user

   # Check database logs
   docker-compose logs db

   # Reset database connection
   docker-compose restart app
   ```

3. **Vector database issues:**
   ```bash
   # Check Qdrant health
   curl http://localhost:6333/health

   # Reinitialize Qdrant
   docker-compose exec app python manage.py init_qdrant

   # Resync FAQ data
   docker-compose exec app python manage.py sync_faqs_to_qdrant
   ```

4. **High resource usage:**
   ```bash
   # Check resource usage
   ./scripts/monitor-resources.sh

   # Scale down if needed
   docker-compose up -d --scale app=1

   # Clean up resources
   ./deploy.sh cleanup
   ```

### Emergency Procedures

1. **Complete service failure:**
   ```bash
   # Stop all services
   ./deploy.sh stop

   # Check system resources
   df -h
   free -h

   # Restart services
   ./deploy.sh restart

   # Check health
   ./deploy.sh health
   ```

2. **Data corruption:**
   ```bash
   # Stop services
   ./deploy.sh stop

   # Restore from backup
   ./scripts/restore.sh --force backups/backup_YYYYMMDD_HHMMSS

   # Verify restoration
   ./deploy.sh health
   ```

## Scaling Guidelines

### Vertical Scaling

For increased load, adjust resources in `.env`:

```bash
# High-performance configuration
APP_MEMORY_LIMIT=4G
APP_CPU_LIMIT=4.0
GUNICORN_WORKERS=17  # (4 cores * 4) + 1
DB_MEMORY_LIMIT=2G
QDRANT_MEMORY_LIMIT=2G
```

### Horizontal Scaling

For multiple servers:

1. **Load balancer setup:**
   - Use nginx or HAProxy as load balancer
   - Configure health checks
   - Implement session affinity if needed

2. **Database separation:**
   - Use external PostgreSQL service
   - Configure connection pooling
   - Set up read replicas if needed

3. **Shared storage:**
   - Use NFS or object storage for static files
   - Configure shared vector database
   - Implement distributed caching

## Security Best Practices

### 1. Environment Security

- Never commit `.env` files to version control
- Use strong, unique passwords
- Rotate secrets regularly
- Implement proper access controls

### 2. Network Security

- Use firewall to restrict access
- Implement SSL/TLS encryption
- Use VPN for administrative access
- Monitor network traffic

### 3. Application Security

- Keep dependencies updated
- Monitor security advisories
- Implement proper logging
- Use security headers

### 4. Data Security

- Encrypt sensitive data
- Implement regular backups
- Test backup restoration
- Monitor data access

## Performance Monitoring

### Key Metrics to Monitor

1. **Application Performance:**
   - Response time
   - Error rate
   - Request throughput
   - Queue length

2. **System Resources:**
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network I/O

3. **Database Performance:**
   - Query execution time
   - Connection count
   - Lock waits
   - Cache hit ratio

4. **Vector Database Performance:**
   - Search latency
   - Index size
   - Memory usage
   - Query throughput

### Monitoring Tools

```bash
# Real-time dashboard
./scripts/dashboard.sh

# Resource monitoring
./scripts/monitor-resources.sh

# Log analysis
./scripts/analyze-logs.sh

# Health checks
./scripts/health-check.sh
```

## Support and Documentation

### Additional Resources

- [Docker Deployment Guide](DOCKER_DEPLOYMENT.md) - Detailed Docker configuration
- [Qdrant Integration Guide](QDRANT_INTEGRATION.md) - Vector database setup
- [Application Documentation](README.md) - Application-specific information

### Getting Help

1. **Check logs first:**
   ```bash
   ./deploy.sh logs
   docker-compose logs -f
   ```

2. **Use monitoring tools:**
   ```bash
   ./scripts/dashboard.sh
   ./deploy.sh health
   ```

3. **Review configuration:**
   ```bash
   docker-compose config
   cat .env
   ```

4. **Test components individually:**
   ```bash
   # Test database
   docker-compose exec db pg_isready

   # Test vector database
   curl http://localhost:6333/health

   # Test application
   curl http://localhost/health/
   ```

For persistent issues, collect the following information:
- System specifications
- Docker and Docker Compose versions
- Complete error logs
- Environment configuration (without secrets)
- Recent changes or updates

This comprehensive deployment guide ensures a robust, monitored, and maintainable production environment for the Django FAQ/RAG application.