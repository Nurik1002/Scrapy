#!/usr/bin/env bash
# Multi-Database Restore Script for Marketplace Analytics Platform
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
    echo "Multi-Database Restore Script"
    echo "============================="
    echo ""
    echo "Usage: $0 [OPTIONS] [DATABASE] [BACKUP_FILE]"
    echo ""
    echo "Options:"
    echo "  --all, -a           Restore all databases from backup set"
    echo "  --force, -f         Skip confirmation prompts"
    echo "  --drop-first        Drop existing database before restore"
    echo "  --schema-only       Restore schema only"
    echo "  --data-only         Restore data only"
    echo "  --list, -l          List available backup files"
    echo "  --help, -h          Show this help"
    echo ""
    echo "Databases:"
    echo "  ecommerce           ecommerce_db - $(get_db_description ecommerce)"
    echo "  classifieds         classifieds_db - $(get_db_description classifieds)"
    echo "  procurement         procurement_db - $(get_db_description procurement)"
    echo "  legacy              uzum_scraping - $(get_db_description legacy)"
    echo ""
    echo "Examples:"
    echo "  $0 ecommerce backup.sql        # Restore ecommerce from backup.sql"
    echo "  $0 --all 20241208_120000       # Restore all DBs from timestamp backup set"
    echo "  $0 --list                      # Show available backups"
    echo "  $0 --force ecommerce latest    # Restore without confirmation"
    echo ""
    echo "Backup location: $BACKUP_DIR"
}

check_prerequisites() {
    # Check if backup directory exists
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "Backup directory does not exist: $BACKUP_DIR"
        exit 1
    fi

    # Check if PostgreSQL container is running
    if ! docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" > /dev/null 2>&1; then
        log_error "Cannot connect to PostgreSQL container: $DB_CONTAINER"
        log_info "Make sure PostgreSQL is running: docker-compose up postgres -d"
        exit 1
    fi
}

list_available_backups() {
    log_info "Available backup files in: $BACKUP_DIR"
    echo ""

    if [ ! "$(ls -A "$BACKUP_DIR"/*.sql* 2>/dev/null)" ]; then
        log_warning "No backup files found"
        return
    fi

    # Group backups by timestamp
    local timestamps=($(find "$BACKUP_DIR" -name "*.sql*" -type f -exec basename {} \; | sed -E 's/^[^_]+_([0-9]{8}_[0-9]{6}).*/\1/' | sort -u))

    for timestamp in "${timestamps[@]}"; do
        echo "📅 Backup Set: $timestamp"
        for db_key in ecommerce classifieds procurement legacy; do
            local backup_files=($(find "$BACKUP_DIR" -name "${db_key}_*${timestamp}*.sql*" -type f | sort))
            if [ ${#backup_files[@]} -gt 0 ]; then
                for backup_file in "${backup_files[@]}"; do
                    local filename=$(basename "$backup_file")
                    local size=$(ls -lh "$backup_file" | awk '{print $5}')
                    local date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$backup_file" 2>/dev/null || stat -c "%y" "$backup_file" 2>/dev/null | cut -d' ' -f1,2 | cut -d':' -f1,2)
                    echo "   📄 $filename ($size) - $date"
                done
            fi
        done
        echo ""
    done

    # Show individual backup files not part of sets
    local individual_files=($(find "$BACKUP_DIR" -name "*.sql*" -type f ! -name "*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9]*" | sort))
    if [ ${#individual_files[@]} -gt 0 ]; then
        echo "📁 Individual backup files:"
        for backup_file in "${individual_files[@]}"; do
            local filename=$(basename "$backup_file")
            local size=$(ls -lh "$backup_file" | awk '{print $5}')
            local date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$backup_file" 2>/dev/null || stat -c "%y" "$backup_file" 2>/dev/null | cut -d' ' -f1,2 | cut -d':' -f1,2)
            echo "   📄 $filename ($size) - $date"
        done
    fi
}

find_backup_file() {
    local db_key="$1"
    local backup_identifier="$2"

    # If backup_identifier is a full path and exists, use it
    if [ -f "$backup_identifier" ]; then
        echo "$backup_identifier"
        return 0
    fi

    # If it's just a filename in backup directory
    if [ -f "$BACKUP_DIR/$backup_identifier" ]; then
        echo "$BACKUP_DIR/$backup_identifier"
        return 0
    fi

    # If it's a timestamp, find the corresponding backup file
    if [[ "$backup_identifier" =~ ^[0-9]{8}_[0-9]{6}$ ]]; then
        local backup_files=($(find "$BACKUP_DIR" -name "${db_key}_*${backup_identifier}*.sql*" -type f | sort -r))
        if [ ${#backup_files[@]} -gt 0 ]; then
            echo "${backup_files[0]}"  # Return most recent if multiple
            return 0
        fi
    fi

    # If it's "latest", find the most recent backup
    if [ "$backup_identifier" = "latest" ]; then
        local backup_files=($(find "$BACKUP_DIR" -name "${db_key}_*.sql*" -type f | sort -r))
        if [ ${#backup_files[@]} -gt 0 ]; then
            echo "${backup_files[0]}"
            return 0
        fi
    fi

    return 1
}

confirm_restore() {
    local db_name="$1"
    local backup_file="$2"
    local force="$3"

    if [ "$force" = true ]; then
        return 0
    fi

    echo ""
    log_warning "⚠️  DANGER: This will REPLACE all data in database: $db_name"
    log_info "Backup file: $(basename "$backup_file")"
    log_info "Database size will be lost and replaced with backup data"
    echo ""
    read -p "Are you absolutely sure you want to continue? (type 'yes' to confirm): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
}

create_database_backup() {
    local db_name="$1"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local pre_restore_backup="$BACKUP_DIR/pre_restore_${db_name}_${timestamp}.sql"

    log_info "Creating pre-restore backup of $db_name..."
    if docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$db_name" > "$pre_restore_backup" 2>/dev/null; then
        log_success "Pre-restore backup created: $(basename "$pre_restore_backup")"
        echo "$pre_restore_backup"
    else
        log_warning "Could not create pre-restore backup (database may not exist)"
        echo ""
    fi
}

restore_database() {
    local db_key="$1"
    local backup_file="$2"
    local force="$3"
    local drop_first="$4"
    local schema_only="$5"
    local data_only="$6"

    local db_name=$(get_db_name "$db_key")
    if [ -z "$db_name" ]; then
        log_error "Unknown database key: $db_key"
        return 1
    fi

    # Find backup file
    local actual_backup_file=$(find_backup_file "$db_key" "$backup_file")
    if [ -z "$actual_backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        log_info "Use --list to see available backups"
        return 1
    fi

    # Check if backup file exists and is readable
    if [ ! -f "$actual_backup_file" ] || [ ! -r "$actual_backup_file" ]; then
        log_error "Cannot read backup file: $actual_backup_file"
        return 1
    fi

    local backup_size=$(ls -lh "$actual_backup_file" | awk '{print $5}')
    log_info "Restoring database: $db_name"
    log_info "Description: $(get_db_description "$db_key")"
    log_info "Backup file: $(basename "$actual_backup_file") ($backup_size)"

    # Confirm restore
    confirm_restore "$db_name" "$actual_backup_file" "$force"

    # Create pre-restore backup
    local pre_restore_backup=$(create_database_backup "$db_name")

    # Handle compressed files
    local sql_file="$actual_backup_file"
    local temp_file=""
    if [[ "$actual_backup_file" == *.gz ]]; then
        temp_file="/tmp/restore_$(basename "${actual_backup_file%.gz}")"
        log_info "Decompressing backup file..."
        gunzip -c "$actual_backup_file" > "$temp_file"
        sql_file="$temp_file"
    fi

    # Drop database if requested
    if [ "$drop_first" = true ]; then
        log_info "Dropping existing database: $db_name"
        docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$db_name\";" || true
        docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$db_name\";"
    else
        # Ensure database exists
        if ! docker exec "$DB_CONTAINER" psql -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$db_name"; then
            log_info "Database $db_name does not exist, creating..."
            docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$db_name\";"
        fi
    fi

    # Prepare psql options
    local psql_options=""
    if [ "$schema_only" = false ] && [ "$data_only" = false ]; then
        # Full restore - no special options
        psql_options=""
    elif [ "$schema_only" = true ]; then
        log_warning "Schema-only restore: This may not work as expected with pg_restore"
    elif [ "$data_only" = true ]; then
        log_warning "Data-only restore: This may not work as expected with pg_restore"
    fi

    # Perform restore
    log_info "Restoring database content..."
    if docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$db_name" $psql_options < "$sql_file"; then
        log_success "Database $db_name restored successfully"

        # Clean up temp file
        if [ -n "$temp_file" ] && [ -f "$temp_file" ]; then
            rm "$temp_file"
        fi

        # Show restore summary
        echo ""
        log_info "Restore Summary:"
        echo "   📊 Database: $db_name"
        echo "   📄 From: $(basename "$actual_backup_file")"
        if [ -n "$pre_restore_backup" ]; then
            echo "   💾 Pre-restore backup: $(basename "$pre_restore_backup")"
        fi

        return 0
    else
        log_error "Failed to restore database $db_name"

        # Clean up temp file
        if [ -n "$temp_file" ] && [ -f "$temp_file" ]; then
            rm "$temp_file"
        fi

        # Offer to restore from pre-restore backup
        if [ -n "$pre_restore_backup" ] && [ "$force" = false ]; then
            echo ""
            read -p "Restore from pre-restore backup? (y/N) " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "Restoring from pre-restore backup..."
                docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$db_name" < "$pre_restore_backup"
                log_success "Restored from pre-restore backup"
            fi
        fi

        return 1
    fi
}

restore_all_databases() {
    local timestamp="$1"
    local force="$2"
    local drop_first="$3"
    local schema_only="$4"
    local data_only="$5"

    log_info "Restoring all databases from backup set: $timestamp"
    echo ""

    local failed_dbs=()
    local restored_count=0

    for db_key in ecommerce classifieds procurement legacy; do
        echo "────────────────────────────────────────"

        # Find backup file for this database and timestamp
        local backup_files=($(find "$BACKUP_DIR" -name "${db_key}_*${timestamp}*.sql*" -type f | sort -r))

        if [ ${#backup_files[@]} -eq 0 ]; then
            log_warning "No backup found for $db_key with timestamp $timestamp, skipping..."
            continue
        fi

        local backup_file="${backup_files[0]}"  # Use most recent if multiple

        if restore_database "$db_key" "$backup_file" "$force" "$drop_first" "$schema_only" "$data_only"; then
            log_success "✓ $db_key restore successful"
            ((restored_count++))
        else
            log_error "✗ $db_key restore failed"
            failed_dbs+=("$db_key")
        fi
        echo ""
    done

    echo "════════════════════════════════════════"
    log_info "Restore Summary"
    echo "════════════════════════════════════════"

    log_info "Successful restores: $restored_count"

    if [ ${#failed_dbs[@]} -eq 0 ]; then
        log_success "All database restores completed successfully!"
        return 0
    else
        log_error "Failed databases: ${failed_dbs[*]}"
        return 1
    fi
}

# Main script logic
main() {
    local target_db=""
    local backup_file=""
    local force=false
    local drop_first=false
    local schema_only=false
    local data_only=false
    local restore_all=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --list|-l)
                check_prerequisites
                list_available_backups
                exit 0
                ;;
            --all|-a)
                restore_all=true
                shift
                ;;
            --force|-f)
                force=true
                shift
                ;;
            --drop-first)
                drop_first=true
                shift
                ;;
            --schema-only)
                schema_only=true
                shift
                ;;
            --data-only)
                data_only=true
                shift
                ;;
            ecommerce|classifieds|procurement|legacy)
                if [ -z "$target_db" ]; then
                    target_db="$1"
                else
                    log_error "Multiple databases specified. Use --all to restore all databases."
                    exit 1
                fi
                shift
                ;;
            *)
                if [ -z "$backup_file" ]; then
                    backup_file="$1"
                else
                    log_error "Unknown option: $1"
                    show_help
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Validate conflicting options
    if [ "$schema_only" = true ] && [ "$data_only" = true ]; then
        log_error "Cannot specify both --schema-only and --data-only"
        exit 1
    fi

    check_prerequisites

    # Handle restore all
    if [ "$restore_all" = true ]; then
        if [ -z "$backup_file" ]; then
            log_error "Timestamp required for --all option"
            log_info "Example: $0 --all 20241208_120000"
            exit 1
        fi
        restore_all_databases "$backup_file" "$force" "$drop_first" "$schema_only" "$data_only"
        exit $?
    fi

    # Validate arguments for single database restore
    if [ -z "$target_db" ] || [ -z "$backup_file" ]; then
        if [ -z "$target_db" ] && [ -z "$backup_file" ]; then
            log_info "Interactive mode: Please specify database and backup file"
            echo ""
            list_available_backups
            echo ""
            read -p "Enter database (ecommerce/classifieds/procurement/legacy): " target_db
            read -p "Enter backup file/timestamp/latest: " backup_file

            if [ -z "$target_db" ] || [ -z "$backup_file" ]; then
                log_error "Database and backup file are required"
                exit 1
            fi
        else
            log_error "Both database and backup file are required"
            log_info "Usage: $0 <database> <backup_file>"
            show_help
            exit 1
        fi
    fi

    # Validate database name
    case " ecommerce classifieds procurement legacy " in
        *" $target_db "*) ;;
        *) log_error "Invalid database: $target_db"
           log_info "Valid databases: ecommerce classifieds procurement legacy"
           exit 1 ;;
    esac

    # Perform single database restore
    restore_database "$target_db" "$backup_file" "$force" "$drop_first" "$schema_only" "$data_only"
    exit $?
}

# Run main function with all arguments
main "$@"
