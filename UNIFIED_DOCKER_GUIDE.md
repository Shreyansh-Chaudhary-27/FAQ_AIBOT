# 🐳 Unified Dockerfile Guide

## 📋 Single Dockerfile for All Scenarios

The unified `Dockerfile` combines the best features from all previous Docker configurations:
- **Production**: Multi-stage build, security, entrypoint script
- **Cloud/Render**: Dynamic port binding, static file collection
- **Simple**: Fast single-stage build for development

## 🔧 Build Arguments

### BUILD_MODE Options:

| Mode | Description | Use Case |
|------|-------------|----------|
| `production` | Multi-stage build, security features, entrypoint script | Production servers, full security |
| `cloud` | Single-stage, dynamic port, static collection | Render, Railway, Heroku |
| `simple` | Basic single-stage build | Development, testing |

### Additional Arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `PYTHON_VERSION` | `3.11-slim` | Python base image version |
| `PORT` | `8000` | Application port |

## 🚀 Build Examples

### Production Build (Default)
```bash
# Full production build with security and multi-stage
docker build -t faq-app .

# Explicit production build
docker build --build-arg BUILD_MODE=production -t faq-app .
```

### Cloud/Render Build
```bash
# Optimized for cloud platforms
docker build --build-arg BUILD_MODE=cloud -t faq-app .

# With custom port
docker build --build-arg BUILD_MODE=cloud --build-arg PORT=3000 -t faq-app .
```

### Simple Build
```bash
# Fast build for development
docker build --build-arg BUILD_MODE=simple -t faq-app .
```

### Custom Python Version
```bash
# Use different Python version
docker build --build-arg PYTHON_VERSION=3.12-slim -t faq-app .
```

## 🏃 Run Examples

### Production Mode
```bash
# Run production container
docker run -p 8000:8000 \
  -e DJANGO_ENV=production \
  -e SECRET_KEY=your-secret-key \
  -e DATABASE_URL=your-db-url \
  faq-app
```

### Cloud Mode (Render-style)
```bash
# Run with environment port
docker run -p 3000:3000 \
  -e PORT=3000 \
  -e DJANGO_ENV=production \
  -e SECRET_KEY=your-secret-key \
  faq-app
```

### Simple Mode
```bash
# Run simple container
docker run -p 8000:8000 \
  -e DJANGO_ENV=development \
  faq-app
```

## 🔍 Features by Build Mode

### Production Mode Features:
- ✅ Multi-stage build (smaller final image)
- ✅ Virtual environment isolation
- ✅ Non-root user (django)
- ✅ Entrypoint script with initialization
- ✅ Full security hardening
- ✅ Gunicorn with configuration file
- ✅ Health checks
- ✅ Proper logging and monitoring

### Cloud Mode Features:
- ✅ Single-stage build (faster)
- ✅ Dynamic port binding ($PORT)
- ✅ Static file collection
- ✅ Health checks
- ✅ Optimized for cloud platforms
- ✅ Direct gunicorn startup
- ✅ Timeout configuration

### Simple Mode Features:
- ✅ Fastest build time
- ✅ Minimal configuration
- ✅ Direct dependency installation
- ✅ Basic gunicorn setup
- ✅ Development-friendly

## 🎯 Render Deployment

For Render, use the cloud mode:

**Dockerfile Build:**
```bash
# Render will automatically use this
docker build --build-arg BUILD_MODE=cloud -t faq-app .
```

**Environment Variables:**
```
BUILD_MODE=cloud
DJANGO_ENV=production
SECRET_KEY=your-secret-key
GEMINI_API_KEY=your-api-key
ALLOWED_HOSTS=your-app.onrender.com
```

## 🔧 Docker Compose Integration

### Production
```yaml
version: '3.8'
services:
  web:
    build:
      context: .
      args:
        BUILD_MODE: production
    ports:
      - "8000:8000"
    environment:
      - DJANGO_ENV=production
```

### Cloud
```yaml
version: '3.8'
services:
  web:
    build:
      context: .
      args:
        BUILD_MODE: cloud
        PORT: 3000
    ports:
      - "3000:3000"
    environment:
      - PORT=3000
      - DJANGO_ENV=production
```

## 🛠️ Troubleshooting

### Build Issues
```bash
# Clean build without cache
docker build --no-cache --build-arg BUILD_MODE=cloud -t faq-app .

# Check build logs
docker build --progress=plain --build-arg BUILD_MODE=cloud -t faq-app .
```

### Runtime Issues
```bash
# Check container logs
docker logs container-name

# Interactive shell
docker run -it --build-arg BUILD_MODE=simple faq-app bash
```

### Permission Issues (Production Mode)
```bash
# Check if running as django user
docker run faq-app whoami

# Check file permissions
docker run faq-app ls -la /app
```

## 📊 Image Size Comparison

| Build Mode | Approximate Size | Build Time |
|------------|------------------|------------|
| Production | ~800MB | Slower (multi-stage) |
| Cloud | ~1.2GB | Medium |
| Simple | ~1.2GB | Fastest |

## 🔒 Security Features

### Production Mode Security:
- ✅ Non-root user execution
- ✅ Minimal runtime dependencies
- ✅ Virtual environment isolation
- ✅ Proper file permissions
- ✅ Security-hardened base image

### All Modes:
- ✅ Health checks
- ✅ No cache for pip installs
- ✅ Clean package cache
- ✅ Environment variable support

## 🎉 Benefits of Unified Dockerfile

1. **Single Source of Truth** - One file to maintain
2. **Flexible Deployment** - Works with any platform
3. **Optimized Builds** - Right features for each scenario
4. **Consistent Base** - Same foundation, different optimizations
5. **Easy Maintenance** - Update once, works everywhere

Your Django FAQ application now has a single, powerful Dockerfile that handles all deployment scenarios! 🚀