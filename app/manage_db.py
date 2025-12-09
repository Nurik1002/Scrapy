#!/usr/bin/env python3
"""
Multi-Database Management Script for Marketplace Analytics Platform

This script manages the three-database architecture:
- ecommerce_db: B2C platforms (Uzum, Yandex)
- classifieds_db: C2C platforms (OLX)
- procurement_db: B2B platforms (UZEX)

Usage:
    python manage_db.py create-all          # Create all databases
    python manage_db.py migrate-all         # Run all migrations
    python manage_db.py init-ecommerce      # Initialize ecommerce database
    python manage_db.py revision ecommerce "message"  # Create new migration
    python manage_db.py upgrade classifieds # Upgrade classifieds database
    python manage_db.py status              # Show status of all databases
"""

import argparse
import asyncio
import subprocess
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
    get_database_for_platform,
    get_post_create_functions,
)

# Database configurations
DATABASES = {
    "ecommerce": {
        "name": "ecommerce_db",
        "description": "B2C E-commerce platforms (Uzum, Yandex)",
        "config": settings.databases.ecommerce,
        "platforms": ["uzum", "yandex", "wildberries", "ozon"],
    },
    "classifieds": {
        "name": "classifieds_db",
        "description": "C2C Classifieds platforms (OLX)",
        "config": settings.databases.classifieds,
        "platforms": ["olx"],
    },
    "procurement": {
        "name": "procurement_db",
        "description": "B2B Procurement platforms (UZEX)",
        "config": settings.databases.procurement,
        "platforms": ["uzex"],
    },
}


class DatabaseManager:
    """Manages multiple database operations."""

    def __init__(self):
        self.databases = DATABASES

    async def create_database(self, db_key: str) -> bool:
        """Create a single database."""
        db_info = self.databases[db_key]
        config = db_info["config"]
        db_name = db_info["name"]

        # Connect to postgres database to create new database
        postgres_url = f"postgresql://{config.user}:{config.password}@{config.host}:{config.port}/postgres"

        try:
            # Use psycopg2 for database creation (asyncpg can't create databases)
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

            if cursor.fetchone():
                print(f"✅ Database '{db_name}' already exists")
                return True

            # Create database
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"🗄️  Created database '{db_name}' - {db_info['description']}")

            cursor.close()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ Failed to create database '{db_name}': {e}")
            return False

    async def create_all_databases(self) -> bool:
        """Create all databases."""
        print("🚀 Creating all databases...")
        success = True

        for db_key in self.databases:
            if not await self.create_database(db_key):
                success = False

        return success

    def run_alembic_command(self, db_key: str, command: list) -> bool:
        """Run an Alembic command for a specific database."""
        try:
            # Build alembic command with database name
            cmd = ["alembic", "-n", db_key] + command
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=Path(__file__).parent
            )

            if result.returncode == 0:
                print(f"✅ Alembic command succeeded for {db_key}")
                if result.stdout.strip():
                    print(result.stdout)
                return True
            else:
                print(f"❌ Alembic command failed for {db_key}")
                print(f"Error: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Failed to run Alembic command for {db_key}: {e}")
            return False

    def create_revision(
        self, db_key: str, message: str, autogenerate: bool = True
    ) -> bool:
        """Create a new migration revision."""
        db_info = self.databases[db_key]
        print(
            f"📝 Creating revision for {db_key} ({db_info['description']}): {message}"
        )

        cmd = ["revision", "-m", message]
        if autogenerate:
            cmd.append("--autogenerate")

        # Set version path for this database
        version_path = f"migrations/versions/{db_key}"
        cmd.extend(["--version-path", version_path])

        return self.run_alembic_command(db_key, cmd)

    def upgrade_database(self, db_key: str, revision: str = "head") -> bool:
        """Upgrade a database to a specific revision."""
        db_info = self.databases[db_key]
        print(f"⬆️  Upgrading {db_key} ({db_info['description']}) to {revision}")

        return self.run_alembic_command(db_key, ["upgrade", revision])

    def downgrade_database(self, db_key: str, revision: str) -> bool:
        """Downgrade a database to a specific revision."""
        db_info = self.databases[db_key]
        print(f"⬇️  Downgrading {db_key} ({db_info['description']}) to {revision}")

        return self.run_alembic_command(db_key, ["downgrade", revision])

    def get_database_status(self, db_key: str) -> dict:
        """Get the current status of a database."""
        try:
            result = subprocess.run(
                ["alembic", "-n", db_key, "current"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent,
            )

            if result.returncode == 0:
                return {
                    "status": "connected",
                    "current_revision": result.stdout.strip() or "No revisions",
                    "error": None,
                }
            else:
                return {
                    "status": "error",
                    "current_revision": None,
                    "error": result.stderr.strip(),
                }
        except Exception as e:
            return {"status": "error", "current_revision": None, "error": str(e)}

    def show_status(self):
        """Show status of all databases."""
        print("\n📊 Database Status Report")
        print("=" * 80)

        for db_key, db_info in self.databases.items():
            status = self.get_database_status(db_key)

            print(f"\n🗄️  {db_key.upper()} - {db_info['description']}")
            print(f"   Database: {db_info['name']}")
            print(f"   Platforms: {', '.join(db_info['platforms'])}")
            print(f"   Status: {status['status']}")
            print(f"   Current Revision: {status['current_revision'] or 'None'}")

            if status["error"]:
                print(f"   ❌ Error: {status['error']}")

    async def initialize_database(self, db_key: str) -> bool:
        """Initialize a database with schema and post-creation functions."""
        db_info = self.databases[db_key]
        config = db_info["config"]

        print(f"🔧 Initializing {db_key} database...")

        try:
            # Connect to the database
            conn = await asyncpg.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.name,
            )

            # Get post-creation functions
            post_functions = get_post_create_functions(db_key)

            for func in post_functions:
                try:
                    if callable(func):
                        sql = func()  # Execute function to get SQL
                        if sql and sql.strip():
                            await conn.execute(sql)
                            print(f"   ✅ Executed {func.__name__}")
                    else:
                        print(f"   ⚠️  Skipped {func} (not callable)")
                except Exception as e:
                    print(f"   ❌ Failed to execute {func.__name__}: {e}")

            await conn.close()
            print(f"✅ {db_key} database initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize {db_key} database: {e}")
            return False

    async def migrate_all(self) -> bool:
        """Run migrations for all databases."""
        print("🚀 Running migrations for all databases...")
        success = True

        for db_key in self.databases:
            if not self.upgrade_database(db_key):
                success = False

        return success

    async def init_all(self) -> bool:
        """Initialize all databases (create + migrate + setup)."""
        print("🚀 Full initialization of all databases...")

        # Step 1: Create databases
        if not await self.create_all_databases():
            return False

        # Step 2: Run initial migrations (this will create the schema)
        if not await self.migrate_all():
            return False

        # Step 3: Initialize with post-creation functions
        success = True
        for db_key in self.databases:
            if not await self.initialize_database(db_key):
                success = False

        return success


async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Multi-Database Management for Marketplace Analytics Platform"
    )

    parser.add_argument(
        "command",
        choices=[
            "create-all",
            "migrate-all",
            "init-all",
            "status",
            "create",
            "upgrade",
            "downgrade",
            "revision",
            "init-ecommerce",
            "init-classifieds",
            "init-procurement",
        ],
        help="Command to execute",
    )

    parser.add_argument(
        "database",
        nargs="?",
        choices=["ecommerce", "classifieds", "procurement"],
        help="Specific database to operate on",
    )

    parser.add_argument(
        "message_or_revision",
        nargs="?",
        help="Migration message or revision identifier",
    )

    args = parser.parse_args()

    manager = DatabaseManager()

    try:
        if args.command == "create-all":
            success = await manager.create_all_databases()
            sys.exit(0 if success else 1)

        elif args.command == "migrate-all":
            success = await manager.migrate_all()
            sys.exit(0 if success else 1)

        elif args.command == "init-all":
            success = await manager.init_all()
            sys.exit(0 if success else 1)

        elif args.command == "status":
            manager.show_status()

        elif args.command == "create":
            if not args.database:
                print("❌ Database name required for create command")
                sys.exit(1)
            success = await manager.create_database(args.database)
            sys.exit(0 if success else 1)

        elif args.command == "upgrade":
            if not args.database:
                print("❌ Database name required for upgrade command")
                sys.exit(1)
            revision = args.message_or_revision or "head"
            success = manager.upgrade_database(args.database, revision)
            sys.exit(0 if success else 1)

        elif args.command == "downgrade":
            if not args.database or not args.message_or_revision:
                print("❌ Database name and revision required for downgrade command")
                sys.exit(1)
            success = manager.downgrade_database(
                args.database, args.message_or_revision
            )
            sys.exit(0 if success else 1)

        elif args.command == "revision":
            if not args.database or not args.message_or_revision:
                print("❌ Database name and message required for revision command")
                sys.exit(1)
            success = manager.create_revision(args.database, args.message_or_revision)
            sys.exit(0 if success else 1)

        elif args.command.startswith("init-"):
            db_name = args.command.split("-")[1]
            if db_name not in DATABASES:
                print(f"❌ Unknown database: {db_name}")
                sys.exit(1)

            # Full initialization for single database
            print(f"🚀 Full initialization of {db_name} database...")
            await manager.create_database(db_name)
            manager.upgrade_database(db_name)
            success = await manager.initialize_database(db_name)
            sys.exit(0 if success else 1)

        else:
            print(f"❌ Unknown command: {args.command}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
