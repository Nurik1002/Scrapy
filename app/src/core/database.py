"""
Multi-Database Module - Async PostgreSQL connection and session management.

Supports the three-database architecture:
- ecommerce_db: B2C platforms (Uzum, Yandex)
- classifieds_db: C2C platforms (OLX)
- procurement_db: B2B platforms (UZEX)
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import DatabaseType, settings

# Suppress verbose SQLAlchemy SQL logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


class MultiDatabaseManager:
    """
    Manages multiple database connections and sessions.

    Provides unified access to all three databases with proper
    connection pooling and session management.
    """

    def __init__(self):
        self.engines: Dict[str, any] = {}
        self.session_makers: Dict[str, any] = {}
        self._initialized = False

    def initialize(self):
        """Initialize all database engines and session makers."""
        debug_logger.debug("Initializing MultiDatabaseManager")
        if self._initialized:
            debug_logger.debug("Database manager already initialized, skipping")
            return

        debug_logger.debug("Setting up database configurations")
        # Database configurations
        db_configs = {
            "ecommerce": settings.databases.ecommerce,
            "classifieds": settings.databases.classifieds,
            "procurement": settings.databases.procurement,
        }
        debug_logger.debug(
            f"Configured {len(db_configs)} databases: {list(db_configs.keys())}"
        )

        for db_name, config in db_configs.items():
            debug_logger.debug(
                f"Initializing database engine for '{db_name}': {config.name}"
            )
            debug_logger.debug(
                f"Database URL (masked): postgresql+asyncpg://***@{config.host}:{config.port}/{config.name}"
            )

            # Create async engine for each database
            engine = create_async_engine(
                config.async_url,
                echo=settings.debug,  # Enable SQL logging in debug mode
                poolclass=NullPool,  # Use NullPool for Celery workers
                pool_pre_ping=True,  # Validate connections before use
            )
            debug_logger.debug(f"Created async engine for '{db_name}' with NullPool")

            # Create session maker for each database
            session_maker = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            debug_logger.debug(
                f"Created session maker for '{db_name}' with expire_on_commit=False"
            )

            self.engines[db_name] = engine
            self.session_makers[db_name] = session_maker

            logger.info(f"Initialized {db_name} database engine: {config.name}")
            debug_logger.debug(
                f"Successfully registered engine and session maker for '{db_name}'"
            )

        self._initialized = True
        debug_logger.debug("MultiDatabaseManager initialization completed successfully")

    def get_engine(self, database: str):
        """Get engine for a specific database."""
        debug_logger.debug(f"Getting engine for database: '{database}'")
        if not self._initialized:
            debug_logger.debug("Database manager not initialized, initializing now")
            self.initialize()

        if database not in self.engines:
            debug_logger.debug(
                f"Database '{database}' not found in engines: {list(self.engines.keys())}"
            )
            raise ValueError(
                f"Unknown database: {database}. Available: {list(self.engines.keys())}"
            )

        debug_logger.debug(f"Successfully retrieved engine for '{database}'")
        return self.engines[database]

    def get_session_maker(self, database: str):
        """Get session maker for a specific database."""
        debug_logger.debug(f"Getting session maker for database: '{database}'")
        if not self._initialized:
            debug_logger.debug("Database manager not initialized, initializing now")
            self.initialize()

        if database not in self.session_makers:
            debug_logger.debug(
                f"Database '{database}' not found in session makers: {list(self.session_makers.keys())}"
            )
            raise ValueError(
                f"Unknown database: {database}. Available: {list(self.session_makers.keys())}"
            )

        debug_logger.debug(f"Successfully retrieved session maker for '{database}'")
        return self.session_makers[database]

    @asynccontextmanager
    async def get_session(self, database: str) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session for a specific database."""
        debug_logger.debug(f"Creating session for database: '{database}'")
        session_maker = self.get_session_maker(database)

        async with session_maker() as session:
            debug_logger.debug(f"Session created for '{database}', yielding to context")
            try:
                yield session
                debug_logger.debug(
                    f"Session for '{database}' completed successfully, committing"
                )
                await session.commit()
            except Exception as e:
                debug_logger.debug(
                    f"Exception in session for '{database}': {type(e).__name__}: {str(e)}"
                )
                debug_logger.debug(f"Rolling back session for '{database}'")
                await session.rollback()
                raise
            finally:
                debug_logger.debug(f"Closing session for '{database}'")
                await session.close()

    async def init_database_schema(self, database: str):
        """Initialize database schema for a specific database."""
        debug_logger.debug(f"Initializing schema for database: '{database}'")
        from ..schemas import get_base_for_database

        base = get_base_for_database(database)
        if not base:
            logger.warning(f"No base found for database: {database}")
            debug_logger.debug(
                f"No SQLAlchemy base available for '{database}', skipping schema creation"
            )
            return

        debug_logger.debug(f"Found base for '{database}', getting engine")
        engine = self.get_engine(database)

        debug_logger.debug(f"Creating schema tables for '{database}'")
        async with engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)
            logger.info(f"Initialized schema for {database} database")
            debug_logger.debug(f"Successfully created all tables for '{database}'")

    async def init_all_schemas(self):
        """Initialize schemas for all databases."""
        debug_logger.debug("Initializing schemas for all databases")
        databases = ["ecommerce", "classifieds", "procurement"]
        debug_logger.debug(f"Will initialize {len(databases)} databases: {databases}")

        for database in databases:
            debug_logger.debug(f"Attempting to initialize schema for '{database}'")
            try:
                await self.init_database_schema(database)
                debug_logger.debug(f"Successfully initialized schema for '{database}'")
            except Exception as e:
                logger.error(f"Failed to initialize {database} schema: {e}")
                debug_logger.debug(
                    f"Schema initialization failed for '{database}': {type(e).__name__}: {str(e)}"
                )

        debug_logger.debug("Completed schema initialization for all databases")

    async def close_all(self):
        """Close all database connections."""
        debug_logger.debug(
            f"Closing all database connections: {list(self.engines.keys())}"
        )
        for db_name, engine in self.engines.items():
            debug_logger.debug(f"Disposing engine for '{db_name}'")
            try:
                await engine.dispose()
                logger.info(f"Closed {db_name} database connections")
                debug_logger.debug(f"Successfully disposed engine for '{db_name}'")
            except Exception as e:
                logger.error(f"Error closing {db_name} database: {e}")
                debug_logger.debug(
                    f"Engine disposal failed for '{db_name}': {type(e).__name__}: {str(e)}"
                )

        debug_logger.debug("Completed closing all database connections")


# Global database manager instance
db_manager = MultiDatabaseManager()


# Convenience functions for easy access
@asynccontextmanager
async def get_ecommerce_session() -> AsyncGenerator[AsyncSession, None]:
    """Get session for ecommerce database."""
    async with db_manager.get_session("ecommerce") as session:
        yield session


@asynccontextmanager
async def get_classifieds_session() -> AsyncGenerator[AsyncSession, None]:
    """Get session for classifieds database."""
    async with db_manager.get_session("classifieds") as session:
        yield session


@asynccontextmanager
async def get_procurement_session() -> AsyncGenerator[AsyncSession, None]:
    """Get session for procurement database."""
    async with db_manager.get_session("procurement") as session:
        yield session


@asynccontextmanager
async def get_session_for_platform(platform: str) -> AsyncGenerator[AsyncSession, None]:
    """Get appropriate database session for a platform."""
    from ..schemas import get_database_for_platform

    database = get_database_for_platform(platform)
    async with db_manager.get_session(database) as session:
        yield session


# Backward compatibility functions
@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session (backward compatibility).

    Defaults to ecommerce database for existing code compatibility.
    """
    async with get_ecommerce_session() as session:
        yield session


async def init_db():
    """Initialize all database schemas."""
    await db_manager.init_all_schemas()


async def close_db():
    """Close all database connections."""
    await db_manager.close_all()


# Legacy Base import for backward compatibility
# This imports the ecommerce base as the default Base
try:
    from ..schemas.ecommerce import EcommerceBase as Base
except ImportError:
    # Fallback if schemas not available
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()


# Platform-specific session getters
PLATFORM_SESSION_MAP = {
    # B2C E-commerce platforms
    "uzum": get_ecommerce_session,
    "yandex": get_ecommerce_session,
    "wildberries": get_ecommerce_session,
    "ozon": get_ecommerce_session,
    # C2C Classifieds platforms
    "olx": get_classifieds_session,
    # B2B Procurement platforms
    "uzex": get_procurement_session,
}


def get_session_factory_for_platform(platform: str):
    """Get the appropriate session factory for a platform."""
    return PLATFORM_SESSION_MAP.get(platform, get_ecommerce_session)


# Database utilities
class DatabaseConfig:
    """Database configuration helper."""

    @staticmethod
    def get_database_url(database: str, async_mode: bool = True) -> str:
        """Get database URL for a database."""
        config_map = {
            "ecommerce": settings.databases.ecommerce,
            "classifieds": settings.databases.classifieds,
            "procurement": settings.databases.procurement,
        }

        if database not in config_map:
            raise ValueError(f"Unknown database: {database}")

        config = config_map[database]
        return config.async_url if async_mode else config.url

    @staticmethod
    def get_all_database_urls() -> Dict[str, str]:
        """Get all database URLs."""
        return {
            "ecommerce": settings.databases.ecommerce.async_url,
            "classifieds": settings.databases.classifieds.async_url,
            "procurement": settings.databases.procurement.async_url,
        }


# Health check functions
async def check_database_health(database: str) -> bool:
    """Check if a database is accessible."""
    debug_logger.debug(f"Performing health check for database: '{database}'")
    try:
        debug_logger.debug(f"Creating session for health check of '{database}'")
        async with db_manager.get_session(database) as session:
            debug_logger.debug(f"Executing SELECT 1 query for '{database}'")
            await session.execute("SELECT 1")
        debug_logger.debug(f"Health check passed for '{database}'")
        return True
    except Exception as e:
        logger.error(f"Database {database} health check failed: {e}")
        debug_logger.debug(
            f"Health check failed for '{database}': {type(e).__name__}: {str(e)}"
        )
        return False


async def check_all_databases_health() -> Dict[str, bool]:
    """Check health of all databases."""
    debug_logger.debug("Starting health check for all databases")
    databases = ["ecommerce", "classifieds", "procurement"]
    results = {}

    for database in databases:
        debug_logger.debug(f"Checking health of '{database}'")
        results[database] = await check_database_health(database)
        debug_logger.debug(f"Health check result for '{database}': {results[database]}")

    debug_logger.debug(f"All database health checks completed: {results}")
    return results


# Initialize the database manager when module is imported
debug_logger.debug("Initializing database manager on module import")
try:
    db_manager.initialize()
    debug_logger.debug("Database manager initialized successfully on import")
except Exception as e:
    logger.error(f"Failed to initialize database manager: {e}")
    debug_logger.debug(
        f"Database manager initialization failed on import: {type(e).__name__}: {str(e)}"
    )
