"""
Core Configuration - Central settings for the analytics platform.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
RAW_STORAGE_DIR = STORAGE_DIR / "raw"


@dataclass
class DatabaseConfig:
    """PostgreSQL configuration."""
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5434")))
    database: str = field(default_factory=lambda: os.getenv("DB_NAME", "uzum_scraping"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "scraper"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", "scraper123"))
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


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
    broker_url: str = field(default_factory=lambda: os.getenv("CELERY_BROKER", RedisConfig().url))
    result_backend: str = field(default_factory=lambda: os.getenv("CELERY_BACKEND", RedisConfig().url))
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = field(default_factory=lambda: ["json"])
    timezone: str = "Asia/Tashkent"
    enable_utc: bool = True


@dataclass
class DownloaderConfig:
    """Downloader settings."""
    concurrency: int = field(default_factory=lambda: int(os.getenv("DOWNLOAD_CONCURRENCY", "50")))
    timeout: int = field(default_factory=lambda: int(os.getenv("DOWNLOAD_TIMEOUT", "10")))
    retry_count: int = 3
    retry_delay: float = 1.0
    batch_size: int = 500
    
    # Rate limiting
    requests_per_second: int = field(default_factory=lambda: int(os.getenv("RPS_LIMIT", "100")))


@dataclass
class PlatformConfig:
    """Platform-specific configs."""
    name: str
    api_base_url: str
    web_base_url: str
    id_range_start: int = 1
    id_range_end: int = 5000000


# Platform configurations
PLATFORMS = {
    "uzum": PlatformConfig(
        name="uzum",
        api_base_url="https://api.uzum.uz/api/v2",
        web_base_url="https://uzum.uz",
        id_range_start=1,
        id_range_end=3000000
    ),
    # Future platforms
    # "wildberries": PlatformConfig(...),
    # "ozon": PlatformConfig(...),
}


@dataclass
class Settings:
    """Main settings container."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    celery: CeleryConfig = field(default_factory=CeleryConfig)
    downloader: DownloaderConfig = field(default_factory=DownloaderConfig)
    
    # Environment
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


# Global settings instance
settings = Settings()
