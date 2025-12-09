"""
Procurement Database Schema - B2B Government Platforms (UZEX, etc.)

This schema supports B2B procurement platforms where government entities
post tenders/auctions and private companies bid on contracts.

Key Features:
- Government tenders and auctions
- Complex lot structures with multiple items
- Bidding process tracking
- Customer/Provider relationship management
- Audit trails and compliance data
- Budget and financial tracking

Supported Platforms:
- UZEX (✅ Active)
- Future government procurement platforms
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Create base for procurement models
ProcurementBase = declarative_base()


class ProcurementOrganization(ProcurementBase):
    """
    Organizations involved in procurement (both customers and providers).

    Customers: Government entities that create tenders
    Providers: Companies that bid on tenders
    """

    __tablename__ = "procurement_organizations"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Organization type
    org_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # 'customer', 'provider', 'both'

    # Basic information
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(Text)
    short_name: Mapped[Optional[str]] = mapped_column(String(200))

    # Legal identification
    inn: Mapped[Optional[str]] = mapped_column(String(20), index=True)  # Tax ID
    legal_address: Mapped[Optional[str]] = mapped_column(Text)
    registration_number: Mapped[Optional[str]] = mapped_column(String(50))

    # Location
    region: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    country: Mapped[str] = mapped_column(String(50), default="UZ")

    # Organization characteristics
    industry: Mapped[Optional[str]] = mapped_column(String(200))
    organization_size: Mapped[Optional[str]] = mapped_column(String(50))
    is_government: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_state_owned: Mapped[bool] = mapped_column(Boolean, default=False)

    # Performance metrics (for providers)
    total_bids: Mapped[int] = mapped_column(Integer, default=0)
    won_bids: Mapped[int] = mapped_column(Integer, default=0)
    total_contract_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    avg_contract_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    # Performance metrics (for customers)
    total_tenders: Mapped[int] = mapped_column(Integer, default=0)
    total_procurement_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    avg_tender_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Flexible storage
    contact_info: Mapped[Optional[dict]] = mapped_column(JSONB)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    customer_lots: Mapped[List["ProcurementLot"]] = relationship(
        foreign_keys="ProcurementLot.customer_id", back_populates="customer_org"
    )
    provider_lots: Mapped[List["ProcurementLot"]] = relationship(
        foreign_keys="ProcurementLot.provider_id", back_populates="provider_org"
    )

    __table_args__ = (
        # Unique constraint for platform + external_id
        UniqueConstraint(
            "platform", "external_id", name="uq_procurement_org_platform_external"
        ),
        # Unique constraint for INN (if provided)
        UniqueConstraint("inn", name="uq_procurement_org_inn"),
        # Performance indexes
        Index("idx_procurement_orgs_platform", "platform"),
        Index("idx_procurement_orgs_type", "org_type"),
        Index("idx_procurement_orgs_inn", "inn"),
        Index("idx_procurement_orgs_name", "name"),
        Index("idx_procurement_orgs_region", "region"),
        Index("idx_procurement_orgs_city", "city"),
        Index("idx_procurement_orgs_government", "is_government"),
        Index("idx_procurement_orgs_active", "is_active"),
        Index("idx_procurement_orgs_blacklisted", "is_blacklisted"),
        Index("idx_procurement_orgs_updated", "updated_at"),
        # Composite indexes for common queries
        Index("idx_procurement_orgs_type_active", "org_type", "is_active"),
        Index("idx_procurement_orgs_region_type", "region", "org_type"),
        Index("idx_procurement_orgs_government_active", "is_government", "is_active"),
        # Full-text search on organization names
        Index(
            "idx_procurement_orgs_search",
            func.to_tsvector(
                "russian",
                func.coalesce("name", "") + " " + func.coalesce("full_name", ""),
            ),
            postgresql_using="gin",
        ),
        # JSONB indexes
        Index("idx_procurement_orgs_attributes", "attributes", postgresql_using="gin"),
        Index("idx_procurement_orgs_contact", "contact_info", postgresql_using="gin"),
    )


class ProcurementLot(ProcurementBase):
    """
    Government procurement lots (tenders/auctions).

    Each lot represents a procurement opportunity where the government
    seeks to purchase goods or services through competitive bidding.
    """

    __tablename__ = "procurement_lots"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Display identification
    display_no: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    lot_number: Mapped[Optional[str]] = mapped_column(String(100))

    # Lot type and classification
    lot_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # 'auction', 'tender', 'shop', 'national_shop'
    procurement_method: Mapped[Optional[str]] = mapped_column(String(50))

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # 'active', 'completed', 'cancelled', 'failed'

    # Budget and financing
    is_budget: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    budget_type: Mapped[Optional[str]] = mapped_column(String(50))
    financing_source: Mapped[Optional[str]] = mapped_column(String(200))

    # Pricing information
    start_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), index=True)
    deal_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), index=True)
    reserve_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    currency: Mapped[str] = mapped_column(String(10), default="UZS")

    # Savings calculation
    savings_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    savings_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))

    # Organization relationships
    customer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("procurement_organizations.id"), index=True
    )
    provider_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("procurement_organizations.id"), index=True
    )

    # Legacy string fields (for backward compatibility)
    customer_name: Mapped[Optional[str]] = mapped_column(String(500))
    customer_inn: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(500))
    provider_inn: Mapped[Optional[str]] = mapped_column(String(20), index=True)

    # Category and classification
    category_name: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    category_code: Mapped[Optional[str]] = mapped_column(String(50))
    procurement_subject: Mapped[Optional[str]] = mapped_column(Text)

    # Lot details
    pcp_count: Mapped[int] = mapped_column(Integer, default=0)  # Number of items
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    bid_count: Mapped[int] = mapped_column(Integer, default=0)

    # Important dates
    announced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    lot_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    lot_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    deal_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)

    # Deal information
    deal_id: Mapped[Optional[str]] = mapped_column(String(100))
    contract_number: Mapped[Optional[str]] = mapped_column(String(100))

    # Additional status fields
    kazna_status: Mapped[Optional[str]] = mapped_column(String(50))
    execution_status: Mapped[Optional[str]] = mapped_column(String(50))

    # Location and delivery
    delivery_region: Mapped[Optional[str]] = mapped_column(String(100))
    delivery_city: Mapped[Optional[str]] = mapped_column(String(100))
    delivery_address: Mapped[Optional[str]] = mapped_column(Text)
    delivery_terms: Mapped[Optional[str]] = mapped_column(Text)

    # Quality and compliance
    quality_requirements: Mapped[Optional[str]] = mapped_column(Text)
    technical_specifications: Mapped[Optional[dict]] = mapped_column(JSONB)
    compliance_requirements: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Flexible storage
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB)
    documents: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # Links to tender documents
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    customer_org: Mapped[Optional["ProcurementOrganization"]] = relationship(
        foreign_keys=[customer_id], back_populates="customer_lots"
    )
    provider_org: Mapped[Optional["ProcurementOrganization"]] = relationship(
        foreign_keys=[provider_id], back_populates="provider_lots"
    )
    lot_items: Mapped[List["ProcurementLotItem"]] = relationship(
        back_populates="lot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Unique constraint for platform + external_id
        UniqueConstraint(
            "platform", "external_id", name="uq_procurement_lot_platform_external"
        ),
        # Performance indexes
        Index("idx_procurement_lots_platform", "platform"),
        Index("idx_procurement_lots_display_no", "display_no"),
        Index("idx_procurement_lots_type", "lot_type"),
        Index("idx_procurement_lots_status", "status"),
        Index("idx_procurement_lots_budget", "is_budget"),
        Index("idx_procurement_lots_customer", "customer_id"),
        Index("idx_procurement_lots_provider", "provider_id"),
        Index("idx_procurement_lots_customer_inn", "customer_inn"),
        Index("idx_procurement_lots_provider_inn", "provider_inn"),
        Index("idx_procurement_lots_category", "category_name"),
        Index("idx_procurement_lots_start_cost", "start_cost"),
        Index("idx_procurement_lots_deal_cost", "deal_cost"),
        Index("idx_procurement_lots_start_date", "lot_start_date"),
        Index("idx_procurement_lots_end_date", "lot_end_date"),
        Index("idx_procurement_lots_deal_date", "deal_date"),
        Index("idx_procurement_lots_updated", "updated_at"),
        Index("idx_procurement_lots_scraped", "scraped_at"),
        # Composite indexes for common queries
        Index("idx_procurement_lots_type_status", "lot_type", "status"),
        Index("idx_procurement_lots_budget_status", "is_budget", "status"),
        Index("idx_procurement_lots_customer_status", "customer_id", "status"),
        Index("idx_procurement_lots_provider_status", "provider_id", "status"),
        Index("idx_procurement_lots_date_range", "lot_start_date", "lot_end_date"),
        Index("idx_procurement_lots_cost_range", "start_cost", "deal_cost"),
        Index("idx_procurement_lots_category_budget", "category_name", "is_budget"),
        # Time-based partitioning hints
        Index("idx_procurement_lots_deal_month", func.date_trunc("month", "deal_date")),
        Index(
            "idx_procurement_lots_start_month",
            func.date_trunc("month", "lot_start_date"),
        ),
        # Full-text search
        Index(
            "idx_procurement_lots_search",
            func.to_tsvector(
                "russian",
                func.coalesce("display_no", "")
                + " "
                + func.coalesce("category_name", "")
                + " "
                + func.coalesce("customer_name", "")
                + " "
                + func.coalesce("provider_name", "")
                + " "
                + func.coalesce("procurement_subject", ""),
            ),
            postgresql_using="gin",
        ),
        # JSONB indexes
        Index("idx_procurement_lots_attributes", "attributes", postgresql_using="gin"),
        Index(
            "idx_procurement_lots_technical",
            "technical_specifications",
            postgresql_using="gin",
        ),
        Index(
            "idx_procurement_lots_compliance",
            "compliance_requirements",
            postgresql_using="gin",
        ),
        Index("idx_procurement_lots_documents", "documents", postgresql_using="gin"),
    )


class ProcurementLotItem(ProcurementBase):
    """
    Individual items within procurement lots.

    Each lot can contain multiple items that are being procured.
    This table stores the specific products/services requested.
    """

    __tablename__ = "procurement_lot_items"

    # Primary identification
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Parent lot relationship
    lot_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("procurement_lots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Item identification
    item_number: Mapped[Optional[int]] = mapped_column(Integer)
    order_num: Mapped[Optional[int]] = mapped_column(Integer)
    position_number: Mapped[Optional[str]] = mapped_column(String(50))

    # Product information
    product_name: Mapped[Optional[str]] = mapped_column(Text, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    technical_specification: Mapped[Optional[str]] = mapped_column(Text)

    # Quantity and measurements
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    measure_name: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    measure_code: Mapped[Optional[str]] = mapped_column(String(20))

    # Pricing per item
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), index=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2), index=True
    )  # Total cost
    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 2)
    )  # Alternative total
    currency: Mapped[str] = mapped_column(String(10), default="UZS")

    # Unit pricing
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    total_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    # Product characteristics
    brand: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    model: Mapped[Optional[str]] = mapped_column(String(200))
    country_name: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(10))

    # Quality specifications
    quality_standard: Mapped[Optional[str]] = mapped_column(String(200))
    certification: Mapped[Optional[str]] = mapped_column(String(200))
    warranty_period: Mapped[Optional[str]] = mapped_column(String(100))

    # Delivery requirements
    delivery_terms: Mapped[Optional[str]] = mapped_column(Text)
    delivery_period: Mapped[Optional[str]] = mapped_column(String(100))
    delivery_location: Mapped[Optional[str]] = mapped_column(String(200))

    # Classification
    category_name: Mapped[Optional[str]] = mapped_column(String(300), index=True)
    category_code: Mapped[Optional[str]] = mapped_column(String(50))
    commodity_code: Mapped[Optional[str]] = mapped_column(String(50))

    # Status and compliance
    is_compliant: Mapped[bool] = mapped_column(Boolean, default=True)
    compliance_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    # Flexible storage for item-specific data
    properties: Mapped[Optional[dict]] = mapped_column(JSONB)
    technical_params: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    lot: Mapped["ProcurementLot"] = relationship(back_populates="lot_items")

    __table_args__ = (
        # Performance indexes
        Index("idx_procurement_items_lot", "lot_id"),
        Index("idx_procurement_items_product_name", "product_name"),
        Index("idx_procurement_items_brand", "brand"),
        Index("idx_procurement_items_country", "country_name"),
        Index("idx_procurement_items_category", "category_name"),
        Index("idx_procurement_items_measure", "measure_name"),
        Index("idx_procurement_items_price", "price"),
        Index("idx_procurement_items_cost", "cost"),
        Index("idx_procurement_items_updated", "updated_at"),
        # Composite indexes for common queries
        Index("idx_procurement_items_lot_item_num", "lot_id", "item_number"),
        Index(
            "idx_procurement_items_category_country", "category_name", "country_name"
        ),
        Index("idx_procurement_items_brand_model", "brand", "model"),
        Index("idx_procurement_items_lot_cost", "lot_id", "cost"),
        # Value-based indexes
        Index("idx_procurement_items_quantity_price", "quantity", "price"),
        Index("idx_procurement_items_unit_total", "unit_price", "total_value"),
        # Full-text search on product information
        Index(
            "idx_procurement_items_search",
            func.to_tsvector(
                "russian",
                func.coalesce("product_name", "")
                + " "
                + func.coalesce("description", "")
                + " "
                + func.coalesce("brand", "")
                + " "
                + func.coalesce("model", "")
                + " "
                + func.coalesce("category_name", ""),
            ),
            postgresql_using="gin",
        ),
        # JSONB indexes for flexible properties
        Index("idx_procurement_items_properties", "properties", postgresql_using="gin"),
        Index(
            "idx_procurement_items_technical",
            "technical_params",
            postgresql_using="gin",
        ),
    )


# Additional utility functions for procurement-specific features
def create_procurement_constraints():
    """
    Create additional constraints specific to procurement data.
    """
    return """
    -- Ensure positive quantities and prices
    ALTER TABLE procurement_lot_items
    ADD CONSTRAINT chk_procurement_items_quantity_positive
    CHECK (quantity IS NULL OR quantity > 0);

    ALTER TABLE procurement_lot_items
    ADD CONSTRAINT chk_procurement_items_price_positive
    CHECK (price IS NULL OR price > 0);

    ALTER TABLE procurement_lot_items
    ADD CONSTRAINT chk_procurement_items_cost_positive
    CHECK (cost IS NULL OR cost > 0);

    -- Ensure valid lot status
    ALTER TABLE procurement_lots
    ADD CONSTRAINT chk_procurement_lots_status_valid
    CHECK (status IN ('active', 'completed', 'cancelled', 'failed', 'suspended'));

    -- Ensure valid lot types
    ALTER TABLE procurement_lots
    ADD CONSTRAINT chk_procurement_lots_type_valid
    CHECK (lot_type IN ('auction', 'tender', 'shop', 'national_shop', 'framework', 'quotation'));

    -- Ensure valid organization types
    ALTER TABLE procurement_organizations
    ADD CONSTRAINT chk_procurement_orgs_type_valid
    CHECK (org_type IN ('customer', 'provider', 'both'));

    -- Ensure positive costs for lots
    ALTER TABLE procurement_lots
    ADD CONSTRAINT chk_procurement_lots_start_cost_positive
    CHECK (start_cost IS NULL OR start_cost > 0);

    ALTER TABLE procurement_lots
    ADD CONSTRAINT chk_procurement_lots_deal_cost_positive
    CHECK (deal_cost IS NULL OR deal_cost > 0);

    -- Ensure deal cost is not greater than start cost (savings calculation)
    ALTER TABLE procurement_lots
    ADD CONSTRAINT chk_procurement_lots_deal_cost_reasonable
    CHECK (start_cost IS NULL OR deal_cost IS NULL OR deal_cost <= start_cost * 1.1);
    """


def create_procurement_views():
    """
    Create useful views for procurement analytics.
    """
    return """
    -- View for active tenders with customer and provider info
    CREATE OR REPLACE VIEW active_procurement_lots AS
    SELECT
        l.*,
        c.name as customer_org_name,
        c.region as customer_region,
        c.is_government as customer_is_government,
        p.name as provider_org_name,
        p.region as provider_region,
        (l.start_cost - l.deal_cost) as savings_amount_calc,
        CASE
            WHEN l.start_cost > 0 THEN
                ROUND(((l.start_cost - l.deal_cost) / l.start_cost * 100), 2)
            ELSE NULL
        END as savings_percent_calc
    FROM procurement_lots l
    LEFT JOIN procurement_organizations c ON l.customer_id = c.id
    LEFT JOIN procurement_organizations p ON l.provider_id = p.id
    WHERE l.status = 'active';

    -- View for procurement statistics by category
    CREATE OR REPLACE VIEW procurement_category_stats AS
    SELECT
        category_name,
        COUNT(*) as lot_count,
        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
        SUM(start_cost) as total_start_cost,
        SUM(deal_cost) as total_deal_cost,
        AVG(deal_cost) as avg_deal_cost,
        SUM(start_cost - deal_cost) as total_savings,
        CASE
            WHEN SUM(start_cost) > 0 THEN
                ROUND((SUM(start_cost - deal_cost) / SUM(start_cost) * 100), 2)
            ELSE NULL
        END as avg_savings_percent
    FROM procurement_lots
    WHERE category_name IS NOT NULL AND start_cost IS NOT NULL AND deal_cost IS NOT NULL
    GROUP BY category_name;

    -- View for organization performance (providers)
    CREATE OR REPLACE VIEW procurement_provider_performance AS
    SELECT
        o.id,
        o.name,
        o.inn,
        o.region,
        COUNT(l.id) as total_bids,
        COUNT(CASE WHEN l.status = 'completed' THEN 1 END) as won_bids,
        ROUND(
            CASE WHEN COUNT(l.id) > 0 THEN
                COUNT(CASE WHEN l.status = 'completed' THEN 1 END)::float / COUNT(l.id) * 100
            ELSE 0 END, 2
        ) as win_rate_percent,
        SUM(l.deal_cost) as total_contract_value,
        AVG(l.deal_cost) as avg_contract_value,
        MIN(l.deal_date) as first_contract_date,
        MAX(l.deal_date) as latest_contract_date
    FROM procurement_organizations o
    LEFT JOIN procurement_lots l ON o.id = l.provider_id
    WHERE o.org_type IN ('provider', 'both')
    GROUP BY o.id, o.name, o.inn, o.region;

    -- View for monthly procurement trends
    CREATE OR REPLACE VIEW procurement_monthly_trends AS
    SELECT
        DATE_TRUNC('month', deal_date) as month,
        COUNT(*) as lot_count,
        SUM(deal_cost) as total_value,
        AVG(deal_cost) as avg_value,
        COUNT(CASE WHEN is_budget THEN 1 END) as budget_lot_count,
        SUM(CASE WHEN is_budget THEN deal_cost END) as budget_total_value
    FROM procurement_lots
    WHERE deal_date IS NOT NULL AND status = 'completed'
    GROUP BY DATE_TRUNC('month', deal_date)
    ORDER BY month DESC;
    """


def create_procurement_functions():
    """
    Create utility functions for procurement data processing.
    """
    return """
    -- Function to calculate procurement savings
    CREATE OR REPLACE FUNCTION calculate_procurement_savings()
    RETURNS TRIGGER AS $$
    BEGIN
        -- Calculate savings amount and percentage when deal_cost is updated
        IF NEW.start_cost IS NOT NULL AND NEW.deal_cost IS NOT NULL THEN
            NEW.savings_amount = NEW.start_cost - NEW.deal_cost;

            IF NEW.start_cost > 0 THEN
                NEW.savings_percent = ROUND(
                    (NEW.savings_amount / NEW.start_cost * 100), 2
                );
            END IF;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- Trigger to automatically calculate savings
    DROP TRIGGER IF EXISTS trg_calculate_procurement_savings ON procurement_lots;
    CREATE TRIGGER trg_calculate_procurement_savings
        BEFORE INSERT OR UPDATE ON procurement_lots
        FOR EACH ROW
        EXECUTE FUNCTION calculate_procurement_savings();

    -- Function to update organization statistics
    CREATE OR REPLACE FUNCTION update_organization_stats()
    RETURNS TRIGGER AS $$
    BEGIN
        -- Update customer organization stats
        IF NEW.customer_id IS NOT NULL THEN
            UPDATE procurement_organizations SET
                total_tenders = (
                    SELECT COUNT(*) FROM procurement_lots
                    WHERE customer_id = NEW.customer_id
                ),
                total_procurement_value = (
                    SELECT COALESCE(SUM(deal_cost), 0) FROM procurement_lots
                    WHERE customer_id = NEW.customer_id AND deal_cost IS NOT NULL
                ),
                avg_tender_value = (
                    SELECT COALESCE(AVG(deal_cost), 0) FROM procurement_lots
                    WHERE customer_id = NEW.customer_id AND deal_cost IS NOT NULL
                )
            WHERE id = NEW.customer_id;
        END IF;

        -- Update provider organization stats
        IF NEW.provider_id IS NOT NULL THEN
            UPDATE procurement_organizations SET
                total_bids = (
                    SELECT COUNT(*) FROM procurement_lots
                    WHERE provider_id = NEW.provider_id
                ),
                won_bids = (
                    SELECT COUNT(*) FROM procurement_lots
                    WHERE provider_id = NEW.provider_id AND status = 'completed'
                ),
                total_contract_value = (
                    SELECT COALESCE(SUM(deal_cost), 0) FROM procurement_lots
                    WHERE provider_id = NEW.provider_id AND deal_cost IS NOT NULL
                ),
                avg_contract_value = (
                    SELECT COALESCE(AVG(deal_cost), 0) FROM procurement_lots
                    WHERE provider_id = NEW.provider_id AND deal_cost IS NOT NULL
                )
            WHERE id = NEW.provider_id;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- Trigger to update organization stats when lots change
    DROP TRIGGER IF EXISTS trg_update_organization_stats ON procurement_lots;
    CREATE TRIGGER trg_update_organization_stats
        AFTER INSERT OR UPDATE ON procurement_lots
        FOR EACH ROW
        EXECUTE FUNCTION update_organization_stats();
    """


# Create any additional indexes or optimizations
def create_additional_indexes():
    """
    Create additional performance indexes that can't be defined in __table_args__.
    This function should be called after table creation.
    """
    return """
    -- Create partial indexes for active lots only (better performance)
    CREATE INDEX IF NOT EXISTS idx_procurement_lots_active_category
        ON procurement_lots (category_name, deal_cost)
        WHERE status = 'active';

    CREATE INDEX IF NOT EXISTS idx_procurement_lots_active_customer
        ON procurement_lots (customer_id, lot_start_date)
        WHERE status = 'active';

    -- Create indexes for common date range queries
    CREATE INDEX IF NOT EXISTS idx_procurement_lots_deal_date_cost
        ON procurement_lots (deal_date, deal_cost)
        WHERE deal_date IS NOT NULL AND deal_cost IS NOT NULL;

    -- Create composite index for savings analysis
    CREATE INDEX IF NOT EXISTS idx_procurement_lots_savings_analysis
        ON procurement_lots (category_name, start_cost, deal_cost)
        WHERE start_cost IS NOT NULL AND deal_cost IS NOT NULL;
    """
