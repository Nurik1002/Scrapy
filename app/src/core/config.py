"""
Multi-Database Configuration - Central settings for the three-database analytics platform.

Supports three separate databases:
- ecommerce_db: B2C platforms (Uzum, Yandex)
- classifieds_db: C2C platforms (OLX)
- procurement_db: B2B platforms (UZEX)
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
RAW_STORAGE_DIR = STORAGE_DIR / "raw"
MIGRATIONS_DIR = BASE_DIR / "migrations"


class DatabaseType(Enum):
    """Database types for different business models."""

    ECOMMERCE = "ecommerce"  # B2C: Uzum, Yandex
    CLASSIFIEDS = "classifieds"  # C2C: OLX
    PROCUREMENT = "procurement"  # B2B: UZEX


@dataclass
class DatabaseConfig:
    """PostgreSQL configuration for a single database."""

    name: str
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5434")))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "scraper"))
    password: str = field(
        default_factory=lambda: os.getenv("DB_PASSWORD", "scraper123")
    )

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class MultiDatabaseConfig:
    """Multi-database configuration for the three-database architecture."""

    # Primary databases
    ecommerce: DatabaseConfig = field(
        default_factory=lambda: DatabaseConfig(
            name=os.getenv("ECOMMERCE_DB", "ecommerce_db")
        )
    )
    classifieds: DatabaseConfig = field(
        default_factory=lambda: DatabaseConfig(
            name=os.getenv("CLASSIFIEDS_DB", "classifieds_db")
        )
    )
    procurement: DatabaseConfig = field(
        default_factory=lambda: DatabaseConfig(
            name=os.getenv("PROCUREMENT_DB", "procurement_db")
        )
    )

    # Legacy database (for migration compatibility)
    legacy: DatabaseConfig = field(
        default_factory=lambda: DatabaseConfig(
            name=os.getenv("DB_NAME", "uzum_scraping")
        )
    )

    def get_database(self, db_type: DatabaseType) -> DatabaseConfig:
        """Get database config by type."""
        mapping = {
            DatabaseType.ECOMMERCE: self.ecommerce,
            DatabaseType.CLASSIFIEDS: self.classifieds,
            DatabaseType.PROCUREMENT: self.procurement,
        }
        return mapping[db_type]

    def get_database_for_platform(self, platform: str) -> DatabaseConfig:
        """Get appropriate database for a platform."""
        platform_mapping = {
            # B2C E-commerce platforms
            "uzum": self.ecommerce,
            "yandex": self.ecommerce,
            "wildberries": self.ecommerce,
            "ozon": self.ecommerce,
            # C2C Classifieds platforms
            "olx": self.classifieds,
            # B2B Procurement platforms
            "uzex": self.procurement,
        }
        return platform_mapping.get(platform, self.legacy)


@dataclass
class RedisConfig:
    """Redis configuration."""

    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class CeleryConfig:
    """Celery configuration."""

    broker_url: str = field(
        default_factory=lambda: os.getenv("CELERY_BROKER", RedisConfig().url)
    )
    result_backend: str = field(
        default_factory=lambda: os.getenv("CELERY_BACKEND", RedisConfig().url)
    )
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = field(default_factory=lambda: ["json"])
    timezone: str = "Asia/Tashkent"
    enable_utc: bool = True


@dataclass
class DownloaderConfig:
    """Downloader settings."""

    concurrency: int = field(
        default_factory=lambda: int(os.getenv("DOWNLOAD_CONCURRENCY", "50"))
    )
    timeout: int = field(
        default_factory=lambda: int(os.getenv("DOWNLOAD_TIMEOUT", "15"))
    )
    retry_count: int = 3
    retry_delay: float = 1.0
    batch_size: int = 500
    db_batch_size: int = 100

    # Rate limiting
    requests_per_second: int = field(
        default_factory=lambda: int(os.getenv("RPS_LIMIT", "100"))
    )

    # User agents for rotation
    user_agents: List[str] = field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        ]
    )


@dataclass
class PlatformConfig:
    """Platform-specific configuration."""

    name: str
    platform_type: str  # 'ecommerce', 'classifieds', 'procurement'
    api_base_url: str
    web_base_url: str
    database_type: DatabaseType

    # Scraping parameters
    id_range_start: int = 1
    id_range_end: int = 5000000
    concurrency: int = 50
    enabled: bool = True

    # Platform-specific settings
    requires_session: bool = False
    requires_proxy: bool = False
    rate_limit: int = 100  # requests per minute


# Platform configurations
PLATFORMS = {
    # B2C E-commerce Platforms
    "uzum": PlatformConfig(
        name="uzum",
        platform_type="ecommerce",
        api_base_url="https://api.uzum.uz/api/v2",
        web_base_url="https://uzum.uz",
        database_type=DatabaseType.ECOMMERCE,
        id_range_start=1,
        id_range_end=3000000,
        concurrency=150,  # High-performance API
        rate_limit=200,
        enabled=True,
    ),
    "yandex": PlatformConfig(
        name="yandex",
        platform_type="ecommerce",
        api_base_url="https://market.yandex.uz",
        web_base_url="https://market.yandex.uz",
        database_type=DatabaseType.ECOMMERCE,
        id_range_start=1000000,
        id_range_end=10000000,
        concurrency=10,  # Conservative due to aggressive bot protection
        requires_proxy=True,  # Essential for Yandex Market
        requires_session=True,  # Session persistence needed
        rate_limit=60,  # 60 requests per minute max
        enabled=True,  # Now implemented
    ),
    # C2C Classifieds Platforms
    "olx": PlatformConfig(
        name="olx",
        platform_type="classifieds",
        api_base_url="https://www.olx.uz/api",
        web_base_url="https://www.olx.uz",
        database_type=DatabaseType.CLASSIFIEDS,
        concurrency=20,
        requires_proxy=True,
        rate_limit=120,
        enabled=True,  # ENABLED: Fully implemented with 3 Celery tasks
    ),
    # B2B Procurement Platforms
    "uzex": PlatformConfig(
        name="uzex",
        platform_type="procurement",
        api_base_url="https://uzex.uz/api",
        web_base_url="https://uzex.uz",
        database_type=DatabaseType.PROCUREMENT,
        concurrency=5,  # Limited by session management
        requires_session=True,
        rate_limit=30,
        enabled=True,
    ),
}


@dataclass
class ProxyConfig:
    """Proxy configuration."""

    enabled: bool = field(
        default_factory=lambda: os.getenv("PROXY_ENABLED", "false").lower() == "true"
    )
    provider: str = field(
        default_factory=lambda: os.getenv("PROXY_PROVIDER", "smartproxy")
    )
    host: str = field(default_factory=lambda: os.getenv("PROXY_HOST", ""))
    port: int = field(default_factory=lambda: int(os.getenv("PROXY_PORT", "7000")))
    username: str = field(default_factory=lambda: os.getenv("PROXY_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("PROXY_PASS", ""))

    def get_proxy_url(
        self, country: str = "uz", session_id: Optional[str] = None
    ) -> Optional[str]:
        """Get proxy URL with country and session."""
        if not self.enabled or not self.username:
            return None

        user = f"{self.username}-country-{country}"
        if session_id:
            user = f"{user}-session-{session_id}"

        return f"http://{user}:{self.password}@{self.host}:{self.port}"


@dataclass
class ValidationConfig:
    """Data validation settings."""

    max_price_uzs: int = 1_000_000_000  # Max price in UZS (~$80K)
    min_price_uzs: int = 1000  # Min price in UZS (~$0.08)
    max_title_length: int = 1000
    max_description_length: int = 50000

    # Price change alert thresholds
    price_drop_threshold: float = 0.1  # 10% drop
    price_spike_threshold: float = 2.0  # 100% increase


@dataclass
class Settings:
    """Main settings container for the multi-database architecture."""

    # Database configurations
    databases: MultiDatabaseConfig = field(default_factory=MultiDatabaseConfig)

    # Other configurations
    redis: RedisConfig = field(default_factory=RedisConfig)
    celery: CeleryConfig = field(default_factory=CeleryConfig)
    downloader: DownloaderConfig = field(default_factory=DownloaderConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)

    # Environment settings
    environment: str = field(default_factory=lambda: os.getenv("ENV", "development"))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    def get_database_url(self, platform: str, async_mode: bool = True) -> str:
        """Get database URL for a platform."""
        db_config = self.databases.get_database_for_platform(platform)
        return db_config.async_url if async_mode else db_config.url

    def get_platform_config(self, platform: str) -> Optional[PlatformConfig]:
        """Get platform configuration."""
        return PLATFORMS.get(platform)

    def get_enabled_platforms(self) -> List[str]:
        """Get list of enabled platforms."""
        return [name for name, config in PLATFORMS.items() if config.enabled]

    def get_platforms_by_type(self, platform_type: str) -> List[str]:
        """Get platforms by type (ecommerce, classifieds, procurement)."""
        return [
            name
            for name, config in PLATFORMS.items()
            if config.platform_type == platform_type and config.enabled
        ]


# Global settings instance
settings = Settings()

# Backward compatibility aliases
database = settings.databases.legacy  # For legacy code
