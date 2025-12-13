#!/bin/bash
# Start ALL 6 UZEX Lot Type Scrapers
# This will scrape all 1.5M UZEX lots:
# - auction+completed (200K)
# - shop+completed (624K)  
# - national+completed (362K)
# - auction+active (328K)
# - shop+active (14K)
# - national+active (7K)

set -e

echo "🚀 Starting ALL 6 UZEX Scrapers..."
echo "=================================="
echo ""

# Path to celery app
CELERY_APP="src.workers.celery_app"

# Start each scraper in background
echo "Starting auction+completed scraper..."
celery -A $CELERY_APP call src.workers.uzex_continuous_scrapers.uzex_auction_completed &
sleep 2

echo "Starting shop+completed scraper (BIGGEST - 624K lots)..."
celery -A $CELERY_APP call src.workers.uzex_continuous_scrapers.uzex_shop_completed &
sleep 2

echo "Starting national+completed scraper (362K lots)..."
celery -A $CELERY_APP call src.workers.uzex_continuous_scrapers.uzex_national_completed &
sleep 2

echo "Starting auction+active scraper (328K lots)..."
celery -A $CELERY_APP call src.workers.uzex_continuous_scrapers.uzex_auction_active &
sleep 2

echo "Starting shop+active scraper (14K lots)..."
celery -A $CELERY_APP call src.workers.uzex_continuous_scrapers.uzex_shop_active &
sleep 2

echo "Starting national+active scraper (7K lots)..."
celery -A $CELERY_APP call src.workers.uzex_continuous_scrapers.uzex_national_active &

echo ""
echo "✅ All 6 UZEX scrapers started!"
echo ""
echo "Monitor progress:"
echo "  docker logs app-celery_worker-1 -f | grep '✅'"
echo ""
echo "Check database growth:"
echo "  make counts"
