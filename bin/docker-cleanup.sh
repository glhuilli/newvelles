#!/bin/bash

# Docker Cleanup Script for Newvelles
# Helps manage and clean up timestamped Docker images and containers

set -e

IMAGE_NAME="docker-lambda-newvelles"

echo "🧹 Docker Cleanup for Newvelles"
echo "================================"

# Function to list all newvelles images
list_images() {
    echo "📦 Current Newvelles Docker Images:"
    docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" 2>/dev/null || echo "No images found"
}

# Function to list all newvelles containers
list_containers() {
    echo "🏃 Current Newvelles Containers:"
    docker ps -a --filter "name=newvelles-lambda" --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}" 2>/dev/null || echo "No containers found"
}

# Function to clean up old images (keep latest 3)
cleanup_images() {
    echo "🗑️  Cleaning up old images (keeping latest 3)..."
    
    # Get image IDs sorted by creation time (oldest first), excluding 'latest' tag
    OLD_IMAGES=$(docker images "${IMAGE_NAME}" --format "{{.ID}} {{.Tag}}" | grep -v latest | head -n -3 | awk '{print $1}')
    
    if [ -z "$OLD_IMAGES" ]; then
        echo "✅ No old images to clean up"
    else
        echo "🗑️  Removing old images:"
        echo "$OLD_IMAGES" | while read -r image_id; do
            if [ ! -z "$image_id" ]; then
                docker rmi "$image_id" 2>/dev/null || echo "⚠️  Could not remove image $image_id (may be in use)"
            fi
        done
    fi
}

# Function to clean up stopped containers
cleanup_containers() {
    echo "🗑️  Cleaning up stopped containers..."
    
    STOPPED_CONTAINERS=$(docker ps -a --filter "name=newvelles-lambda" --filter "status=exited" -q)
    
    if [ -z "$STOPPED_CONTAINERS" ]; then
        echo "✅ No stopped containers to clean up"
    else
        echo "🗑️  Removing stopped containers:"
        echo "$STOPPED_CONTAINERS" | xargs docker rm
    fi
}

# Function to stop all running containers
stop_containers() {
    echo "🛑 Stopping all running newvelles containers..."
    
    RUNNING_CONTAINERS=$(docker ps --filter "name=newvelles-lambda" -q)
    
    if [ -z "$RUNNING_CONTAINERS" ]; then
        echo "✅ No running containers to stop"
    else
        echo "🛑 Stopping containers:"
        echo "$RUNNING_CONTAINERS" | xargs docker stop
    fi
}

# Parse command line arguments
case "${1:-help}" in
    "list"|"ls")
        list_images
        echo ""
        list_containers
        ;;
    "images")
        cleanup_images
        ;;
    "containers")
        cleanup_containers
        ;;
    "stop")
        stop_containers
        ;;
    "all")
        stop_containers
        cleanup_containers
        cleanup_images
        echo ""
        echo "✅ Cleanup complete!"
        ;;
    "help"|*)
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  list        - List all newvelles images and containers"
        echo "  images      - Clean up old images (keep latest 3)"
        echo "  containers  - Remove stopped containers"
        echo "  stop        - Stop all running containers"
        echo "  all         - Stop containers + clean up everything"
        echo "  help        - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 list     # See what's currently running"
        echo "  $0 all      # Full cleanup"
        echo "  $0 stop     # Stop running containers"
        ;;
esac
