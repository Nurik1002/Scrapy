#!/usr/bin/env bash
# Multi-Database Backup Script for Marketplace Analytics Platform
# Supports the three-database architecture:
# - ecommerce_db: B2C platforms (Uzum, Yandex)
# - classifieds_db: C2C platforms (OLX)
# - procurement_db: B2B platforms (UZEX)

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
DB_CONTAINER="${DB_CONTAINER:-app-postgres-1}"
DB_USER="${DB_USER:-scraper}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Database configurations (using functions for compatibility)
get_db_name() {
    case "$1" in
        "ecommerce") echo "ecommerce_db" ;;
        "classifieds") echo "classifieds_db" ;;
        "procurement") echo "procurement_db" ;;
        "legacy") echo "uzum_scraping" ;;
        *) echo "" ;;
    esac
}

get_db_description() {
    case "$1" in
        "ecommerce") echo "B2C E-commerce platforms (Uzum, Yandex)" ;;
        "classifieds") echo "C2C Classifieds platforms (OLX)" ;;
        "procurement") echo "B2B Procurement platforms (UZEX)" ;;
        "legacy") echo "Legacy single database" ;;
        *) echo "" ;;
    esac
}

# Available databases
DATABASES="ecommerce classifieds procurement"
ALL_DATABASES="ecommerce classifieds procurement legacy"

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
    echo "Multi-Database Backup Script"
    echo "============================"
    echo ""
    echo "Usage: $0 [OPTIONS] [DATABASE]"
    echo ""
    echo "Options:"
    echo "  --all, -a           Backup all databases"
    echo "  --schema-only, -s   Backup schema only (no data)"
    echo "  --data-only, -d     Backup data only (no schema)"
    echo "  --compress, -c      Compress backups with gzip"
    echo "  --help, -h          Show this help"
    echo ""
    echo "Databases:"
    echo "  ecommerce           ecommerce_db - $(get_db_description ecommerce)"
    echo "  classifieds         classifieds_db - $(get_db_description classifieds)"
    echo "  procurement         procurement_db - $(get_db_description procurement)"
    echo "  legacy              uzum_scraping - $(get_db_description legacy)"
    echo ""
    echo "Examples:"
    echo "  $0 --all                    # Backup all databases"
    echo "  $0 --all --compress        # Backup all databases with compression"
    echo "  $0 ecommerce              # Backup ecommerce database only"
    echo "  $0 --schema-only ecommerce # Backup ecommerce schema only"
    echo ""
    echo "Backup location: $BACKUP_DIR"
}

check_prerequisites() {
    # Check if backup directory exists, create if not
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        log_info "Created backup directory: $BACKUP_DIR"
    fi

    # Check if PostgreSQL container is running
    if ! docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" > /dev/null 2>&1; then
        log_error "Cannot connect to PostgreSQL container: $DB_CONTAINER"
        log_info "Make sure PostgreSQL is running: docker-compose up postgres -d"
        exit 1
    fi

    # Check available space (warn if less than 1GB)
    available_space=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 1048576 ]; then # 1GB in KB
        log_warning "Less than 1GB available space in backup directory"
    fi
}

get_database_size() {
    local db_name="$1"
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$db_name" -t -c "SELECT pg_size_pretty(pg_database_size('$db_name'));" 2>/dev/null | xargs || echo "Unknown"
}

backup_database() {
    local db_key="$1"
    local schema_only="$2"
    local data_only="$3"
    local compress="$4"

    local db_name=$(get_db_name "$db_key")
    if [ -z "$db_name" ]; then
        log_error "Unknown database key: $db_key"
        return 1
    fi

    # Check if database exists
    if ! docker exec "$DB_CONTAINER" psql -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$db_name"; then
        log_warning "Database $db_name does not exist, skipping..."
        return 0
    fi

    local db_size=$(get_database_size "$db_name")
    log_info "Backing up: $db_name ($db_size)"
    log_info "Description: $(get_db_description "$db_key")"

    # Determine backup type and filename
    local backup_type="full"
    local type_suffix=""
    local pg_dump_args=""

    if [ "$schema_only" = true ]; then
        backup_type="schema"
        type_suffix="_schema"
        pg_dump_args="--schema-only"
    elif [ "$data_only" = true ]; then
        backup_type="data"
        type_suffix="_data"
        pg_dump_args="--data-only"
    fi

    local backup_filename="${db_key}${type_suffix}_${TIMESTAMP}.sql"
    local backup_path="$BACKUP_DIR/$backup_filename"

    # Create backup
    log_info "Creating $backup_type backup..."
    if docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" $pg_dump_args "$db_name" > "$backup_path"; then
        local file_size=$(ls -lh "$backup_path" | awk '{print $5}')
        log_success "Backup created: $backup_filename ($file_size)"

        # Compress if requested
        if [ "$compress" = true ]; then
            log_info "Compressing backup..."
            gzip "$backup_path"
            local compressed_size=$(ls -lh "${backup_path}.gz" | awk '{print $5}')
            log_success "Compressed: ${backup_filename}.gz ($compressed_size)"
            backup_filename="${backup_filename}.gz"
        fi

        # Store backup info
        echo "$backup_filename" >> "$BACKUP_DIR/backup_list_$TIMESTAMP.txt"
        return 0
    else
        log_error "Failed to backup $db_name"
        return 1
    fi
}

backup_all_databases() {
    local schema_only="$1"
    local data_only="$2"
    local compress="$3"

    log_info "Starting backup of all databases..."
    log_info "Timestamp: $TIMESTAMP"
    echo ""

    local failed_dbs=()
    local total_size=0

    # Include legacy database in full backup
    local all_dbs=("${DATABASES[@]}" "legacy")

    for db_key in "${all_dbs[@]}"; do
        echo "────────────────────────────────────────"
        if backup_database "$db_key" "$schema_only" "$data_only" "$compress"; then
            log_success "✓ $db_key backup successful"
        else
            log_error "✗ $db_key backup failed"
            failed_dbs+=("$db_key")
        fi
        echo ""
    done

    echo "════════════════════════════════════════"
    log_info "Backup Summary"
    echo "════════════════════════════════════════"

    # Show backup files created
    if [ -f "$BACKUP_DIR/backup_list_$TIMESTAMP.txt" ]; then
        log_info "Backup files created:"
        while IFS= read -r filename; do
            local filepath="$BACKUP_DIR/$filename"
            if [ -f "$filepath" ]; then
                local size=$(ls -lh "$filepath" | awk '{print $5}')
                echo "   📄 $filename ($size)"
            fi
        done < "$BACKUP_DIR/backup_list_$TIMESTAMP.txt"
        rm "$BACKUP_DIR/backup_list_$TIMESTAMP.txt"
    fi

    echo ""
    local success_count=$(( ${#all_dbs[@]} - ${#failed_dbs[@]} ))
    log_info "Successful backups: $success_count/${#all_dbs[@]}"

    if [ ${#failed_dbs[@]} -eq 0 ]; then
        log_success "All database backups completed successfully!"

        # Show total backup directory size
        local total_backup_size=$(du -sh "$BACKUP_DIR" | cut -f1)
        log_info "Total backup directory size: $total_backup_size"

        return 0
    else
        log_error "Failed databases: ${failed_dbs[*]}"
        return 1
    fi
}

# Clean old backups (keep last N backups)
clean_old_backups() {
    local keep_count="${1:-10}"

    log_info "Cleaning old backups (keeping last $keep_count)..."

    for db_key in ecommerce classifieds procurement legacy; do
        # Find backup files for this database
        find "$BACKUP_DIR" -name "${db_key}_*.sql*" -type f | sort -r | tail -n +$((keep_count + 1)) | while read file; do
            rm "$file"
            log_info "Removed old backup: $(basename "$file")"
        done
    done
}

show_backup_stats() {
    if [ ! -d "$BACKUP_DIR" ]; then
        log_warning "Backup directory does not exist: $BACKUP_DIR"
        return
    fi

    log_info "Backup Statistics"
    echo "=================="

    local total_backups=$(find "$BACKUP_DIR" -name "*.sql*" -type f | wc -l)
    local total_size=$(du -sh "$BACKUP_DIR" | cut -f1)

    echo "   📊 Total backups: $total_backups"
    echo "   💾 Total size: $total_size"
    echo "   📁 Location: $BACKUP_DIR"
    echo ""

    log_info "Recent backups by database:"
    for db_key in ecommerce classifieds procurement legacy; do
        local recent_backup=$(find "$BACKUP_DIR" -name "${db_key}_*.sql*" -type f | sort -r | head -n 1)
        if [ -n "$recent_backup" ]; then
            local backup_date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$recent_backup" 2>/dev/null || stat -c "%y" "$recent_backup" 2>/dev/null | cut -d' ' -f1,2 | cut -d':' -f1,2)
            local backup_size=$(ls -lh "$recent_backup" | awk '{print $5}')
            echo "   📄 $db_key: $(basename "$recent_backup") ($backup_size) - $backup_date"
        else
            echo "   📄 $db_key: No backups found"
        fi
    done
}

# Main script logic
main() {
    local schema_only=false
    local data_only=false
    local compress=false
    local target_db=""
    local show_stats=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --all|-a)
                target_db="all"
                shift
                ;;
            --schema-only|-s)
                schema_only=true
                shift
                ;;
            --data-only|-d)
                data_only=true
                shift
                ;;
            --compress|-c)
                compress=true
                shift
                ;;
            --stats)
                show_stats=true
                shift
                ;;
            --clean)
                check_prerequisites
                clean_old_backups "${2:-10}"
                exit 0
                ;;
            ecommerce|classifieds|procurement|legacy)
                if [ -z "$target_db" ]; then
                    target_db="$1"
                else
                    log_error "Multiple databases specified. Use --all to backup all databases."
                    exit 1
                fi
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Show stats if requested
    if [ "$show_stats" = true ]; then
        show_backup_stats
        exit 0
    fi

    # Validate conflicting options
    if [ "$schema_only" = true ] && [ "$data_only" = true ]; then
        log_error "Cannot specify both --schema-only and --data-only"
        exit 1
    fi

    check_prerequisites

    # Default to all databases if none specified
    if [ -z "$target_db" ]; then
        echo "No database specified. Available options:"
        echo ""
        for db_key in ecommerce classifieds procurement legacy; do
            echo "  $db_key - $(get_db_description "$db_key")"
        done
        echo ""
        read -p "Backup all databases? (y/N) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            target_db="all"
        else
            log_info "Backup cancelled"
            exit 0
        fi
    fi

    # Execute backup
    if [ "$target_db" = "all" ]; then
        backup_all_databases "$schema_only" "$data_only" "$compress"
        exit_code=$?
    else
        backup_database "$target_db" "$schema_only" "$data_only" "$compress"
        exit_code=$?

        if [ $exit_code -eq 0 ]; then
            log_info "Backup location: $BACKUP_DIR"
        fi
    fi

    # Clean old backups after successful backup
    if [ $exit_code -eq 0 ] && [ "$target_db" = "all" ]; then
        echo ""
        clean_old_backups 10
    fi

    exit $exit_code
}

# Run main function with all arguments
main "$@"
