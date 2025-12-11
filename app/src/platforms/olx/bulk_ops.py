"""
Bulk database operations for OLX platform
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from .models import OLXProduct, OLXSeller

logger = logging.getLogger(__name__)


async def bulk_upsert_olx_sellers(session: AsyncSession, sellers: List[Dict[str, Any]]) -> int:
    """
    Bulk upsert OLX sellers.
    
    Args:
        session: Database session
        sellers: List of seller dicts
    
    Returns:
        Number of sellers upserted
    """
    if not sellers:
        return 0
    
    stmt = insert(OLXSeller).values(sellers)
    stmt = stmt.on_conflict_do_update(
        index_elements=['external_id'],
        set_={
            'name': stmt.excluded.name,
            'seller_type': stmt.excluded.seller_type,
            'rating': stmt.excluded.rating,
            'total_reviews': stmt.excluded.total_reviews,
            'total_ads': stmt.excluded.total_ads,
            'location': stmt.excluded.location,
            'contact_phone': stmt.excluded.contact_phone,
            'contact_telegram': stmt.excluded.contact_telegram,
            'last_seen': stmt.excluded.last_seen,
            'updated_at': stmt.excluded.updated_at,
        }
    )
    
    await session.execute(stmt)
    logger.info(f"Upserted {len(sellers)} OLX sellers")
    return len(sellers)


async def bulk_upsert_olx_products(session: AsyncSession, products: List[Dict[str, Any]]) -> int:
    """
    Bulk upsert OLX products.
    
    Args:
        session: Database session
        products: List of product dicts
    
    Returns:
        Number of products upserted
    """
    if not products:
        return 0
    
    stmt = insert(OLXProduct).values(products)
    stmt = stmt.on_conflict_do_update(
        index_elements=['external_id'],
        set_={
            'title': stmt.excluded.title,
            'description': stmt.excluded.description,
            'price': stmt.excluded.price,
            'currency': stmt.excluded.currency,
            'location': stmt.excluded.location,
            'url': stmt.excluded.url,
            'images': stmt.excluded.images,
            'attributes': stmt.excluded.attributes,
            'status': stmt.excluded.status,
            'updated_at': stmt.excluded.updated_at,
        }
    )
    
    await session.execute(stmt)
    logger.info(f"Upserted {len(products)} OLX products")
    return len(products)


async def get_seller_by_external_id(session: AsyncSession, external_id: str) -> int:
    """
    Get seller ID by external ID.
    
    Args:
        session: Database session
        external_id: OLX seller external ID
        
    Returns:
        Seller database ID or None
    """
    from sqlalchemy import select
    
    stmt = select(OLXSeller.id).where(OLXSeller.external_id == external_id)
    result = await session.execute(stmt)
    seller_id = result.scalar()
    return seller_id
