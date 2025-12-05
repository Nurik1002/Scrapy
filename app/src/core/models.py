"""
SQLAlchemy Models - Database tables for the analytics platform.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, 
    DateTime, Numeric, ForeignKey, Index, ARRAY, JSON
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from .database import Base


class Seller(Base):
    """Marketplace seller."""
    __tablename__ = "sellers"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), default="uzum")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(2, 1))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    total_products: Mapped[int] = mapped_column(Integer, default=0)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    
    registration_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    account_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Relationships
    products: Mapped[List["Product"]] = relationship(back_populates="seller")
    
    __table_args__ = (
        Index("idx_sellers_platform", "platform"),
        Index("idx_sellers_rating", "rating"),
    )


class Category(Base):
    """Product category with hierarchy."""
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), default="uzum")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_ru: Mapped[Optional[str]] = mapped_column(String(500))
    title_uz: Mapped[Optional[str]] = mapped_column(String(500))
    
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("categories.id"))
    level: Mapped[int] = mapped_column(Integer, default=0)
    path_ids: Mapped[Optional[List[int]]] = mapped_column(ARRAY(BigInteger))
    path_titles: Mapped[Optional[str]] = mapped_column(Text)
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(back_populates="children", remote_side=[id])
    children: Mapped[List["Category"]] = relationship(back_populates="parent")
    products: Mapped[List["Product"]] = relationship(back_populates="category")
    
    __table_args__ = (
        Index("idx_categories_platform", "platform"),
        Index("idx_categories_parent", "parent_id"),
    )


class Product(Base):
    """Product listing."""
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), default="uzum")
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    title_normalized: Mapped[Optional[str]] = mapped_column(String(1000))  # For matching
    
    category_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("categories.id"))
    seller_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("sellers.id"))
    
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(2, 1))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    total_available: Mapped[int] = mapped_column(Integer, default=0)
    
    description: Mapped[Optional[str]] = mapped_column(Text)
    photos: Mapped[Optional[dict]] = mapped_column(JSONB)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB)
    characteristics: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Relationships
    category: Mapped[Optional["Category"]] = relationship(back_populates="products")
    seller: Mapped[Optional["Seller"]] = relationship(back_populates="products")
    skus: Mapped[List["SKU"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_products_platform", "platform"),
        Index("idx_products_seller", "seller_id"),
        Index("idx_products_category", "category_id"),
        Index("idx_products_available", "is_available"),
    )


class SKU(Base):
    """Product variant with pricing."""
    __tablename__ = "skus"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"))
    
    full_price: Mapped[Optional[int]] = mapped_column(BigInteger)  # In tiyin
    purchase_price: Mapped[Optional[int]] = mapped_column(BigInteger)
    discount_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    
    available_amount: Mapped[int] = mapped_column(Integer, default=0)
    barcode: Mapped[Optional[str]] = mapped_column(String(100))
    characteristics: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    product: Mapped["Product"] = relationship(back_populates="skus")
    price_history: Mapped[List["PriceHistory"]] = relationship(back_populates="sku", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_skus_product", "product_id"),
        Index("idx_skus_price", "purchase_price"),
    )


class PriceHistory(Base):
    """Historical price tracking."""
    __tablename__ = "price_history"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("skus.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"))
    
    full_price: Mapped[Optional[int]] = mapped_column(BigInteger)
    purchase_price: Mapped[Optional[int]] = mapped_column(BigInteger)
    discount_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    available_amount: Mapped[int] = mapped_column(Integer, default=0)
    
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    price_change: Mapped[Optional[int]] = mapped_column(BigInteger)
    price_change_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    
    # Relationships
    sku: Mapped["SKU"] = relationship(back_populates="price_history")
    
    __table_args__ = (
        Index("idx_price_history_sku", "sku_id"),
        Index("idx_price_history_date", "recorded_at"),
    )


class RawSnapshot(Base):
    """Raw API response storage."""
    __tablename__ = "raw_snapshots"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), default="uzum")
    product_id: Mapped[int] = mapped_column(BigInteger)
    
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    __table_args__ = (
        Index("idx_raw_product", "product_id"),
        Index("idx_raw_pending", "processed"),
    )
