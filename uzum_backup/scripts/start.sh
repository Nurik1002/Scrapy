#!/bin/bash
# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting Uzum Scraper from $PROJECT_DIR..."
cd "$PROJECT_DIR"
docker-compose up -d --build
echo "Services started."
