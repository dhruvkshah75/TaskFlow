#!/bin/bash
# TaskFlow One-Line Installer
# Usage: curl -sSL https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main/install.sh | bash

set -e

REPO_URL="https://github.com/dhruvkshah75/TaskFlow"
RAW_URL="https://raw.githubusercontent.com/dhruvkshah75/TaskFlow/main"

echo "=================================================="
echo "   TaskFlow - Distributed Task Queue Installer"
echo "=================================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first:"
    echo "   https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Docker Compose is not installed. Please install Docker Compose first:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

echo "Docker installed: $(docker --version)"
echo "Docker Compose installed"
echo ""

# Create installation directory
INSTALL_DIR="taskflow"
if [ -d "$INSTALL_DIR" ]; then
    echo "Directory '$INSTALL_DIR' already exists!"
    read -p "Remove and reinstall? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
    else
        echo "Installation cancelled."
        exit 1
    fi
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo "Created installation directory: $INSTALL_DIR"
echo ""

# Download required files
echo "Downloading configuration files..."

curl -sSL "$RAW_URL/docker-compose.prod.yml" -o docker-compose.prod.yml
echo "Downloaded docker-compose.prod.yml"

curl -sSL "$RAW_URL/.env.production.example" -o .env.production.example
echo "Downloaded .env.production.example"

curl -sSL "$RAW_URL/scripts/setup-production.sh" -o setup-production.sh
chmod +x setup-production.sh
echo "Downloaded setup-production.sh"

echo ""

# Run setup script
echo "=================================================="
echo "Setting up production environment..."
echo "=================================================="
echo ""

./setup-production.sh

echo ""
echo "=================================================="
echo "Downloading Docker images..."
echo "=================================================="
echo ""

docker-compose -f docker-compose.prod.yml pull 2>/dev/null || echo "Building images locally (first time may take a few minutes)..."

echo ""
echo "=================================================="
echo "Starting TaskFlow services..."
echo "=================================================="
echo ""

docker-compose -f docker-compose.prod.yml up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check if services are running
if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
    echo ""
    echo "=================================================="
    echo "TaskFlow successfully installed and running!"
    echo "=================================================="
    echo ""
    echo "Installation directory: $(pwd)"
    echo "API endpoint: http://localhost:8000"
    echo "API documentation: http://localhost:8000/docs"
    echo ""
    echo "Check status:"
    echo "   docker-compose -f docker-compose.prod.yml ps"
    echo ""
    echo "View logs:"
    echo "   docker-compose -f docker-compose.prod.yml logs -f"
    echo ""
    echo "Test the API:"
    echo "   curl http://localhost:8000/status"
    echo ""
    echo "Full documentation: QUICK_START.md"
    echo "GitHub: $REPO_URL"
    echo ""
else
    echo ""
    echo "Services started but may not be healthy yet."
    echo "Check logs with: docker-compose -f docker-compose.prod.yml logs"
fi
