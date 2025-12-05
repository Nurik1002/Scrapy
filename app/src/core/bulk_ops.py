"""
Bulk Operations - High-performance database operations.
"""
import logging
from typing import List, Dict, Any, Type
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Product, Seller, Category, SKU, PriceHistory, UzexLot, UzexLotItem

logger = logging.getLogger(__name__)


async def bulk_upsert_products(
    session: AsyncSession,
    products: List[Dict[str, Any]],
    platform: str = "uzum"
) -> int:
    """
    Bulk upsert products using PostgreSQL ON CONFLICT.
    
    5x faster than individual merges.
    
    Args:
        session: Database session
        products: List of product dicts
        platform: Platform name
        
    Returns:
        Number of rows affected
    """
    if not products:
        return 0
    
    # Prepare data
    values = []
    for p in products:
        values.append({
            "id": p["id"],
            "platform": platform,
            "title": p.get("title"),
            "title_normalized": p.get("title_normalized"),
            "category_id": p.get("category_id"),
            "seller_id": p.get("seller_id"),
            "rating": p.get("rating"),
            "review_count": p.get("review_count"),
            "order_count": p.get("order_count"),
            "is_available": p.get("is_available", True),
            "total_available": p.get("total_available", 0),
            "description": p.get("description"),
            "photos": p.get("photos"),
            "raw_data": p.get("raw_data"),
            "updated_at": datetime.now(timezone.utc),
        })
    
    stmt = insert(Product).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
            "title_normalized": stmt.excluded.title_normalized,
            "rating": stmt.excluded.rating,
            "review_count": stmt.excluded.review_count,
            "order_count": stmt.excluded.order_count,
            "is_available": stmt.excluded.is_available,
            "total_available": stmt.excluded.total_available,
            "raw_data": stmt.excluded.raw_data,
            "updated_at": stmt.excluded.updated_at,
        }
    )
    
    result = await session.execute(stmt)
    return result.rowcount


async def bulk_upsert_sellers(
    session: AsyncSession,
    sellers: List[Dict[str, Any]],
    platform: str = "uzum"
) -> int:
    """Bulk upsert sellers."""
    if not sellers:
        return 0
    
    values = []
    for s in sellers:
        values.append({
            "id": s["id"],
            "platform": platform,
            "title": s.get("title"),
            "link": s.get("link"),
            "rating": s.get("rating"),
            "review_count": s.get("review_count", 0),
            "order_count": s.get("order_count", 0),
            "account_id": s.get("account_id"),
            "updated_at": datetime.now(timezone.utc),
        })
    
    stmt = insert(Seller).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
            "rating": stmt.excluded.rating,
            "review_count": stmt.excluded.review_count,
            "order_count": stmt.excluded.order_count,
            "updated_at": stmt.excluded.updated_at,
        }
    )
    
    result = await session.execute(stmt)
    return result.rowcount


async def bulk_upsert_skus(
    session: AsyncSession,
    skus: List[Dict[str, Any]]
) -> int:
    """Bulk upsert SKUs."""
    if not skus:
        return 0
    
    values = []
    for s in skus:
        values.append({
            "id": s["id"],
            "product_id": s["product_id"],
            "full_price": s.get("full_price"),
            "purchase_price": s.get("purchase_price"),
            "discount_percent": s.get("discount_percent"),
            "available_amount": s.get("available_amount", 0),
            "barcode": s.get("barcode"),
            "characteristics": s.get("characteristics"),
            "updated_at": datetime.now(timezone.utc),
        })
    
    stmt = insert(SKU).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "full_price": stmt.excluded.full_price,
            "purchase_price": stmt.excluded.purchase_price,
            "discount_percent": stmt.excluded.discount_percent,
            "available_amount": stmt.excluded.available_amount,
            "updated_at": stmt.excluded.updated_at,
        }
    )
    
    result = await session.execute(stmt)
    return result.rowcount


async def bulk_insert_price_history(
    session: AsyncSession,
    prices: List[Dict[str, Any]]
) -> int:
    """Bulk insert price history (no upsert, always insert)."""
    if not prices:
        return 0
    
    values = []
    for p in prices:
        values.append({
            "sku_id": p["sku_id"],
            "product_id": p["product_id"],
            "full_price": p.get("full_price"),
            "purchase_price": p.get("purchase_price"),
            "discount_percent": p.get("discount_percent"),
            "available_amount": p.get("available_amount", 0),
        })
    
    stmt = insert(PriceHistory).values(values)
    result = await session.execute(stmt)
    return result.rowcount


async def bulk_upsert_uzex_lots(
    session: AsyncSession,
    lots: List[Dict[str, Any]]
) -> int:
    """Bulk upsert UZEX lots."""
    if not lots:
        return 0
    
    values = []
    for lot in lots:
        values.append({
            "id": lot["id"],
            "display_no": lot.get("display_no"),
            "lot_type": lot.get("lot_type", "auction"),
            "status": lot.get("status", "completed"),
            "is_budget": lot.get("is_budget", False),
            "type_name": lot.get("type_name"),
            "start_cost": lot.get("start_cost"),
            "deal_cost": lot.get("deal_cost"),
            "currency_name": lot.get("currency_name", "Сом"),
            "customer_name": lot.get("customer_name"),
            "customer_inn": lot.get("customer_inn"),
            "provider_name": lot.get("provider_name"),
            "provider_inn": lot.get("provider_inn"),
            "deal_id": lot.get("deal_id"),
            "deal_date": lot.get("deal_date"),
            "category_name": lot.get("category_name"),
            "pcp_count": lot.get("pcp_count", 0),
            "lot_start_date": lot.get("lot_start_date"),
            "lot_end_date": lot.get("lot_end_date"),
            "kazna_status": lot.get("kazna_status"),
            "raw_data": lot.get("raw_data"),
            "updated_at": datetime.now(timezone.utc),
        })
    
    stmt = insert(UzexLot).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "deal_cost": stmt.excluded.deal_cost,
            "provider_name": stmt.excluded.provider_name,
            "provider_inn": stmt.excluded.provider_inn,
            "kazna_status": stmt.excluded.kazna_status,
            "updated_at": stmt.excluded.updated_at,
        }
    )
    
    result = await session.execute(stmt)
    return result.rowcount


async def bulk_insert_uzex_items(
    session: AsyncSession,
    items: List[Dict[str, Any]]
) -> int:
    """Bulk insert UZEX lot items."""
    if not items:
        return 0
    
    values = []
    for item in items:
        values.append({
            "lot_id": item["lot_id"],
            "order_num": item.get("order_num"),
            "product_name": item.get("product_name"),
            "description": item.get("description"),
            "quantity": item.get("quantity"),
            "amount": item.get("amount"),
            "measure_name": item.get("measure_name"),
            "price": item.get("price"),
            "cost": item.get("cost"),
            "country_name": item.get("country_name"),
            "properties": item.get("properties"),
        })
    
    stmt = insert(UzexLotItem).values(values)
    result = await session.execute(stmt)
    return result.rowcount
