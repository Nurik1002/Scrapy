"""
Analytics Tasks - Celery tasks for analytics and reporting.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from celery import shared_task
from sqlalchemy import select, func, text

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task
def calculate_daily_stats(platform: str) -> dict:
    """
    Calculate daily statistics for all sellers.
    
    Args:
        platform: Platform name
        
    Returns:
        Statistics summary
    """
    from src.core.database import get_session
    from src.core.models import Seller, Product, SKU
    
    async def do_calculate():
        async with get_session() as session:
            # Get seller stats using raw SQL for performance
            query = text("""
                INSERT INTO seller_daily_stats (
                    seller_id, stats_date, product_count, available_product_count,
                    sku_count, avg_price, min_price, max_price, total_inventory_value,
                    avg_rating, total_reviews, total_orders
                )
                SELECT 
                    s.id,
                    CURRENT_DATE,
                    COUNT(DISTINCT p.id),
                    COUNT(DISTINCT CASE WHEN p.is_available THEN p.id END),
                    COUNT(sk.id),
                    AVG(sk.purchase_price),
                    MIN(sk.purchase_price),
                    MAX(sk.purchase_price),
                    SUM(sk.purchase_price * sk.available_amount),
                    AVG(p.rating),
                    SUM(p.review_count),
                    SUM(p.order_count)
                FROM sellers s
                LEFT JOIN products p ON s.id = p.seller_id
                LEFT JOIN skus sk ON p.id = sk.product_id
                WHERE s.platform = :platform
                GROUP BY s.id
                ON CONFLICT (seller_id, stats_date) 
                DO UPDATE SET
                    product_count = EXCLUDED.product_count,
                    available_product_count = EXCLUDED.available_product_count,
                    sku_count = EXCLUDED.sku_count,
                    avg_price = EXCLUDED.avg_price,
                    min_price = EXCLUDED.min_price,
                    max_price = EXCLUDED.max_price,
                    total_inventory_value = EXCLUDED.total_inventory_value,
                    avg_rating = EXCLUDED.avg_rating,
                    total_reviews = EXCLUDED.total_reviews,
                    total_orders = EXCLUDED.total_orders,
                    recorded_at = NOW()
            """)
            
            await session.execute(query, {"platform": platform})
            await session.commit()
            
            # Get count
            result = await session.execute(
                select(func.count()).select_from(Seller).where(Seller.platform == platform)
            )
            seller_count = result.scalar()
            
            return {"sellers_updated": seller_count}
    
    return run_async(do_calculate())


@shared_task
def detect_price_changes(platform: str, threshold_percent: float = 5.0) -> dict:
    """
    Detect significant price changes.
    
    Args:
        platform: Platform name
        threshold_percent: Minimum change to report
        
    Returns:
        Price change summary
    """
    from src.core.database import get_session
    from src.core.models import PriceHistory, SKU, Product
    
    async def do_detect():
        async with get_session() as session:
            # Find SKUs with price changes in last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            
            query = text("""
                WITH recent AS (
                    SELECT DISTINCT ON (sku_id) 
                        sku_id, purchase_price, recorded_at
                    FROM price_history
                    WHERE recorded_at > :one_hour_ago
                    ORDER BY sku_id, recorded_at DESC
                ),
                previous AS (
                    SELECT DISTINCT ON (ph.sku_id)
                        ph.sku_id, ph.purchase_price
                    FROM price_history ph
                    JOIN recent r ON ph.sku_id = r.sku_id
                    WHERE ph.recorded_at < r.recorded_at
                    ORDER BY ph.sku_id, ph.recorded_at DESC
                )
                SELECT 
                    r.sku_id,
                    p.purchase_price as old_price,
                    r.purchase_price as new_price,
                    ((r.purchase_price - p.purchase_price)::float / NULLIF(p.purchase_price, 0) * 100) as change_percent
                FROM recent r
                JOIN previous p ON r.sku_id = p.sku_id
                WHERE ABS((r.purchase_price - p.purchase_price)::float / NULLIF(p.purchase_price, 0) * 100) >= :threshold
            """)
            
            result = await session.execute(query, {
                "one_hour_ago": one_hour_ago,
                "threshold": threshold_percent
            })
            changes = result.fetchall()
            
            increases = [c for c in changes if c.change_percent > 0]
            decreases = [c for c in changes if c.change_percent < 0]
            
            return {
                "total_changes": len(changes),
                "price_increases": len(increases),
                "price_decreases": len(decreases),
                "avg_change_percent": sum(c.change_percent for c in changes) / len(changes) if changes else 0
            }
    
    return run_async(do_detect())


@shared_task
def generate_seller_report(seller_id: int) -> dict:
    """
    Generate comprehensive seller report.
    
    Args:
        seller_id: Seller ID
        
    Returns:
        Report data
    """
    from src.core.database import get_session
    from src.core.models import Seller, Product, SKU
    
    async def do_generate():
        async with get_session() as session:
            # Get seller
            result = await session.execute(
                select(Seller).where(Seller.id == seller_id)
            )
            seller = result.scalar_one_or_none()
            
            if not seller:
                return {"error": "Seller not found"}
            
            # Get product stats
            product_stats = await session.execute(
                select(
                    func.count(Product.id).label("total"),
                    func.count(Product.id).filter(Product.is_available == True).label("available"),
                    func.avg(Product.rating).label("avg_rating"),
                    func.sum(Product.review_count).label("total_reviews"),
                )
                .where(Product.seller_id == seller_id)
            )
            stats = product_stats.first()
            
            # Get price range
            price_stats = await session.execute(
                select(
                    func.min(SKU.purchase_price).label("min_price"),
                    func.max(SKU.purchase_price).label("max_price"),
                    func.avg(SKU.purchase_price).label("avg_price"),
                )
                .join(Product, SKU.product_id == Product.id)
                .where(Product.seller_id == seller_id)
            )
            prices = price_stats.first()
            
            return {
                "seller": {
                    "id": seller.id,
                    "title": seller.title,
                    "rating": float(seller.rating) if seller.rating else None,
                },
                "products": {
                    "total": stats.total or 0,
                    "available": stats.available or 0,
                    "avg_rating": float(stats.avg_rating) if stats.avg_rating else None,
                    "total_reviews": stats.total_reviews or 0,
                },
                "pricing": {
                    "min": prices.min_price,
                    "max": prices.max_price,
                    "avg": float(prices.avg_price) if prices.avg_price else None,
                }
            }
    
    return run_async(do_generate())
