"""
UZEX SQLAlchemy Models - Database tables for government procurement.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean,
    DateTime, Numeric, ForeignKey, Index, JSON
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.core.database import Base


class UzexCategory(Base):
    """UZEX product category."""
    __tablename__ = "uzex_categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uzex_categories.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class UzexProduct(Base):
    """UZEX product catalog."""
    __tablename__ = "uzex_products"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("uzex_categories.id"))
    category_name: Mapped[Optional[str]] = mapped_column(String(500))
    measure_id: Mapped[Optional[int]] = mapped_column(Integer)
    measure_name: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class UzexLot(Base):
    """UZEX lot/deal."""
    __tablename__ = "uzex_lots"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    display_no: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Type
    lot_type: Mapped[str] = mapped_column(String(30), nullable=False)  # auction, shop, national
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed, active
    is_budget: Mapped[bool] = mapped_column(Boolean, default=False)
    type_name: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Pricing
    start_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    deal_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency_name: Mapped[str] = mapped_column(String(20), default="Сом")
    
    # Customer
    customer_name: Mapped[Optional[str]] = mapped_column(String(500))
    customer_inn: Mapped[Optional[str]] = mapped_column(String(20))
    customer_region: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Provider
    provider_name: Mapped[Optional[str]] = mapped_column(String(500))
    provider_inn: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Deal info
    deal_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    deal_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    category_name: Mapped[Optional[str]] = mapped_column(String(500))
    pcp_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Dates
    lot_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    lot_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Kazna
    kazna_status: Mapped[Optional[str]] = mapped_column(String(100))
    kazna_status_id: Mapped[Optional[int]] = mapped_column(Integer)
    kazna_payment_status: Mapped[Optional[str]] = mapped_column(String(100))
    kazna_created_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Additional
    beneficiary: Mapped[Optional[str]] = mapped_column(String(500))
    founder: Mapped[Optional[str]] = mapped_column(String(500))
    deal_status_name: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Metadata
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    items: Mapped[List["UzexLotItem"]] = relationship(back_populates="lot", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_uzex_lots_type", "lot_type"),
        Index("idx_uzex_lots_status", "status"),
        Index("idx_uzex_lots_customer", "customer_inn"),
        Index("idx_uzex_lots_provider", "provider_inn"),
    )


class UzexLotItem(Base):
    """Item/product within a UZEX lot."""
    __tablename__ = "uzex_lot_items"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("uzex_lots.id", ondelete="CASCADE"))
    
    order_num: Mapped[Optional[int]] = mapped_column(Integer)
    product_name: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    measure_name: Mapped[Optional[str]] = mapped_column(String(100))
    
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    currency_name: Mapped[str] = mapped_column(String(20), default="Сом")
    
    country_name: Mapped[Optional[str]] = mapped_column(String(100))
    properties: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # Relationships
    lot: Mapped["UzexLot"] = relationship(back_populates="items")
    
    __table_args__ = (
        Index("idx_uzex_lot_items_lot", "lot_id"),
    )
