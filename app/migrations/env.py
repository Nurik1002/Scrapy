"""
Multi-Database Alembic Environment Configuration

Supports three separate databases:
- ecommerce_db: B2C platforms (Uzum, Yandex)
- classifieds_db: C2C platforms (OLX)
- procurement_db: B2B platforms (UZEX)

Usage:
  alembic -n ecommerce revision --autogenerate -m "Add product features"
  alembic -n classifieds upgrade head
  alembic -n procurement downgrade -1
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import configurations
from src.core.config import DatabaseType, settings

# Import all models for metadata
from src.core.models import Base as EcommerceBase

# Import UZEX models for procurement database
try:
    from src.platforms.uzex.models import Base as ProcurementBase
except ImportError:
    # If UZEX models don't exist yet, create empty base
    from sqlalchemy.ext.declarative import declarative_base

    ProcurementBase = declarative_base()

# Import OLX models for classifieds database (when implemented)
try:
    from src.platforms.olx.models import Base as ClassifiedsBase
except ImportError:
    # If OLX models don't exist yet, create empty base
    from sqlalchemy.ext.declarative import declarative_base

    ClassifiedsBase = declarative_base()

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Determine which database we're targeting based on the config name
config_name = context.get_x_argument(as_dictionary=True).get("config", "alembic")
if (
    hasattr(context, "config")
    and hasattr(context.config, "cmd_opts")
    and context.config.cmd_opts
):
    # Check if we're using -n flag
    if hasattr(context.config.cmd_opts, "name"):
        config_name = context.config.cmd_opts.name or "ecommerce"

# Map config names to database types and metadata
DATABASE_CONFIG = {
    "ecommerce": {
        "metadata": EcommerceBase.metadata,
        "db_type": DatabaseType.ECOMMERCE,
        "description": "B2C E-commerce platforms (Uzum, Yandex)",
    },
    "classifieds": {
        "metadata": ClassifiedsBase.metadata,
        "db_type": DatabaseType.CLASSIFIEDS,
        "description": "C2C Classifieds platforms (OLX)",
    },
    "procurement": {
        "metadata": ProcurementBase.metadata,
        "db_type": DatabaseType.PROCUREMENT,
        "description": "B2B Procurement platforms (UZEX)",
    },
    # Default/legacy
    "alembic": {
        "metadata": EcommerceBase.metadata,
        "db_type": DatabaseType.ECOMMERCE,
        "description": "Legacy configuration (defaults to ecommerce)",
    },
}

# Get the target database configuration
db_config = DATABASE_CONFIG.get(config_name, DATABASE_CONFIG["ecommerce"])
target_metadata = db_config["metadata"]

print(f"🗄️  Alembic targeting: {config_name} database ({db_config['description']})")


def get_database_url() -> str:
    """
    Get the database URL for the current target database.

    Priority:
    1. Environment variable (e.g., ECOMMERCE_DATABASE_URL)
    2. Config file section
    3. Settings from config.py
    """
    # Try environment variable first
    env_var_name = f"{config_name.upper()}_DATABASE_URL"
    if env_var_name in os.environ:
        return os.environ[env_var_name]

    # Try config file section
    try:
        section = config.get_section(config_name, {})
        if "sqlalchemy.url" in section:
            return section["sqlalchemy.url"]
    except:
        pass

    # Fall back to settings
    if config_name == "ecommerce":
        return settings.databases.ecommerce.url
    elif config_name == "classifieds":
        return settings.databases.classifieds.url
    elif config_name == "procurement":
        return settings.databases.procurement.url
    else:
        # Default to legacy database
        return settings.databases.legacy.url


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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Include object name in version table for multi-db support
            version_table_name=f"alembic_version_{config_name}",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
