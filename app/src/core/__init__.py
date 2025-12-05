"""Core module - shared infrastructure."""
from .config import settings, PLATFORMS, STORAGE_DIR, RAW_STORAGE_DIR
from .database import get_session, init_db, close_db, Base
from .models import Seller, Category, Product, SKU, PriceHistory, RawSnapshot
from .redis_client import redis_client

__all__ = [
    "settings",
    "PLATFORMS",
    "STORAGE_DIR",
    "RAW_STORAGE_DIR",
    "get_session",
    "init_db",
    "close_db",
    "Base",
    "Seller",
    "Category",
    "Product",
    "SKU",
    "PriceHistory",
    "RawSnapshot",
    "redis_client",
]
