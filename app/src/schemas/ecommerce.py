"""
Ecommerce Database Schema - B2C Platforms (Uzum, Yandex, etc.)

This schema supports multiple B2C e-commerce platforms in a unified structure,
enabling cross-platform price comparison and analytics.

Supported Platforms:
- Uzum.uz (✅ Active)
- Yandex Market (📋 Planned)
- Wildberries (🔮 Future)
- Ozon (🔮 Future)
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Create base for ecommerce models
EcommerceBase = declarative_base()


class EcommerceSeller(EcommerceBase):
    """
    Unified seller table for all B2C platforms.

    Supports cross-platform seller comparison and analytics.
    """

    __tablename__ = "ecommerce_sellers"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Yandex-specific fields
    business_id: Mapped[Optional[str]] = mapped_column(String(50))  # Yandex business ID
    slug: Mapped[Optional[str]] = mapped_column(String(255))  # URL slug

    # Basic information
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Performance metrics
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    total_products: Mapped[int] = mapped_column(Integer, default=0)

    # Status flags
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Additional info
    registration_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    profile_url: Mapped[Optional[str]] = mapped_column(Text)
    contact_info: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Platform-specific data
    legal_info: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Legal business information

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Flexible storage for platform-specific data
    attributes: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Canonical mapped attributes
    raw_attributes: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Original localized attributes
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Yandex-specific fields
    variant_logic: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # color_storage_split, etc.
    data_sources: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Track Model/Offers/Specs sources

    # Relationships
    products: Mapped[List["EcommerceProduct"]] = relationship(
        back_populates="seller", cascade="all, delete-orphan"
    )
    offers: Mapped[List["EcommerceOffer"]] = relationship(
        back_populates="seller", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Unique constraint for platform + external_id
        UniqueConstraint("platform", "external_id", name="uq_seller_platform_external"),
        # Performance indexes
        Index("idx_ecommerce_sellers_platform", "platform"),
        Index("idx_ecommerce_sellers_rating", "rating"),
        Index("idx_ecommerce_sellers_active", "is_active"),
        Index("idx_ecommerce_sellers_verified", "is_verified"),
        Index("idx_ecommerce_sellers_updated", "updated_at"),
        # JSONB indexes for fast attribute queries
        Index("idx_ecommerce_sellers_attributes", "attributes", postgresql_using="gin"),
    )


class EcommerceCategory(EcommerceBase):
    """
    Unified category hierarchy for all B2C platforms.

    Supports cross-platform category mapping and navigation.
    """

    __tablename__ = "ecommerce_categories"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Category information
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_ru: Mapped[Optional[str]] = mapped_column(String(500))
    name_uz: Mapped[Optional[str]] = mapped_column(String(500))
    name_en: Mapped[Optional[str]] = mapped_column(String(500))

    # Hierarchy
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("ecommerce_categories.id"), index=True
    )
    level: Mapped[int] = mapped_column(Integer, default=0, index=True)
    path_ids: Mapped[Optional[List[int]]] = mapped_column(ARRAY(BigInteger))
    path_names: Mapped[Optional[str]] = mapped_column(
        Text
    )  # "Electronics > Phones > Smartphones"

    # Statistics
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    active_product_count: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Flexible storage
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    parent: Mapped[Optional["EcommerceCategory"]] = relationship(
        back_populates="children", remote_side=[id]
    )
    children: Mapped[List["EcommerceCategory"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    products: Mapped[List["EcommerceProduct"]] = relationship(back_populates="category")

    __table_args__ = (
        # Unique constraint for platform + external_id
        UniqueConstraint(
            "platform", "external_id", name="uq_category_platform_external"
        ),
        # Performance indexes
        Index("idx_ecommerce_categories_platform", "platform"),
        Index("idx_ecommerce_categories_parent", "parent_id"),
        Index("idx_ecommerce_categories_level", "level"),
        Index("idx_ecommerce_categories_active", "is_active"),
        Index("idx_ecommerce_categories_product_count", "product_count"),
        # Full-text search on category names
        Index(
            "idx_ecommerce_categories_search",
            func.to_tsvector(
                "russian",
                func.coalesce("name", "") + " " + func.coalesce("name_ru", ""),
            ),
            postgresql_using="gin",
        ),
        # JSONB indexes
        Index(
            "idx_ecommerce_categories_attributes", "attributes", postgresql_using="gin"
        ),
    )


class EcommerceProduct(EcommerceBase):
    """
    Unified product catalog for all B2C platforms.

    Enables cross-platform product comparison and price monitoring.
    """

    __tablename__ = "ecommerce_products"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Yandex offer identification
    offer_hash: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # Yandex offer hash ID

    # Yandex-specific identifiers
    model_id: Mapped[Optional[str]] = mapped_column(String(100))  # Yandex Model ID
    slug: Mapped[Optional[str]] = mapped_column(String(500))  # Product URL slug

    # Basic information
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_normalized: Mapped[Optional[str]] = mapped_column(
        String(1000), index=True
    )  # For cross-seller matching
    title_ru: Mapped[Optional[str]] = mapped_column(Text)
    title_uz: Mapped[Optional[str]] = mapped_column(Text)
    title_en: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    category_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("ecommerce_categories.id"), index=True
    )
    seller_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("ecommerce_sellers.id"), index=True
    )

    # Performance metrics
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    order_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)

    # Availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    total_available: Mapped[int] = mapped_column(Integer, default=0)

    # Price range (for products with multiple offers)
    min_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), index=True)
    max_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), index=True)
    currency: Mapped[str] = mapped_column(String(10), default="UZS")

    # Media
    images: Mapped[Optional[dict]] = mapped_column(JSONB)  # {"urls": ["url1", "url2"]}
    video_url: Mapped[Optional[str]] = mapped_column(Text)

    # Product attributes
    brand: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    model: Mapped[Optional[str]] = mapped_column(String(200))
    sku: Mapped[Optional[str]] = mapped_column(String(100))
    barcode: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Product flags
    is_eco: Mapped[bool] = mapped_column(Boolean, default=False)
    is_adult: Mapped[bool] = mapped_column(Boolean, default=False)
    is_perishable: Mapped[bool] = mapped_column(Boolean, default=False)
    has_warranty: Mapped[bool] = mapped_column(Boolean, default=False)
    warranty_info: Mapped[Optional[str]] = mapped_column(Text)

    # Search and categorization
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    search_keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    last_price_check: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Flexible storage
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB)
    characteristics: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    category: Mapped[Optional["EcommerceCategory"]] = relationship(
        back_populates="products"
    )
    seller: Mapped[Optional["EcommerceSeller"]] = relationship(
        back_populates="products"
    )
    offers: Mapped[List["EcommerceOffer"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Unique constraint for platform + external_id
        UniqueConstraint(
            "platform", "external_id", name="uq_product_platform_external"
        ),
        # Performance indexes
        Index("idx_ecommerce_products_platform", "platform"),
        Index("idx_ecommerce_products_seller", "seller_id"),
        Index("idx_ecommerce_products_category", "category_id"),
        Index("idx_ecommerce_products_available", "is_available"),
        Index("idx_ecommerce_products_brand", "brand"),
        Index("idx_ecommerce_products_barcode", "barcode"),
        Index("idx_ecommerce_products_title_norm", "title_normalized"),
        Index("idx_ecommerce_products_price_range", "min_price", "max_price"),
        Index("idx_ecommerce_products_rating", "rating"),
        Index("idx_ecommerce_products_updated", "updated_at"),
        # Full-text search
        Index(
            "idx_ecommerce_products_search",
            func.to_tsvector(
                "russian",
                func.coalesce("title", "") + " " + func.coalesce("description", ""),
            ),
            postgresql_using="gin",
        ),
        # JSONB indexes
        Index(
            "idx_ecommerce_products_attributes", "attributes", postgresql_using="gin"
        ),
        Index(
            "idx_ecommerce_products_characteristics",
            "characteristics",
            postgresql_using="gin",
        ),
        # Array indexes
        Index("idx_ecommerce_products_tags", "tags", postgresql_using="gin"),
        Index(
            "idx_ecommerce_products_keywords", "search_keywords", postgresql_using="gin"
        ),
    )


class EcommerceOffer(EcommerceBase):
    """
    Product offers/variants with pricing information.

    Represents specific sellable items with price, stock, and variant info.
    Multiple offers can exist for the same product (different sizes, colors, etc.).
    """

    __tablename__ = "ecommerce_offers"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ecommerce_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ecommerce_sellers.id"), nullable=False, index=True
    )

    # Pricing
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, index=True)
    old_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(10), default="UZS")
    discount_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Availability
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    stock_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    available_amount: Mapped[int] = mapped_column(Integer, default=0)

    # Variant information
    variant_title: Mapped[Optional[str]] = mapped_column(String(500))
    variant_attributes: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # {color: "Red", size: "M"}
    barcode: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Shipping and fulfillment
    shipping_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    delivery_days: Mapped[Optional[int]] = mapped_column(Integer)

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Flexible storage
    characteristics: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    product: Mapped["EcommerceProduct"] = relationship(back_populates="offers")
    seller: Mapped["EcommerceSeller"] = relationship(back_populates="offers")
    price_history: Mapped[List["EcommercePriceHistory"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Unique constraint for platform + external_id (if external_id exists)
        UniqueConstraint("platform", "external_id", name="uq_offer_platform_external"),
        # Performance indexes
        Index("idx_ecommerce_offers_platform", "platform"),
        Index("idx_ecommerce_offers_product", "product_id"),
        Index("idx_ecommerce_offers_seller", "seller_id"),
        Index("idx_ecommerce_offers_price", "price"),
        Index("idx_ecommerce_offers_available", "is_available"),
        Index("idx_ecommerce_offers_barcode", "barcode"),
        Index("idx_ecommerce_offers_updated", "updated_at"),
        Index("idx_ecommerce_offers_scraped", "scraped_at"),
        # Composite indexes for common queries
        Index("idx_ecommerce_offers_product_price", "product_id", "price"),
        Index("idx_ecommerce_offers_seller_price", "seller_id", "price"),
        Index("idx_ecommerce_offers_available_price", "is_available", "price"),
        # JSONB indexes
        Index(
            "idx_ecommerce_offers_variant_attrs",
            "variant_attributes",
            postgresql_using="gin",
        ),
        Index(
            "idx_ecommerce_offers_characteristics",
            "characteristics",
            postgresql_using="gin",
        ),
    )


class EcommercePriceHistory(EcommerceBase):
    """
    Historical price tracking for offers.

    Essential for price monitoring, alerts, and analytics.
    """

    __tablename__ = "ecommerce_price_history"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Relationships
    offer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("ecommerce_offers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Price data
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, index=True)
    old_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(10), default="UZS")
    discount_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Stock data
    available_amount: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    # Change tracking
    price_change: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    price_change_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Timestamps
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), index=True
    )

    # Event tracking
    is_significant_change: Mapped[bool] = mapped_column(Boolean, default=False)
    change_reason: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # 'sale', 'discount', 'regular'

    # Relationships
    offer: Mapped["EcommerceOffer"] = relationship(back_populates="price_history")

    __table_args__ = (
        # Performance indexes
        Index("idx_ecommerce_price_history_offer", "offer_id"),
        Index("idx_ecommerce_price_history_recorded", "recorded_at"),
        Index("idx_ecommerce_price_history_price", "price"),
        Index("idx_ecommerce_price_history_significant", "is_significant_change"),
        # Composite indexes for time-series queries
        Index("idx_ecommerce_price_history_offer_time", "offer_id", "recorded_at"),
        Index(
            "idx_ecommerce_price_history_offer_price_time",
            "offer_id",
            "price",
            "recorded_at",
        ),
        # Partial indexes for better performance
        Index(
            "idx_ecommerce_price_history_significant_changes",
            "offer_id",
            "recorded_at",
            postgresql_where=Column("is_significant_change") == True,
        ),
    )


# Create indexes after table creation
def create_additional_indexes():
    """
    Create additional performance indexes that can't be defined in __table_args__.
    This function should be called after table creation.
    """
    pass  # All indexes are defined in __table_args__ for now
