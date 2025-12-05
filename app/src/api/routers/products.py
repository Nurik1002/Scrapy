"""
Products Router - API endpoints for product data.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, or_

from src.core.database import get_session
from src.core.models import Product, SKU, Seller, Category

router = APIRouter()


class ProductResponse(BaseModel):
    """Product response schema."""
    id: int
    title: str
    category_id: Optional[int] = None
    seller_id: Optional[int] = None
    seller_name: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0
    order_count: int = 0
    is_available: bool = True
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    
    class Config:
        from_attributes = True


class ProductDetailResponse(ProductResponse):
    """Detailed product response."""
    description: Optional[str] = None
    photos: Optional[List[str]] = None
    skus: List[dict] = []


@router.get("", response_model=List[ProductResponse])
async def list_products(
    platform: str = "uzum",
    seller_id: Optional[int] = None,
    category_id: Optional[int] = None,
    available_only: bool = False,
    search: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    """
    List products with filters.
    """
    async with get_session() as session:
        query = (
            select(
                Product.id,
                Product.title,
                Product.category_id,
                Product.seller_id,
                Seller.title.label("seller_name"),
                Product.rating,
                Product.review_count,
                Product.order_count,
                Product.is_available,
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
        if available_only:
            query = query.where(Product.is_available == True)
        if search:
            query = query.where(Product.title.ilike(f"%{search}%"))
        if min_price:
            query = query.having(func.min(SKU.purchase_price) >= min_price)
        if max_price:
            query = query.having(func.max(SKU.purchase_price) <= max_price)
        
        query = query.order_by(Product.order_count.desc()).offset(offset).limit(limit)
        
        result = await session.execute(query)
        products = result.fetchall()
        
        return [ProductResponse(**dict(row._mapping)) for row in products]


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(product_id: int):
    """
    Get product details.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Get seller name
        seller_name = None
        if product.seller_id:
            seller_result = await session.execute(
                select(Seller.title).where(Seller.id == product.seller_id)
            )
            seller_name = seller_result.scalar()
        
        # Get SKUs
        skus_result = await session.execute(
            select(SKU).where(SKU.product_id == product_id)
        )
        skus = skus_result.scalars().all()
        
        sku_list = [
            {
                "id": sku.id,
                "full_price": sku.full_price,
                "purchase_price": sku.purchase_price,
                "discount_percent": float(sku.discount_percent) if sku.discount_percent else None,
                "available_amount": sku.available_amount,
            }
            for sku in skus
        ]
        
        prices = [s["purchase_price"] for s in sku_list if s["purchase_price"]]
        
        return ProductDetailResponse(
            id=product.id,
            title=product.title,
            category_id=product.category_id,
            seller_id=product.seller_id,
            seller_name=seller_name,
            rating=float(product.rating) if product.rating else None,
            review_count=product.review_count,
            order_count=product.order_count,
            is_available=product.is_available,
            min_price=min(prices) if prices else None,
            max_price=max(prices) if prices else None,
            description=product.description,
            photos=product.photos if isinstance(product.photos, list) else None,
            skus=sku_list,
        )


@router.get("/{product_id}/price-history")
async def get_price_history(
    product_id: int,
    days: int = Query(30, le=365),
):
    """
    Get price history for a product.
    """
    from datetime import datetime, timedelta
    from src.core.models import PriceHistory
    
    async with get_session() as session:
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await session.execute(
            select(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .where(PriceHistory.recorded_at >= since)
            .order_by(PriceHistory.recorded_at)
        )
        history = result.scalars().all()
        
        return [
            {
                "sku_id": h.sku_id,
                "purchase_price": h.purchase_price,
                "recorded_at": h.recorded_at.isoformat(),
                "price_change": h.price_change,
            }
            for h in history
        ]
