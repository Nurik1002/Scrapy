# Marketplace Analytics Platform - Multi-Database Makefile
# ========================================================
# Supports three-database architecture:
# - ecommerce_db: B2C platforms (Uzum, Yandex)
# - classifieds_db: C2C platforms (OLX)
# - procurement_db: B2B platforms (UZEX)

.PHONY: help up down restart logs db-shell api worker beat flower \
        migrate migrate-all migrate-status create-schemas dump dump-all restore \
        counts uzum-download uzex-download test clean init-db db-status

# Default target
help:
	@echo "Marketplace Analytics Platform - Multi-Database Architecture"
	@echo "============================================================="
	@echo ""
	@echo "🚀 Docker Commands:"
	@echo "  make up              - Start all services"
	@echo "  make down            - Stop all services"
	@echo "  make restart         - Restart all services"
	@echo "  make logs            - View logs (tail -f)"
	@echo "  make infra           - Start only PostgreSQL & Redis"
	@echo ""
	@echo "🗄️ Database Management:"
	@echo "  make init-db         - Initialize all databases (create + migrate + setup)"
	@echo "  make create-schemas  - Create database schemas manually"
	@echo "  make db-status       - Show status of all databases"
	@echo "  make db-shell DB=ecommerce - PostgreSQL shell for specific database"
	@echo "  make counts          - Show table row counts for all databases"
	@echo ""
	@echo "📝 Migrations (Alembic):"
	@echo "  make migrate-all     - Run migrations for all databases"
	@echo "  make migrate DB=ecommerce - Migrate specific database"
	@echo "  make migrate-status  - Show migration status for all databases"
	@echo "  make revision DB=ecommerce MSG='Add indexes' - Create new migration"
	@echo ""
	@echo "💾 Backup & Restore:"
	@echo "  make dump-all        - Backup all databases"
	@echo "  make dump DB=ecommerce - Backup specific database"
	@echo "  make restore DB=ecommerce FILE=backup.sql - Restore database"
	@echo "  make restore-all TIMESTAMP=20241208_120000 - Restore all from backup set"
	@echo ""
	@echo "🔧 Services:"
	@echo "  make api             - Start FastAPI only"
	@echo "  make worker          - Start Celery worker"
	@echo "  make beat            - Start Celery beat scheduler"
	@echo "  make flower          - Start Flower (monitoring)"
	@echo ""
	@echo "📊 Scrapers:"
	@echo "  make uzum-download N=1000    - Download N Uzum products"
	@echo "  make uzex-download N=100     - Download N UZEX lots"
	@echo "  make continuous-uzum         - Start continuous Uzum scraping"
	@echo "  make continuous-uzex         - Start continuous UZEX scraping"
	@echo ""
	@echo "🧪 Development:"
	@echo "  make test            - Run tests"
	@echo "  make clean           - Remove temp files"
	@echo "  make lint            - Run code linting"
	@echo ""
	@echo "Database Options: ecommerce, classifieds, procurement, legacy"

# =============================================================================
# Docker Commands
# =============================================================================

up:
	@echo "🚀 Starting all services..."
	docker-compose up -d
	@echo "✅ Services started"
	@docker-compose ps

down:
	@echo "🛑 Stopping all services..."
	docker-compose down
	@echo "✅ Services stopped"

restart:
	@echo "🔄 Restarting all services..."
	docker-compose restart
	@echo "✅ Services restarted"

logs:
	@echo "📋 Showing logs (Ctrl+C to exit)..."
	docker-compose logs -f --tail=100

# Start only infrastructure (PostgreSQL + Redis)
infra:
	@echo "🏗️ Starting infrastructure services..."
	docker-compose up -d postgres redis
	@sleep 3
	@echo "✅ PostgreSQL & Redis started"
	@docker-compose ps postgres redis

# =============================================================================
# Database Management
# =============================================================================

# Initialize all databases (full setup)
init-db:
	@echo "🎯 Initializing all databases..."
	python manage_db.py init-all
	@echo "✅ Database initialization complete"

# Create schemas manually (without Alembic)
create-schemas:
	@echo "🔧 Creating database schemas..."
	python create_schemas.py --all
	@echo "✅ Schema creation complete"

# Show status of all databases
db-status:
	@echo "📊 Database Status Report"
	@echo "========================"
	python manage_db.py status

# Database shell - specify DB with DB=ecommerce
DB ?= ecommerce
db-shell:
	@echo "🐘 Opening PostgreSQL shell for $(DB)..."
	@if [ "$(DB)" = "ecommerce" ]; then \
		docker exec -it app-postgres-1 psql -U scraper -d ecommerce_db; \
	elif [ "$(DB)" = "classifieds" ]; then \
		docker exec -it app-postgres-1 psql -U scraper -d classifieds_db; \
	elif [ "$(DB)" = "procurement" ]; then \
		docker exec -it app-postgres-1 psql -U scraper -d procurement_db; \
	elif [ "$(DB)" = "legacy" ]; then \
		docker exec -it app-postgres-1 psql -U scraper -d uzum_scraping; \
	else \
		echo "❌ Invalid DB: $(DB). Use: ecommerce, classifieds, procurement, legacy"; \
		exit 1; \
	fi

# Show table counts for all databases
counts:
	@echo "📊 Table Row Counts"
	@echo "==================="
	@echo ""
	@echo "🛒 Ecommerce Database:"
	@docker exec app-postgres-1 psql -U scraper -d ecommerce_db -c "\
		SELECT schemaname,tablename,n_tup_ins-n_tup_del as rowcount \
		FROM pg_stat_user_tables \
		ORDER BY rowcount DESC;" 2>/dev/null || echo "   Database not accessible"
	@echo ""
	@echo "🏪 Classifieds Database:"
	@docker exec app-postgres-1 psql -U scraper -d classifieds_db -c "\
		SELECT schemaname,tablename,n_tup_ins-n_tup_del as rowcount \
		FROM pg_stat_user_tables \
		ORDER BY rowcount DESC;" 2>/dev/null || echo "   Database not accessible"
	@echo ""
	@echo "🏛️ Procurement Database:"
	@docker exec app-postgres-1 psql -U scraper -d procurement_db -c "\
		SELECT schemaname,tablename,n_tup_ins-n_tup_del as rowcount \
		FROM pg_stat_user_tables \
		ORDER BY rowcount DESC;" 2>/dev/null || echo "   Database not accessible"

# =============================================================================
# Migrations (Alembic)
# =============================================================================

# Run migrations for all databases
migrate-all:
	@echo "📝 Running migrations for all databases..."
	@chmod +x scripts/migrate.sh
	@./scripts/migrate.sh --all

# Migrate specific database
migrate:
ifndef DB
	@echo "❌ Please specify database: make migrate DB=ecommerce"
	@echo "   Available: ecommerce, classifieds, procurement"
	@exit 1
endif
	@echo "📝 Migrating $(DB) database..."
	@chmod +x scripts/migrate.sh
	@./scripts/migrate.sh $(DB)

# Show migration status
migrate-status:
	@echo "📋 Migration Status Report"
	@echo "=========================="
	@chmod +x scripts/migrate.sh
	@./scripts/migrate.sh --status

# Create new migration (requires DB and MSG)
revision:
ifndef DB
	@echo "❌ Please specify database: make revision DB=ecommerce MSG='Description'"
	@exit 1
endif
ifndef MSG
	@echo "❌ Please specify message: make revision DB=ecommerce MSG='Add new indexes'"
	@exit 1
endif
	@echo "📝 Creating migration for $(DB): $(MSG)"
	@chmod +x scripts/migrate.sh
	@./scripts/migrate.sh create $(DB) "$(MSG)"

# =============================================================================
# Backup & Restore
# =============================================================================

# Backup all databases
dump-all:
	@echo "💾 Backing up all databases..."
	@chmod +x scripts/dump_db.sh
	@./scripts/dump_db.sh --all --compress
	@echo "✅ Backup complete"

# Backup specific database
dump:
ifndef DB
	@echo "❌ Please specify database: make dump DB=ecommerce"
	@echo "   Available: ecommerce, classifieds, procurement, legacy"
	@exit 1
endif
	@echo "💾 Backing up $(DB) database..."
	@chmod +x scripts/dump_db.sh
	@./scripts/dump_db.sh --compress $(DB)

# List available backups
list-backups:
	@echo "📋 Available Backups"
	@echo "===================="
	@chmod +x scripts/restore_db.sh
	@./scripts/restore_db.sh --list

# Restore specific database (requires DB and FILE)
restore:
ifndef DB
	@echo "❌ Please specify database: make restore DB=ecommerce FILE=backup.sql"
	@exit 1
endif
ifndef FILE
	@echo "❌ Please specify backup file: make restore DB=ecommerce FILE=backup.sql"
	@echo "   Or use: make restore DB=ecommerce FILE=latest"
	@exit 1
endif
	@echo "🔄 Restoring $(DB) from $(FILE)..."
	@chmod +x scripts/restore_db.sh
	@./scripts/restore_db.sh $(DB) $(FILE)

# Restore all databases from backup set (requires TIMESTAMP)
restore-all:
ifndef TIMESTAMP
	@echo "❌ Please specify timestamp: make restore-all TIMESTAMP=20241208_120000"
	@exit 1
endif
	@echo "🔄 Restoring all databases from backup set: $(TIMESTAMP)"
	@chmod +x scripts/restore_db.sh
	@./scripts/restore_db.sh --all $(TIMESTAMP)

# =============================================================================
# Services
# =============================================================================

api:
	@echo "🚀 Starting FastAPI server..."
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	@echo "👷 Starting Celery worker..."
	celery -A src.workers.celery_app worker --loglevel=info --concurrency=15

beat:
	@echo "⏰ Starting Celery beat scheduler..."
	celery -A src.workers.celery_app beat --loglevel=info

flower:
	@echo "🌸 Starting Flower monitoring..."
	@echo "   Access at: http://localhost:5555"
	celery -A src.workers.celery_app flower --port=5555

# =============================================================================
# Scrapers
# =============================================================================

N ?= 100

uzum-download:
	@echo "🛒 Downloading $(N) Uzum products..."
	python -m src.platforms.uzum.downloader --target $(N)

uzex-download:
	@echo "🏛️ Downloading $(N) UZEX lots..."
	python -m src.platforms.uzex.downloader --type auction --target $(N)

# Continuous scrapers
continuous-uzum:
	@echo "🔄 Starting continuous Uzum scraping..."
	@echo "   This will run forever - press Ctrl+C to stop"
	celery -A src.workers.celery_app call src.workers.continuous_scraper.continuous_scan --args='["uzum"]'

continuous-uzex:
	@echo "🔄 Starting continuous UZEX scraping..."
	@echo "   This will run forever - press Ctrl+C to stop"
	celery -A src.workers.celery_app call src.workers.continuous_scraper.continuous_scan --args='["uzex"]'

# Check scraper status
scraper-status:
	@echo "📊 Scraper Status"
	@echo "================"
	@echo ""
	@echo "🛒 Uzum Scraper:"
	@celery -A src.workers.celery_app call src.workers.continuous_scraper.check_continuous_status --args='["uzum"]' || echo "   Not running"
	@echo ""
	@echo "🏛️ UZEX Scraper:"
	@celery -A src.workers.celery_app call src.workers.continuous_scraper.check_continuous_status --args='["uzex"]' || echo "   Not running"

# =============================================================================
# Development
# =============================================================================

test:
	@echo "🧪 Running tests..."
	pytest tests/ -v --tb=short

lint:
	@echo "🔍 Running code linting..."
	@echo "Black formatting:"
	@black --check src/ || black src/
	@echo "Flake8 linting:"
	@flake8 src/ || echo "Linting issues found"

clean:
	@echo "🧹 Cleaning temporary files..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .coverage htmlcov/ 2>/dev/null || true
	@rm -rf build/ dist/ *.egg-info/ 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Create required directories
init:
	@echo "📁 Creating storage directories..."
	@mkdir -p storage/raw/uzum storage/raw/uzex storage/raw/olx backups logs
	@mkdir -p migrations/versions/ecommerce migrations/versions/classifieds migrations/versions/procurement
	@echo "✅ Storage directories created"

# =============================================================================
# Quick Start
# =============================================================================

# Full setup for new installation
setup:
	@echo "🚀 Full Platform Setup"
	@echo "======================"
	@echo ""
	@echo "1. Creating directories..."
	@make init
	@echo ""
	@echo "2. Starting infrastructure..."
	@make infra
	@echo ""
	@echo "3. Waiting for PostgreSQL..."
	@sleep 5
	@echo ""
	@echo "4. Initializing databases..."
	@make init-db
	@echo ""
	@echo "5. Showing status..."
	@make db-status
	@echo ""
	@echo "✅ Setup complete! Platform is ready to use."
	@echo ""
	@echo "Next steps:"
	@echo "  - Start all services: make up"
	@echo "  - Start scraping: make uzum-download N=1000"
	@echo "  - View API: http://localhost:8000"
	@echo "  - Monitor workers: make flower"

# Reset everything (DANGEROUS)
reset:
	@echo "⚠️  This will DELETE ALL DATA and reset the platform!"
	@echo ""
	@read -p "Are you sure? Type 'reset' to confirm: " confirm && [ "$$confirm" = "reset" ] || exit 1
	@echo ""
	@echo "🗑️ Stopping services..."
	@make down || true
	@echo "🗑️ Removing containers and volumes..."
	@docker-compose down -v --remove-orphans || true
	@echo "🗑️ Cleaning directories..."
	@rm -rf storage/raw/* backups/* logs/* || true
	@echo "🚀 Starting fresh setup..."
	@make setup
	@echo ""
	@echo "✅ Platform reset complete!"

# =============================================================================
# Monitoring & Health
# =============================================================================

# Health check for all services
health:
	@echo "🏥 Health Check Report"
	@echo "====================="
	@echo ""
	@echo "🐘 PostgreSQL:"
	@docker exec app-postgres-1 pg_isready -U scraper && echo "   ✅ Healthy" || echo "   ❌ Unhealthy"
	@echo ""
	@echo "🔴 Redis:"
	@docker exec app-redis-1 redis-cli ping | grep -q PONG && echo "   ✅ Healthy" || echo "   ❌ Unhealthy"
	@echo ""
	@echo "📊 Databases:"
	@python manage_db.py status 2>/dev/null || echo "   ❌ Cannot check database status"
	@echo ""
	@echo "👷 Workers:"
	@docker-compose ps celery_worker | grep -q Up && echo "   ✅ Celery workers running" || echo "   ❌ Celery workers not running"

# Show resource usage
stats:
	@echo "📊 Resource Usage"
	@echo "================="
	@echo ""
	@echo "🐳 Docker Containers:"
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
	@echo ""
	@echo "💾 Database Sizes:"
	@docker exec app-postgres-1 psql -U scraper -d postgres -c "\
		SELECT datname as database, pg_size_pretty(pg_database_size(datname)) as size \
		FROM pg_database \
		WHERE datname IN ('ecommerce_db', 'classifieds_db', 'procurement_db', 'uzum_scraping') \
		ORDER BY pg_database_size(datname) DESC;" 2>/dev/null || echo "   Cannot access database"

# =============================================================================
# Platform Information
# =============================================================================

info:
	@echo "ℹ️  Platform Information"
	@echo "========================"
	@echo ""
	@echo "🏗️ Architecture: Multi-Database (3 databases)"
	@echo ""
	@echo "🗄️ Databases:"
	@echo "   • ecommerce_db    - B2C E-commerce (Uzum, Yandex)"
	@echo "   • classifieds_db  - C2C Classifieds (OLX)"
	@echo "   • procurement_db  - B2B Procurement (UZEX)"
	@echo ""
	@echo "🔧 Services:"
	@echo "   • PostgreSQL 17   - Primary database"
	@echo "   • Redis Alpine    - Cache & message queue"
	@echo "   • FastAPI         - REST API server"
	@echo "   • Celery          - Distributed task queue"
	@echo "   • Flower          - Task monitoring"
	@echo ""
	@echo "📊 Current Status:"
	@docker-compose ps --format "table {{.Name}}\t{{.State}}\t{{.Ports}}"
	@echo ""
	@echo "🌐 Access Points:"
	@echo "   • API:      http://localhost:8000"
	@echo "   • Flower:   http://localhost:5555"
	@echo "   • PostgreSQL: localhost:5434"
	@echo "   • Redis:    localhost:6379"

# Show this help
.DEFAULT_GOAL := help
