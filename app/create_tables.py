#!/usr/bin/env python3
"""
Create all database tables using SQLAlchemy.
This script creates tables directly without Alembic migrations.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from src.core.config import settings
from src.schemas.ecommerce import EcommerceBase
from src.schemas.classifieds import ClassifiedsBase
from src.schemas.procurement import ProcurementBase


def create_ecommerce_tables():
    """Create ecommerce tables."""
    print("🛒 Creating ecommerce tables...")
    config = settings.databases.ecommerce
    url = f"postgresql://{config.user}:{config.password}@{config.host}:{config.port}/{config.name}"
    engine = create_engine(url)
    
    EcommerceBase.metadata.create_all(engine)
    
    # Verify tables
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name;
        """))
        tables = [row[0] for row in result]
        print(f"   Created tables: {', '.join(tables)}")
    
    engine.dispose()
    return len(tables)


def create_classifieds_tables():
    """Create classifieds tables."""
    print("📢 Creating classifieds tables...")
    config = settings.databases.classifieds
    url = f"postgresql://{config.user}:{config.password}@{config.host}:{config.port}/{config.name}"
    engine = create_engine(url)
    
    ClassifiedsBase.metadata.create_all(engine)
    
    # Verify tables
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name;
        """))
        tables = [row[0] for row in result]
        print(f"   Created tables: {', '.join(tables)}")
    
    engine.dispose()
    return len(tables)


def create_procurement_tables():
    """Create procurement tables."""
    print("🏛️ Creating procurement tables...")
    config = settings.databases.procurement
    url = f"postgresql://{config.user}:{config.password}@{config.host}:{config.port}/{config.name}"
    engine = create_engine(url)
    
    ProcurementBase.metadata.create_all(engine)
    
    # Verify tables
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name;
        """))
        tables = [row[0] for row in result]
        print(f"   Created tables: {', '.join(tables)}")
    
    engine.dispose()
    return len(tables)


def main():
    print("=" * 60)
    print("🚀 CREATING ALL DATABASE TABLES")
    print("=" * 60)
    print()
    
    total = 0
    
    try:
        total += create_ecommerce_tables()
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    try:
        total += create_classifieds_tables()
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    try:
        total += create_procurement_tables()
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("=" * 60)
    print(f"✅ TOTAL TABLES CREATED: {total}")
    print("=" * 60)


if __name__ == "__main__":
    main()
