"""
Database Module - Async PostgreSQL connection and session management.

Uses SINGLE database (uzum_scraping) with THREE schemas:
- ecommerce: B2C platforms (Uzum, Yandex)
- classifieds: C2C platforms (OLX)
- procurement: B2B platforms (UZEX)

The search_path is set to include all schemas, so queries work without schema prefix.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import settings

# Suppress verbose SQLAlchemy SQL logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
debug_logger = logging.getLogger(f"{__name__}.debug")


# =============================================================================
# DATABASE ENGINE (Single Database)
# =============================================================================

# Use the legacy database (uzum_scraping) as the single source of truth
DATABASE_URL = settings.databases.legacy.async_url

# Create single async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    poolclass=NullPool,  # Use NullPool for Celery workers
    pool_pre_ping=True,
)

# Set search_path on new connections to include all schemas
@event.listens_for(engine.sync_engine, "connect")
def set_search_path(dbapi_connection, connection_record):
    """Set search_path to include all schemas on new connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO ecommerce, procurement, classifieds, public")
    cursor.close()

# Create session maker
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

logger.info(f"Database engine initialized: {settings.databases.legacy.name}")


# =============================================================================
# SESSION MANAGEMENT
# =============================================================================

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Backward compatibility aliases
get_ecommerce_session = get_session
get_classifieds_session = get_session
get_procurement_session = get_session


@asynccontextmanager
async def get_session_for_platform(platform: str) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for a platform (all use same database now)."""
    async with get_session() as session:
        yield session


# =============================================================================
# INITIALIZATION
# =============================================================================

async def init_db():
    """Initialize database schemas."""
    from .models import Base
    
    async with engine.begin() as conn:
        # Ensure search_path is set
        await conn.execute(text("SET search_path TO ecommerce, procurement, classifieds, public"))
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database schema initialized")


async def close_db():
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")


# =============================================================================
# HEALTH CHECK
# =============================================================================

async def check_database_health() -> bool:
    """Check if database is accessible."""
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def check_all_databases_health() -> Dict[str, bool]:
    """Check health (single database now)."""
    healthy = await check_database_health()
    return {
        "ecommerce": healthy,
        "classifieds": healthy,
        "procurement": healthy,
    }


# =============================================================================
# LEGACY SUPPORT
# =============================================================================

# Platform session map (all point to same session now)
PLATFORM_SESSION_MAP = {
    "uzum": get_session,
    "yandex": get_session,
    "wildberries": get_session,
    "ozon": get_session,
    "olx": get_session,
    "uzex": get_session,
}


def get_session_factory_for_platform(platform: str):
    """Get the session factory for a platform."""
    return PLATFORM_SESSION_MAP.get(platform, get_session)


# Legacy Base import
try:
    from .models import Base
except ImportError:
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()


# MultiDatabaseManager compatibility (deprecated but kept for imports)
class MultiDatabaseManager:
    """Deprecated - kept for backward compatibility."""
    
    def __init__(self):
        self._initialized = True
        self.engines = {"ecommerce": engine, "classifieds": engine, "procurement": engine}
        self.session_makers = {"ecommerce": SessionLocal, "classifieds": SessionLocal, "procurement": SessionLocal}
    
    def initialize(self):
        pass
    
    def get_engine(self, database: str):
        return engine
    
    def get_session_maker(self, database: str):
        return SessionLocal
    
    @asynccontextmanager
    async def get_session(self, database: str):
        async with get_session() as session:
            yield session
    
    async def close_all(self):
        await close_db()


# Global instance for compatibility
db_manager = MultiDatabaseManager()
