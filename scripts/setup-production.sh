#!/bin/bash

# Production Setup Script for Django FAQ/RAG Application
# This script prepares the environment for production deployment

set -e

echo "🚀 Setting up production environment for Django FAQ/RAG Application"

# Create necessary directories
echo "📁 Creating data directories..."
mkdir -p data/postgres
mkdir -p data/qdrant
mkdir -p data/redis
mkdir -p logs
mkdir -p logs/nginx
mkdir -p backups
mkdir -p nginx/ssl

# Set proper permissions
echo "🔒 Setting directory permissions..."
chmod 755 data
chmod 700 data/postgres
chmod 755 data/qdrant
chmod 755 data/redis
chmod 755 logs
chmod 755 logs/nginx
chmod 755 backups

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your production values before deployment!"
else
    echo "✅ .env file already exists"
fi

# Validate Docker and Docker Compose installation
echo "🐳 Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Check if .env file has required variables
echo "🔍 Checking environment configuration..."
required_vars=("SECRET_KEY" "DB_PASSWORD" "GEMINI_API_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env || grep -q "^${var}=.*your-.*" .env; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "⚠️  The following required environment variables need to be set in .env:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    echo "Please update .env file before proceeding with deployment."
fi

# Create a simple backup script
echo "💾 Creating backup script..."
cat > scripts/backup.sh << 'EOF'
#!/bin/bash
# Simple backup script for production data

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

# Backup PostgreSQL
docker-compose exec -T db pg_dump -U $DB_USER $DB_NAME > "$BACKUP_DIR/postgres_backup.sql"

# Backup Qdrant data
docker-compose exec -T qdrant tar czf - /qdrant/storage > "$BACKUP_DIR/qdrant_backup.tar.gz"

# Backup application logs
tar czf "$BACKUP_DIR/logs_backup.tar.gz" logs/

echo "Backup completed: $BACKUP_DIR"
EOF

chmod +x scripts/backup.sh

echo "✅ Production environment setup completed!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your production values"
echo "2. Configure SSL certificates in nginx/ssl/ directory"
echo "3. Run: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
echo "4. Monitor logs: docker-compose logs -f"
echo ""
echo "For development, simply run: docker-compose up -d"