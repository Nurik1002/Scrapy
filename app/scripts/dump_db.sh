#!/bin/bash
# Database dump script for Marketplace Analytics Platform

set -e

# Configuration
DB_CONTAINER="${DB_CONTAINER:-uzum-postgres-1}"
DB_NAME="${DB_NAME:-uzum_scraping}"
DB_USER="${DB_USER:-scraper}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "🗄️ Dumping database: $DB_NAME"
echo "   Container: $DB_CONTAINER"
echo "   Timestamp: $TIMESTAMP"

# Full database dump
DUMP_FILE="$BACKUP_DIR/db_full_$TIMESTAMP.sql"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" > "$DUMP_FILE"
echo "✅ Full dump: $DUMP_FILE"

# Compress
gzip "$DUMP_FILE"
echo "📦 Compressed: ${DUMP_FILE}.gz"

# Show size
ls -lh "${DUMP_FILE}.gz"

echo "✅ Backup complete!"
