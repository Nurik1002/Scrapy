"""
Classifieds Database Schema - C2C Platforms (OLX, etc.)

This schema supports C2C (Consumer-to-Consumer) classifieds platforms where
private individuals sell used or new items directly to other consumers.

Key Differences from E-commerce:
- Listings (not products): Temporary, one-time sales
- Private sellers: Individuals, not businesses
- Negotiable pricing: Not fixed catalog prices
- No variants/SKUs: Each listing is a single item
- Status lifecycle: Active → Sold/Expired

Supported Platforms:
- OLX.uz (📋 Planned)
- Future C2C platforms
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
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Create base for classifieds models
ClassifiedsBase = declarative_base()


class ClassifiedsSeller(ClassifiedsBase):
    """
    Private sellers (individuals) for classifieds platforms.

    Represents real people selling their personal items, not businesses.
    """

    __tablename__ = "classifieds_sellers"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Basic information
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(300))
    seller_type: Mapped[str] = mapped_column(
        String(20), default="private"
    )  # 'private', 'business'

    # Contact information
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(100))

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    region: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(50), default="UZ")

    # Reputation
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    successful_sales: Mapped[int] = mapped_column(Integer, default=0)
    total_listings: Mapped[int] = mapped_column(Integer, default=0)
    active_listings: Mapped[int] = mapped_column(Integer, default=0)

    # Membership info
    member_since: Mapped[Optional[str]] = mapped_column(String(50))
    membership_type: Mapped[str] = mapped_column(
        String(20), default="basic"
    )  # 'basic', 'premium'
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Response metrics
    response_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    avg_response_time: Mapped[Optional[int]] = mapped_column(Integer)  # in hours

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Flexible storage
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    listings: Mapped[List["ClassifiedsListing"]] = relationship(
        back_populates="seller", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Unique constraint for platform + external_id
        UniqueConstraint(
            "platform", "external_id", name="uq_classifieds_seller_platform_external"
        ),
        # Performance indexes
        Index("idx_classifieds_sellers_platform", "platform"),
        Index("idx_classifieds_sellers_location", "location"),
        Index("idx_classifieds_sellers_city", "city"),
        Index("idx_classifieds_sellers_type", "seller_type"),
        Index("idx_classifieds_sellers_verified", "is_verified"),
        Index("idx_classifieds_sellers_active", "is_active"),
        Index("idx_classifieds_sellers_rating", "rating"),
        Index("idx_classifieds_sellers_updated", "updated_at"),
        # Composite indexes for common queries
        Index("idx_classifieds_sellers_city_active", "city", "is_active"),
        Index("idx_classifieds_sellers_location_verified", "location", "is_verified"),
        # JSONB indexes
        Index(
            "idx_classifieds_sellers_attributes",
            "attributes",
            postgresql_using="gin",
        ),
    )


class ClassifiedsListing(ClassifiedsBase):
    """
    Individual listings for sale on classifieds platforms.

    Each listing represents a single item (or set of items) being sold
    by a private individual. Unlike e-commerce products, these are
    temporary and removed once sold.
    """

    __tablename__ = "classifieds_listings"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Basic information
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Category (simplified path structure for classifieds)
    category_path: Mapped[Optional[str]] = mapped_column(
        String(200), index=True
    )  # "transport/cars/sedan"
    category_name: Mapped[Optional[str]] = mapped_column(String(100))
    subcategory_name: Mapped[Optional[str]] = mapped_column(String(100))

    # Seller relationship
    seller_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("classifieds_sellers.id"), nullable=False, index=True
    )

    # Pricing
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), index=True)
    currency: Mapped[str] = mapped_column(String(10), default="UZS")
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_price_on_request: Mapped[bool] = mapped_column(Boolean, default=False)
    original_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    region: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(50), default="UZ")

    # Coordinates for map-based search
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))

    # Item condition and details
    condition: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # 'new', 'like_new', 'good', 'fair', 'poor'
    brand: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    model: Mapped[Optional[str]] = mapped_column(String(100))
    year: Mapped[Optional[int]] = mapped_column(Integer)

    # For vehicles
    mileage: Mapped[Optional[int]] = mapped_column(Integer)
    fuel_type: Mapped[Optional[str]] = mapped_column(String(20))
    transmission: Mapped[Optional[str]] = mapped_column(String(20))

    # For electronics
    warranty_remaining: Mapped[Optional[str]] = mapped_column(String(50))

    # For real estate
    area_sqm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    rooms: Mapped[Optional[int]] = mapped_column(Integer)

    # Media
    images: Mapped[Optional[dict]] = mapped_column(JSONB)  # {"urls": ["url1", "url2"]}
    video_urls: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    image_count: Mapped[int] = mapped_column(Integer, default=0)

    # Status and lifecycle
    status: Mapped[str] = mapped_column(
        String(20), default="active", index=True
    )  # 'active', 'sold', 'expired', 'removed', 'suspended'
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    # Engagement metrics
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    contact_count: Mapped[int] = mapped_column(Integer, default=0)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    posted_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_bumped_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Scraping timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Search optimization
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR
    )  # Generated column for full-text search
    search_keywords: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))

    # Flexible attributes for category-specific fields
    attributes: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # {brand, model, year, etc.}
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    seller: Mapped["ClassifiedsSeller"] = relationship(back_populates="listings")

    __table_args__ = (
        # Unique constraint for platform + external_id
        UniqueConstraint(
            "platform", "external_id", name="uq_classifieds_listing_platform_external"
        ),
        # Performance indexes
        Index("idx_classifieds_listings_platform", "platform"),
        Index("idx_classifieds_listings_seller", "seller_id"),
        Index("idx_classifieds_listings_category", "category_path"),
        Index("idx_classifieds_listings_price", "price"),
        Index("idx_classifieds_listings_location", "location"),
        Index("idx_classifieds_listings_city", "city"),
        Index("idx_classifieds_listings_status", "status"),
        Index("idx_classifieds_listings_condition", "condition"),
        Index("idx_classifieds_listings_brand", "brand"),
        Index("idx_classifieds_listings_posted", "posted_at"),
        Index("idx_classifieds_listings_negotiable", "is_negotiable"),
        Index("idx_classifieds_listings_featured", "is_featured"),
        # Composite indexes for common queries
        Index("idx_classifieds_listings_city_category", "city", "category_path"),
        Index("idx_classifieds_listings_city_price", "city", "price"),
        Index("idx_classifieds_listings_status_posted", "status", "posted_at"),
        Index("idx_classifieds_listings_category_price", "category_path", "price"),
        Index("idx_classifieds_listings_brand_model", "brand", "model"),
        # Location-based composite indexes
        Index("idx_classifieds_listings_location_active", "location", "status"),
        Index("idx_classifieds_listings_city_active_price", "city", "status", "price"),
        # Special indexes for vehicles
        Index("idx_classifieds_listings_year_mileage", "year", "mileage"),
        # Full-text search index (will be created as generated column)
        Index(
            "idx_classifieds_listings_search",
            "search_vector",
            postgresql_using="gin",
        ),
        # JSONB indexes for flexible attributes
        Index(
            "idx_classifieds_listings_attributes", "attributes", postgresql_using="gin"
        ),
        # Array indexes for tags and keywords
        Index("idx_classifieds_listings_tags", "tags", postgresql_using="gin"),
        Index(
            "idx_classifieds_listings_keywords",
            "search_keywords",
            postgresql_using="gin",
        ),
        # Geospatial index for location-based searches
        Index(
            "idx_classifieds_listings_coordinates",
            "latitude",
            "longitude",
        ),
        # Partial indexes for better performance on active listings
        Index(
            "idx_classifieds_listings_active_recent",
            "posted_at",
            postgresql_where=Column("status") == "active",
        ),
        Index(
            "idx_classifieds_listings_active_city",
            "city",
            "price",
            postgresql_where=Column("status") == "active",
        ),
        # Time-based partitioning hints (for future optimization)
        Index(
            "idx_classifieds_listings_posted_month",
            func.date_trunc("month", Column("posted_at")),
        ),
    )


# Additional utility functions and constraints
def create_search_vector_trigger():
    """
    SQL function to automatically update search_vector column.
    Should be executed after table creation.
    """
    return """
    -- Create or update the search vector trigger for full-text search
    CREATE OR REPLACE FUNCTION update_classifieds_listings_search_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector := to_tsvector('russian',
            COALESCE(NEW.title, '') || ' ' ||
            COALESCE(NEW.description, '') || ' ' ||
            COALESCE(NEW.brand, '') || ' ' ||
            COALESCE(NEW.model, '') || ' ' ||
            COALESCE(NEW.category_name, '') || ' ' ||
            COALESCE(NEW.location, '')
        );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- Create the trigger
    DROP TRIGGER IF EXISTS trg_update_classifieds_search_vector ON classifieds_listings;
    CREATE TRIGGER trg_update_classifieds_search_vector
        BEFORE INSERT OR UPDATE ON classifieds_listings
        FOR EACH ROW
        EXECUTE FUNCTION update_classifieds_listings_search_vector();
    """


def create_additional_constraints():
    """
    Additional constraints that can't be defined in model declarations.
    """
    return """
    -- Ensure price is positive when specified
    ALTER TABLE classifieds_listings
    ADD CONSTRAINT chk_classifieds_listings_price_positive
    CHECK (price IS NULL OR price > 0);

    -- Ensure valid status values
    ALTER TABLE classifieds_listings
    ADD CONSTRAINT chk_classifieds_listings_status_valid
    CHECK (status IN ('active', 'sold', 'expired', 'removed', 'suspended'));

    -- Ensure valid condition values
    ALTER TABLE classifieds_listings
    ADD CONSTRAINT chk_classifieds_listings_condition_valid
    CHECK (condition IS NULL OR condition IN ('new', 'like_new', 'good', 'fair', 'poor'));

    -- Ensure seller_type is valid
    ALTER TABLE classifieds_sellers
    ADD CONSTRAINT chk_classifieds_sellers_type_valid
    CHECK (seller_type IN ('private', 'business'));

    -- Ensure coordinates are within valid ranges
    ALTER TABLE classifieds_listings
    ADD CONSTRAINT chk_classifieds_listings_latitude_valid
    CHECK (latitude IS NULL OR (latitude >= -90 AND latitude <= 90));

    ALTER TABLE classifieds_listings
    ADD CONSTRAINT chk_classifieds_listings_longitude_valid
    CHECK (longitude IS NULL OR (longitude >= -180 AND longitude <= 180));
    """


# Views for common queries
def create_useful_views():
    """
    Create database views for common classifieds queries.
    """
    return """
    -- View for active listings with seller info
    CREATE OR REPLACE VIEW active_classifieds_listings AS
    SELECT
        l.*,
        s.name as seller_name,
        s.location as seller_location,
        s.rating as seller_rating,
        s.is_verified as seller_verified,
        s.member_since as seller_member_since
    FROM classifieds_listings l
    JOIN classifieds_sellers s ON l.seller_id = s.id
    WHERE l.status = 'active';

    -- View for listings by city with category breakdown
    CREATE OR REPLACE VIEW classifieds_city_summary AS
    SELECT
        city,
        category_path,
        COUNT(*) as listing_count,
        AVG(price) as avg_price,
        MIN(price) as min_price,
        MAX(price) as max_price,
        COUNT(CASE WHEN is_negotiable THEN 1 END) as negotiable_count
    FROM classifieds_listings
    WHERE status = 'active' AND price IS NOT NULL
    GROUP BY city, category_path;

    -- View for seller statistics
    CREATE OR REPLACE VIEW classifieds_seller_stats AS
    SELECT
        s.id,
        s.name,
        s.city,
        s.is_verified,
        COUNT(l.id) as total_listings,
        COUNT(CASE WHEN l.status = 'active' THEN 1 END) as active_listings,
        COUNT(CASE WHEN l.status = 'sold' THEN 1 END) as sold_listings,
        AVG(l.price) as avg_listing_price,
        MIN(l.posted_at) as first_listing_date,
        MAX(l.posted_at) as latest_listing_date
    FROM classifieds_sellers s
    LEFT JOIN classifieds_listings l ON s.id = l.seller_id
    GROUP BY s.id, s.name, s.city, s.is_verified;
    """
