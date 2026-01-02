# 🚀 Render Deployment Guide - Unified Docker

## 📋 Unified Setup

### ✅ Single File Architecture
- **`requirements.txt`** - Unified dependencies, Linux-compatible
- **`Dockerfile`** - Single file with multiple build modes
- **No duplicates** - Clean, maintainable setup

## 🐳 Unified Dockerfile

### Build Modes Available:

| Mode | Description | Best For |
|------|-------------|----------|
| `cloud` | Optimized for cloud platforms | **Render, Railway, Heroku** |
| `production` | Full security, multi-stage | Production servers |
| `simple` | Fast development build | Local development |

## 🔧 Render Configuration

### Method 1: Docker with Cloud Mode (Recommended)

**Service Type:** Web Service  
**Build Command:** (leave empty - Docker handles it)  
**Start Command:** (leave empty - Docker handles it)  

**Docker Build Arguments (optional):**
```
BUILD_MODE=cloud
```

### Method 2: Direct Python Deployment

**Service Type:** Web Service  
**Build Command:**
```bash
pip install -r requirements.txt
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
BUILD_MODE=cloud
```

## 📊 Database Setup

1. **Add PostgreSQL Database** in Render dashboard
2. Render will automatically provide `DATABASE_URL`
3. No additional database configuration needed

## 🎯 Deployment Steps

1. **Push code** to your GitHub repository
2. **Create Web Service** on Render
3. **Connect repository**
4. **Set Docker build arguments** (optional): `BUILD_MODE=cloud`
5. **Add PostgreSQL database**
6. **Set environment variables**
7. **Deploy!**

## ✅ Unified Architecture Benefits

### Removed Files:
- ❌ `Dockerfile.simple` - Merged into main Dockerfile
- ❌ `Dockerfile.render` - Merged into main Dockerfile
- ❌ `requirements-render.txt` - Merged into requirements.txt
- ❌ `requirements-production.txt` - Merged into requirements.txt

### Single File Features:
- ✅ **Multi-mode Docker** - One file, multiple scenarios
- ✅ **Build arguments** - Customize deployment
- ✅ **Unified requirements** - No conflicts or duplicates
- ✅ **Easy maintenance** - Update once, works everywhere

## 🔍 Troubleshooting

### Build Fails with Package Errors
- All Windows-specific packages removed
- Uses `psycopg2-binary` for better compatibility
- Unified requirements eliminate conflicts

### Static Files Not Loading
- Environment variable `DJANGO_ENV=production` is set
- WhiteNoise is configured (already done in settings)

### Database Connection Errors
- PostgreSQL database is added in Render
- `DATABASE_URL` is automatically provided
- Check environment variables

## 🚀 Local Testing

### Test Cloud Mode (Render-like)
```bash
# Build for cloud deployment
docker build --build-arg BUILD_MODE=cloud -t faq-app .

# Run with environment port
docker run -p 3000:3000 -e PORT=3000 -e DJANGO_ENV=development faq-app
```

### Test Production Mode
```bash
# Build for production
docker build --build-arg BUILD_MODE=production -t faq-app .

# Run production container
docker run -p 8000:8000 -e DJANGO_ENV=production -e SECRET_KEY=test-key faq-app
```

### Test Simple Mode
```bash
# Build for development
docker build --build-arg BUILD_MODE=simple -t faq-app .

# Run simple container
docker run -p 8000:8000 -e DJANGO_ENV=development faq-app
```

## 📈 Performance Tips

1. **Use cloud mode** for Render deployment
2. **Single Dockerfile** reduces maintenance overhead
3. **Unified requirements** eliminate conflicts
4. **Build arguments** optimize for your scenario

## 🔒 Security Checklist

- ✅ Generate new SECRET_KEY
- ✅ Set ALLOWED_HOSTS to your domain
- ✅ Enable HTTPS redirect
- ✅ Configure CSRF trusted origins
- ✅ Use environment variables for secrets
- ✅ Unified setup reduces complexity

## 🎉 Quick Commands

### Generate Secret Key
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Build for Different Scenarios
```bash
# For Render/Cloud
docker build --build-arg BUILD_MODE=cloud -t faq-app .

# For Production
docker build --build-arg BUILD_MODE=production -t faq-app .

# For Development
docker build --build-arg BUILD_MODE=simple -t faq-app .
```

Your Django FAQ application is now ready for seamless deployment with the unified Docker setup! 🎉

## 📚 Additional Resources

- See `UNIFIED_DOCKER_GUIDE.md` for detailed Docker usage
- See `REQUIREMENTS_OPTIMIZATION_SUMMARY.md` for dependency changes