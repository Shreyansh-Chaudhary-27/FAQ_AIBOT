# Production Deployment Guide

This guide provides step-by-step instructions for deploying the Django FAQ/RAG application to production environments.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ installed
- Git repository cloned
- Domain name configured (for production)
- SSL certificates (for HTTPS)

## Quick Start

### 1. Set Up Production Environment

```bash
# Copy production environment template
cp .env.production .env

# Generate secure secret key and configure environment
./scripts/setup-production-env.sh setup
```

### 2. Configure Environment Variables

Edit `.env` file and update the following required values:

```bash
# Generate a secure secret key
SECRET_KEY=your-secure-secret-key-here

# Database configuration
DB_PASSWORD=your-secure-database-password

# Gemini AI API key (required for RAG functionality)
GEMINI_API_KEY=your-gemini-api-key

# Production domains
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Enable HTTPS (when SSL certificates are configured)
SECURE_SSL_REDIRECT=True
```

### 3. Validate Configuration

```bash
# Validate production configuration
python validate_production_config.py

# Or use the setup script
./scripts/setup-production-env.sh validate
```

### 4. Deploy Application

```bash
# Deploy with Docker Compose
./deploy.sh deploy

# Or use the production deployment script
./production-deploy.sh deploy
```

## Detailed Configuration

### Environment Variables

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `DB_PASSWORD` | PostgreSQL password | `secure_password_123` |
| `GEMINI_API_KEY` | Gemini AI API key | `AIza...` |
| `ALLOWED_HOSTS` | Allowed domains | `yourdomain.com,www.yourdomain.com` |

#### Database Configuration

```bash
DB_NAME=faq_production
DB_USER=faq_user
DB_PASSWORD=your-secure-password
DB_HOST=db  # Docker service name
DB_PORT=5432
```

#### Vector Database (Qdrant)

```bash
QDRANT_HOST=qdrant  # Docker service name
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=faq_embeddings
RAG_VECTOR_STORE_TYPE=qdrant
```

#### Security Settings

```bash
DEBUG=False
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
CSRF_TRUSTED_ORIGINS=https://yourdomain.com
```

### Docker Compose Configuration

The application uses a multi-container architecture:

- **nginx**: Reverse proxy and static file server
- **app**: Django application with Gunicorn
- **db**: PostgreSQL database
- **qdrant**: Vector database for embeddings
- **redis**: Cache and session storage

#### Production Deployment

```bash
# Deploy with production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or use the deployment script
./deploy.sh deploy
```

#### Resource Limits

Production deployment includes resource limits:

```yaml
# Application server
APP_MEMORY_LIMIT=1G
APP_CPU_LIMIT=1.0

# Database
DB_MEMORY_LIMIT=512M
DB_CPU_LIMIT=0.5

# Vector database
QDRANT_MEMORY_LIMIT=1G
QDRANT_CPU_LIMIT=1.0
```

## Validation and Testing

### Configuration Validation

The `validate_production_config.py` script performs comprehensive validation:

```bash
python validate_production_config.py
```

Validation checks:
- ✅ Environment variables
- ✅ Django settings
- ✅ Database configuration
- ✅ Security settings
- ✅ Static files configuration
- ✅ External services
- ✅ RAG system configuration
- ✅ Caching configuration
- ✅ Logging configuration
- ✅ Service connections

### Service Health Checks

```bash
# Check all service health
./deploy.sh health

# Test specific services
./scripts/setup-production-env.sh test-db
./scripts/setup-production-env.sh test-qdrant
./scripts/setup-production-env.sh test-gemini
```

### End-to-End Testing

```bash
# Test complete deployment stack
./deploy.sh test-qdrant

# Test RAG system functionality
python manage.py test_qdrant --verbose
```

## Deployment Process

### 1. Pre-deployment Validation

```bash
# Validate configuration
python validate_production_config.py

# Check prerequisites
./deploy.sh health
```

### 2. Backup (if updating existing deployment)

```bash
# Create backup before deployment
./deploy.sh backup
```

### 3. Deploy Services

```bash
# Deploy all services
./deploy.sh deploy

# Or step-by-step deployment
docker-compose pull
docker-compose build
docker-compose up -d
```

### 4. Post-deployment Verification

```bash
# Check service status
./deploy.sh health

# Test application functionality
curl http://localhost/health/
curl http://localhost/api/health/
```

## Monitoring and Maintenance

### Log Management

```bash
# View application logs
./deploy.sh logs

# View specific service logs
docker-compose logs app
docker-compose logs nginx
docker-compose logs db
```

### Backup and Restore

```bash
# Create backup
./deploy.sh backup

# Restore from backup
./deploy.sh restore
```

### Updates and Maintenance

```bash
# Update application
./deploy.sh update

# Restart services
./deploy.sh restart

# Clean up Docker resources
./deploy.sh cleanup
```

## Troubleshooting

### Common Issues

#### 1. Environment Variable Errors

```bash
# Error: Required environment variable not set
# Solution: Check .env file and ensure all required variables are configured
python validate_production_config.py
```

#### 2. Database Connection Issues

```bash
# Error: Database connection failed
# Solution: Check database service status and credentials
docker-compose logs db
./scripts/setup-production-env.sh test-db
```

#### 3. Qdrant Connection Issues

```bash
# Error: Qdrant connection failed
# Solution: Check Qdrant service status
docker-compose logs qdrant
./scripts/setup-production-env.sh test-qdrant
```

#### 4. Static Files Not Loading

```bash
# Error: Static files not found
# Solution: Check WhiteNoise configuration and collect static files
docker-compose exec app python manage.py collectstatic --noinput
```

#### 5. "I Don't Know" Responses

```bash
# Error: RAG system returning "I don't know"
# Solution: Check embedding system and Qdrant data
python manage.py sync_faqs_to_qdrant
docker-compose exec app python manage.py test_qdrant
```

### Debug Mode

For debugging production issues (temporarily):

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
docker-compose restart app

# View detailed logs
docker-compose logs -f app
```

**⚠️ Warning**: Never enable Django DEBUG=True in production.

## Security Considerations

### SSL/HTTPS Configuration

1. Obtain SSL certificates (Let's Encrypt, commercial CA)
2. Configure Nginx with SSL
3. Enable HTTPS redirect: `SECURE_SSL_REDIRECT=True`
4. Update CSRF origins: `CSRF_TRUSTED_ORIGINS=https://yourdomain.com`

### Database Security

- Use strong passwords
- Restrict database access to application only
- Enable connection encryption
- Regular security updates

### API Key Management

- Store API keys in environment variables only
- Never commit API keys to version control
- Rotate API keys regularly
- Monitor API key usage

## Performance Optimization

### Application Server

```bash
# Adjust Gunicorn workers based on CPU cores
GUNICORN_WORKERS=8  # 2 * CPU cores + 1

# Configure worker memory limits
GUNICORN_WORKER_MEMORY_LIMIT=1073741824  # 1GB
```

### Database Optimization

```bash
# Connection pooling
DB_CONN_MAX_AGE=600
DB_MAX_CONNECTIONS=20

# Resource allocation
DB_MEMORY_LIMIT=1G
DB_CPU_LIMIT=1.0
```

### Caching

```bash
# Redis cache configuration
REDIS_URL=redis://redis:6379/0
CACHE_TTL=3600
```

## Scaling Considerations

### Horizontal Scaling

- Load balancer configuration
- Multiple application instances
- Shared database and cache
- Distributed vector storage

### Vertical Scaling

- Increase resource limits
- Optimize worker processes
- Database performance tuning
- Vector database optimization

## Support and Documentation

- [Docker Deployment Guide](DOCKER_DEPLOYMENT.md)
- [Qdrant Integration Guide](QDRANT_INTEGRATION.md)
- [Deployment Checklist](config/deployment-checklist.md)
- [Quick Fix Guide](QUICK_FIX_GUIDE.md)

For additional support, check the troubleshooting guides and log files.