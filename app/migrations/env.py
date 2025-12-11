"""
Single Database Alembic Environment Configuration

Uses ONE database (uzum_scraping) with THREE schemas:
- ecommerce: B2C platforms (Uzum, Yandex)
- classifieds: C2C platforms (OLX)
- procurement: B2B platforms (UZEX)

Usage:
  alembic revision -m "Add new feature"
  alembic upgrade head
  alembic downgrade -1
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import all models for metadata
from src.core.models import Base

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Get the database URL.
    
    Priority:
    1. Environment variable DATABASE_URL
    2. Config file
    """
    # Try environment variable first
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    
    # Fall back to config file
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Get database URL
    url = get_database_url()

    # Override the config URL
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Set search_path to include all schemas
        connection.execute(text("SET search_path TO ecommerce, procurement, classifieds, public"))
        
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Include schemas in autogenerate
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
