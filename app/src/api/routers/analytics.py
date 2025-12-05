"""
Analytics Router - API endpoints for analytics and insights.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, func, text

from src.core.database import get_session
from src.core.models import Product, SKU, Seller, PriceHistory

router = APIRouter()


@router.get("/price-comparison")
async def compare_prices(
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    limit: int = Query(50, le=200),
):
    """
    Compare prices for same/similar products across different sellers.
    
    This is KEY for seller analytics - find out who's selling cheaper!
    """
    async with get_session() as session:
        # Find products with same normalized title from different sellers
        query = text("""
            SELECT 
                p1.title_normalized,
                p1.title as sample_title,
                COUNT(DISTINCT p1.seller_id) as seller_count,
                MIN(s.purchase_price) as min_price,
                MAX(s.purchase_price) as max_price,
                AVG(s.purchase_price)::int as avg_price,
                ARRAY_AGG(DISTINCT jsonb_build_object(
                    'seller_id', sel.id,
                    'seller_name', sel.title,
                    'product_id', p1.id,
                    'price', s.purchase_price
                )) as sellers
            FROM products p1
            JOIN skus s ON p1.id = s.product_id
            JOIN sellers sel ON p1.seller_id = sel.id
            WHERE p1.title_normalized IS NOT NULL
              AND s.purchase_price > 0
              AND (:search IS NULL OR p1.title ILIKE '%' || :search || '%')
              AND (:category_id IS NULL OR p1.category_id = :category_id)
            GROUP BY p1.title_normalized, p1.title
            HAVING COUNT(DISTINCT p1.seller_id) > 1
            ORDER BY COUNT(DISTINCT p1.seller_id) DESC, AVG(s.purchase_price) DESC
            LIMIT :limit
        """)
        
        result = await session.execute(query, {
            "search": search,
            "category_id": category_id,
            "limit": limit
        })
        rows = result.fetchall()
        
        return [
            {
                "title": row.sample_title,
                "seller_count": row.seller_count,
                "min_price": row.min_price,
                "max_price": row.max_price,
                "avg_price": row.avg_price,
                "price_spread": row.max_price - row.min_price if row.max_price and row.min_price else 0,
                "sellers": row.sellers[:10],  # Limit sellers shown
            }
            for row in rows
        ]


@router.get("/price-drops")
async def get_price_drops(
    platform: str = "uzum",
    hours: int = Query(24, le=168),
    min_drop_percent: float = Query(10, ge=1, le=90),
    limit: int = Query(50, le=200),
):
    """
    Get products with recent price drops.
    """
    async with get_session() as session:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        query = text("""
            WITH price_changes AS (
                SELECT 
                    ph.product_id,
                    ph.sku_id,
                    ph.purchase_price as current_price,
                    LAG(ph.purchase_price) OVER (
                        PARTITION BY ph.sku_id ORDER BY ph.recorded_at
                    ) as previous_price,
                    ph.recorded_at
                FROM price_history ph
                WHERE ph.recorded_at >= :since
            )
            SELECT 
                p.id,
                p.title,
                s.title as seller_name,
                pc.current_price,
                pc.previous_price,
                ROUND(((pc.previous_price - pc.current_price)::float / 
                       NULLIF(pc.previous_price, 0) * 100)::numeric, 1) as drop_percent,
                (pc.previous_price - pc.current_price) as savings,
                pc.recorded_at
            FROM price_changes pc
            JOIN products p ON pc.product_id = p.id
            JOIN sellers s ON p.seller_id = s.id
            WHERE pc.previous_price > pc.current_price
              AND ((pc.previous_price - pc.current_price)::float / 
                   NULLIF(pc.previous_price, 0) * 100) >= :min_drop
            ORDER BY drop_percent DESC
            LIMIT :limit
        """)
        
        result = await session.execute(query, {
            "since": since,
            "min_drop": min_drop_percent,
            "limit": limit
        })
        rows = result.fetchall()
        
        return [
            {
                "product_id": row.id,
                "title": row.title,
                "seller": row.seller_name,
                "current_price": row.current_price,
                "previous_price": row.previous_price,
                "drop_percent": float(row.drop_percent),
                "savings": row.savings,
                "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
            }
            for row in rows
        ]


@router.get("/top-sellers")
async def get_top_sellers(
    platform: str = "uzum",
    metric: str = Query("orders", enum=["orders", "rating", "products", "revenue"]),
    category_id: Optional[int] = None,
    limit: int = Query(20, le=100),
):
    """
    Get top sellers by various metrics.
    """
    async with get_session() as session:
        base_query = """
            SELECT 
                s.id,
                s.title,
                s.rating,
                s.order_count,
                COUNT(DISTINCT p.id) as product_count,
                SUM(sk.purchase_price * sk.available_amount) as revenue_potential
            FROM sellers s
            LEFT JOIN products p ON s.id = p.seller_id
            LEFT JOIN skus sk ON p.id = sk.product_id
            WHERE s.platform = :platform
        """
        
        if category_id:
            base_query += " AND p.category_id = :category_id"
        
        base_query += " GROUP BY s.id"
        
        # Order by metric
        if metric == "rating":
            base_query += " ORDER BY s.rating DESC NULLS LAST"
        elif metric == "products":
            base_query += " ORDER BY product_count DESC"
        elif metric == "revenue":
            base_query += " ORDER BY revenue_potential DESC NULLS LAST"
        else:
            base_query += " ORDER BY s.order_count DESC NULLS LAST"
        
        base_query += " LIMIT :limit"
        
        result = await session.execute(
            text(base_query),
            {"platform": platform, "category_id": category_id, "limit": limit}
        )
        rows = result.fetchall()
        
        return [
            {
                "id": row.id,
                "title": row.title,
                "rating": float(row.rating) if row.rating else None,
                "order_count": row.order_count,
                "product_count": row.product_count,
                "revenue_potential": row.revenue_potential,
            }
            for row in rows
        ]


@router.get("/category-insights")
async def get_category_insights(
    platform: str = "uzum",
    limit: int = Query(20, le=100),
):
    """
    Get insights by category.
    """
    async with get_session() as session:
        query = text("""
            SELECT 
                c.id,
                c.title,
                c.level,
                COUNT(DISTINCT p.id) as product_count,
                COUNT(DISTINCT p.seller_id) as seller_count,
                AVG(sk.purchase_price)::int as avg_price,
                MIN(sk.purchase_price) as min_price,
                MAX(sk.purchase_price) as max_price,
                AVG(p.rating)::numeric(2,1) as avg_rating
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id
            LEFT JOIN skus sk ON p.id = sk.product_id
            WHERE c.platform = :platform
            GROUP BY c.id
            HAVING COUNT(DISTINCT p.id) > 0
            ORDER BY COUNT(DISTINCT p.id) DESC
            LIMIT :limit
        """)
        
        result = await session.execute(query, {"platform": platform, "limit": limit})
        rows = result.fetchall()
        
        return [
            {
                "id": row.id,
                "title": row.title,
                "level": row.level,
                "product_count": row.product_count,
                "seller_count": row.seller_count,
                "avg_price": row.avg_price,
                "min_price": row.min_price,
                "max_price": row.max_price,
                "avg_rating": float(row.avg_rating) if row.avg_rating else None,
            }
            for row in rows
        ]


@router.get("/export/catalog.csv")
async def export_catalog_csv(
    platform: str = "uzum",
    seller_id: Optional[int] = None,
    category_id: Optional[int] = None,
):
    """
    Export product catalog as CSV.
    """
    from fastapi.responses import StreamingResponse
    import csv
    import io
    
    async with get_session() as session:
        query = (
            select(
                Product.id,
                Product.title,
                Seller.title.label("seller"),
                Product.rating,
                Product.order_count,
                func.min(SKU.purchase_price).label("min_price"),
                func.max(SKU.purchase_price).label("max_price"),
            )
            .outerjoin(Seller, Product.seller_id == Seller.id)
            .outerjoin(SKU, Product.id == SKU.product_id)
            .where(Product.platform == platform)
            .group_by(Product.id, Seller.title)
        )
        
        if seller_id:
            query = query.where(Product.seller_id == seller_id)
        if category_id:
            query = query.where(Product.category_id == category_id)
        
        result = await session.execute(query.limit(10000))
        rows = result.fetchall()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "Seller", "Rating", "Orders", "Min Price", "Max Price"])
    
    for row in rows:
        writer.writerow([
            row.id, row.title, row.seller, row.rating, 
            row.order_count, row.min_price, row.max_price
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=catalog_{platform}.csv"}
    )
