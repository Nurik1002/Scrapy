#!/bin/bash
# Show row counts for all database tables

set -e

DB_CONTAINER="${DB_CONTAINER:-app_postgres_1}"
DB_NAME="${DB_NAME:-uzum_scraping}"
DB_USER="${DB_USER:-scraper}"

echo "📊 Database Table Counts for $DB_NAME"
echo "========================================"
echo ""

# SQL query to get counts for all tables
read -r -d '' SQL_QUERY << 'EOF' || true
-- UZUM E-COMMERCE TABLES
SELECT
    '📦 UZUM E-COMMERCE' as section,
    '' as table_name,
    NULL as row_count,
    '' as formatted_count
UNION ALL
SELECT
    '',
    'sellers',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM sellers
UNION ALL
SELECT
    '',
    'categories',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM categories
UNION ALL
SELECT
    '',
    'products',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM products
UNION ALL
SELECT
    '',
    'skus',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM skus
UNION ALL
SELECT
    '',
    'price_history',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM price_history
UNION ALL
SELECT
    '',
    'product_sellers',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM product_sellers
UNION ALL
SELECT
    '',
    'seller_daily_stats',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM seller_daily_stats
UNION ALL
SELECT
    '',
    'raw_snapshots',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM raw_snapshots
UNION ALL

-- UZEX GOVERNMENT PROCUREMENT TABLES
SELECT
    '',
    '',
    NULL,
    ''
UNION ALL
SELECT
    '🏛️  UZEX GOVERNMENT',
    '',
    NULL,
    ''
UNION ALL
SELECT
    '',
    'uzex_categories',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM uzex_categories
UNION ALL
SELECT
    '',
    'uzex_products',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM uzex_products
UNION ALL
SELECT
    '',
    'uzex_lots',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM uzex_lots
UNION ALL
SELECT
    '',
    'uzex_lot_items',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM uzex_lot_items
UNION ALL
SELECT
    '',
    'uzex_daily_stats',
    COUNT(*),
    TO_CHAR(COUNT(*), 'FM999,999,999')
FROM uzex_daily_stats
ORDER BY row_count NULLS FIRST, table_name;
EOF

# Execute query and format output
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -F'|' -c "$SQL_QUERY" | while IFS='|' read -r section table count formatted; do
    if [ -n "$section" ]; then
        echo ""
        echo "$section"
        echo "-------------------"
    elif [ -n "$table" ]; then
        printf "  %-25s %15s\n" "$table" "$formatted"
    fi
done

# Summary statistics
echo ""
echo "========================================"
echo "📈 SUMMARY STATISTICS"
echo "========================================"

read -r -d '' SUMMARY_SQL << 'EOF' || true
SELECT
    'Total Tables' as metric,
    '13' as value
UNION ALL
SELECT
    'Uzum Products',
    TO_CHAR((SELECT COUNT(*) FROM products), 'FM999,999,999')
UNION ALL
SELECT
    'Uzum Sellers',
    TO_CHAR((SELECT COUNT(*) FROM sellers), 'FM999,999,999')
UNION ALL
SELECT
    'Price Records',
    TO_CHAR((SELECT COUNT(*) FROM price_history), 'FM999,999,999')
UNION ALL
SELECT
    'UZEX Lots',
    TO_CHAR((SELECT COUNT(*) FROM uzex_lots), 'FM999,999,999')
UNION ALL
SELECT
    'UZEX Items',
    TO_CHAR((SELECT COUNT(*) FROM uzex_lot_items), 'FM999,999,999');
EOF

docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -A -F'|' -c "$SUMMARY_SQL" | while IFS='|' read -r metric value; do
    printf "  %-25s %15s\n" "$metric" "$value"
done

echo ""
echo "✅ Database stats retrieved successfully!"
