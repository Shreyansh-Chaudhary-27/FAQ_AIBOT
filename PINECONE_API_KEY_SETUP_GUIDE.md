# 🔑 Pinecone API Key Setup Guide for Render

## Step 1: Get Your Pinecone API Key

### 1.1 Create Pinecone Account
1. Go to **[pinecone.io](https://pinecone.io)**
2. Click **"Sign Up"** (or "Sign In" if you have an account)
3. Complete the registration process

### 1.2 Get API Key from Pinecone Dashboard
1. After logging in, you'll see the Pinecone dashboard
2. Look for **"API Keys"** in the left sidebar or main dashboard
3. Click **"Create API Key"** or copy your existing key
4. **Copy the API key** - it looks like: `pc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

⚠️ **Important**: Keep this API key secure - don't share it publicly!

---

## Step 2: Add API Key to Render

### 2.1 Access Your Render Service
1. Go to **[render.com](https://render.com)**
2. Sign in to your account
3. Find your **Web Service** (your Django app)
4. Click on your service name to open it

### 2.2 Navigate to Environment Variables
1. In your service dashboard, look for the **"Environment"** tab
2. Click on **"Environment"** in the left sidebar
3. You'll see a section called **"Environment Variables"**

### 2.3 Add Pinecone Environment Variables
Click **"Add Environment Variable"** and add these **one by one**:

#### Required Variables:
```
Key: PINECONE_API_KEY
Value: pc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
(paste your actual API key here)

Key: DJANGO_ENV
Value: production

Key: SECRET_KEY
Value: your-generated-secret-key-here

Key: GEMINI_API_KEY
Value: AIzaSyBnpxlk6PvtQO09MbIHhe-Lxp9t-GosdB0

Key: ALLOWED_HOSTS
Value: your-app-name.onrender.com

Key: SECURE_SSL_REDIRECT
Value: True

Key: CSRF_TRUSTED_ORIGINS
Value: https://your-app-name.onrender.com

Key: BUILD_MODE
Value: cloud
```

#### Optional Pinecone Configuration:
```
Key: PINECONE_INDEX_NAME
Value: faq-embeddings

Key: PINECONE_ENVIRONMENT
Value: us-east-1-aws

Key: PINECONE_METRIC
Value: cosine
```

### 2.4 Save and Deploy
1. After adding all environment variables, click **"Save Changes"**
2. Render will automatically **redeploy** your service
3. Wait for deployment to complete

---

## Step 3: Visual Guide - Render Dashboard

### What You'll See in Render:

```
┌─────────────────────────────────────────────────────────┐
│ 🏠 Dashboard > Your Service Name                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ┌─ Sidebar ─┐  ┌─ Main Content ─────────────────────┐   │
│ │ Overview   │  │                                   │   │
│ │ Events     │  │ Environment Variables             │   │
│ │ Logs       │  │                                   │   │
│ │ Settings   │  │ ┌─────────────────────────────┐   │   │
│ │ Environment│◄─┤ │ Key: PINECONE_API_KEY       │   │   │
│ │ Metrics    │  │ │ Value: pc-xxxxx-xxxx-xxx... │   │   │
│ │            │  │ └─────────────────────────────┘   │   │
│ │            │  │                                   │   │
│ │            │  │ ┌─────────────────────────────┐   │   │
│ │            │  │ │ Key: DJANGO_ENV             │   │   │
│ │            │  │ │ Value: production           │   │   │
│ │            │  │ └─────────────────────────────┘   │   │
│ │            │  │                                   │   │
│ │            │  │ [+ Add Environment Variable]     │   │
│ └────────────┘  └───────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Step 4: Verify Deployment

### 4.1 Check Deployment Logs
1. Go to **"Logs"** tab in your Render service
2. Look for these success messages:
```
✅ Using Pinecone vector database - no database connection wait needed
✅ Pinecone vector database initialized successfully
✅ Initialization complete, starting application...
```

### 4.2 No More Database Errors
You should **NOT** see these errors anymore:
```
❌ Database is unavailable - sleeping for 2 seconds
❌ Database connection failed: connection to server at "localhost"
```

---

## Step 5: Complete Environment Variables List

Here's the **complete list** of environment variables you need in Render:

### ✅ Copy-Paste Ready Format:

```
DJANGO_ENV=production
SECRET_KEY=django-insecure-your-secret-key-generate-a-new-one
GEMINI_API_KEY=AIzaSyBnpxlk6PvtQO09MbIHhe-Lxp9t-GosdB0
PINECONE_API_KEY=pc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PINECONE_INDEX_NAME=faq-embeddings
PINECONE_ENVIRONMENT=us-east-1-aws
ALLOWED_HOSTS=your-app-name.onrender.com
SECURE_SSL_REDIRECT=True
CSRF_TRUSTED_ORIGINS=https://your-app-name.onrender.com
BUILD_MODE=cloud
```

### 🔄 Replace These Values:
- `your-secret-key-generate-a-new-one` → Generate new Django secret key
- `pc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` → Your actual Pinecone API key
- `your-app-name.onrender.com` → Your actual Render app URL

---

## Step 6: Generate Django Secret Key

### Option 1: Python Command
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Option 2: Online Generator
Visit: **[djecrety.ir](https://djecrety.ir/)** to generate a secure Django secret key

---

## 🚨 Troubleshooting

### If Deployment Still Fails:

1. **Check API Key Format**
   - Pinecone API keys start with `pc-`
   - Should be about 50+ characters long
   - No spaces or extra characters

2. **Verify All Required Variables**
   - `PINECONE_API_KEY` ✅
   - `SECRET_KEY` ✅
   - `DJANGO_ENV=production` ✅
   - `GEMINI_API_KEY` ✅

3. **Check Render Logs**
   - Go to "Logs" tab
   - Look for specific error messages
   - Should see "Pinecone vector database initialized successfully"

4. **Pinecone Account Issues**
   - Verify your Pinecone account is active
   - Check if you're within free tier limits
   - Ensure API key hasn't expired

---

## 🎉 Success Indicators

### ✅ You'll Know It's Working When:
1. **No database connection errors** in logs
2. **Deployment completes successfully**
3. **Application starts without waiting for database**
4. **Logs show**: "Pinecone vector database initialized successfully"
5. **Your app loads** at your-app-name.onrender.com

### 🚀 Next Steps After Success:
1. Test your FAQ application
2. Upload FAQ documents
3. Try asking questions
4. Monitor Pinecone usage in their dashboard

---

## 📞 Need Help?

If you're still having issues:
1. **Check the logs** in Render dashboard
2. **Verify API key** is correct in Pinecone dashboard
3. **Double-check environment variables** are saved
4. **Try redeploying** after making changes

The key is making sure your `PINECONE_API_KEY` is correctly set in the Render environment variables section!