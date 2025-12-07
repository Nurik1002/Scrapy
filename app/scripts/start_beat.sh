#!/bin/bash
# =============================================================================
# Startup script for Celery Beat - NON-STOP 24/7 scraping mode
# =============================================================================

echo "🚀 Starting NON-STOP scraping mode..."
echo "$(date): Initializing continuous scraping tasks"

# Wait for workers to be ready
echo "⏳ Waiting for workers to be ready..."
sleep 15

# Start continuous Uzum scraping (runs forever with auto-resume)
echo "📦 Starting Uzum continuous scraper..."
python -c "
from src.workers.continuous_scraper import continuous_scan
result = continuous_scan.delay('uzum', 20000, 300, 3000000)
print(f'✅ Uzum CONTINUOUS scraping started: {result.id}')
print('   - Target: 20,000 products per batch')
print('   - Pause between cycles: 300 seconds')
print('   - Max ID: 3,000,000')
" 2>&1 || echo "⚠️ Failed to start Uzum scraper (will retry via Beat)"

# Start continuous UZEX scraping (runs forever with auto-resume)
echo "📦 Starting UZEX continuous scraper..."
python -c "
from src.workers.continuous_scraper import continuous_scan
result = continuous_scan.delay('uzex', 5000, 600, 500000)
print(f'✅ UZEX CONTINUOUS scraping started: {result.id}')
print('   - Target: 5,000 lots per batch')
print('   - Pause between cycles: 600 seconds')
print('   - Max ID: 500,000')
" 2>&1 || echo "⚠️ Failed to start UZEX scraper (will retry via Beat)"

# Run initial health check
echo "📊 Running initial health check..."
python -c "
from src.workers.maintenance_tasks import health_check
result = health_check()
print(f'Health: {result}')
" 2>&1 || echo "⚠️ Health check skipped"

echo ""
echo "=============================================="
echo "🎯 NON-STOP SCRAPING MODE ACTIVATED"
echo "=============================================="
echo "- Continuous scrapers: RUNNING (forever)"
echo "- Health checks: Every hour"
echo "- Database VACUUM: Daily at 4 AM"
echo "- Scraper watchdog: Every 2 hours"
echo ""
echo "Starting Celery Beat scheduler..."
echo "=============================================="

# Start Celery Beat (for health checks, maintenance, and scraper watchdog)
exec celery -A src.workers.celery_app beat --loglevel=info

