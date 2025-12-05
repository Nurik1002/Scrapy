"""
Sellers Router - API endpoints for seller data.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func

from src.core.database import get_session
from src.core.models import Seller, Product, SKU

router = APIRouter()


class SellerResponse(BaseModel):
    """Seller response schema."""
    id: int
    title: str
    link: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0
    order_count: int = 0
    product_count: int = 0
    available_products: int = 0
    avg_price: Optional[int] = None
    
    class Config:
        from_attributes = True


class SellerDetailResponse(SellerResponse):
    """Detailed seller response."""
    description: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None


@router.get("", response_model=List[SellerResponse])
async def list_sellers(
    platform: str = "uzum",
    search: Optional[str] = None,
    min_rating: Optional[float] = None,
    sort_by: str = Query("order_count", enum=["order_count", "rating", "product_count"]),
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    """
    List all sellers with stats.
    """
    async with get_session() as session:
        query = (
            select(
                Seller.id,
                Seller.title,
                Seller.link,
                Seller.rating,
                Seller.review_count,
                Seller.order_count,
                func.count(Product.id).label("product_count"),
                func.count(Product.id).filter(Product.is_available == True).label("available_products"),
                func.avg(SKU.purchase_price).label("avg_price"),
            )
            .outerjoin(Product, Seller.id == Product.seller_id)
            .outerjoin(SKU, Product.id == SKU.product_id)
            .where(Seller.platform == platform)
            .group_by(Seller.id)
        )
        
        if search:
            query = query.where(Seller.title.ilike(f"%{search}%"))
        if min_rating:
            query = query.where(Seller.rating >= min_rating)
        
        # Sorting
        if sort_by == "rating":
            query = query.order_by(Seller.rating.desc().nullslast())
        elif sort_by == "product_count":
            query = query.order_by(func.count(Product.id).desc())
        else:
            query = query.order_by(Seller.order_count.desc().nullslast())
        
        query = query.offset(offset).limit(limit)
        
        result = await session.execute(query)
        sellers = result.fetchall()
        
        return [
            SellerResponse(
                id=row.id,
                title=row.title,
                link=row.link,
                rating=float(row.rating) if row.rating else None,
                review_count=row.review_count or 0,
                order_count=row.order_count or 0,
                product_count=row.product_count or 0,
                available_products=row.available_products or 0,
                avg_price=int(row.avg_price) if row.avg_price else None,
            )
            for row in sellers
        ]


@router.get("/{seller_id}", response_model=SellerDetailResponse)
async def get_seller(seller_id: int):
    """
    Get seller details.
    """
    async with get_session() as session:
        # Get seller with aggregated stats
        result = await session.execute(
            select(
                Seller,
                func.count(Product.id).label("product_count"),
                func.count(Product.id).filter(Product.is_available == True).label("available_products"),
                func.avg(SKU.purchase_price).label("avg_price"),
                func.min(SKU.purchase_price).label("min_price"),
                func.max(SKU.purchase_price).label("max_price"),
            )
            .outerjoin(Product, Seller.id == Product.seller_id)
            .outerjoin(SKU, Product.id == SKU.product_id)
            .where(Seller.id == seller_id)
            .group_by(Seller.id)
        )
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Seller not found")
        
        seller = row[0]
        
        return SellerDetailResponse(
            id=seller.id,
            title=seller.title,
            link=seller.link,
            rating=float(seller.rating) if seller.rating else None,
            description=seller.description,
            review_count=seller.review_count or 0,
            order_count=seller.order_count or 0,
            product_count=row.product_count or 0,
            available_products=row.available_products or 0,
            avg_price=int(row.avg_price) if row.avg_price else None,
            min_price=row.min_price,
            max_price=row.max_price,
        )


@router.get("/{seller_id}/products")
async def get_seller_products(
    seller_id: int,
    available_only: bool = False,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    """
    Get products by seller.
    """
    async with get_session() as session:
        query = (
            select(
                Product.id,
                Product.title,
                Product.rating,
                Product.order_count,
                Product.is_available,
                func.min(SKU.purchase_price).label("min_price"),
            )
            .outerjoin(SKU, Product.id == SKU.product_id)
            .where(Product.seller_id == seller_id)
            .group_by(Product.id)
        )
        
        if available_only:
            query = query.where(Product.is_available == True)
        
        query = query.order_by(Product.order_count.desc()).offset(offset).limit(limit)
        
        result = await session.execute(query)
        products = result.fetchall()
        
        return [
            {
                "id": row.id,
                "title": row.title,
                "rating": float(row.rating) if row.rating else None,
                "order_count": row.order_count,
                "is_available": row.is_available,
                "min_price": row.min_price,
            }
            for row in products
        ]


@router.get("/{seller_id}/competitors")
async def get_seller_competitors(seller_id: int, limit: int = 10):
    """
    Find sellers selling similar products.
    """
    async with get_session() as session:
        # Get this seller's category distribution
        query = """
            WITH seller_categories AS (
                SELECT category_id, COUNT(*) as cnt
                FROM products
                WHERE seller_id = :seller_id
                GROUP BY category_id
            )
            SELECT 
                s.id, s.title, s.rating, s.order_count,
                COUNT(DISTINCT p.category_id) as shared_categories
            FROM sellers s
            JOIN products p ON s.id = p.seller_id
            WHERE s.id != :seller_id
              AND p.category_id IN (SELECT category_id FROM seller_categories)
            GROUP BY s.id
            ORDER BY shared_categories DESC, s.order_count DESC
            LIMIT :limit
        """
        
        from sqlalchemy import text
        result = await session.execute(
            text(query), 
            {"seller_id": seller_id, "limit": limit}
        )
        competitors = result.fetchall()
        
        return [
            {
                "id": row.id,
                "title": row.title,
                "rating": float(row.rating) if row.rating else None,
                "order_count": row.order_count,
                "shared_categories": row.shared_categories,
            }
            for row in competitors
        ]
