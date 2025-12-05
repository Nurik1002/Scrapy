"""
FastAPI Main Application - Analytics API for Uzum sellers.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core import init_db, close_db, redis_client, settings
from src.api.routers import products, sellers, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    await redis_client.connect()
    yield
    # Shutdown
    await redis_client.close()
    await close_db()


app = FastAPI(
    title="Marketplace Analytics API",
    description="Analytics platform for Uzum.uz sellers",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(sellers.router, prefix="/api/sellers", tags=["Sellers"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])


@app.get("/")
async def root():
    """API root."""
    return {
        "name": "Marketplace Analytics API",
        "version": "1.0.0",
        "platforms": ["uzum"],
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}


@app.get("/api/stats")
async def get_stats():
    """Get platform statistics."""
    from src.core.database import get_session
    from src.core.models import Product, Seller, SKU
    from sqlalchemy import select, func
    
    async with get_session() as session:
        products_count = await session.execute(select(func.count(Product.id)))
        sellers_count = await session.execute(select(func.count(Seller.id)))
        skus_count = await session.execute(select(func.count(SKU.id)))
        
        return {
            "products": products_count.scalar() or 0,
            "sellers": sellers_count.scalar() or 0,
            "skus": skus_count.scalar() or 0,
        }
