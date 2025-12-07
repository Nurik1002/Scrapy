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
    elif platform == "uzex":
        from src.platforms.uzex import parser
        from src.platforms.uzex.models import UzexLot, UzexLotItem
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
        # Use rglob to find all JSON files recursively (handles nested structure for UZEX)
        json_files = list(products_dir.rglob("*.json"))
    
    async def do_process():
        stats = {"total": len(json_files), "processed": 0, "success": 0, "errors": 0}
        
        if platform == "uzum":
            from src.core.bulk_ops import (
                bulk_upsert_products, bulk_upsert_sellers, 
                bulk_upsert_skus, bulk_insert_price_history
            )
        elif platform == "uzex":
            from src.core.bulk_ops import bulk_upsert_uzex_lots, bulk_insert_uzex_items
        
        products_buffer = []
        sellers_buffer = []
        skus_buffer = []
        # products_buffer = [] # Removed from here
        # sellers_buffer = [] # Removed from here
        # skus_buffer = [] # Removed from here
        # prices_buffer = [] # Removed from here

        # from src.core.models import Category # Removed from here
        
        async with get_session() as session:
            # UZEX processing (lots and items)
            if platform == "uzex":
                lots_buffer = []
                items_buffer = []
                
                for i, json_file in enumerate(json_files):
                    try:
                        with open(json_file) as f:
                            file_data = json.load(f)
                        
                        # Extract lot data from nested structure
                        raw_lot_data = file_data.get('lot', file_data)
                        lot_type = "auction" if "auction" in str(json_file) else "shop"
                        
                        lot = parser.parse_lot(raw_lot_data, lot_type=lot_type, status="completed")
                        if not lot:
                            stats["errors"] += 1
                            continue
                        
                        lots_buffer.append({
                            "id": lot.id, "display_no": lot.display_no,
                            "lot_type": lot.lot_type, "status": lot.status,
                            "is_budget": lot.is_budget, "type_name": lot.type_name,
                            "start_cost": lot.start_cost, "deal_cost": lot.deal_cost,
                            "currency_name": lot.currency_name,
                            "customer_name": lot.customer_name, "customer_inn": lot.customer_inn,
                            "customer_region": lot.customer_region,
                            "provider_name": lot.provider_name, "provider_inn": lot.provider_inn,
                            "deal_id": lot.deal_id, "deal_date": lot.deal_date,
                            "category_name": lot.category_name, "pcp_count": lot.pcp_count,
                            "lot_start_date": lot.lot_start_date, "lot_end_date": lot.lot_end_date,
                            "kazna_status": lot.kazna_status, "kazna_status_id": lot.kazna_status_id,
                            "kazna_payment_status": lot.kazna_payment_status,
                            "raw_data": lot.raw_data,
                        })
                        
                        # Process items
                        items_data = file_data.get("items") or file_data.get("lot_items") or []
                        if items_data:
                            for item in parser.parse_lot_items(items_data):
                                items_buffer.append({
                                    "lot_id": lot.id, "order_num": item.order_num,
                                    "product_name": item.product_name, "description": item.description,
                                    "quantity": item.quantity, "measure_name": item.measure_name,
                                    "price": item.price, "cost": item.cost,
                                    "currency_name": item.currency_name, "country_name": item.country_name,
                                    "properties": item.properties,
                                })
                        
                        stats["success"] += 1
                        stats["processed"] += 1
                        
                        # Bulk insert every 500 lots
                        if len(lots_buffer) >= 500:
                            await bulk_upsert_uzex_lots(session, lots_buffer)
                            if items_buffer:
                                await bulk_insert_uzex_items(session, items_buffer)
                            await session.commit()
                            logger.info(f"Processed {stats['processed']}/{stats['total']}")
                            lots_buffer, items_buffer = [], []
                            
                    except Exception as e:
                        logger.error(f"Error processing {json_file}: {e}")
                        stats["errors"] += 1
                        stats["processed"] += 1
                
                # Insert remaining
                if lots_buffer:
                    await bulk_upsert_uzex_lots(session, lots_buffer)
                    if items_buffer:
                        await bulk_insert_uzex_items(session, items_buffer)
                    await session.commit()
            
            # Uzum processing (products, sellers, SKUs)
            else:
                products_buffer = []
                sellers_buffer = []
                skus_buffer = []
                prices_buffer = []
                
                from src.core.models import Category
                
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

                        # Upsert categories
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
