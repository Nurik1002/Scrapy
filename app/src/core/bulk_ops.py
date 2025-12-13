"""
Bulk Operations - High-performance database operations with deadlock resilience.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Type

from asyncpg.exceptions import DeadlockDetectedError
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import SKU, Category, PriceHistory, Product, Seller

# UzexLot and UzexLotItem should be imported from src.platforms.uzex.models when needed

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


# Retry decorator for deadlock handling
deadlock_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(DeadlockDetectedError),
    before_sleep=lambda retry_state: logger.warning(
        f"Deadlock detected, retrying in {retry_state.next_action.sleep} seconds... (attempt {retry_state.attempt_number})"
    ),
)


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
                    logger.warning(
                        f"Deadlock detected (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.2f}s..."
                    )
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
    session: AsyncSession, categories: List[Dict[str, Any]], platform: str = "uzum"
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
        values.append(
            {
                "id": c["id"],
                "platform": platform,
                "title": c.get("title") or "Unknown",
            }
        )

    debug_logger.debug(f"Executing bulk upsert for {len(values)} category values")
    stmt = insert(Category).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
        },
    )

    result = await session.execute(stmt)
    rowcount = result.rowcount
    debug_logger.debug(f"Categories bulk upsert completed, affected rows: {rowcount}")
    return rowcount


@deadlock_retry
async def bulk_upsert_categories(
    session: AsyncSession,
    categories: List[Dict[str, Any]],
    platform: str = "uzum",
    skip_on_contention: bool = False,
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

    debug_logger.debug(
        f"bulk_upsert_categories called with {len(categories)} categories, platform: {platform}, skip_on_contention: {skip_on_contention}"
    )

    if skip_on_contention:
        debug_logger.debug(
            "Skip on contention mode enabled, will not retry on deadlock"
        )
        # For continuous operations, skip if locked
        try:
            result = await _bulk_upsert_categories_impl(session, categories, platform)
            debug_logger.debug(
                f"Categories upsert completed without contention, result: {result}"
            )
            return result
        except DBAPIError as e:
            debug_logger.debug(
                f"DBAPIError in skip_on_contention mode: {type(e).__name__}: {str(e)}"
            )
            if "deadlock" in str(e).lower() or "lock" in str(e).lower():
                logger.debug(
                    f"Skipping {len(categories)} categories due to lock contention (skip_on_contention=True)"
                )
                debug_logger.debug(
                    "Lock contention detected, skipping categories as requested"
                )
                return 0
            raise
    else:
        debug_logger.debug("Retry on deadlock mode enabled")
        # For initial loads, retry on deadlock
        logger.info(f"Bulk upserting {len(categories)} categories for {platform}")
        result = await retry_on_deadlock(
            _bulk_upsert_categories_impl, session, categories, platform
        )
        debug_logger.debug(
            f"Categories upsert completed with retry logic, result: {result}"
        )
        return result


@deadlock_retry
async def bulk_upsert_products(
    session: AsyncSession, products: List[Dict[str, Any]], platform: str = "uzum"
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
    debug_logger.debug(
        f"Starting bulk_upsert_products with {len(products)} products, platform: {platform}"
    )
    if not products:
        debug_logger.debug("No products provided, returning 0")
        return 0

    # Deduplicate by ID (keep last occurrence to avoid CardinalityViolationError)
    original_count = len(products)
    debug_logger.debug(f"Deduplicating {original_count} products by ID")
    seen_ids = {}
    for p in products:
        seen_ids[p["id"]] = p
    products = list(seen_ids.values())
    debug_logger.debug(
        f"After deduplication: {len(products)} unique products (removed {original_count - len(products)} duplicates)"
    )

    # Prepare data
    values = []
    for p in products:
        values.append(
            {
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
            }
        )

    debug_logger.debug(f"Prepared {len(values)} product values for bulk upsert")
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
        },
    )

    debug_logger.debug("Executing products bulk upsert statement")
    result = await session.execute(stmt)
    rowcount = result.rowcount
    debug_logger.debug(f"Products bulk upsert completed, affected rows: {rowcount}")
    return rowcount


@deadlock_retry
async def bulk_upsert_sellers(
    session: AsyncSession, sellers: List[Dict[str, Any]], platform: str = "uzum"
) -> int:
    """Bulk upsert sellers."""
    debug_logger.debug(
        f"Starting bulk_upsert_sellers with {len(sellers)} sellers, platform: {platform}"
    )
    if not sellers:
        debug_logger.debug("No sellers provided, returning 0")
        return 0

    # Deduplicate by ID (keep last occurrence)
    original_count = len(sellers)
    debug_logger.debug(f"Deduplicating {original_count} sellers by ID")
    seen_ids = {}
    for s in sellers:
        seen_ids[s["id"]] = s
    sellers = list(seen_ids.values())

    # Debug logging
    debug_logger.debug(
        f"After deduplication: {len(sellers)} unique sellers (removed {original_count - len(sellers)} duplicates)"
    )
    logger.info(
        f"Deduplicating sellers: received batch, after dedup have {len(sellers)} unique sellers"
    )

    values = []
    for s in sellers:
        values.append(
            {
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
                "raw_data": s.get("raw_data"),  # FIX: Added raw_data field
                "last_seen_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

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
            "raw_data": stmt.excluded.raw_data,  # FIX: Update raw_data on conflict
            "last_seen_at": stmt.excluded.last_seen_at,
            "updated_at": stmt.excluded.updated_at,
        },
    )

    debug_logger.debug("Executing sellers bulk upsert statement")
    result = await session.execute(stmt)
    rowcount = result.rowcount
    debug_logger.debug(f"Sellers bulk upsert completed, affected rows: {rowcount}")
    return rowcount


@deadlock_retry
async def bulk_upsert_skus(session: AsyncSession, skus: List[Dict[str, Any]]) -> int:
    """Bulk upsert SKUs."""
    debug_logger.debug(f"Starting bulk_upsert_skus with {len(skus)} SKUs")
    if not skus:
        debug_logger.debug("No SKUs provided, returning 0")
        return 0

    # Deduplicate by ID (keep last occurrence)
    original_count = len(skus)
    debug_logger.debug(f"Deduplicating {original_count} SKUs by ID")
    seen_ids = {}
    for s in skus:
        seen_ids[s["id"]] = s
    skus = list(seen_ids.values())
    debug_logger.debug(
        f"After deduplication: {len(skus)} unique SKUs (removed {original_count - len(skus)} duplicates)"
    )

    values = []
    for s in skus:
        # Convert barcode to string if it's an integer
        barcode = s.get("barcode")
        if barcode is not None and not isinstance(barcode, str):
            barcode = str(barcode)

        values.append(
            {
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
            }
        )

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
        },
    )

    debug_logger.debug("Executing SKUs bulk upsert statement")
    result = await session.execute(stmt)
    rowcount = result.rowcount
    debug_logger.debug(f"SKUs bulk upsert completed, affected rows: {rowcount}")
    return rowcount


async def bulk_insert_price_history(
    session: AsyncSession, prices: List[Dict[str, Any]]
) -> int:
    """Bulk insert price history (no upsert, always insert)."""
    debug_logger.debug(
        f"Starting bulk_insert_price_history with {len(prices)} price records"
    )
    if not prices:
        debug_logger.debug("No price records provided, returning 0")
        return 0

    debug_logger.debug("Preparing price history values for bulk insert")
    values = []
    for p in prices:
        values.append(
            {
                "sku_id": p["sku_id"],
                "product_id": p["product_id"],
                "full_price": p.get("full_price"),
                "purchase_price": p.get("purchase_price"),
                "discount_percent": p.get("discount_percent"),
                "available_amount": p.get("available_amount", 0),
                "price_change": p.get("price_change"),  # FIX: Added price change
                "price_change_percent": p.get("price_change_percent"),  # FIX: Added price change percent
            }
        )

    debug_logger.debug(f"Prepared {len(values)} price history values for bulk insert")
    stmt = insert(PriceHistory).values(values)
    debug_logger.debug("Executing price history bulk insert statement")
    result = await session.execute(stmt)
    rowcount = result.rowcount
    debug_logger.debug(
        f"Price history bulk insert completed, affected rows: {rowcount}"
    )
    return rowcount


async def bulk_upsert_uzex_lots(
    session: AsyncSession, lots: List[Dict[str, Any]]
) -> int:
    """Bulk upsert UZEX lots."""
    debug_logger.debug(f"Starting bulk_upsert_uzex_lots with {len(lots)} UZEX lots")
    if not lots:
        debug_logger.debug("No UZEX lots provided, returning 0")
        return 0

    # Deduplicate by ID (keep last occurrence)
    original_count = len(lots)
    debug_logger.debug(f"Deduplicating {original_count} UZEX lots by ID")
    seen_ids = {}
    for lot in lots:
        seen_ids[lot["id"]] = lot
    lots = list(seen_ids.values())
    debug_logger.debug(
        f"After deduplication: {len(lots)} unique lots (removed {original_count - len(lots)} duplicates)"
    )

    from src.platforms.uzex.models import UzexLot

    values = []
    for lot in lots:
        values.append(
            {
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
            }
        )

    stmt = insert(UzexLot).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "deal_cost": stmt.excluded.deal_cost,
            "provider_name": stmt.excluded.provider_name,
            "provider_inn": stmt.excluded.provider_inn,
            "kazna_status": stmt.excluded.kazna_status,
            "updated_at": stmt.excluded.updated_at,
        },
    )

    debug_logger.debug("Executing UZEX lots bulk upsert statement")
    result = await session.execute(stmt)
    rowcount = result.rowcount
    debug_logger.debug(f"UZEX lots bulk upsert completed, affected rows: {rowcount}")
    return rowcount


async def bulk_insert_uzex_items(
    session: AsyncSession, items: List[Dict[str, Any]]
) -> int:
    """Bulk insert UZEX lot items."""
    debug_logger.debug(
        f"Starting bulk_insert_uzex_items with {len(items)} UZEX lot items"
    )
    if not items:
        debug_logger.debug("No UZEX lot items provided, returning 0")
        return 0

    from src.platforms.uzex.models import UzexLotItem

    debug_logger.debug("Preparing UZEX lot item values for bulk insert")
    values = []
    for item in items:
        values.append(
            {
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
            }
        )

    debug_logger.debug(f"Prepared {len(values)} UZEX lot item values for bulk insert")
    stmt = insert(UzexLotItem).values(values)
    debug_logger.debug("Executing UZEX lot items bulk insert statement")
    result = await session.execute(stmt)
    rowcount = result.rowcount
    debug_logger.debug(
        f"UZEX lot items bulk insert completed, affected rows: {rowcount}"
    )
    return rowcount
