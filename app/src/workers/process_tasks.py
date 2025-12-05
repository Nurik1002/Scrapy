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
            
            for snapshot in snapshots:
                try:
                    # Parse product
                    parsed = parser.parse_product(snapshot.raw_json)
                    if not parsed:
                        continue
                    
                    # Upsert seller
                    if parsed.seller_data:
                        seller = Seller(
                            id=parsed.seller_id,
                            platform=platform,
                            title=parsed.seller_title,
                            **{k: v for k, v in parsed.seller_data.items() 
                               if k in ['link', 'rating', 'description', 'account_id']}
                        )
                        await session.merge(seller)
                    
                    # Upsert categories
                    for cat_data in (parsed.category_path or []):
                        cat = Category(
                            id=cat_data['id'],
                            platform=platform,
                            title=cat_data['title'],
                        )
                        await session.merge(cat)
                    
                    # Upsert product
                    product = Product(
                        id=parsed.id,
                        platform=platform,
                        title=parsed.title,
                        title_normalized=parser.normalize_title(parsed.title),
                        category_id=parsed.category_id,
                        seller_id=parsed.seller_id,
                        rating=parsed.rating,
                        review_count=parsed.review_count,
                        order_count=parsed.order_count,
                        is_available=parsed.is_available,
                        total_available=parsed.total_available,
                        description=parsed.description,
                        photos=parsed.photos,
                        raw_data=parsed.raw_data,
                    )
                    await session.merge(product)
                    
                    # Upsert SKUs + price history
                    for sku_data in (parsed.skus or []):
                        sku = SKU(
                            id=sku_data['id'],
                            product_id=parsed.id,
                            full_price=sku_data.get('full_price'),
                            purchase_price=sku_data.get('purchase_price'),
                            discount_percent=sku_data.get('discount_percent'),
                            available_amount=sku_data.get('available_amount', 0),
                            barcode=sku_data.get('barcode'),
                            characteristics=sku_data.get('characteristics'),
                        )
                        await session.merge(sku)
                        
                        # Add price history
                        price_record = PriceHistory(
                            sku_id=sku_data['id'],
                            product_id=parsed.id,
                            full_price=sku_data.get('full_price'),
                            purchase_price=sku_data.get('purchase_price'),
                            discount_percent=sku_data.get('discount_percent'),
                            available_amount=sku_data.get('available_amount', 0),
                        )
                        session.add(price_record)
                    
                    # Mark as processed
                    snapshot.processed = True
                    snapshot.processed_at = datetime.now(timezone.utc)
                    
                    stats["success"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing snapshot {snapshot.id}: {e}")
                    stats["errors"] += 1
                
                stats["processed"] += 1
            
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
        
        async with get_session() as session:
            for json_file in json_files:
                try:
                    with open(json_file) as f:
                        raw_data = json.load(f)
                    
                    parsed = parser.parse_product(raw_data)
                    if not parsed:
                        continue
                    
                    # Upsert seller
                    if parsed.seller_data:
                        seller = Seller(
                            id=parsed.seller_id,
                            platform=platform,
                            title=parsed.seller_title,
                            link=parsed.seller_data.get('link'),
                            rating=parsed.seller_data.get('rating'),
                            review_count=parsed.seller_data.get('reviews', 0),
                            order_count=parsed.seller_data.get('orders', 0),
                            description=parsed.seller_data.get('description'),
                            account_id=parsed.seller_data.get('account_id'),
                        )
                        await session.merge(seller)
                    
                    # Upsert product
                    product = Product(
                        id=parsed.id,
                        platform=platform,
                        title=parsed.title,
                        title_normalized=parser.normalize_title(parsed.title),
                        category_id=parsed.category_id,
                        seller_id=parsed.seller_id,
                        rating=parsed.rating,
                        review_count=parsed.review_count,
                        order_count=parsed.order_count,
                        is_available=parsed.is_available,
                        total_available=parsed.total_available,
                        raw_data=parsed.raw_data,
                    )
                    await session.merge(product)
                    
                    # Upsert SKUs
                    for sku_data in (parsed.skus or []):
                        sku = SKU(
                            id=sku_data['id'],
                            product_id=parsed.id,
                            full_price=sku_data.get('full_price'),
                            purchase_price=sku_data.get('purchase_price'),
                            available_amount=sku_data.get('available_amount', 0),
                        )
                        await session.merge(sku)
                    
                    stats["success"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing {json_file}: {e}")
                    stats["errors"] += 1
                
                stats["processed"] += 1
                
                # Commit every 100 records
                if stats["processed"] % 100 == 0:
                    await session.commit()
                    logger.info(f"Processed {stats['processed']}/{stats['total']}")
            
            await session.commit()
        
        return stats
    
    return run_async(do_process())
