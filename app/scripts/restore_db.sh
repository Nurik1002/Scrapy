#!/bin/bash
# Restore database from backup

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Example: $0 backups/db_full_20231205_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
DB_CONTAINER="${DB_CONTAINER:-uzum-postgres-1}"
DB_NAME="${DB_NAME:-uzum_scraping}"
DB_USER="${DB_USER:-scraper}"

echo "⚠️  This will REPLACE all data in $DB_NAME!"
read -p "Continue? (y/N) " confirm
if [ "$confirm" != "y" ]; then
    echo "Cancelled."
    exit 0
fi

echo "🗄️ Restoring from: $BACKUP_FILE"

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -k "$BACKUP_FILE"
    SQL_FILE="${BACKUP_FILE%.gz}"
else
    SQL_FILE="$BACKUP_FILE"
fi

# Restore
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" "$DB_NAME" < "$SQL_FILE"

echo "✅ Restore complete!"
