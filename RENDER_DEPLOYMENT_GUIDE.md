# 🚀 Render Deployment Guide - Pinecone Vector Database

## 📋 Unified Setup

### ✅ Single File Architecture
- **`requirements.txt`** - Unified dependencies, Linux-compatible
- **`Dockerfile`** - Single file with multiple build modes
- **No duplicates** - Clean, maintainable setup
- **No external database** - Uses Pinecone for vector storage

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

### For Pinecone Vector Database (Recommended)

Set these in your Render dashboard:

```
DJANGO_ENV=production
SECRET_KEY=your-generated-secret-key-here
GEMINI_API_KEY=AIzaSyBnpxlk6PvtQO09MbIHhe-Lxp9t-GosdB0
PINECONE_API_KEY=your-pinecone-api-key-here
PINECONE_INDEX_NAME=faq-embeddings
PINECONE_ENVIRONMENT=us-east-1-aws
ALLOWED_HOSTS=your-app-name.onrender.com
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://your-app-name.onrender.com
BUILD_MODE=cloud
```

## 📊 Database Setup

### Pinecone Vector Database (No Traditional Database Needed)

**Benefits:**
- ✅ **No external database service required**
- ✅ **Managed vector database** - Pinecone handles infrastructure
- ✅ **High performance** - Optimized for similarity search
- ✅ **Scalable** - Handles large vector datasets
- ✅ **No connection issues** - Cloud-native, always available

**Setup:**
1. **Create Pinecone account** at [pinecone.io](https://pinecone.io)
2. **Get API key** from Pinecone dashboard
3. **Set environment variables** in Render
4. **Deploy** - Pinecone index created automatically

**No Traditional Database:**
- Uses SQLite for minimal Django app data (sessions, admin)
- All FAQ data stored in Pinecone vector database
- No PostgreSQL or external database service needed

## 🎯 Deployment Steps

1. **Create Pinecone account** and get API key
2. **Push code** to your GitHub repository
3. **Create Web Service** on Render
4. **Connect repository**
5. **Set Docker build arguments** (optional): `BUILD_MODE=cloud`
6. **Set environment variables** (including `PINECONE_API_KEY`)
7. **Deploy!** (No database service needed)

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

### Pinecone Connection Errors
- Verify `PINECONE_API_KEY` is set correctly
- Check Pinecone dashboard for API key validity
- Ensure Pinecone index name is correct
- Check Pinecone environment/region setting

### "Database is unavailable" Error (FIXED)
- **This error is now resolved** - no external database needed
- Application uses Pinecone for vector storage
- SQLite used only for minimal Django app data
- No PostgreSQL connection required

### Application Startup Issues
- Check `PINECONE_API_KEY` environment variable
- Verify all required environment variables are set
- Check Render deployment logs for specific errors

## 🚀 Local Testing

### Test Cloud Mode with Pinecone (Render-like)
```bash
# Build for cloud deployment
docker build --build-arg BUILD_MODE=cloud -t faq-app .

# Run with Pinecone (requires API key)
docker run -p 3000:3000 \
  -e PORT=3000 \
  -e DJANGO_ENV=production \
  -e SECRET_KEY=test-key \
  -e PINECONE_API_KEY=your-api-key \
  -e GEMINI_API_KEY=your-gemini-key \
  faq-app
```

### Test Production Mode
```bash
# Build for production
docker build --build-arg BUILD_MODE=production -t faq-app .

# Run production container
docker run -p 8000:8000 \
  -e DJANGO_ENV=production \
  -e SECRET_KEY=test-key \
  -e PINECONE_API_KEY=your-api-key \
  -e GEMINI_API_KEY=your-gemini-key \
  faq-app
```

### Test Simple Mode
```bash
# Build for development
docker build --build-arg BUILD_MODE=simple -t faq-app .

# Run simple container
docker run -p 8000:8000 -e DJANGO_ENV=development faq-app
```

## 📈 Performance Tips

1. **Use Pinecone** for vector database - managed and scalable
2. **Use cloud mode** for Render deployment
3. **Single Dockerfile** reduces maintenance overhead
4. **Unified requirements** eliminate conflicts
5. **No external database** reduces connection issues

## 🔒 Security Checklist

- ✅ Generate new SECRET_KEY
- ✅ Set ALLOWED_HOSTS to your domain
- ✅ Enable HTTPS redirect
- ✅ Configure CSRF trusted origins
- ✅ Use environment variables for secrets
- ✅ Secure Pinecone API key
- ✅ Unified setup reduces complexity

## 🎉 Quick Commands

### Generate Secret Key
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Get Pinecone API Key
1. Visit [pinecone.io](https://pinecone.io)
2. Create account or sign in
3. Go to API Keys section
4. Copy your API key

### Build for Different Scenarios
```bash
# For Render/Cloud with Pinecone
docker build --build-arg BUILD_MODE=cloud -t faq-app .

# For Production with Pinecone
docker build --build-arg BUILD_MODE=production -t faq-app .

# For Development
docker build --build-arg BUILD_MODE=simple -t faq-app .
```

Your Django FAQ application is now ready for seamless deployment with Pinecone vector database! 🎉

## 📚 Additional Resources

- [Pinecone Documentation](https://docs.pinecone.io/)
- See `UNIFIED_DOCKER_GUIDE.md` for detailed Docker usage
- See `REQUIREMENTS_OPTIMIZATION_SUMMARY.md` for dependency changes