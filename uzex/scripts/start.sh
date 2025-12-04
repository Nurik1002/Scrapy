#!/bin/bash
echo "Starting Docker services..."
docker-compose up -d
echo "Services started. Use 'docker-compose logs -f' to follow logs."
