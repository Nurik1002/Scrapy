"""
Uzum.uz Enterprise Scraper Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
RAW_STORAGE_DIR = STORAGE_DIR / "raw"
EXPORTS_DIR = STORAGE_DIR / "exports"


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
    """Redis configuration for queues."""
    host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    db: int = field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    
    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class ProxyConfig:
    """Proxy configuration (Smartproxy recommended)."""
    enabled: bool = field(default_factory=lambda: os.getenv("PROXY_ENABLED", "false").lower() == "true")
    provider: str = field(default_factory=lambda: os.getenv("PROXY_PROVIDER", "smartproxy"))
    host: str = field(default_factory=lambda: os.getenv("PROXY_HOST", "gate.smartproxy.com"))
    port: int = field(default_factory=lambda: int(os.getenv("PROXY_PORT", "7000")))
    username: str = field(default_factory=lambda: os.getenv("PROXY_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("PROXY_PASS", ""))
    country: str = field(default_factory=lambda: os.getenv("PROXY_COUNTRY", "uz"))
    
    def get_url(self, session_id: Optional[str] = None) -> str:
        """Get proxy URL with optional sticky session."""
        if not self.enabled or not self.username:
            return ""
        
        user = self.username
        # Add country targeting
        user = f"{user}-country-{self.country}"
        # Add session for rotation/sticky
        if session_id:
            user = f"{user}-session-{session_id}"
        
        return f"http://{user}:{self.password}@{self.host}:{self.port}"


@dataclass
class ScraperConfig:
    """Scraper behavior configuration."""
    # Rate limiting
    requests_per_minute: int = 20
    min_delay: float = 2.0
    max_delay: float = 5.0
    
    # Human-like behavior
    reading_pause_chance: float = 0.1  # 10% chance of long pause
    reading_pause_min: float = 10.0
    reading_pause_max: float = 30.0
    
    # Retry configuration
    max_retries: int = 3
    retry_base_delay: float = 2.0
    
    # Concurrent requests (per worker)
    concurrent_requests: int = 5
    
    # User agents pool
    user_agents: list = field(default_factory=lambda: [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ])


@dataclass
class ValidationConfig:
    """Data validation thresholds."""
    max_price_drop_percent: float = 50.0  # Alert if price drops more than 50%
    max_price_increase_percent: float = 200.0  # Alert if price increases more than 200%
    min_valid_price: int = 1000  # Minimum valid price in UZS (about $0.08)
    max_valid_price: int = 1_000_000_000  # Maximum valid price in UZS (~$80,000)


@dataclass
class UzumAPIConfig:
    """Uzum.uz API endpoints."""
    base_url: str = "https://api.uzum.uz"
    product_endpoint: str = "/api/v2/product/{product_id}"
    category_endpoint: str = "/api/main/category/{category_id}"
    
    # Website URLs
    web_base_url: str = "https://uzum.uz"
    category_page: str = "/ru/category/{category_slug}"
    product_page: str = "/ru/product/{product_slug}"
    seller_page: str = "/ru/shop/{seller_link}"
    
    def get_product_url(self, product_id: int) -> str:
        return f"{self.base_url}{self.product_endpoint.format(product_id=product_id)}"


@dataclass
class Config:
    """Main configuration container."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    uzum_api: UzumAPIConfig = field(default_factory=UzumAPIConfig)
    
    # Environment
    environment: str = field(default_factory=lambda: os.getenv("ENV", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")


# Global config instance
config = Config()
