#!/bin/bash

# AgentOS Deployment Script
# Usage: ./deploy.sh [environment]

set -e

ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying AgentOS to $ENVIRONMENT environment..."

# Load environment variables
if [ -f "$PROJECT_ROOT/.env.$ENVIRONMENT" ]; then
    export $(cat "$PROJECT_ROOT/.env.$ENVIRONMENT" | grep -v '^#' | xargs)
else
    echo "❌ Error: .env.$ENVIRONMENT file not found"
    exit 1
fi

# Validate required environment variables
required_vars=("SECRET_KEY" "JWT_SECRET" "DB_PASSWORD" "REDIS_PASSWORD")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ] || [ "${!var}" == "CHANGE_ME"* ]; then
        echo "❌ Error: $var is not set or uses default value"
        exit 1
    fi
done

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p "$PROJECT_ROOT/data"
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/backups"

# Backup current database (if exists)
if [ "$ENVIRONMENT" == "production" ]; then
    echo "💾 Creating database backup..."
    BACKUP_FILE="$PROJECT_ROOT/backups/db_backup_$(date +%Y%m%d_%H%M%S).sql"
    docker-compose exec -T postgres pg_dump -U agentos agentos > "$BACKUP_FILE" 2>/dev/null || echo "No existing database to backup"
fi

# Pull latest code (if using git)
if [ -d "$PROJECT_ROOT/.git" ]; then
    echo "📥 Pulling latest code..."
    cd "$PROJECT_ROOT"
    git pull origin main
fi

# Build Docker images
echo "🔨 Building Docker images..."
cd "$PROJECT_ROOT"
docker-compose build --no-cache

# Run database migrations
echo "🗄️  Running database migrations..."
docker-compose run --rm agentos alembic upgrade head || echo "No migrations to run"

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Start services
echo "▶️  Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo "🏥 Checking service health..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ AgentOS is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Health check failed after 30 attempts"
        docker-compose logs agentos
        exit 1
    fi
    echo "Attempt $i/30..."
    sleep 2
done

# Show running containers
echo "📊 Running containers:"
docker-compose ps

# Show logs
echo "📝 Recent logs:"
docker-compose logs --tail=50 agentos

echo "✅ Deployment complete!"
echo "🌐 AgentOS is running at http://localhost:8000"
echo "📊 Grafana dashboard: http://localhost:3000"
echo "📈 Prometheus: http://localhost:9090"
