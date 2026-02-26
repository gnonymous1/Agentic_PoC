#!/bin/bash

# AgentOS Rollback Script
# Usage: ./rollback.sh [backup_file]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Available backups:"
    ls -lh "$PROJECT_ROOT/backups/"
    echo ""
    echo "Usage: ./rollback.sh <backup_file>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will rollback the database to: $BACKUP_FILE"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Rollback cancelled"
    exit 0
fi

echo "🔄 Rolling back AgentOS..."

# Stop current services
echo "🛑 Stopping services..."
cd "$PROJECT_ROOT"
docker-compose down

# Restore database
echo "💾 Restoring database..."
docker-compose up -d postgres
sleep 5
docker-compose exec -T postgres psql -U agentos -c "DROP DATABASE IF EXISTS agentos;"
docker-compose exec -T postgres psql -U agentos -c "CREATE DATABASE agentos;"
docker-compose exec -T postgres psql -U agentos agentos < "$BACKUP_FILE"

# Start all services
echo "▶️  Starting services..."
docker-compose up -d

# Wait for health
echo "⏳ Waiting for services..."
sleep 10

# Check health
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Rollback complete!"
else
    echo "❌ Health check failed after rollback"
    docker-compose logs agentos
    exit 1
fi

echo "✅ System rolled back successfully"
