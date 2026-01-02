"""
URL configuration for faqbackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from faq.views import home
from faq.health_views import (
    health_check, 
    health_detailed, 
    health_vector_store,
    health_qdrant,
    health_readiness,
    health_liveness,
    health_embeddings,
    regenerate_embeddings
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('api/', include('faq.urls')),
    path('captcha/', include('captcha.urls')),
    path('admin-dashboard/', include('faq.admin_urls')),
    
    # Health check endpoints
    path('health/', health_check, name='health_check'),
    path('health/detailed/', health_detailed, name='health_detailed'),
    path('health/vector-store/', health_vector_store, name='health_vector_store'),
    path('health/qdrant/', health_qdrant, name='health_qdrant'),
    path('health/embeddings/', health_embeddings, name='health_embeddings'),
    path('health/ready/', health_readiness, name='health_readiness'),
    path('health/live/', health_liveness, name='health_liveness'),
    
    # Embedding management endpoints
    path('admin/regenerate-embeddings/', regenerate_embeddings, name='regenerate_embeddings'),
]
