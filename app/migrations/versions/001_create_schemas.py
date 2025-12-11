"""Create schemas and migrate tables

Revision ID: 001
Revises: 
Create Date: 2025-12-11

This migration:
1. Creates three PostgreSQL schemas: ecommerce, classifieds, procurement
2. Moves existing tables to appropriate schemas
3. Sets default search_path for the database
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_create_schemas'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create schemas and migrate tables."""
    
    # ==========================================================================
    # STEP 1: Create schemas
    # ==========================================================================
    op.execute("CREATE SCHEMA IF NOT EXISTS ecommerce")
    op.execute("CREATE SCHEMA IF NOT EXISTS classifieds")
    op.execute("CREATE SCHEMA IF NOT EXISTS procurement")
    
    print("✅ Created schemas: ecommerce, classifieds, procurement")
    
    # ==========================================================================
    # STEP 2: Move B2C tables to ecommerce schema
    # ==========================================================================
    ecommerce_tables = [
        'products',
        'sellers', 
        'categories',
        'skus',
        'price_history',
        'product_sellers',
        'raw_snapshots',
        'seller_daily_stats',
    ]
    
    for table in ecommerce_tables:
        try:
            op.execute(f"ALTER TABLE IF EXISTS public.{table} SET SCHEMA ecommerce")
            print(f"   ✅ Moved {table} → ecommerce")
        except Exception as e:
            print(f"   ⚠️  Table {table} not found or already moved: {e}")
    
    # ==========================================================================
    # STEP 3: Move UZEX tables to procurement schema
    # ==========================================================================
    procurement_tables = [
        'uzex_lots',
        'uzex_lot_items',
        'uzex_categories',
        'uzex_products',
        'uzex_daily_stats',
    ]
    
    for table in procurement_tables:
        try:
            op.execute(f"ALTER TABLE IF EXISTS public.{table} SET SCHEMA procurement")
            print(f"   ✅ Moved {table} → procurement")
        except Exception as e:
            print(f"   ⚠️  Table {table} not found or already moved: {e}")
    
    # ==========================================================================
    # STEP 4: Set default search_path for database
    # ==========================================================================
    # This ensures queries work without schema prefix
    op.execute("""
        ALTER DATABASE uzum_scraping 
        SET search_path TO ecommerce, procurement, classifieds, public
    """)
    
    print("✅ Set database search_path to: ecommerce, procurement, classifieds, public")
    print("🎉 Migration complete!")


def downgrade() -> None:
    """Reverse migration - move tables back to public schema."""
    
    # Move ecommerce tables back
    ecommerce_tables = [
        'products', 'sellers', 'categories', 'skus', 
        'price_history', 'product_sellers', 'raw_snapshots', 'seller_daily_stats'
    ]
    for table in ecommerce_tables:
        try:
            op.execute(f"ALTER TABLE IF EXISTS ecommerce.{table} SET SCHEMA public")
        except:
            pass
    
    # Move procurement tables back
    procurement_tables = [
        'uzex_lots', 'uzex_lot_items', 'uzex_categories', 
        'uzex_products', 'uzex_daily_stats'
    ]
    for table in procurement_tables:
        try:
            op.execute(f"ALTER TABLE IF EXISTS procurement.{table} SET SCHEMA public")
        except:
            pass
    
    # Reset search_path
    op.execute("ALTER DATABASE uzum_scraping SET search_path TO public")
    
    # Drop schemas
    op.execute("DROP SCHEMA IF EXISTS ecommerce CASCADE")
    op.execute("DROP SCHEMA IF EXISTS classifieds CASCADE")
    op.execute("DROP SCHEMA IF EXISTS procurement CASCADE")
    
    print("⬇️ Downgrade complete - tables moved back to public schema")
