"""
SQLAlchemy Models for OLX Platform (Classifieds)
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy import Column, Integer, BigInteger, String, Text, Numeric, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ...core.database import Base


class OLXSeller(Base):
    """OLX Seller (Private person or Business)"""
    __tablename__ = "olx_sellers"
    __table_args__ = {'schema': 'classifieds'}
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="olx.uz")
    
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    seller_type: Mapped[Optional[str]] = mapped_column(String(20))
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_ads: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    
    contact_phone: Mapped[Optional[str]] = mapped_column(String(30))
    contact_telegram: Mapped[Optional[str]] = mapped_column(String(100))
    
    registered_since: Mapped[Optional[str]] = mapped_column(String(50))
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    products = relationship("OLXProduct", back_populates="seller")


class OLXProduct(Base):
    """OLX Product Listing"""
    __tablename__ = "olx_products"
    __table_args__ = {'schema': 'classifieds'}
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="olx.uz")
    category_path: Mapped[str] = mapped_column(String(200), nullable=False)
    listing_type: Mapped[str] = mapped_column(String(20), default="simple")
    
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    location: Mapped[Optional[str]] = mapped_column(String(200))
    url: Mapped[Optional[str]] = mapped_column(Text)
    
    images: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    seller_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("classifieds.olx_sellers.id"))
    
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    seller = relationship("OLXSeller", back_populates="products")
