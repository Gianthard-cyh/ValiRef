#!/bin/bash
# ValiRef Development Environment Setup Script
# Usage: ./scripts/dev-setup.sh

set -e

echo "=== ValiRef Development Environment Setup ==="
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "Warning: .env file not found, creating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "Created .env from .env.example"
        echo "Please edit .env and set your DEEPSEEK_API_KEY"
    else
        echo "Error: .env.example not found"
        exit 1
    fi
fi

echo "1. Starting infrastructure services (Postgres + RabbitMQ)..."
docker-compose up -d

echo ""
echo "2. Waiting for services to be healthy..."
sleep 5

# Check Postgres
until docker-compose exec -T postgres pg_isready -U valiref -d arxiv_db > /dev/null 2>&1; do
    echo "   Waiting for Postgres..."
    sleep 2
done
echo "   Postgres is ready!"

# Check RabbitMQ
until docker-compose exec -T rabbitmq rabbitmq-diagnostics -q ping > /dev/null 2>&1; do
    echo "   Waiting for RabbitMQ..."
    sleep 2
done
echo "   RabbitMQ is ready!"

echo ""
echo "=== Infrastructure Ready ==="
echo ""
echo "Next steps:"
echo ""
echo "1. Start API server:"
echo "   uv run uvicorn src.api.main:app --reload"
echo ""
echo "2. Start Worker (in another terminal):"
echo "   uv run python -m src.api.worker.consumer"
echo ""
echo "3. Access services:"
echo "   - API:        http://localhost:8000"
echo "   - RabbitMQ UI: http://localhost:15672 (guest/guest)"
echo "   - Adminer:    http://localhost:8080"
echo ""
echo "4. Stop infrastructure:"
echo "   docker-compose down"
echo ""
