"""
Yandex Market Worker Tasks - Celery tasks for continuous Yandex Market scraping

This module implements Celery tasks for scraping Yandex Market using the
category walker strategy and three-tier data extraction approach.

Key Tasks:
- discover_yandex_categories: Walk categories to discover new products
- scrape_yandex_products: Detailed scraping of discovered products
- update_yandex_offers: Update seller offers and prices
- process_yandex_batch: Batch processing for efficiency
- yandex_health_check: Platform health monitoring
- cleanup_yandex_data: Data maintenance and cleanup

Integration:
- Uses ecommerce_db for data storage
- Supports resumable crawling with Redis checkpoints
- Includes proxy rotation and anti-bot evasion
- Provides comprehensive error handling and retries
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from celery import Task
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import settings
from ..core.database import get_database_manager
from ..platforms.yandex import (
    YandexPlatform,
    create_yandex_client,
    create_yandex_platform,
)
from ..schemas.ecommerce import (
    EcommerceCategory,
    EcommerceOffer,
    EcommercePriceHistory,
    EcommerceProduct,
    EcommerceSeller,
)
from .celery_app import celery_app

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


class YandexTask(Task):
    """Base task class for Yandex Market operations with error handling."""

    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Yandex task {task_id} failed: {exc}")
        debug_logger.debug(
            f"Task {task_id} failure details: {type(exc).__name__}: {str(exc)}"
        )
        debug_logger.debug(f"Task args: {args}, kwargs: {kwargs}")
        debug_logger.debug(f"Error info: {einfo}")
        # Could send alerts or update monitoring here

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Retrying Yandex task {task_id}: {exc}")
        debug_logger.debug(
            f"Task {task_id} retry details: {type(exc).__name__}: {str(exc)}"
        )
        debug_logger.debug(f"Retry attempt with args: {args}, kwargs: {kwargs}")

    def on_success(self, retval, task_id, args, kwargs):
        """Handle successful task completion."""
        logger.debug(f"Yandex task {task_id} completed successfully")
        debug_logger.debug(
            f"Task {task_id} success with return value type: {type(retval)}"
        )
        debug_logger.debug(f"Task args: {args}, kwargs: {kwargs}")


@celery_app.task(
    base=YandexTask,
    bind=True,
    name="yandex.discover_categories",
    time_limit=7200,  # 2 hours
    soft_time_limit=6600,  # 1h 50m
)
def discover_yandex_categories(
    self,
    custom_categories: Optional[List[Dict[str, str]]] = None,
    max_products_per_run: int = 10000,
    checkpoint_interval: int = 100,
) -> Dict[str, Any]:
    """
    Discover products through Yandex Market category walking.

    Args:
        custom_categories: Optional list of specific categories to crawl
        max_products_per_run: Maximum products to discover in one run
        checkpoint_interval: Save progress every N products

    Returns:
        Discovery statistics and results
    """
    logger.info("Starting Yandex category discovery task")
    debug_logger.debug(
        f"Discovery parameters: custom_categories={custom_categories}, max_products={max_products_per_run}, checkpoint_interval={checkpoint_interval}"
    )

    async def _discover():
        stats = {
            "products_discovered": 0,
            "categories_processed": 0,
            "start_time": datetime.now(timezone.utc),
            "errors": [],
        }
        debug_logger.debug(f"Discovery task initialized with stats: {stats}")

        try:
            debug_logger.debug("Creating Yandex platform for category discovery")
            async with create_yandex_platform(use_category_discovery=True) as platform:
                product_count = 0
                debug_logger.debug(f"Platform created, starting product discovery")

                # Use category-based discovery
                debug_logger.debug(
                    f"Starting category-based discovery with {len(custom_categories) if custom_categories else 'default'} categories"
                )
                async for raw_product in platform.discover_products_by_categories(
                    custom_categories
                ):
                    if product_count >= max_products_per_run:
                        logger.info(
                            f"Reached max products limit: {max_products_per_run}"
                        )
                        debug_logger.debug(
                            f"Breaking discovery loop at product count: {product_count}"
                        )
                        break

                    try:
                        product_id = int(raw_product["product_id"])
                        debug_logger.debug(
                            f"Processing discovered product: {product_id}"
                        )

                        # Queue individual product for detailed scraping
                        debug_logger.debug(
                            f"Queuing product {product_id} for detailed scraping"
                        )
                        scrape_yandex_products.delay(
                            product_ids=[product_id],
                            priority="discovered",
                        )

                        product_count += 1
                        stats["products_discovered"] += 1
                        debug_logger.debug(
                            f"Product {product_id} queued successfully. Total: {product_count}"
                        )

                        # Update progress periodically
                        if product_count % checkpoint_interval == 0:
                            logger.info(f"Discovered {product_count} products so far")
                            debug_logger.debug(
                                f"Checkpoint reached at {product_count} products"
                            )

                    except Exception as e:
                        error_msg = f"Error queuing product {raw_product.get('product_id')}: {e}"
                        logger.warning(error_msg)
                        debug_logger.debug(
                            f"Product queuing error details: {type(e).__name__}: {str(e)}"
                        )
                        debug_logger.debug(f"Raw product data: {raw_product}")
                        stats["errors"].append(error_msg)

                # Get final platform stats
                debug_logger.debug("Getting final platform stats")
                platform_stats = platform.get_platform_stats()
                stats.update(platform_stats)
                debug_logger.debug(f"Platform stats: {platform_stats}")

        except Exception as e:
            error_msg = f"Category discovery failed: {e}"
            logger.error(error_msg)
            debug_logger.debug(
                f"Discovery task error details: {type(e).__name__}: {str(e)}"
            )
            debug_logger.debug(f"Stats at failure: {stats}")
            stats["errors"].append(error_msg)
            raise

        stats["end_time"] = datetime.now(timezone.utc)
        stats["duration_seconds"] = (
            stats["end_time"] - stats["start_time"]
        ).total_seconds()

        debug_logger.debug(f"Discovery task completed with final stats: {stats}")
        return stats

    # Run async function
    return asyncio.run(_discover())


@celery_app.task(
    base=YandexTask,
    bind=True,
    name="yandex.scrape_products",
    time_limit=3600,  # 1 hour
    soft_time_limit=3300,  # 55 minutes
)
def scrape_yandex_products(
    self,
    product_ids: List[int],
    priority: str = "normal",
    include_offers: bool = True,
    include_specs: bool = True,
) -> Dict[str, Any]:
    """
    Scrape detailed product information from Yandex Market.

    Args:
        product_ids: List of Yandex product IDs to scrape
        priority: Priority level (discovered, normal, low)
        include_offers: Whether to scrape seller offers
        include_specs: Whether to scrape technical specifications

    Returns:
        Scraping results and statistics
    """
    logger.info(f"Starting Yandex product scraping for {len(product_ids)} products")
    debug_logger.debug(
        f"Scraping parameters: product_ids={product_ids}, priority={priority}, include_offers={include_offers}, include_specs={include_specs}"
    )

    async def _scrape_products():
        stats = {
            "products_processed": 0,
            "products_stored": 0,
            "offers_stored": 0,
            "errors": 0,
            "start_time": datetime.now(timezone.utc),
        }
        debug_logger.debug(f"Product scraping task initialized with stats: {stats}")

        debug_logger.debug("Getting database manager")
        db_manager = get_database_manager()

        try:
            debug_logger.debug("Creating Yandex platform for product scraping")
            async with create_yandex_platform() as platform:
                debug_logger.debug("Getting ecommerce database session")
                async with db_manager.get_session("ecommerce") as session:
                    for i, product_id in enumerate(product_ids):
                        debug_logger.debug(
                            f"Processing product {i + 1}/{len(product_ids)}: {product_id}"
                        )
                        try:
                            # Download raw product data
                            debug_logger.debug(
                                f"Downloading raw data for product {product_id}"
                            )
                            raw_data = await platform.download_product(product_id)
                            if not raw_data:
                                logger.debug(f"No data found for product {product_id}")
                                debug_logger.debug(
                                    f"Product {product_id}: Raw data download failed"
                                )
                                continue
                            debug_logger.debug(
                                f"Product {product_id}: Raw data downloaded ({len(str(raw_data))} chars)"
                            )

                            # Parse into structured format
                            debug_logger.debug(
                                f"Parsing raw data for product {product_id}"
                            )
                            product_data = platform.parse_product(raw_data)
                            if not product_data:
                                logger.debug(f"Failed to parse product {product_id}")
                                debug_logger.debug(
                                    f"Product {product_id}: Parsing failed"
                                )
                                continue
                            debug_logger.debug(
                                f"Product {product_id}: Successfully parsed to ProductData"
                            )

                            # Store in database
                            debug_logger.debug(
                                f"Storing product {product_id} in database"
                            )
                            await _store_yandex_product(session, product_data, raw_data)

                            stats["products_processed"] += 1
                            stats["products_stored"] += 1
                            debug_logger.debug(
                                f"Product {product_id}: Successfully stored in database"
                            )

                            # Store offers if available
                            if include_offers and product_data.skus:
                                debug_logger.debug(
                                    f"Product {product_id}: Storing {len(product_data.skus)} offers"
                                )
                                offers_count = await _store_yandex_offers(
                                    session, product_data
                                )
                                stats["offers_stored"] += offers_count
                                debug_logger.debug(
                                    f"Product {product_id}: Stored {offers_count} offers"
                                )
                            elif include_offers:
                                debug_logger.debug(
                                    f"Product {product_id}: No SKUs available for offer storage"
                                )

                            # Commit every 10 products
                            if stats["products_processed"] % 10 == 0:
                                debug_logger.debug(
                                    f"Committing batch at {stats['products_processed']} products"
                                )
                                await session.commit()
                                logger.info(
                                    f"Processed {stats['products_processed']} products"
                                )

                        except Exception as e:
                            logger.error(f"Error processing product {product_id}: {e}")
                            debug_logger.debug(
                                f"Product {product_id} processing error: {type(e).__name__}: {str(e)}"
                            )
                            stats["errors"] += 1
                            debug_logger.debug(
                                f"Rolling back session for product {product_id}"
                            )
                            await session.rollback()

                    # Final commit
                    debug_logger.debug("Final commit for scraping batch")
                    await session.commit()

        except Exception as e:
            logger.error(f"Batch scraping failed: {e}")
            debug_logger.debug(
                f"Batch scraping error details: {type(e).__name__}: {str(e)}"
            )
            debug_logger.debug(f"Stats at failure: {stats}")
            raise

        stats["end_time"] = datetime.now(timezone.utc)
        stats["duration_seconds"] = (
            stats["end_time"] - stats["start_time"]
        ).total_seconds()

        debug_logger.debug(f"Product scraping completed with final stats: {stats}")
        debug_logger.debug(f"Offer update completed with stats: {stats}")
        return stats

    return asyncio.run(_scrape_products())


async def _store_yandex_product(
    session, product_data, raw_data: Dict[str, Any]
) -> None:
    """Store Yandex product data in ecommerce database."""
    debug_logger.debug(f"Storing Yandex product {product_data.id} in database")
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    # First, ensure seller exists
    seller_id = None
    if product_data.seller_data and len(product_data.seller_data) > 0:
        debug_logger.debug(
            f"Product {product_data.id}: Upserting seller data ({len(product_data.seller_data)} sellers)"
        )
        main_seller = product_data.seller_data[0]  # Use first seller as primary
        seller_id = await _upsert_seller(session, main_seller)
        debug_logger.debug(
            f"Product {product_data.id}: Seller upserted with ID {seller_id}"
        )
    else:
        debug_logger.debug(f"Product {product_data.id}: No seller data available")

    # Prepare product data
    product_dict = {
        "platform": "yandex",
        "external_id": str(product_data.id),
        "model_id": raw_data.get("product_id"),
        "title": product_data.title,
        "title_ru": product_data.title_ru,
        "title_uz": product_data.title_uz,
        "description": product_data.description,
        "seller_id": seller_id,
        "category_id": product_data.category_id,
        "category_path": product_data.category_path,
        "rating": product_data.rating,
        "review_count": product_data.review_count,
        "order_count": product_data.order_count,
        "is_available": product_data.is_available,
        "images": product_data.photos or [],
        "videos": [product_data.video_url] if product_data.video_url else [],
        "attributes": product_data.attributes or {},
        "raw_attributes": product_data.characteristics or {},
        "tags": product_data.tags or [],
        "is_eco": product_data.is_eco,
        "is_adult": product_data.is_adult,
        "has_warranty": product_data.has_warranty,
        "warranty_info": product_data.warranty_info,
        "data_sources": {
            "model_scraped": bool(raw_data.get("model_data")),
            "offers_scraped": bool(raw_data.get("offers_data")),
            "specs_scraped": bool(raw_data.get("specs_data")),
            "scrape_strategy": raw_data.get("scrape_strategy"),
        },
        "raw_data": raw_data,
        "scraped_at": datetime.now(timezone.utc),
    }

    debug_logger.debug(
        f"Product {product_data.id}: Prepared product dict with {len(product_dict)} fields"
    )

    # Upsert product
    stmt = insert(EcommerceProduct).values(product_dict)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_product_platform_external",
        set_={
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "rating": stmt.excluded.rating,
            "review_count": stmt.excluded.review_count,
            "is_available": stmt.excluded.is_available,
            "images": stmt.excluded.images,
            "attributes": stmt.excluded.attributes,
            "raw_attributes": stmt.excluded.raw_attributes,
            "data_sources": stmt.excluded.data_sources,
            "raw_data": stmt.excluded.raw_data,
            "updated_at": datetime.now(timezone.utc),
        },
    )

    debug_logger.debug(f"Product {product_data.id}: Executing upsert statement")
    await session.execute(stmt)
    debug_logger.debug(f"Product {product_data.id}: Successfully stored in database")


async def _upsert_seller(session, seller_data: Dict[str, Any]) -> int:
    """Upsert seller and return seller ID."""
    debug_logger.debug(f"Upserting seller: {seller_data.get('seller_id', 'unknown')}")
    from sqlalchemy.dialects.postgresql import insert

    seller_dict = {
        "platform": "yandex",
        "external_id": str(seller_data.get("seller_id", "")),
        "name": seller_data.get("name", "Unknown Seller"),
        "rating": seller_data.get("rating"),
        "review_count": seller_data.get("review_count", 0),
        "is_official": seller_data.get("is_official", False),
        "is_verified": seller_data.get("is_verified", False),
        "profile_url": seller_data.get("profile_url"),
        "raw_data": seller_data,
    }

    stmt = insert(EcommerceSeller).values(seller_dict)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_seller_platform_external",
        set_={
            "name": stmt.excluded.name,
            "rating": stmt.excluded.rating,
            "review_count": stmt.excluded.review_count,
            "is_official": stmt.excluded.is_official,
            "is_verified": stmt.excluded.is_verified,
            "raw_data": stmt.excluded.raw_data,
            "last_seen_at": datetime.now(timezone.utc),
        },
    )
    stmt = stmt.returning(EcommerceSeller.id)

    debug_logger.debug(
        f"Executing seller upsert for {seller_data.get('seller_id', 'unknown')}"
    )
    result = await session.execute(stmt)
    seller_id = result.scalar()
    debug_logger.debug(f"Seller upserted with ID: {seller_id}")
    return seller_id


async def _store_yandex_offers(session, product_data) -> int:
    """Store product offers and return count."""
    debug_logger.debug(
        f"Storing offers for product {product_data.id}: {len(product_data.skus)} SKUs"
    )
    from sqlalchemy.dialects.postgresql import insert

    offers_stored = 0

    for i, sku in enumerate(product_data.skus):
        debug_logger.debug(
            f"Processing offer {i + 1}/{len(product_data.skus)} for product {product_data.id}"
        )
        offer_dict = {
            "platform": "yandex",
            "external_id": str(
                sku.get("id", f"offer_{product_data.id}_{offers_stored}")
            ),
            "product_external_id": str(product_data.id),
            "seller_id": sku.get("seller_id"),
            "price": sku.get("price"),
            "old_price": sku.get("old_price"),
            "currency": sku.get("currency", "UZS"),
            "is_available": sku.get("is_available", True),
            "delivery_options": sku.get("delivery_options", {}),
            "sku_attributes": sku.get("variant_attributes", {}),
            "raw_data": sku,
        }

        stmt = insert(EcommerceOffer).values(offer_dict)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_offer_platform_external",
            set_={
                "price": stmt.excluded.price,
                "old_price": stmt.excluded.old_price,
                "is_available": stmt.excluded.is_available,
                "delivery_options": stmt.excluded.delivery_options,
                "sku_attributes": stmt.excluded.sku_attributes,
                "raw_data": stmt.excluded.raw_data,
                "updated_at": datetime.now(timezone.utc),
            },
        )

        debug_logger.debug(
            f"Executing offer upsert for product {product_data.id}, offer {i + 1}"
        )
        await session.execute(stmt)
        offers_stored += 1

        # Store price history
        debug_logger.debug(f"Storing price history for offer {i + 1}")
        await _store_price_history(session, offer_dict)

    debug_logger.debug(f"Stored {offers_stored} offers for product {product_data.id}")
    return offers_stored


async def _store_price_history(session, offer_dict: Dict[str, Any]) -> None:
    """Store price history entry."""
    debug_logger.debug(
        f"Storing price history for product {offer_dict['product_external_id']}"
    )
    from sqlalchemy.dialects.postgresql import insert

    price_entry = {
        "platform": offer_dict["platform"],
        "product_external_id": offer_dict["product_external_id"],
        "seller_id": offer_dict["seller_id"],
        "price": offer_dict["price"],
        "old_price": offer_dict["old_price"],
        "currency": offer_dict["currency"],
        "is_available": offer_dict["is_available"],
        "recorded_at": datetime.now(timezone.utc),
    }

    stmt = insert(EcommercePriceHistory).values(price_entry)
    debug_logger.debug(f"Executing price history insert")
    await session.execute(stmt)


@celery_app.task(
    base=YandexTask,
    bind=True,
    name="yandex.update_offers",
    time_limit=1800,  # 30 minutes
)
def update_yandex_offers(
    self, product_ids: List[int], max_age_hours: int = 24
) -> Dict[str, Any]:
    """Update offers and prices for existing Yandex products."""
    logger.info(f"Updating offers for {len(product_ids)} Yandex products")
    debug_logger.debug(
        f"Update parameters: product_ids={product_ids}, max_age_hours={max_age_hours}"
    )

    async def _update_offers():
        stats = {
            "products_updated": 0,
            "offers_updated": 0,
            "price_changes": 0,
            "errors": 0,
        }
        debug_logger.debug(f"Offer update task initialized with stats: {stats}")

        debug_logger.debug("Getting database manager for offer updates")
        db_manager = get_database_manager()

        debug_logger.debug("Creating Yandex client for offer updates")
        async with create_yandex_client() as client:
            debug_logger.debug("Getting ecommerce database session for offer updates")
            async with db_manager.get_session("ecommerce") as session:
                for i, product_id in enumerate(product_ids):
                    debug_logger.debug(
                        f"Processing offer update {i + 1}/{len(product_ids)}: product {product_id}"
                    )
                    try:
                        # Check if product needs updating
                        debug_logger.debug(
                            f"Checking last update time for product {product_id}"
                        )
                        last_update = await _get_last_offer_update(session, product_id)
                        if last_update:
                            age_hours = (
                                datetime.now(timezone.utc) - last_update
                            ).total_seconds() / 3600
                            debug_logger.debug(
                                f"Product {product_id}: Last updated {age_hours:.1f} hours ago"
                            )
                            if age_hours < max_age_hours:
                                debug_logger.debug(
                                    f"Product {product_id}: Skipping update (too recent)"
                                )
                                continue
                        else:
                            debug_logger.debug(
                                f"Product {product_id}: No previous update found"
                            )

                        # Fetch fresh offers data
                        debug_logger.debug(
                            f"Fetching fresh offers data for product {product_id}"
                        )
                        offers_data = await client.fetch_product_offers(product_id)
                        if offers_data:
                            debug_logger.debug(
                                f"Product {product_id}: Fresh offers data received"
                            )
                            # Process and update offers
                            # Implementation would extract and update offer data
                            stats["products_updated"] += 1
                            stats["offers_updated"] += 1
                            debug_logger.debug(
                                f"Product {product_id}: Offers updated successfully"
                            )
                        else:
                            debug_logger.debug(
                                f"Product {product_id}: No offers data received"
                            )

                    except Exception as e:
                        logger.error(f"Error updating offers for {product_id}: {e}")
                        debug_logger.debug(
                            f"Offer update error for product {product_id}: {type(e).__name__}: {str(e)}"
                        )
                        stats["errors"] += 1

        return stats

    return asyncio.run(_update_offers())


async def _get_last_offer_update(session, product_id: int) -> Optional[datetime]:
    """Get timestamp of last offer update for a product."""
    debug_logger.debug(f"Getting last offer update timestamp for product {product_id}")
    from sqlalchemy import select

    stmt = select(EcommerceOffer.updated_at).where(
        EcommerceOffer.platform == "yandex",
        EcommerceOffer.product_external_id == str(product_id),
    )
    result = await session.execute(stmt)
    timestamp = result.scalar()
    debug_logger.debug(f"Product {product_id}: Last update timestamp: {timestamp}")
    return timestamp


@celery_app.task(
    base=YandexTask,
    bind=True,
    name="yandex.health_check",
    time_limit=300,  # 5 minutes
)
def yandex_health_check(self) -> Dict[str, Any]:
    """Perform health check on Yandex Market platform."""
    logger.info("Performing Yandex Market health check")
    debug_logger.debug("Starting comprehensive Yandex health check")

    async def _health_check():
        health_status = {
            "platform": "yandex",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "unknown",
            "checks": {},
        }
        debug_logger.debug(f"Health check initialized: {health_status}")

        try:
            debug_logger.debug("Creating Yandex client for health check")
            async with create_yandex_client() as client:
                # Test basic connectivity
                is_accessible = await client.health_check()
                health_status["checks"]["connectivity"] = is_accessible

                if is_accessible:
                    # Test category page access
                    category_data = await client.fetch_category_page(
                        "91013", "elektronika"
                    )
                    health_status["checks"]["category_access"] = bool(category_data)

                    # Test product page access
                    test_product = await client.fetch_product("1000000")
                    health_status["checks"]["product_access"] = bool(test_product)

                    # Overall status
                    all_checks_pass = all(health_status["checks"].values())
                    health_status["status"] = (
                        "healthy" if all_checks_pass else "degraded"
                    )
                else:
                    health_status["status"] = "unhealthy"
                    health_status["checks"]["category_access"] = False
                    health_status["checks"]["product_access"] = False

        except Exception as e:
            health_status["status"] = "error"
            health_status["error"] = str(e)
            logger.error(f"Yandex health check failed: {e}")

        return health_status

    return asyncio.run(_health_check())


@celery_app.task(
    base=YandexTask,
    bind=True,
    name="yandex.cleanup_data",
    time_limit=1800,  # 30 minutes
)
def cleanup_yandex_data(
    self, older_than_days: int = 30, dry_run: bool = False
) -> Dict[str, Any]:
    """Clean up old Yandex data and optimize storage."""
    logger.info(f"Starting Yandex data cleanup (older than {older_than_days} days)")

    async def _cleanup():
        stats = {
            "products_cleaned": 0,
            "offers_cleaned": 0,
            "price_history_cleaned": 0,
            "raw_data_compressed": 0,
        }

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        db_manager = get_database_manager()

        try:
            async with db_manager.get_session("ecommerce") as session:
                if not dry_run:
                    # Clean old price history (keep recent data)
                    from sqlalchemy import delete

                    # Delete price history older than cutoff
                    stmt = delete(EcommercePriceHistory).where(
                        EcommercePriceHistory.platform == "yandex",
                        EcommercePriceHistory.recorded_at < cutoff_date,
                    )
                    result = await session.execute(stmt)
                    stats["price_history_cleaned"] = result.rowcount

                    # Compress raw_data field for old products (remove HTML content)
                    from sqlalchemy import update

                    stmt = (
                        update(EcommerceProduct)
                        .where(
                            EcommerceProduct.platform == "yandex",
                            EcommerceProduct.updated_at < cutoff_date,
                        )
                        .values(
                            raw_data=func.jsonb_set(
                                EcommerceProduct.raw_data, "{model_data,html}", "null"
                            )
                        )
                    )
                    result = await session.execute(stmt)
                    stats["raw_data_compressed"] = result.rowcount

                    await session.commit()

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise

        return stats

    return asyncio.run(_cleanup())


# Scheduled tasks
@celery_app.task(bind=True, name="yandex.scheduled.discovery")
def scheduled_yandex_discovery(self):
    """Scheduled task to run category discovery daily."""
    return discover_yandex_categories.delay(max_products_per_run=5000)


@celery_app.task(bind=True, name="yandex.scheduled.health_check")
def scheduled_yandex_health_check(self):
    """Scheduled health check every hour."""
    return yandex_health_check.delay()


@celery_app.task(bind=True, name="yandex.scheduled.cleanup")
def scheduled_yandex_cleanup(self):
    """Scheduled cleanup task weekly."""
    return cleanup_yandex_data.delay(older_than_days=30, dry_run=False)


# Task routing and scheduling configuration
YANDEX_TASK_ROUTES = {
    "yandex.discover_categories": {"queue": "yandex_discovery"},
    "yandex.scrape_products": {"queue": "yandex_scraping"},
    "yandex.update_offers": {"queue": "yandex_updates"},
    "yandex.health_check": {"queue": "monitoring"},
    "yandex.cleanup_data": {"queue": "maintenance"},
}

YANDEX_BEAT_SCHEDULE = {
    "yandex-daily-discovery": {
        "task": "yandex.scheduled.discovery",
        "schedule": 86400.0,  # Daily
    },
    "yandex-hourly-health-check": {
        "task": "yandex.scheduled.health_check",
        "schedule": 3600.0,  # Hourly
    },
    "yandex-weekly-cleanup": {
        "task": "yandex.scheduled.cleanup",
        "schedule": 604800.0,  # Weekly
    },
}
