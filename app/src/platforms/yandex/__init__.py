"""
Yandex Market Platform Module - market.yandex.uz scraper

This module implements scraping for Yandex Market Uzbekistan, handling:
- Complex bot protection (SmartCaptcha, TLS fingerprinting)
- Category-based product discovery
- Model-Offer data structure
- Localized attribute mapping
- Proxy rotation and session management

Key Components:
- YandexPlatform: Main platform implementation
- YandexClient: HTTP client with anti-bot evasion
- YandexParser: Data parser with attribute mapping
- CategoryWalker: Category-based product discovery
- AttributeMapper: Uzbek to canonical attribute mapping
"""

from .attribute_mapper import AttributeMapper
from .category_walker import CategoryWalker
from .client import YandexClient
from .parser import YandexParser
from .platform import YandexPlatform

__all__ = [
    "YandexPlatform",
    "YandexClient",
    "YandexParser",
    "CategoryWalker",
    "AttributeMapper",
]

# Version and metadata
__version__ = "1.0.0"
__platform__ = "yandex"
__supported_domains__ = ["market.yandex.uz"]
