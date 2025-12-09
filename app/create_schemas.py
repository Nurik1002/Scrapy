#!/usr/bin/env python3
"""
Manual Database Schema Creation Script

This script creates the database schemas for the three-database architecture
without relying on Alembic. Useful for initial setup or when migrations fail.

Usage:
    python create_schemas.py --all              # Create all schemas
    python create_schemas.py --db ecommerce     # Create specific database
    python create_schemas.py --drop-first       # Drop and recreate
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import asyncpg
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.config import settings
from src.schemas import (
    DATABASE_BASES,
    ClassifiedsBase,
    EcommerceBase,
    ProcurementBase,
    get_post_create_functions,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Database configurations
DATABASES = {
    "ecommerce": {
        "name": "ecommerce_db",
        "config": settings.databases.ecommerce,
        "base": EcommerceBase,
        "description": "B2C E-commerce platforms (Uzum, Yandex)",
    },
    "classifieds": {
        "name": "classifieds_db",
        "config": settings.databases.classifieds,
        "base": ClassifiedsBase,
        "description": "C2C Classifieds platforms (OLX)",
    },
    "procurement": {
        "name": "procurement_db",
        "config": settings.databases.procurement,
        "base": ProcurementBase,
        "description": "B2B Procurement platforms (UZEX)",
    },
}


class SchemaCreator:
    """Creates database schemas manually."""

    def __init__(self, drop_first: bool = False):
        self.drop_first = drop_first

    async def create_database_if_not_exists(self, db_key: str) -> bool:
        """Create database if it doesn't exist."""
        db_info = DATABASES[db_key]
        config = db_info["config"]
        db_name = db_info["name"]

        logger.info(f"🗄️  Checking database: {db_name}")

        try:
            # Connect to postgres database to create new database
            conn = psycopg2.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database="postgres",
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            exists = cursor.fetchone() is not None

            if exists and self.drop_first:
                logger.warning(f"🗑️  Dropping existing database: {db_name}")
                # Terminate connections first
                cursor.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = %s AND pid <> pg_backend_pid()
                    """,
                    (db_name,),
                )
                cursor.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
                exists = False

            if not exists:
                cursor.execute(f'CREATE DATABASE "{db_name}"')
                logger.info(f"✅ Created database: {db_name}")
            else:
                logger.info(f"✅ Database already exists: {db_name}")

            cursor.close()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create database {db_name}: {e}")
            return False

    async def create_schema(self, db_key: str) -> bool:
        """Create schema for a specific database."""
        db_info = DATABASES[db_key]
        config = db_info["config"]
        base = db_info["base"]
        description = db_info["description"]

        logger.info(f"🔧 Creating schema for {db_key} - {description}")

        try:
            # Create database connection
            conn = await asyncpg.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.name,
            )

            # Get all table creation SQL
            from sqlalchemy import create_engine
            from sqlalchemy.dialects import postgresql
            from sqlalchemy.schema import CreateTable

            # Create a temporary sync engine just for SQL generation
            temp_engine = create_engine(config.url)

            # Generate CREATE TABLE statements
            tables_created = 0
            for table_name, table in base.metadata.tables.items():
                try:
                    create_sql = str(
                        CreateTable(table).compile(dialect=postgresql.dialect())
                    )
                    await conn.execute(create_sql)
                    logger.info(f"   ✅ Created table: {table_name}")
                    tables_created += 1
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info(f"   ⚪ Table already exists: {table_name}")
                    else:
                        logger.error(f"   ❌ Failed to create table {table_name}: {e}")

            # Create indexes
            indexes_created = 0
            for table_name, table in base.metadata.tables.items():
                for index in table.indexes:
                    try:
                        create_index_sql = str(
                            index.create().compile(dialect=postgresql.dialect())
                        )
                        await conn.execute(create_index_sql)
                        logger.info(f"   ✅ Created index: {index.name}")
                        indexes_created += 1
                    except Exception as e:
                        if "already exists" in str(e):
                            logger.debug(f"   ⚪ Index already exists: {index.name}")
                        else:
                            logger.warning(
                                f"   ⚠️  Failed to create index {index.name}: {e}"
                            )

            # Run post-creation functions
            post_functions = get_post_create_functions(db_key)
            functions_executed = 0

            for func in post_functions:
                try:
                    if callable(func):
                        sql = func()
                        if sql and sql.strip():
                            # Split multiple statements
                            statements = [
                                s.strip() for s in sql.split(";") if s.strip()
                            ]
                            for statement in statements:
                                await conn.execute(statement)
                            logger.info(f"   ✅ Executed function: {func.__name__}")
                            functions_executed += 1
                        else:
                            logger.debug(
                                f"   ⚪ Function returned no SQL: {func.__name__}"
                            )
                    else:
                        logger.warning(f"   ⚠️  Not callable: {func}")
                except Exception as e:
                    logger.error(f"   ❌ Failed to execute {func.__name__}: {e}")

            await conn.close()

            logger.info(
                f"✅ Schema creation completed for {db_key}:\n"
                f"   📊 Tables: {tables_created}\n"
                f"   📇 Indexes: {indexes_created}\n"
                f"   ⚙️  Functions: {functions_executed}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create schema for {db_key}: {e}")
            return False

    async def create_all_schemas(self) -> bool:
        """Create schemas for all databases."""
        logger.info("🚀 Creating all database schemas...")
        success = True

        for db_key in DATABASES:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing: {db_key.upper()}")
            logger.info(f"{'=' * 60}")

            # Create database
            if not await self.create_database_if_not_exists(db_key):
                success = False
                continue

            # Create schema
            if not await self.create_schema(db_key):
                success = False
                continue

        return success

    async def verify_schemas(self) -> bool:
        """Verify all schemas are created correctly."""
        logger.info("\n🔍 Verifying schemas...")

        all_good = True
        for db_key, db_info in DATABASES.items():
            config = db_info["config"]
            base = db_info["base"]

            try:
                conn = await asyncpg.connect(
                    host=config.host,
                    port=config.port,
                    user=config.user,
                    password=config.password,
                    database=config.name,
                )

                # Check tables exist
                expected_tables = set(base.metadata.tables.keys())
                result = await conn.fetch(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
                existing_tables = {row["table_name"] for row in result}

                missing_tables = expected_tables - existing_tables
                if missing_tables:
                    logger.error(f"❌ Missing tables in {db_key}: {missing_tables}")
                    all_good = False
                else:
                    logger.info(
                        f"✅ All tables present in {db_key}: {len(existing_tables)} tables"
                    )

                await conn.close()

            except Exception as e:
                logger.error(f"❌ Failed to verify {db_key}: {e}")
                all_good = False

        return all_good


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Create database schemas manually")

    parser.add_argument(
        "--all", action="store_true", help="Create schemas for all databases"
    )
    parser.add_argument(
        "--db",
        choices=list(DATABASES.keys()),
        help="Create schema for specific database only",
    )
    parser.add_argument(
        "--drop-first",
        action="store_true",
        help="Drop existing databases before creating",
    )
    parser.add_argument(
        "--verify-only", action="store_true", help="Only verify existing schemas"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.all and not args.db and not args.verify_only:
        logger.error("❌ Must specify --all, --db, or --verify-only")
        sys.exit(1)

    creator = SchemaCreator(drop_first=args.drop_first)

    try:
        if args.verify_only:
            success = await creator.verify_schemas()

        elif args.all:
            success = await creator.create_all_schemas()
            if success:
                logger.info("\n🔍 Running verification...")
                await creator.verify_schemas()

        elif args.db:
            logger.info(f"🚀 Creating schema for {args.db} database...")
            success = await creator.create_database_if_not_exists(args.db)
            if success:
                success = await creator.create_schema(args.db)
            if success:
                logger.info("\n🔍 Running verification...")
                await creator.verify_schemas()

        if success:
            logger.info("\n🎉 Schema creation completed successfully!")
            sys.exit(0)
        else:
            logger.error("\n💥 Schema creation failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
