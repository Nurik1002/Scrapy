"""
Uzum.uz Analytics API - FastAPI endpoints for seller analytics and product catalog.
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import csv
import io

import psycopg2
from psycopg2.extras import RealDictCursor

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

app = FastAPI(
    title="Uzum.uz Analytics API",
    description="Seller analytics and product catalog for Uzum marketplace",
    version="1.0.0"
)


def get_db():
    """Get database connection."""
    return psycopg2.connect(config.database.url, cursor_factory=RealDictCursor)


# ============================================
# MODELS
# ============================================

class SellerSummary(BaseModel):
    id: int
    name: str
    link: Optional[str]
    rating: Optional[float]
    reviews_count: int
    total_orders: int
    product_count: int
    available_products: int
    avg_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]


class ProductCatalog(BaseModel):
    product_id: int
    title: str
    category_name: Optional[str]
    seller_name: str
    seller_rating: Optional[float]
    product_rating: Optional[float]
    reviews_count: int
    total_orders: int
    min_price: Optional[float]
    max_price: Optional[float]
    is_available: bool
    url: str


class PriceChange(BaseModel):
    sku_id: int
    product_id: int
    product_title: str
    seller_name: str
    prev_price: float
    current_price: float
    change_percent: float
    prev_scraped_at: datetime
    scraped_at: datetime


class StatsOverview(BaseModel):
    total_sellers: int
    total_products: int
    total_skus: int
    available_products: int
    price_records: int
    unresolved_alerts: int
    last_updated: Optional[datetime]


# ============================================
# ENDPOINTS
# ============================================

@app.get("/", tags=["Health"])
async def health_check():
    """API health check."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/stats", response_model=StatsOverview, tags=["Analytics"])
async def get_stats():
    """Get overall database statistics."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM sellers) as total_sellers,
                    (SELECT COUNT(*) FROM products) as total_products,
                    (SELECT COUNT(*) FROM skus) as total_skus,
                    (SELECT COUNT(*) FROM products WHERE is_available) as available_products,
                    (SELECT COUNT(*) FROM price_history) as price_records,
                    (SELECT COUNT(*) FROM data_alerts WHERE NOT is_resolved) as unresolved_alerts,
                    (SELECT MAX(scraped_at) FROM price_history) as last_updated
            """)
            result = cur.fetchone()
            return StatsOverview(**result)
    finally:
        conn.close()


@app.get("/api/sellers", response_model=List[SellerSummary], tags=["Sellers"])
async def list_sellers(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("total_orders", regex="^(total_orders|rating|product_count|name)$"),
    order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    List all sellers with their statistics.
    
    - **sort_by**: total_orders, rating, product_count, name
    - **order**: asc, desc
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT 
                    s.id,
                    s.name,
                    s.link,
                    s.rating,
                    s.reviews_count,
                    s.total_orders,
                    COUNT(DISTINCT p.id) as product_count,
                    COUNT(DISTINCT CASE WHEN p.is_available THEN p.id END) as available_products,
                    ROUND(AVG(sk.sell_price)::numeric, 0) as avg_price,
                    MIN(sk.sell_price) as min_price,
                    MAX(sk.sell_price) as max_price
                FROM sellers s
                LEFT JOIN products p ON s.id = p.seller_id
                LEFT JOIN skus sk ON p.id = sk.product_id AND sk.is_available
                GROUP BY s.id
                ORDER BY {sort_by} {order} NULLS LAST
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/sellers/{seller_id}", response_model=SellerSummary, tags=["Sellers"])
async def get_seller(seller_id: int):
    """Get details for a specific seller."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    s.id,
                    s.name,
                    s.link,
                    s.rating,
                    s.reviews_count,
                    s.total_orders,
                    COUNT(DISTINCT p.id) as product_count,
                    COUNT(DISTINCT CASE WHEN p.is_available THEN p.id END) as available_products,
                    ROUND(AVG(sk.sell_price)::numeric, 0) as avg_price,
                    MIN(sk.sell_price) as min_price,
                    MAX(sk.sell_price) as max_price
                FROM sellers s
                LEFT JOIN products p ON s.id = p.seller_id
                LEFT JOIN skus sk ON p.id = sk.product_id AND sk.is_available
                WHERE s.id = %s
                GROUP BY s.id
            """, (seller_id,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Seller not found")
            return result
    finally:
        conn.close()


@app.get("/api/sellers/{seller_id}/products", response_model=List[ProductCatalog], tags=["Sellers"])
async def get_seller_products(
    seller_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get all products for a specific seller."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    p.id as product_id,
                    p.title,
                    c.title as category_name,
                    s.name as seller_name,
                    s.rating as seller_rating,
                    p.rating as product_rating,
                    p.reviews_count,
                    p.total_orders,
                    MIN(sk.sell_price) as min_price,
                    MAX(sk.sell_price) as max_price,
                    BOOL_OR(sk.is_available) as is_available,
                    p.url
                FROM products p
                JOIN sellers s ON p.seller_id = s.id
                LEFT JOIN categories c ON p.category_id = c.id
                LEFT JOIN skus sk ON p.id = sk.product_id
                WHERE s.id = %s
                GROUP BY p.id, c.title, s.id, s.name, s.rating
                ORDER BY p.total_orders DESC
                LIMIT %s OFFSET %s
            """, (seller_id, limit, offset))
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/products/catalog", response_model=List[ProductCatalog], tags=["Products"])
async def get_product_catalog(
    category_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    available_only: bool = False,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get product catalog with filters.
    
    - **category_id**: Filter by category
    - **seller_id**: Filter by seller
    - **available_only**: Only show available products
    - **min_price/max_price**: Price range filter
    - **search**: Text search in product titles
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            
            if category_id:
                conditions.append("p.category_id = %s")
                params.append(category_id)
            
            if seller_id:
                conditions.append("p.seller_id = %s")
                params.append(seller_id)
            
            if available_only:
                conditions.append("p.is_available = true")
            
            if search:
                conditions.append("p.title ILIKE %s")
                params.append(f"%{search}%")
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            # Add HAVING clause for price filtering
            having_conditions = []
            if min_price:
                having_conditions.append("MIN(sk.sell_price) >= %s")
                params.append(min_price)
            if max_price:
                having_conditions.append("MAX(sk.sell_price) <= %s")
                params.append(max_price)
            
            having_clause = f"HAVING {' AND '.join(having_conditions)}" if having_conditions else ""
            
            params.extend([limit, offset])
            
            cur.execute(f"""
                SELECT 
                    p.id as product_id,
                    p.title,
                    c.title as category_name,
                    s.name as seller_name,
                    s.rating as seller_rating,
                    p.rating as product_rating,
                    p.reviews_count,
                    p.total_orders,
                    MIN(sk.sell_price) as min_price,
                    MAX(sk.sell_price) as max_price,
                    BOOL_OR(sk.is_available) as is_available,
                    p.url
                FROM products p
                JOIN sellers s ON p.seller_id = s.id
                LEFT JOIN categories c ON p.category_id = c.id
                LEFT JOIN skus sk ON p.id = sk.product_id
                {where_clause}
                GROUP BY p.id, c.title, s.id, s.name, s.rating
                {having_clause}
                ORDER BY p.total_orders DESC
                LIMIT %s OFFSET %s
            """, params)
            
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/analytics/price-changes", response_model=List[PriceChange], tags=["Analytics"])
async def get_price_changes(
    hours: int = Query(24, ge=1, le=168),
    min_change_percent: float = Query(5.0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get recent price changes.
    
    - **hours**: Look back period (1-168 hours)
    - **min_change_percent**: Minimum price change to include
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                WITH ranked_prices AS (
                    SELECT 
                        ph.*,
                        LAG(ph.price) OVER (PARTITION BY ph.sku_id ORDER BY ph.scraped_at) as prev_price,
                        LAG(ph.scraped_at) OVER (PARTITION BY ph.sku_id ORDER BY ph.scraped_at) as prev_scraped_at
                    FROM price_history ph
                    WHERE ph.scraped_at > NOW() - INTERVAL '%s hours'
                )
                SELECT 
                    rp.sku_id,
                    rp.product_id,
                    p.title as product_title,
                    s.name as seller_name,
                    rp.prev_price,
                    rp.price as current_price,
                    ROUND(((rp.price - rp.prev_price) / rp.prev_price * 100)::numeric, 1) as change_percent,
                    rp.prev_scraped_at,
                    rp.scraped_at
                FROM ranked_prices rp
                JOIN products p ON rp.product_id = p.id
                JOIN sellers s ON rp.seller_id = s.id
                WHERE rp.prev_price IS NOT NULL 
                  AND rp.price != rp.prev_price
                  AND ABS((rp.price - rp.prev_price) / rp.prev_price * 100) >= %s
                ORDER BY ABS(rp.price - rp.prev_price) DESC
                LIMIT %s
            """, (hours, min_change_percent, limit))
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/analytics/top-sellers", tags=["Analytics"])
async def get_top_sellers(
    by: str = Query("orders", regex="^(orders|products|rating)$"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get top sellers by different metrics.
    
    - **by**: orders, products, rating
    """
    order_column = {
        "orders": "total_orders",
        "products": "product_count",
        "rating": "rating"
    }[by]
    
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT 
                    s.id,
                    s.name,
                    s.link,
                    s.rating,
                    s.total_orders,
                    s.reviews_count,
                    COUNT(DISTINCT p.id) as product_count
                FROM sellers s
                LEFT JOIN products p ON s.id = p.seller_id
                GROUP BY s.id
                ORDER BY {order_column} DESC NULLS LAST
                LIMIT %s
            """, (limit,))
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/api/export/catalog.csv", tags=["Export"])
async def export_catalog_csv(
    seller_id: Optional[int] = None,
    category_id: Optional[int] = None
):
    """Export product catalog as CSV."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            
            if seller_id:
                conditions.append("p.seller_id = %s")
                params.append(seller_id)
            if category_id:
                conditions.append("p.category_id = %s")
                params.append(category_id)
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            cur.execute(f"""
                SELECT 
                    p.id as product_id,
                    p.title,
                    c.title as category,
                    s.name as seller,
                    s.rating as seller_rating,
                    MIN(sk.sell_price) as min_price,
                    MAX(sk.sell_price) as max_price,
                    SUM(sk.available_amount) as total_stock,
                    p.total_orders,
                    p.rating,
                    p.reviews_count,
                    p.url
                FROM products p
                JOIN sellers s ON p.seller_id = s.id
                LEFT JOIN categories c ON p.category_id = c.id
                LEFT JOIN skus sk ON p.id = sk.product_id
                {where_clause}
                GROUP BY p.id, c.title, s.id, s.name, s.rating
                ORDER BY p.total_orders DESC
            """, params)
            
            rows = cur.fetchall()
        
        # Generate CSV
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=catalog_{datetime.now().strftime('%Y%m%d')}.csv"}
        )
    finally:
        conn.close()


@app.get("/api/alerts", tags=["Data Quality"])
async def get_alerts(
    severity: Optional[str] = Query(None, regex="^(info|warning|critical)$"),
    resolved: bool = False,
    limit: int = Query(50, ge=1, le=200)
):
    """Get data quality alerts."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            conditions = [f"is_resolved = {resolved}"]
            params = []
            
            if severity:
                conditions.append("severity = %s")
                params.append(severity)
            
            where_clause = f"WHERE {' AND '.join(conditions)}"
            params.append(limit)
            
            cur.execute(f"""
                SELECT 
                    da.id,
                    da.alert_type,
                    da.severity,
                    da.message,
                    da.details,
                    p.title as product_title,
                    s.name as seller_name,
                    da.created_at
                FROM data_alerts da
                LEFT JOIN products p ON da.product_id = p.id
                LEFT JOIN sellers s ON da.seller_id = s.id
                {where_clause}
                ORDER BY 
                    CASE da.severity 
                        WHEN 'critical' THEN 1 
                        WHEN 'warning' THEN 2 
                        ELSE 3 
                    END,
                    da.created_at DESC
                LIMIT %s
            """, params)
            return cur.fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
