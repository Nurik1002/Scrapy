"""
Bulk Operations - High-performance database operations.
"""
import logging
import asyncio
from typing import List, Dict, Any, Type
from datetime import datetime, timezone


from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError

from .models import Product, Seller, Category, SKU, PriceHistory
# UzexLot and UzexLotItem should be imported from src.platforms.uzex.models when needed

logger = logging.getLogger(__name__)


async def retry_on_deadlock(func, *args, max_retries=5, initial_delay=0.1, **kwargs):
    """
    Retry async function on deadlock with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (doubles each retry)

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except DBAPIError as e:
            error_str = str(e)
            # Check for deadlock or lock timeout errors
            if "deadlock detected" in error_str.lower() or "lock" in error_str.lower():
                last_exception = e
                if attempt < max_retries - 1:
                    # Add jitter to prevent thundering herd
                    jitter = delay * 0.5 * (0.5 + asyncio.get_event_loop().time() % 1.0)
                    wait_time = delay + jitter
                    logger.warning(f"Deadlock detected (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded for deadlock")
                    raise
            else:
                # Not a deadlock, re-raise immediately
                raise

    # Should never reach here, but just in case
    if last_exception:
        raise last_exception


async def _bulk_upsert_categories_impl(
    session: AsyncSession,
    categories: List[Dict[str, Any]],
    platform: str = "uzum"
) -> int:
    """
    Internal implementation of bulk category upsert.
    Use bulk_upsert_categories() which includes retry logic.
    """
    if not categories:
        return 0

    # Deduplicate by ID (keep last occurrence)
    seen_ids = {}
    for c in categories:
        seen_ids[c["id"]] = c
    categories = list(seen_ids.values())

    # Simple upsert using ON CONFLICT - minimal fields to avoid errors
    values = []
    for c in categories:
        values.append({
            "id": c["id"],
            "platform": platform,
            "title": c.get("title") or "Unknown",
        })

    stmt = insert(Category).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
        }
    )

    result = await session.execute(stmt)
    return result.rowcount


async def bulk_upsert_categories(
    session: AsyncSession,
    categories: List[Dict[str, Any]],
    platform: str = "uzum",
    skip_on_contention: bool = False
) -> int:
    """
    Bulk upsert categories with deadlock retry logic.

    Args:
        session: Database session
        categories: List of category dicts with 'id' and 'title'
        platform: Platform name
        skip_on_contention: If True, skip and return 0 on deadlock (for continuous scraping)

    Returns:
        Number of rows affected (0 if skipped)
    """
    if not categories:
        return 0

    if skip_on_contention:
        # During continuous scraping, categories rarely change, so skip on contention
        try:
            return await _bulk_upsert_categories_impl(session, categories, platform)
        except DBAPIError as e:
            if "deadlock" in str(e).lower() or "lock" in str(e).lower():
                logger.debug(f"Skipping {len(categories)} categories due to lock contention (skip_on_contention=True)")
                return 0
            raise
    else:
        # For initial loads, retry on deadlock
        logger.info(f"Bulk upserting {len(categories)} categories for {platform}")
        return await retry_on_deadlock(_bulk_upsert_categories_impl, session, categories, platform)


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
    
    # Deduplicate by ID (keep last occurrence to avoid CardinalityViolationError)
    seen_ids = {}
    for p in products:
        seen_ids[p["id"]] = p
    products = list(seen_ids.values())
    
    # Prepare data
    values = []
    for p in products:
        values.append({
            "id": p["id"],
            "platform": platform,
            "title": p.get("title"),
            "title_normalized": p.get("title_normalized"),
            "title_ru": p.get("title_ru"),
            "title_uz": p.get("title_uz"),
            "category_id": p.get("category_id"),
            "seller_id": p.get("seller_id"),
            "rating": p.get("rating"),
            "review_count": p.get("review_count"),
            "order_count": p.get("order_count"),
            "is_available": p.get("is_available", True),
            "total_available": p.get("total_available", 0),
            "description": p.get("description"),
            "photos": p.get("photos"),
            "video_url": p.get("video_url"),
            "attributes": p.get("attributes"),
            "characteristics": p.get("characteristics"),
            "tags": p.get("tags"),
            "is_eco": p.get("is_eco", False),
            "is_adult": p.get("is_adult", False),
            "is_perishable": p.get("is_perishable", False),
            "has_warranty": p.get("has_warranty", False),
            "warranty_info": p.get("warranty_info"),
            "raw_data": p.get("raw_data"),
            "last_seen_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
    
    stmt = insert(Product).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
            "title_normalized": stmt.excluded.title_normalized,
            "title_ru": stmt.excluded.title_ru,
            "title_uz": stmt.excluded.title_uz,
            "rating": stmt.excluded.rating,
            "review_count": stmt.excluded.review_count,
            "order_count": stmt.excluded.order_count,
            "is_available": stmt.excluded.is_available,
            "total_available": stmt.excluded.total_available,
            "description": stmt.excluded.description,
            "photos": stmt.excluded.photos,
            "video_url": stmt.excluded.video_url,
            "attributes": stmt.excluded.attributes,
            "characteristics": stmt.excluded.characteristics,
            "tags": stmt.excluded.tags,
            "is_eco": stmt.excluded.is_eco,
            "is_adult": stmt.excluded.is_adult,
            "is_perishable": stmt.excluded.is_perishable,
            "has_warranty": stmt.excluded.has_warranty,
            "warranty_info": stmt.excluded.warranty_info,
            "raw_data": stmt.excluded.raw_data,
            "last_seen_at": stmt.excluded.last_seen_at,
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
    
    # Deduplicate by ID (keep last occurrence)
    seen_ids = {}
    for s in sellers:
        seen_ids[s["id"]] = s
    sellers = list(seen_ids.values())
    
    # Debug logging
    original_count = len([s for s in sellers])  # This line will be after dedup
    logger.info(f"Deduplicating sellers: received batch, after dedup have {len(sellers)} unique sellers")
    
    values = []
    for s in sellers:
        values.append({
            "id": s["id"],
            "platform": platform,
            "title": s.get("title"),
            "link": s.get("link"),
            "description": s.get("description"),
            "rating": s.get("rating"),
            "review_count": s.get("review_count", 0),
            "order_count": s.get("order_count", 0),
            "total_products": s.get("total_products", 0),
            "is_official": s.get("is_official", False),
            "registration_date": s.get("registration_date"),
            "account_id": s.get("account_id"),
            "last_seen_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
    
    stmt = insert(Seller).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "rating": stmt.excluded.rating,
            "review_count": stmt.excluded.review_count,
            "order_count": stmt.excluded.order_count,
            "total_products": stmt.excluded.total_products,
            "is_official": stmt.excluded.is_official,
            "registration_date": stmt.excluded.registration_date,
            "last_seen_at": stmt.excluded.last_seen_at,
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
    
    # Deduplicate by ID (keep last occurrence)
    seen_ids = {}
    for s in skus:
        seen_ids[s["id"]] = s
    skus = list(seen_ids.values())
    
    values = []
    for s in skus:
        # Convert barcode to string if it's an integer
        barcode = s.get("barcode")
        if barcode is not None and not isinstance(barcode, str):
            barcode = str(barcode)
        
        values.append({
            "id": s["id"],
            "product_id": s["product_id"],
            "full_price": s.get("full_price"),
            "purchase_price": s.get("purchase_price"),
            "discount_percent": s.get("discount_percent"),
            "available_amount": s.get("available_amount", 0),
            "barcode": barcode,
            "characteristics": s.get("characteristics"),
            "last_seen_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
    
    stmt = insert(SKU).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "full_price": stmt.excluded.full_price,
            "purchase_price": stmt.excluded.purchase_price,
            "discount_percent": stmt.excluded.discount_percent,
            "available_amount": stmt.excluded.available_amount,
            "last_seen_at": stmt.excluded.last_seen_at,
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
    
    # Deduplicate by ID (keep last occurrence)
    seen_ids = {}
    for lot in lots:
        seen_ids[lot["id"]] = lot
    lots = list(seen_ids.values())
    
    from src.platforms.uzex.models import UzexLot
    
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
            "updated_at": datetime.utcnow(),
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
    
    from src.platforms.uzex.models import UzexLotItem
    
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
