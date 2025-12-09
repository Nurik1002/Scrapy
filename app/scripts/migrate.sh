#!/usr/bin/env bash
# Multi-Database Migration Script - Alembic-based
# Supports the three-database architecture:
# - ecommerce_db: B2C platforms (Uzum, Yandex)
# - classifieds_db: C2C platforms (OLX)
# - procurement_db: B2B platforms (UZEX)

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
DB_CONTAINER="${DB_CONTAINER:-app-postgres-1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database list
DATABASES="ecommerce classifieds procurement"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

show_help() {
    echo "Multi-Database Migration Script"
    echo "================================"
    echo ""
    echo "Usage: $0 [OPTIONS] [DATABASE]"
    echo ""
    echo "Options:"
    echo "  --all, -a           Migrate all databases"
    echo "  --status, -s        Show migration status"
    echo "  --help, -h          Show this help"
    echo ""
    echo "Databases:"
    echo "  ecommerce           B2C platforms (Uzum, Yandex)"
    echo "  classifieds         C2C platforms (OLX)"
    echo "  procurement         B2B platforms (UZEX)"
    echo ""
    echo "Examples:"
    echo "  $0 --all                    # Migrate all databases"
    echo "  $0 ecommerce               # Migrate ecommerce database"
    echo "  $0 --status                # Show status of all databases"
    echo ""
}

check_prerequisites() {
    # Check if we're in the app directory
    if [ ! -f "$APP_DIR/alembic.ini" ]; then
        log_error "alembic.ini not found. Please run from the app directory."
        exit 1
    fi

    # Check if manage_db.py exists
    if [ ! -f "$APP_DIR/manage_db.py" ]; then
        log_error "manage_db.py not found. Database management script is missing."
        exit 1
    fi

    # Check if databases are accessible
    if ! docker exec "$DB_CONTAINER" pg_isready -U scraper > /dev/null 2>&1; then
        log_error "Cannot connect to PostgreSQL container: $DB_CONTAINER"
        log_info "Make sure PostgreSQL is running: docker-compose up postgres -d"
        exit 1
    fi
}

show_migration_status() {
    log_info "Checking migration status for all databases..."
    echo ""

    cd "$APP_DIR"
    python manage_db.py status
}

migrate_database() {
    local db_name="$1"

    # Validate database name
    if [[ ! " ${DATABASES[@]} " =~ " ${db_name} " ]]; then
        log_error "Invalid database: $db_name"
        log_info "Valid databases: ${DATABASES[*]}"
        return 1
    fi

    log_info "Migrating database: $db_name"

    cd "$APP_DIR"

    # Run migration using manage_db.py
    if python manage_db.py upgrade "$db_name" head; then
        log_success "Migration completed for $db_name"
        return 0
    else
        log_error "Migration failed for $db_name"
        return 1
    fi
}

migrate_all_databases() {
    log_info "Starting migration for all databases..."
    echo ""

    local failed_dbs=()

    for db in ecommerce classifieds procurement; do
        echo "────────────────────────────────────────"
        log_info "Processing: $db"
        echo "────────────────────────────────────────"

        if migrate_database "$db"; then
            log_success "✓ $db migration successful"
        else
            log_error "✗ $db migration failed"
            failed_dbs+=("$db")
        fi
        echo ""
    done

    echo "════════════════════════════════════════"
    log_info "Migration Summary"
    echo "════════════════════════════════════════"

    local total_dbs=3
    local success_count=$((total_dbs - ${#failed_dbs[@]}))
    log_info "Successful: $success_count/$total_dbs"

    if [ ${#failed_dbs[@]} -eq 0 ]; then
        log_success "All databases migrated successfully!"
        return 0
    else
        log_error "Failed databases: ${failed_dbs[*]}"
        return 1
    fi
}

create_migration() {
    local db_name="$1"
    local message="$2"

    if [ -z "$message" ]; then
        log_error "Migration message is required"
        log_info "Usage: $0 create <database> <message>"
        return 1
    fi

    log_info "Creating migration for $db_name: $message"

    cd "$APP_DIR"
    if python manage_db.py revision "$db_name" "$message"; then
        log_success "Migration created for $db_name"
        log_info "Review the generated migration file before applying"
        return 0
    else
        log_error "Failed to create migration for $db_name"
        return 1
    fi
}

# Main script logic
main() {
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --status|-s)
            check_prerequisites
            show_migration_status
            exit 0
            ;;
        --all|-a)
            check_prerequisites
            migrate_all_databases
            exit $?
            ;;
        create)
            if [ -z "$2" ] || [ -z "$3" ]; then
                log_error "Database name and message required for create command"
                log_info "Usage: $0 create <database> <message>"
                exit 1
            fi
            check_prerequisites
            create_migration "$2" "$3"
            exit $?
            ;;
        ecommerce|classifieds|procurement)
            check_prerequisites
            migrate_database "$1"
            exit $?
            ;;
        "")
            # No arguments - show help and migrate all
            show_help
            echo ""
            read -p "Migrate all databases? (y/N) " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                check_prerequisites
                migrate_all_databases
                exit $?
            else
                log_info "Migration cancelled"
                exit 0
            fi
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
