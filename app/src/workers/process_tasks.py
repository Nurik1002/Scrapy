"""
Process Tasks - Celery tasks for processing raw data.
"""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3)
def process_pending(self, platform: str, batch_size: int = 100) -> dict:
    """
    Process pending raw snapshots from database.
    
    Args:
        platform: Platform name
        batch_size: Number of records to process
        
    Returns:
        Processing statistics
    """
    from src.core.database import get_session
    from src.core.models import RawSnapshot, Product, Seller, Category, SKU, PriceHistory
    
    if platform == "uzum":
        from src.platforms.uzum import parser
    else:
        raise ValueError(f"Unknown platform: {platform}")
    
    async def do_process():
        stats = {"processed": 0, "success": 0, "errors": 0}
        
        async with get_session() as session:
            # Get pending snapshots
            result = await session.execute(
                select(RawSnapshot)
                .where(RawSnapshot.platform == platform)
                .where(RawSnapshot.processed == False)
                .limit(batch_size)
            )
            snapshots = result.scalars().all()
            
            if not snapshots:
                return stats

            # Buffers for bulk operations
            from src.core.bulk_ops import (
                bulk_upsert_products, 
                bulk_upsert_sellers, 
                bulk_upsert_skus, 
                bulk_insert_price_history
            )
            
            products_buffer = []
            sellers_buffer = []
            skus_buffer = []
            prices_buffer = []
            categories_buffer = [] # Categories are still individual mostly due to hierarchy, or can be bulked too
            # For simplicity, let's keep categories individual or add bulk op later. 
            # Actually, let's just do categories individually for now as they are fewer.
            
            snapshot_map = {} # Map valid parsed data back to snapshot for status update
            
            from src.core.models import Category
            
            for snapshot in snapshots:
                try:
                    parsed = parser.parse_product(snapshot.raw_json)
                    if not parsed:
                        continue
                        
                    # Prepare product dict
                    p_data = {
                        "id": parsed.id,
                        "title": parsed.title,
                        "title_normalized": parser.normalize_title(parsed.title),
                        "category_id": parsed.category_id,
                        "seller_id": parsed.seller_id,
                        "rating": parsed.rating,
                        "review_count": parsed.review_count,
                        "order_count": parsed.order_count,
                        "is_available": parsed.is_available,
                        "total_available": parsed.total_available,
                        "description": parsed.description,
                        "photos": parsed.photos,
                        "raw_data": parsed.raw_data,
                    }
                    products_buffer.append(p_data)
                    
                    # Prepare seller dict
                    if parsed.seller_data:
                        s_data = {
                            "id": parsed.seller_id,
                            "title": parsed.seller_title,
                            **{k: v for k, v in parsed.seller_data.items() 
                               if k in ['link', 'rating', 'description', 'account_id', 'reviews', 'orders']}
                        }
                        # Normalize keys for bulk op
                        if 'reviews' in s_data: s_data['review_count'] = s_data.pop('reviews')
                        if 'orders' in s_data: s_data['order_count'] = s_data.pop('orders')
                        sellers_buffer.append(s_data)

                    # Upsert categories (still individual for now to ensure consistency)
                    for cat_data in (parsed.category_path or []):
                        cat = Category(
                            id=cat_data['id'],
                            platform=platform,
                            title=cat_data['title'],
                        )
                        await session.merge(cat)

                    # Prepare SKUs and Prices
                    for sku_data in (parsed.skus or []):
                        sku_entry = {
                            "id": sku_data['id'],
                            "product_id": parsed.id,
                            "full_price": sku_data.get('full_price'),
                            "purchase_price": sku_data.get('purchase_price'),
                            "discount_percent": sku_data.get('discount_percent'),
                            "available_amount": sku_data.get('available_amount', 0),
                            "barcode": sku_data.get('barcode'),
                            "characteristics": sku_data.get('characteristics'),
                        }
                        skus_buffer.append(sku_entry)
                        
                        price_entry = {
                            "sku_id": sku_data['id'],
                            "product_id": parsed.id,
                            "full_price": sku_data.get('full_price'),
                            "purchase_price": sku_data.get('purchase_price'),
                            "discount_percent": sku_data.get('discount_percent'),
                            "available_amount": sku_data.get('available_amount', 0),
                        }
                        prices_buffer.append(price_entry)
                    
                    # Track successful parse
                    snapshot_map[snapshot.id] = snapshot
                    stats["success"] += 1
                    
                except Exception as e:
                    logger.error(f"Error parsing snapshot {snapshot.id}: {e}")
                    stats["errors"] += 1
                
                stats["processed"] += 1
            
            # Execute Bulk Operations
            if sellers_buffer:
                await bulk_upsert_sellers(session, sellers_buffer, platform)
            
            if products_buffer:
                await bulk_upsert_products(session, products_buffer, platform)
                
            if skus_buffer:
                await bulk_upsert_skus(session, skus_buffer)
                
            if prices_buffer:
                await bulk_insert_price_history(session, prices_buffer)
            
            # Update snapshots status
            for snap_id, snapshot in snapshot_map.items():
                snapshot.processed = True
                snapshot.processed_at = datetime.now(timezone.utc)
            
            await session.commit()
        
        return stats
    
    return run_async(do_process())


@shared_task
def process_raw_files(platform: str, directory: str = None) -> dict:
    """
    Process raw JSON files from storage.
    
    Args:
        platform: Platform name
        directory: Directory path (optional)
        
    Returns:
        Processing statistics
    """
    from src.core.config import RAW_STORAGE_DIR
    from src.core.database import get_session
    from src.core.models import Product, Seller, Category, SKU, PriceHistory
    
    if platform == "uzum":
        from src.platforms.uzum import parser
    else:
        raise ValueError(f"Unknown platform: {platform}")
    
    # Find latest directory
    products_dir = Path(directory) if directory else RAW_STORAGE_DIR / "products"
    if not products_dir.exists():
        return {"error": "Directory not found"}
    
    # Get all JSON files
    if products_dir.is_file():
        json_files = [products_dir]
    else:
        # Find most recent date folder
        date_folders = sorted(products_dir.glob("2*"))
        if not date_folders:
            return {"error": "No date folders found"}
        json_files = list(date_folders[-1].glob("*.json"))
    
    async def do_process():
        stats = {"total": len(json_files), "processed": 0, "success": 0, "errors": 0}
        
        # Buffers
        from src.core.bulk_ops import (
            bulk_upsert_products, 
            bulk_upsert_sellers, 
            bulk_upsert_skus, 
            bulk_insert_price_history
        )
        
        products_buffer = []
        sellers_buffer = []
        skus_buffer = []
        prices_buffer = []

        from src.core.models import Category
        
        async with get_session() as session:
            for i, json_file in enumerate(json_files):
                try:
                    with open(json_file) as f:
                        raw_data = json.load(f)
                    
                    parsed = parser.parse_product(raw_data)
                    if not parsed:
                        continue
                    
                    # Prepare product dict
                    p_data = {
                        "id": parsed.id,
                        "title": parsed.title,
                        "title_normalized": parser.normalize_title(parsed.title),
                        "category_id": parsed.category_id,
                        "seller_id": parsed.seller_id,
                        "rating": parsed.rating,
                        "review_count": parsed.review_count,
                        "order_count": parsed.order_count,
                        "is_available": parsed.is_available,
                        "total_available": parsed.total_available,
                        "description": parsed.description,
                        "photos": parsed.photos,
                        "raw_data": parsed.raw_data,
                    }
                    products_buffer.append(p_data)
                    
                    # Prepare seller dict
                    if parsed.seller_data:
                        s_data = {
                            "id": parsed.seller_id,
                            "title": parsed.seller_title,
                            **{k: v for k, v in parsed.seller_data.items() 
                               if k in ['link', 'rating', 'description', 'account_id', 'reviews', 'orders']}
                        }
                        if 'reviews' in s_data: s_data['review_count'] = s_data.pop('reviews')
                        if 'orders' in s_data: s_data['order_count'] = s_data.pop('orders')
                        sellers_buffer.append(s_data)

                    # Upsert categories (kept individual for now)
                    for cat_data in (parsed.category_path or []):
                        cat = Category(
                            id=cat_data['id'],
                            platform=platform,
                            title=cat_data['title'],
                        )
                        await session.merge(cat)

                    # Prepare SKUs and Prices
                    for sku_data in (parsed.skus or []):
                        sku_entry = {
                            "id": sku_data['id'],
                            "product_id": parsed.id,
                            "full_price": sku_data.get('full_price'),
                            "purchase_price": sku_data.get('purchase_price'),
                            "discount_percent": sku_data.get('discount_percent'),
                            "available_amount": sku_data.get('available_amount', 0),
                            "barcode": sku_data.get('barcode'),
                            "characteristics": sku_data.get('characteristics'),
                        }
                        skus_buffer.append(sku_entry)
                        
                        price_entry = {
                            "sku_id": sku_data['id'],
                            "product_id": parsed.id,
                            "full_price": sku_data.get('full_price'),
                            "purchase_price": sku_data.get('purchase_price'),
                            "discount_percent": sku_data.get('discount_percent'),
                            "available_amount": sku_data.get('available_amount', 0),
                        }
                        prices_buffer.append(price_entry)
                    
                    stats["success"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {json_file}: {e}")
                    stats["errors"] += 1
                
                stats["processed"] += 1
                
                # Commit every 500 records
                if len(products_buffer) >= 500:
                    if sellers_buffer:
                        await bulk_upsert_sellers(session, sellers_buffer, platform)
                        sellers_buffer = []
                    
                    if products_buffer:
                        await bulk_upsert_products(session, products_buffer, platform)
                        products_buffer = []
                        
                    if skus_buffer:
                        await bulk_upsert_skus(session, skus_buffer)
                        skus_buffer = []
                        
                    if prices_buffer:
                        await bulk_insert_price_history(session, prices_buffer)
                        prices_buffer = []
                        
                    await session.commit()
                    logger.info(f"Processed {stats['processed']}/{stats['total']}")
            
            # Commit remaining
            if products_buffer:
                if sellers_buffer: await bulk_upsert_sellers(session, sellers_buffer, platform)
                await bulk_upsert_products(session, products_buffer, platform)
                if skus_buffer: await bulk_upsert_skus(session, skus_buffer)
                if prices_buffer: await bulk_insert_price_history(session, prices_buffer)
                await session.commit()
        
        return stats
    
    return run_async(do_process())
