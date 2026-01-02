# 🚀 Render Deployment Guide

## 📋 Updated Files for Deployment

### ✅ Fixed Requirements Files
- **`requirements-render.txt`** - Minimal, optimized for Render (recommended)
- **`requirements-production.txt`** - Full production features
- **`requirements.txt`** - Fixed (removed Windows-specific packages)

### 🐳 Docker Options

#### Option 1: Simple Dockerfile (Recommended for Render)
**File:** `Dockerfile.simple`
- Minimal, fast build
- Uses `requirements-render.txt`
- Optimized for cloud deployment

#### Option 2: Render-Optimized Dockerfile
**File:** `Dockerfile.render`
- Includes health checks
- Dynamic port binding
- Uses `requirements-render.txt`

#### Option 3: Full Production Dockerfile
**File:** `Dockerfile` (updated)
- Multi-stage build
- Uses `requirements-production.txt`
- Full security features

## 🔧 Render Configuration

### Method 1: Using Docker (Recommended)

**Service Type:** Web Service
**Build Command:** (leave empty - Docker handles it)
**Start Command:** (leave empty - Docker handles it)
**Dockerfile:** `Dockerfile.simple`

### Method 2: Direct Python Deployment

**Service Type:** Web Service
**Build Command:**
```bash
pip install -r requirements-render.txt
```

**Start Command:**
```bash
gunicorn --bind 0.0.0.0:$PORT --workers 2 faqbackend.wsgi:application
```

## 🔑 Environment Variables

Set these in your Render dashboard:

```
DJANGO_ENV=production
SECRET_KEY=your-generated-secret-key-here
GEMINI_API_KEY=AIzaSyBnpxlk6PvtQO09MbIHhe-Lxp9t-GosdB0
ALLOWED_HOSTS=your-app-name.onrender.com
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://your-app-name.onrender.com
```

## 📊 Database Setup

1. **Add PostgreSQL Database** in Render dashboard
2. Render will automatically provide `DATABASE_URL`
3. No additional database configuration needed

## 🎯 Deployment Steps

1. **Push code** to your GitHub repository
2. **Create Web Service** on Render
3. **Connect repository**
4. **Choose deployment method:**
   - Docker: Select `Dockerfile.simple`
   - Python: Use build/start commands above
5. **Add PostgreSQL database**
6. **Set environment variables**
7. **Deploy!**

## 🔍 Troubleshooting

### Build Fails with Package Errors
- Use `requirements-render.txt` instead of `requirements.txt`
- Ensure `pywin32` is not in requirements

### Static Files Not Loading
- Environment variable `DJANGO_ENV=production` is set
- WhiteNoise is configured (already done in settings)

### Database Connection Errors
- PostgreSQL database is added in Render
- `DATABASE_URL` is automatically provided
- Check environment variables

## 🚀 Quick Start Commands

### Generate Secret Key
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Test Locally with Docker
```bash
# Build with simple Dockerfile
docker build -f Dockerfile.simple -t faq-app .

# Run locally
docker run -p 8000:8000 -e DJANGO_ENV=development faq-app
```

## 📈 Performance Tips

1. **Use minimal requirements** (`requirements-render.txt`)
2. **Enable caching** with Redis (optional)
3. **Use Docker** for consistent builds
4. **Set appropriate worker count** (2 workers for basic plan)

## 🔒 Security Checklist

- ✅ Generate new SECRET_KEY
- ✅ Set ALLOWED_HOSTS to your domain
- ✅ Enable HTTPS redirect
- ✅ Configure CSRF trusted origins
- ✅ Use environment variables for secrets

Your Django FAQ application should now deploy successfully on Render! 🎉