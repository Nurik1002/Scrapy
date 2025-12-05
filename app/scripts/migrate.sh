#!/bin/bash
# Apply all SQL migrations

set -e

DB_CONTAINER="${DB_CONTAINER:-uzum-postgres-1}"
DB_NAME="${DB_NAME:-uzum_scraping}"
DB_USER="${DB_USER:-scraper}"
SQL_DIR="./sql"

echo "📝 Applying migrations to $DB_NAME..."

for file in "$SQL_DIR"/*.sql; do
    if [ -f "$file" ]; then
        echo "   Applying: $(basename $file)"
        docker cp "$file" "$DB_CONTAINER:/tmp/migration.sql"
        docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -f /tmp/migration.sql
    fi
done

echo "✅ All migrations applied!"
