# Qdrant Vector Database Integration

This document describes the Qdrant vector database integration for the Django FAQ/RAG system, including setup, configuration, and troubleshooting.

## Overview

The system now supports Qdrant as the primary vector database for production deployments, with automatic fallback to local storage when Qdrant is unavailable. This ensures reliable operation and prevents "I don't know" responses due to embedding issues.

## Features

- **Production-ready Qdrant integration** with Docker Compose orchestration
- **Automatic fallback mechanisms** to local vector storage when Qdrant is unavailable
- **Comprehensive health monitoring** with multiple health check endpoints
- **Batch operations** for efficient data ingestion and migration
- **Connection pooling and retry logic** for reliability
- **Performance monitoring** and metrics collection

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Django App    │───▶│  Vector Store   │───▶│     Qdrant      │
│                 │    │    Factory      │    │   (Primary)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                │                        ▼
                                │               ┌─────────────────┐
                                └──────────────▶│ Local Storage   │
                                                │  (Fallback)     │
                                                └─────────────────┘
```

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```bash
# Vector Database Configuration
RAG_VECTOR_STORE_TYPE=qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=faq_embeddings
QDRANT_TIMEOUT=30
```

### Docker Compose

The Qdrant service is already configured in `docker-compose.yml`:

```yaml
qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"
    - "6334:6334"
  volumes:
    - qdrant_data:/qdrant/storage
  environment:
    QDRANT__SERVICE__HTTP_PORT: 6333
    QDRANT__SERVICE__GRPC_PORT: 6334
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
    interval: 10s
    timeout: 5s
    retries: 5
  restart: unless-stopped
```

## Deployment

### 1. Start the Services

```bash
# Start all services including Qdrant
docker-compose up -d

# Check service status
docker-compose ps
```

### 2. Initialize Qdrant

```bash
# Initialize Qdrant collection and validate setup
docker-compose exec app python manage.py init_qdrant

# Or with specific options
docker-compose exec app python manage.py init_qdrant --validate --stats
```

### 3. Migrate Existing Data (Optional)

```bash
# Sync existing FAQ data from Django database to Qdrant
docker-compose exec app python manage.py sync_faqs_to_qdrant

# Or with specific options
docker-compose exec app python manage.py sync_faqs_to_qdrant --batch-size 100 --force
```

## Management Commands

### init_qdrant

Initialize and configure Qdrant vector database:

```bash
# Basic initialization
python manage.py init_qdrant

# Health check only
python manage.py init_qdrant --health-check-only

# Validate existing collection
python manage.py init_qdrant --validate --stats

# Recreate collection
python manage.py init_qdrant --recreate

# Migrate from local store
python manage.py init_qdrant --migrate --local-store-path /path/to/local/store
```

### sync_faqs_to_qdrant

Sync FAQ data from Django database to Qdrant:

```bash
# Basic sync
python manage.py sync_faqs_to_qdrant

# Force re-sync
python manage.py sync_faqs_to_qdrant --force

# Dry run (show what would be synced)
python manage.py sync_faqs_to_qdrant --dry-run

# Custom batch size
python manage.py sync_faqs_to_qdrant --batch-size 50

# Statistics only
python manage.py sync_faqs_to_qdrant --stats-only
```

### test_qdrant

Test Qdrant functionality and integration:

```bash
# Comprehensive test
python manage.py test_qdrant

# Skip specific tests
python manage.py test_qdrant --skip-health --skip-operations

# Verbose output
python manage.py test_qdrant --verbose
```

## Health Monitoring

### Health Check Endpoints

The system provides multiple health check endpoints:

- **`/health/`** - Basic health check
- **`/health/detailed/`** - Detailed component health
- **`/health/vector-store/`** - Vector store specific health
- **`/health/qdrant/`** - Qdrant specific health and statistics
- **`/health/ready/`** - Kubernetes readiness probe
- **`/health/live/`** - Kubernetes liveness probe

### Example Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2026-01-02T13:45:45.078727",
  "store_type": "qdrant",
  "server": {
    "host": "qdrant",
    "port": 6333,
    "response_time_ms": 15.2,
    "collections_count": 1
  },
  "collection": {
    "name": "faq_embeddings",
    "exists": true,
    "stats": {
      "total_points": 150,
      "vector_dimension": 384,
      "distance_metric": "COSINE"
    }
  }
}
```

## Fallback Mechanisms

The system implements multiple layers of fallback to ensure reliability:

### 1. Vector Store Factory Fallback

```python
# Automatically creates Qdrant store with local fallback
vector_store = VectorStoreFactory.create_production_store()
```

### 2. Connection Retry Logic

- Automatic reconnection attempts with exponential backoff
- Configurable retry limits and timeouts
- Health status monitoring and recovery

### 3. Graceful Degradation

- Falls back to local vector storage when Qdrant is unavailable
- Continues operation with reduced functionality
- Provides meaningful error messages instead of "I don't know"

## Performance Optimization

### Connection Pooling

Qdrant connections are managed efficiently:

```python
# Configured in QdrantVectorStore
client = QdrantClient(
    host=host,
    port=port,
    timeout=timeout
)
```

### Batch Operations

Large datasets are processed in batches:

```python
# Batch size configuration
batch_size = 100  # Configurable via command line
```

### Indexing Optimization

Collections are optimized for FAQ use cases:

```python
# Optimized collection configuration
optimizers_config=models.OptimizersConfig(
    default_segment_number=2,
    max_segment_size=20000,
    memmap_threshold=20000,
    indexing_threshold=20000,
    flush_interval_sec=5,
    max_optimization_threads=1
)
```

## Troubleshooting

### Common Issues

#### 1. Qdrant Connection Failed

**Symptoms:**
- Health checks return "unhealthy"
- Error: "No connection could be made"

**Solutions:**
```bash
# Check if Qdrant is running
docker-compose ps qdrant

# Check Qdrant logs
docker-compose logs qdrant

# Restart Qdrant service
docker-compose restart qdrant
```

#### 2. Collection Not Found

**Symptoms:**
- Error: "Collection does not exist"
- Empty search results

**Solutions:**
```bash
# Initialize collection
python manage.py init_qdrant

# Validate collection
python manage.py init_qdrant --validate
```

#### 3. Embedding Generation Errors

**Symptoms:**
- Sync fails with embedding errors
- "I don't know" responses

**Solutions:**
```bash
# Check vectorizer dependencies
pip install sentence-transformers

# Test embedding generation
python manage.py test_qdrant --verbose
```

#### 4. Performance Issues

**Symptoms:**
- Slow search responses
- High memory usage

**Solutions:**
```bash
# Check collection statistics
python manage.py init_qdrant --stats

# Optimize collection
# (Collection optimization is automatic)

# Monitor performance
curl http://localhost:8000/health/qdrant/
```

### Debug Mode

Enable debug logging for troubleshooting:

```python
# In settings
LOGGING = {
    'loggers': {
        'faq.rag.components.vector_store': {
            'level': 'DEBUG',
        },
    },
}
```

### Testing Scripts

Use the provided test scripts for validation:

```bash
# Test Qdrant client functionality
python test_qdrant_simple.py

# Test health endpoints
python test_health_endpoints.py

# Comprehensive integration test
python test_qdrant_production.py
```

## Monitoring and Alerts

### Metrics Collection

The system collects various metrics:

- Connection success/failure rates
- Search response times
- Vector count and storage usage
- Fallback usage statistics

### Health Monitoring

Continuous health monitoring includes:

- Connection status
- Collection integrity
- Performance metrics
- Error rates

### Alerting

Set up monitoring alerts for:

- Qdrant service unavailability
- High error rates
- Performance degradation
- Storage capacity issues

## Security Considerations

### Network Security

- Qdrant runs in isolated Docker network
- No external port exposure in production
- Internal service communication only

### Data Security

- Vector data is stored securely in Qdrant
- No sensitive data in vector embeddings
- Backup and restore procedures available

### Access Control

- Service-level access control via Docker networking
- No authentication required for internal communication
- Production deployment should use proper network isolation

## Backup and Recovery

### Data Backup

```bash
# Backup Qdrant data
docker-compose exec qdrant tar -czf /qdrant/storage/backup.tar.gz /qdrant/storage

# Copy backup to host
docker cp $(docker-compose ps -q qdrant):/qdrant/storage/backup.tar.gz ./qdrant_backup.tar.gz
```

### Data Recovery

```bash
# Stop Qdrant service
docker-compose stop qdrant

# Restore data
docker cp ./qdrant_backup.tar.gz $(docker-compose ps -q qdrant):/qdrant/storage/

# Extract backup
docker-compose exec qdrant tar -xzf /qdrant/storage/backup.tar.gz -C /

# Start service
docker-compose start qdrant
```

## Migration Guide

### From Local Storage to Qdrant

1. **Backup existing data:**
   ```bash
   cp -r vector_store_data vector_store_data_backup
   ```

2. **Start Qdrant service:**
   ```bash
   docker-compose up -d qdrant
   ```

3. **Initialize Qdrant:**
   ```bash
   python manage.py init_qdrant
   ```

4. **Migrate data:**
   ```bash
   python manage.py init_qdrant --migrate --local-store-path vector_store_data
   ```

5. **Update configuration:**
   ```bash
   # Set in .env
   RAG_VECTOR_STORE_TYPE=qdrant
   ```

6. **Validate migration:**
   ```bash
   python manage.py init_qdrant --validate --stats
   ```

## Best Practices

### Production Deployment

1. **Use persistent volumes** for Qdrant data
2. **Monitor health endpoints** continuously
3. **Set up proper logging** and alerting
4. **Regular backups** of vector data
5. **Test fallback mechanisms** regularly

### Performance Optimization

1. **Batch operations** for large datasets
2. **Monitor memory usage** and optimize as needed
3. **Use appropriate vector dimensions** (384 for MiniLM)
4. **Regular collection maintenance** and optimization

### Security

1. **Network isolation** in production
2. **Regular security updates** for Qdrant
3. **Monitor access logs** and unusual activity
4. **Secure backup storage** and encryption

## Support and Resources

### Documentation

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Django Management Commands](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)

### Troubleshooting

- Check health endpoints for system status
- Review Docker logs for service issues
- Use test scripts for validation
- Monitor performance metrics

### Community

- [Qdrant GitHub](https://github.com/qdrant/qdrant)
- [Qdrant Discord](https://discord.gg/qdrant)
- [Django Community](https://www.djangoproject.com/community/)