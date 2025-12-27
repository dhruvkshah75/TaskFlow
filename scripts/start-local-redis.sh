#!/bin/bash
# Start Local Redis Instances for TaskFlow
# This script ensures both Redis High (6379) and Redis Low (6380) are running

set -e

echo "========================================="
echo "  Starting Redis Instances for TaskFlow"
echo "========================================="
echo ""

# Check if Redis is installed
if ! command -v redis-server &> /dev/null; then
    echo "Error: redis-server is not installed."
    echo "Please install Redis first:"
    echo "  Ubuntu/Debian: sudo apt-get install redis-server"
    echo "  macOS: brew install redis"
    exit 1
fi

echo "Redis version: $(redis-server --version)"
echo ""

# Function to check if Redis is running on a port
check_redis() {
    local port=$1
    redis-cli -p $port ping &> /dev/null
}

# Start Redis High (port 6379)
echo "Checking Redis High (port 6379)..."
if check_redis 6379; then
    echo "✓ Redis High is already running on port 6379"
else
    echo "Starting Redis High on port 6379..."
    redis-server --port 6379 --daemonize yes
    sleep 1
    if check_redis 6379; then
        echo "✓ Redis High started successfully"
    else
        echo "✗ Failed to start Redis High"
        exit 1
    fi
fi

echo ""

# Start Redis Low (port 6380)
echo "Checking Redis Low (port 6380)..."
if check_redis 6380; then
    echo "✓ Redis Low is already running on port 6380"
else
    echo "Starting Redis Low on port 6380..."
    redis-server --port 6380 --daemonize yes
    sleep 1
    if check_redis 6380; then
        echo "✓ Redis Low started successfully"
    else
        echo "✗ Failed to start Redis Low"
        exit 1
    fi
fi

echo ""
echo "========================================="
echo "  Both Redis instances are running!"
echo "========================================="
echo ""
echo "Redis High (port 6379): Used for auth, caching, rate limiting"
echo "Redis Low (port 6380):  Used for task queue"
echo ""
echo "To stop Redis instances:"
echo "  redis-cli -p 6379 shutdown"
echo "  redis-cli -p 6380 shutdown"
echo ""
