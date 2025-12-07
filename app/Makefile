# Marketplace Analytics Platform - Makefile
# ==========================================

.PHONY: help up down restart logs db-shell api worker beat flower \
        migrate dump restore counts uzum-download uzex-download test clean

# Default target
help:
	@echo "Marketplace Analytics Platform"
	@echo "==============================="
	@echo ""
	@echo "Docker Commands:"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs (tail)"
	@echo ""
	@echo "Database:"
	@echo "  make db-shell    - PostgreSQL shell"
	@echo "  make migrate     - Apply SQL migrations"
	@echo "  make dump        - Backup database"
	@echo "  make restore     - Restore database"
	@echo "  make counts      - Show table row counts"
	@echo ""
	@echo "Services:"
	@echo "  make api         - Start FastAPI only"
	@echo "  make worker      - Start Celery worker"
	@echo "  make beat        - Start Celery beat"
	@echo "  make flower      - Start Flower (monitoring)"
	@echo ""
	@echo "Downloaders:"
	@echo "  make uzum-download N=1000  - Download N Uzum products"
	@echo "  make uzex-download N=100   - Download N UZEX lots"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run tests"
	@echo "  make clean       - Remove temp files"

# =============================================================================
# Docker Commands
# =============================================================================

up:
	docker-compose up -d
	@echo "✅ Services started"
	@docker-compose ps

down:
	docker-compose down
	@echo "✅ Services stopped"

restart:
	docker-compose restart
	@echo "✅ Services restarted"

logs:
	docker-compose logs -f --tail=100

# Start only infrastructure
infra:
	docker-compose up -d postgres redis
	@echo "✅ PostgreSQL & Redis started"

# =============================================================================
# Database
# =============================================================================

db-shell:
	docker exec -it uzum-postgres-1 psql -U scraper -d uzum_scraping

migrate:
	@chmod +x scripts/migrate.sh
	@./scripts/migrate.sh

dump:
	@chmod +x scripts/dump_db.sh
	@./scripts/dump_db.sh

restore:
	@chmod +x scripts/restore_db.sh
	@./scripts/restore_db.sh $(FILE)

counts:
	@chmod +x scripts/table_counts.sh
	@./scripts/table_counts.sh

# =============================================================================
# Services
# =============================================================================

api:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	celery -A src.workers.celery_app worker --loglevel=info

beat:
	celery -A src.workers.celery_app beat --loglevel=info

flower:
	celery -A src.workers.celery_app flower --port=5555

# =============================================================================
# Downloaders
# =============================================================================

N ?= 100

uzum-download:
	python -m src.platforms.uzum.downloader --target $(N)

uzex-download:
	python -m src.platforms.uzex.downloader --type auction --target $(N)

uzex-categories:
	python -m src.platforms.uzex.downloader --type categories

# =============================================================================
# Development
# =============================================================================

test:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache 2>/dev/null || true
	@echo "✅ Cleaned"

# Create storage directories
init:
	mkdir -p storage/raw/uzum storage/raw/uzex backups
	@echo "✅ Storage directories created"
