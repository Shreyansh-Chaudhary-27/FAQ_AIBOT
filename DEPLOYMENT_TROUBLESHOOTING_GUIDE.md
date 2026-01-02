# Deployment Troubleshooting Guide

This comprehensive guide helps diagnose and resolve common issues during production deployment of the Django FAQ/RAG application.

## Quick Diagnosis Commands

### System Status Check
```bash
# Check all services status
docker-compose ps

# Check service health
./deploy.sh health

# Check application logs
docker-compose logs app --tail=50

# Check system resources
docker stats --no-stream
```

### Service-Specific Checks
```bash
# Database connectivity
docker-compose exec app python manage.py dbshell

# Vector database health
curl http://localhost:6333/health

# Nginx status
docker-compose logs nginx --tail=20

# Redis connectivity
docker-compose exec redis redis-cli ping
```

## Common Issues and Solutions

### 1. Container Startup Issues

#### Problem: Services fail to start
```
ERROR: Service 'app' failed to build
```

**Diagnosis:**
```bash
# Check Docker daemon
docker info

# Check available disk space
df -h

# Check memory usage
free -h

# Review build logs
docker-compose build app --no-cache
```

**Solutions:**
- **Insufficient disk space**: Clean up Docker images and containers
  ```bash
  docker system prune -a
  docker volume prune
  ```
- **Memory issues**: Increase Docker memory limits or reduce resource requirements
- **Build failures**: Check Dockerfile syntax and dependency availability

#### Problem: Port conflicts
```
ERROR: Port 80 is already in use
```

**Diagnosis:**
```bash
# Check what's using the port
sudo netstat -tulpn | grep :80
sudo lsof -i :80
```

**Solutions:**
- Stop conflicting services: `sudo systemctl stop apache2` or `sudo systemctl stop nginx`
- Change port mapping in docker-compose.yml
- Use different ports for development: `docker-compose -f docker-compose.yml -f docker-compose.override.yml up`

### 2. Database Issues

#### Problem: Database connection failures
```
django.db.utils.OperationalError: could not connect to server
```

**Diagnosis:**
```bash
# Check database container status
docker-compose ps db

# Check database logs
docker-compose logs db --tail=50

# Test database connectivity
docker-compose exec db pg_isready -U faq_user

# Check environment variables
docker-compose exec app env | grep DB_
```

**Solutions:**
- **Database not ready**: Wait for database initialization or check startup order
  ```bash
  # Restart with proper dependency order
  docker-compose down
  docker-compose up -d db
  sleep 30
  docker-compose up -d
  ```
- **Wrong credentials**: Verify DB_USER, DB_PASSWORD, DB_NAME in .env file
- **Network issues**: Check Docker network configuration
  ```bash
  docker network ls
  docker network inspect $(docker-compose ps -q db)
  ```

#### Problem: Migration failures
```
django.db.utils.ProgrammingError: relation does not exist
```

**Diagnosis:**
```bash
# Check migration status
docker-compose exec app python manage.py showmigrations

# Check database tables
docker-compose exec app python manage.py dbshell
\dt
```

**Solutions:**
- **Missing migrations**: Run migrations manually
  ```bash
  docker-compose exec app python manage.py migrate
  ```
- **Corrupted migrations**: Reset migrations (development only)
  ```bash
  docker-compose exec app python manage.py migrate --fake-initial
  ```
- **Permission issues**: Check database user permissions

### 3. Vector Database (Qdrant) Issues

#### Problem: Qdrant connection failures
```
ConnectionError: Failed to connect to Qdrant
```

**Diagnosis:**
```bash
# Check Qdrant container status
docker-compose ps qdrant

# Check Qdrant health
curl http://localhost:6333/health

# Check Qdrant logs
docker-compose logs qdrant --tail=50

# Test from application container
docker-compose exec app curl http://qdrant:6333/health
```

**Solutions:**
- **Service not ready**: Wait for Qdrant initialization
  ```bash
  # Check if Qdrant is accepting connections
  docker-compose exec app python -c "
  import requests
  try:
      r = requests.get('http://qdrant:6333/health', timeout=5)
      print(f'Status: {r.status_code}')
  except Exception as e:
      print(f'Error: {e}')
  "
  ```
- **Configuration issues**: Check QDRANT_HOST and QDRANT_PORT in .env
- **Memory issues**: Increase Qdrant memory limits in docker-compose.yml

#### Problem: Empty vector database
```
No embeddings found in vector database
```

**Diagnosis:**
```bash
# Check collection status
curl http://localhost:6333/collections/faq_embeddings

# Check FAQ data sync
docker-compose exec app python manage.py sync_faqs_to_qdrant --dry-run
```

**Solutions:**
- **Missing data**: Sync FAQ data to Qdrant
  ```bash
  docker-compose exec app python manage.py sync_faqs_to_qdrant
  ```
- **Collection not created**: Initialize Qdrant collections
  ```bash
  docker-compose exec app python manage.py init_qdrant
  ```

### 4. RAG System Issues

#### Problem: "I don't know" responses
```
RAG system returning "I don't know" for all queries
```

**Diagnosis:**
```bash
# Test embedding system
docker-compose exec app python -c "
from faq.rag.core.rag_system import RAGSystem
rag = RAGSystem()
result = rag.query('test query')
print(f'Result: {result}')
"

# Check embedding model loading
docker-compose logs app | grep -i embedding

# Test vector search
curl -X POST http://localhost:6333/collections/faq_embeddings/points/search \
  -H "Content-Type: application/json" \
  -d '{"vector": [0.1, 0.2, 0.3], "limit": 5}'
```

**Solutions:**
- **Embedding model not loaded**: Check model download and loading
  ```bash
  docker-compose exec app python -c "
  from sentence_transformers import SentenceTransformer
  model = SentenceTransformer('all-MiniLM-L6-v2')
  print('Model loaded successfully')
  "
  ```
- **No FAQ data**: Ensure FAQ data is loaded and embedded
  ```bash
  docker-compose exec app python manage.py sync_faqs_to_qdrant --verbose
  ```
- **Fallback not working**: Check N-gram fallback system
  ```bash
  docker-compose exec app python manage.py shell -c "
  from faq.rag.utils.ngram_utils import NGramMatcher
  matcher = NGramMatcher()
  result = matcher.find_matches('test query')
  print(f'Fallback result: {result}')
  "
  ```

### 5. Static Files Issues

#### Problem: Static files not loading (404 errors)
```
GET /static/css/style.css 404 Not Found
```

**Diagnosis:**
```bash
# Check static files collection
docker-compose exec app python manage.py collectstatic --dry-run

# Check WhiteNoise configuration
docker-compose exec app python manage.py shell -c "
from django.conf import settings
print('STATIC_URL:', settings.STATIC_URL)
print('STATIC_ROOT:', settings.STATIC_ROOT)
print('STATICFILES_STORAGE:', settings.STATICFILES_STORAGE)
"

# Check Nginx configuration
docker-compose exec nginx nginx -t
```

**Solutions:**
- **Static files not collected**: Collect static files
  ```bash
  docker-compose exec app python manage.py collectstatic --noinput
  ```
- **WhiteNoise not configured**: Check MIDDLEWARE setting in production.py
- **Nginx misconfiguration**: Check nginx.conf static file serving rules

### 6. SSL/HTTPS Issues

#### Problem: SSL certificate errors
```
SSL_ERROR_BAD_CERT_DOMAIN
```

**Diagnosis:**
```bash
# Check certificate validity
openssl x509 -in /path/to/cert.pem -text -noout

# Check Nginx SSL configuration
docker-compose exec nginx nginx -t

# Test SSL connection
openssl s_client -connect yourdomain.com:443
```

**Solutions:**
- **Invalid certificate**: Obtain valid SSL certificate
- **Wrong domain**: Ensure certificate matches domain name
- **Nginx configuration**: Update SSL settings in nginx.conf

### 7. Performance Issues

#### Problem: Slow response times
```
Application responding slowly (>5 seconds)
```

**Diagnosis:**
```bash
# Check resource usage
docker stats --no-stream

# Check database performance
docker-compose exec app python manage.py shell -c "
from django.db import connection
print('Database queries:', len(connection.queries))
"

# Check Gunicorn workers
docker-compose exec app ps aux | grep gunicorn

# Test response times
curl -w "@curl-format.txt" -o /dev/null -s http://localhost/
```

**Solutions:**
- **Insufficient resources**: Increase memory/CPU limits
- **Too few workers**: Increase Gunicorn worker count
  ```bash
  # In .env file
  GUNICORN_WORKERS=8  # 2 * CPU cores + 1
  ```
- **Database optimization**: Add database indexes, optimize queries
- **Caching**: Enable Redis caching
  ```bash
  # Check cache configuration
  docker-compose exec app python manage.py shell -c "
  from django.core.cache import cache
  cache.set('test', 'value', 30)
  print('Cache test:', cache.get('test'))
  "
  ```

### 8. Memory Issues

#### Problem: Out of memory errors
```
Container killed due to memory limit
```

**Diagnosis:**
```bash
# Check memory usage
docker stats --no-stream

# Check system memory
free -h

# Check container limits
docker inspect $(docker-compose ps -q app) | grep -i memory
```

**Solutions:**
- **Increase container limits**: Update docker-compose.yml
  ```yaml
  services:
    app:
      deploy:
        resources:
          limits:
            memory: 2G
  ```
- **Optimize application**: Reduce memory usage in code
- **Add swap**: Configure system swap space

### 9. Environment Variable Issues

#### Problem: Configuration errors
```
KeyError: 'REQUIRED_ENV_VAR'
```

**Diagnosis:**
```bash
# Check environment variables
docker-compose exec app env | sort

# Validate configuration
python validate_production_config.py

# Check .env file
cat .env | grep -v "^#" | grep -v "^$"
```

**Solutions:**
- **Missing variables**: Add required variables to .env file
- **Wrong format**: Check variable format and escaping
- **File not loaded**: Ensure .env file is in correct location

### 10. Network Issues

#### Problem: Service communication failures
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Diagnosis:**
```bash
# Check Docker networks
docker network ls
docker network inspect $(docker-compose config --services | head -1)

# Test service connectivity
docker-compose exec app ping db
docker-compose exec app ping qdrant
docker-compose exec app ping redis

# Check port bindings
docker-compose ps
```

**Solutions:**
- **Network isolation**: Ensure services are on same network
- **Port conflicts**: Check for port binding conflicts
- **Firewall issues**: Configure firewall rules for Docker

## Emergency Recovery Procedures

### 1. Complete System Recovery

```bash
# Stop all services
docker-compose down

# Clean up containers and networks
docker system prune -f

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Wait for services to be ready
sleep 60

# Check health
./deploy.sh health
```

### 2. Database Recovery

```bash
# Stop application
docker-compose stop app

# Backup current database (if possible)
./scripts/backup.sh --database-only

# Restore from backup
./scripts/restore.sh --database-only

# Restart application
docker-compose start app
```

### 3. Vector Database Recovery

```bash
# Reinitialize Qdrant
docker-compose exec app python manage.py init_qdrant --force

# Resync all FAQ data
docker-compose exec app python manage.py sync_faqs_to_qdrant --force

# Test vector search
docker-compose exec app python manage.py test_qdrant
```

## Monitoring and Alerting

### Health Check Script

Create a monitoring script to run regularly:

```bash
#!/bin/bash
# health-monitor.sh

# Check service health
if ! ./deploy.sh health > /dev/null 2>&1; then
    echo "ALERT: Service health check failed"
    # Send alert (email, Slack, etc.)
fi

# Check disk space
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "ALERT: Disk usage is ${DISK_USAGE}%"
fi

# Check memory usage
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ $MEMORY_USAGE -gt 80 ]; then
    echo "ALERT: Memory usage is ${MEMORY_USAGE}%"
fi
```

### Log Analysis

```bash
# Check for errors in logs
docker-compose logs app | grep -i error | tail -20

# Check for performance issues
docker-compose logs app | grep -i "slow\|timeout\|performance" | tail -20

# Check authentication failures
docker-compose logs nginx | grep "401\|403" | tail -20
```

## Prevention Best Practices

### 1. Configuration Management
- Use configuration validation before deployment
- Maintain environment-specific .env files
- Document all configuration changes

### 2. Monitoring
- Set up health checks for all services
- Monitor resource usage continuously
- Configure alerting for critical issues

### 3. Backup Strategy
- Automated daily backups
- Test restore procedures regularly
- Store backups in multiple locations

### 4. Testing
- Run integration tests before deployment
- Perform load testing in staging environment
- Validate all functionality after deployment

### 5. Documentation
- Keep troubleshooting guide updated
- Document all configuration changes
- Maintain deployment runbooks

## Getting Help

### Log Collection for Support

```bash
# Collect all relevant logs
mkdir -p debug-logs/$(date +%Y%m%d_%H%M%S)
cd debug-logs/$(date +%Y%m%d_%H%M%S)

# System information
docker --version > system-info.txt
docker-compose --version >> system-info.txt
uname -a >> system-info.txt
free -h >> system-info.txt
df -h >> system-info.txt

# Service logs
docker-compose logs app > app.log
docker-compose logs db > db.log
docker-compose logs qdrant > qdrant.log
docker-compose logs nginx > nginx.log
docker-compose logs redis > redis.log

# Configuration
cp ../../.env config.env
cp ../../docker-compose.yml .
cp ../../docker-compose.prod.yml .

# Service status
docker-compose ps > service-status.txt
docker stats --no-stream > resource-usage.txt

echo "Debug information collected in: $(pwd)"
```

### Support Contacts

- **System Administrator**: [admin@company.com]
- **Database Administrator**: [dba@company.com]
- **Development Team**: [dev-team@company.com]
- **Emergency Contact**: [emergency@company.com]

### Escalation Procedures

1. **Level 1**: Check this troubleshooting guide
2. **Level 2**: Contact system administrator
3. **Level 3**: Contact development team
4. **Level 4**: Emergency escalation for critical issues

Remember to always backup before making changes and test solutions in a staging environment when possible.