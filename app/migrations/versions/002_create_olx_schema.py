"""Create OLX schema for classifieds

Revision ID: 002_create_olx_schema
Revises: 001_create_schemas
Create Date: 2025-12-11 13:44:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_create_olx_schema'
down_revision = '001_create_schemas'
branch_labels = None
depends_on = None


def upgrade():
    # Create olx_sellers table
    op.execute("""
        CREATE TABLE IF NOT EXISTS classifieds.olx_sellers (
            id BIGSERIAL PRIMARY KEY,
            external_id VARCHAR(100) UNIQUE NOT NULL,
            source VARCHAR(50) NOT NULL DEFAULT 'olx.uz',
            
            name VARCHAR(300) NOT NULL,
            seller_type VARCHAR(20),
            rating DECIMAL(3,2),
            total_reviews INTEGER DEFAULT 0,
            total_ads INTEGER DEFAULT 0,
            location VARCHAR(200),
            
            contact_phone VARCHAR(30),
            contact_telegram VARCHAR(100),
            
            registered_since VARCHAR(50),
            last_seen TIMESTAMP,
            
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    
    # Create olx_products table
    op.execute("""
        CREATE TABLE IF NOT EXISTS classifieds.olx_products (
            id BIGSERIAL PRIMARY KEY,
            external_id VARCHAR(100) UNIQUE NOT NULL,
            source VARCHAR(50) NOT NULL DEFAULT 'olx.uz',
            category_path VARCHAR(200) NOT NULL,
            listing_type VARCHAR(20) DEFAULT 'simple',
            
            title TEXT NOT NULL,
            description TEXT,
            price DECIMAL(15,2),
            currency CHAR(3) DEFAULT 'UZS',
            location VARCHAR(200),
            url TEXT,
            
            images JSONB DEFAULT '[]',
            seller_id BIGINT REFERENCES classifieds.olx_sellers(id),
            
            -- EAV for category-specific attributes (brand, model, mileage, etc.)
            attributes JSONB DEFAULT '{}',
            
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            
            -- Full-text search
            search_vector TSVECTOR GENERATED ALWAYS AS (
                to_tsvector('russian', coalesce(title,'') || ' ' || coalesce(description,''))
            ) STORED
        );
    """)
    
    # Create indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_olx_products_external_id ON classifieds.olx_products(external_id);
        CREATE INDEX IF NOT EXISTS idx_olx_products_category ON classifieds.olx_products(category_path);
        CREATE INDEX IF NOT EXISTS idx_olx_products_price ON classifieds.olx_products(price);
        CREATE INDEX IF NOT EXISTS idx_olx_products_search ON classifieds.olx_products USING GIN(search_vector);
        CREATE INDEX IF NOT EXISTS idx_olx_products_attrs ON classifieds.olx_products USING GIN(attributes);
        CREATE INDEX IF NOT EXISTS idx_olx_products_seller ON classifieds.olx_products(seller_id);
        CREATE INDEX IF NOT EXISTS idx_olx_sellers_external_id ON classifieds.olx_sellers(external_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS classifieds.olx_products CASCADE;")
    op.execute("DROP TABLE IF EXISTS classifieds.olx_sellers CASCADE;")
