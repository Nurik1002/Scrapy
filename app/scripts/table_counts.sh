#!/bin/bash
# Show row counts for all database tables
# UPDATED for current schema-based architecture (uzum_scraping with 4 schemas)

set -e

DB_CONTAINER="${DB_CONTAINER:-app-postgres-1}"
DB_NAME="${DB_NAME:-uzum_scraping}"
DB_USER="${DB_USER:-scraper}"

echo "📊 Database Table Counts for $DB_NAME"
echo "========================================"
echo ""

# SQL query to get counts for all tables
read -r -d '' SQL_QUERY <<'EOF' || true
-- UZUM E-COMMERCE TABLES (ecommerce schema)
SELECT
    '📦 UZUM E-COMMERCE (ecommerce schema)' as section,
    '' as table_name,
    NULL as row_count,
    '' as formatted_count
UNION ALL
SELECT
    '',
    'sellers',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.sellers
UNION ALL
SELECT
    '',
    'categories',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.categories
UNION ALL
SELECT
    '',
    'products',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.products
UNION ALL
SELECT
    '',
    'skus',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.skus
UNION ALL
SELECT
    '',
    'price_history',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.price_history
UNION ALL
SELECT
    '',
    'product_sellers',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.product_sellers
UNION ALL
SELECT
    '',
    'seller_daily_stats',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.seller_daily_stats
UNION ALL
SELECT
    '',
    'raw_snapshots',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM ecommerce.raw_snapshots
UNION ALL

-- UZEX GOVERNMENT PROCUREMENT TABLES (procurement schema)
SELECT
    '',
    '',
    NULL,
    ''
UNION ALL
SELECT
    '🏛️  UZEX GOVERNMENT (procurement schema)',
    '',
    NULL,
    ''
UNION ALL
SELECT
    '',
    'uzex_categories',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM procurement.uzex_categories
UNION ALL
SELECT
    '',
    'uzex_products',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM procurement.uzex_products
UNION ALL
SELECT
    '',
    'uzex_lots',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM procurement.uzex_lots
UNION ALL
SELECT
    '',
    'uzex_lot_items',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM procurement.uzex_lot_items
UNION ALL
SELECT
    '',
    'uzex_daily_stats',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM procurement.uzex_daily_stats
UNION ALL

-- OLX CLASSIFIEDS TABLES (classifieds schema)
SELECT
    '',
    '',
    NULL,
    ''
UNION ALL
SELECT
    '🏪 OLX CLASSIFIEDS (classifieds schema)',
    '',
    NULL,
    ''
UNION ALL
SELECT
    '',
    'olx_sellers',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM classifieds.olx_sellers
UNION ALL
SELECT
    '',
    'olx_products',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM classifieds.olx_products
ORDER BY row_count NULLS FIRST, table_name;
EOF

# Execute query and format output
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -F'|' -c "$SQL_QUERY" | while IFS='|' read -r section table count formatted; do
    if [ -n "$section" ]; then
        echo ""
        echo "$section"
        echo "-----------------------------------"
    elif [ -n "$table" ]; then
        printf "  %-25s %15s\n" "$table" "$formatted"
    fi
done

# Summary statistics
echo ""
echo "========================================"
echo "📈 SUMMARY STATISTICS"
echo "========================================"

read -r -d '' SUMMARY_SQL <<'EOF' || true
SELECT
    'Database' as metric,
    'uzum_scraping' as value
UNION ALL
SELECT
    'Total Tables',
    '15'
UNION ALL
SELECT
    'Uzum Products',
    TO_CHAR((SELECT COUNT(*) FROM ecommerce.products), 'FM999,999,999')
UNION ALL
SELECT
    'Uzum Sellers',
    TO_CHAR((SELECT COUNT(*) FROM ecommerce.sellers), 'FM999,999,999')
UNION ALL
SELECT
    'Price Records',
    TO_CHAR((SELECT COUNT(*) FROM ecommerce.price_history), 'FM999,999,999')
UNION ALL
SELECT
    'UZEX Lots',
    TO_CHAR((SELECT COUNT(*) FROM procurement.uzex_lots), 'FM999,999,999')
UNION ALL
SELECT
    'UZEX Items',
    TO_CHAR((SELECT COUNT(*) FROM procurement.uzex_lot_items), 'FM999,999,999')
UNION ALL
SELECT
    'OLX Products',
    TO_CHAR((SELECT COUNT(*) FROM classifieds.olx_products), 'FM999,999,999')
UNION ALL
SELECT
    'DB Size',
    pg_size_pretty(pg_database_size('uzum_scraping'));
EOF

docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -F'|' -c "$SUMMARY_SQL" | while IFS='|' read -r metric value; do
    printf "  %-25s %15s\n" "$metric" "$value"
done

echo ""
echo "✅ Database stats retrieved successfully!"
