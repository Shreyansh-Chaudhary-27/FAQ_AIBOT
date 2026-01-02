# Unified Dockerfile for Django FAQ/RAG Application
# Combines features from all deployment scenarios with build arguments
# 
# Build Examples:
#   docker build -t faq-app .                                    # Production (default)
#   docker build --build-arg BUILD_MODE=simple -t faq-app .     # Simple build  
#   docker build --build-arg BUILD_MODE=cloud -t faq-app .      # Cloud/Render

# ============================================================================
# BUILD ARGUMENTS
# ============================================================================
ARG BUILD_MODE=production
ARG PYTHON_VERSION=3.11-slim
ARG PORT=8000

# ============================================================================
# BUILDER STAGE (Multi-stage for production)
# ============================================================================
FROM python:${PYTHON_VERSION} as builder

ARG DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# MAIN STAGE
# ============================================================================
FROM python:${PYTHON_VERSION}

# Import build arguments
ARG BUILD_MODE=production
ARG PORT=8000

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=faqbackend.settings \
    PORT=${PORT} \
    BUILD_MODE=${BUILD_MODE}

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && if [ "$BUILD_MODE" = "production" ]; then \
        apt-get install -y libpq5 && \
        apt-get remove -y gcc && \
        apt-get autoremove -y; \
    fi \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for production
RUN if [ "$BUILD_MODE" = "production" ]; then \
        groupadd -r django && useradd -r -g django django; \
    fi

# Set working directory
WORKDIR /app

# Handle Python dependencies based on build mode
COPY requirements.txt .

# Production: Use virtual environment from builder
# Others: Install directly
RUN if [ "$BUILD_MODE" = "production" ]; then \
        echo "Using production build with virtual environment"; \
    else \
        pip install --no-cache-dir --upgrade pip && \
        pip install --no-cache-dir -r requirements.txt; \
    fi

# Copy virtual environment from builder stage (production only)
COPY --from=builder /opt/venv /opt/venv

# Set PATH for virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p staticfiles mediafiles logs

# Production setup: entrypoint script and permissions
RUN if [ "$BUILD_MODE" = "production" ]; then \
        cp docker-entrypoint.sh /usr/local/bin/ && \
        chmod +x /usr/local/bin/docker-entrypoint.sh && \
        chown -R django:django /app /usr/local/bin/docker-entrypoint.sh; \
    fi

# Cloud setup: collect static files
RUN if [ "$BUILD_MODE" = "cloud" ]; then \
        python manage.py collectstatic --noinput --settings=faqbackend.settings.production || true; \
    fi

# Switch to non-root user for production
RUN if [ "$BUILD_MODE" = "production" ]; then \
        echo "Will run as django user"; \
    else \
        echo "Will run as root user"; \
    fi

# Expose port
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

# Create startup script that handles user switching and commands
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Switch user for production builds\n\
if [ "$BUILD_MODE" = "production" ]; then\n\
    echo "Starting in production mode as django user..."\n\
    exec su django -c "/usr/local/bin/docker-entrypoint.sh gunicorn --config gunicorn.conf.py faqbackend.wsgi:application"\n\
elif [ "$BUILD_MODE" = "cloud" ]; then\n\
    echo "Starting in cloud mode..."\n\
    exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 30 faqbackend.wsgi:application\n\
else\n\
    echo "Starting in simple mode..."\n\
    exec gunicorn --bind 0.0.0.0:8000 --workers 2 faqbackend.wsgi:application\n\
fi' > /usr/local/bin/unified-entrypoint.sh && \
    chmod +x /usr/local/bin/unified-entrypoint.sh

# Use unified entrypoint
CMD ["/usr/local/bin/unified-entrypoint.sh"]