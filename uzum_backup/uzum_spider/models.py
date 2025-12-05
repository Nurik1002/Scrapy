from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean, BigInteger, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class SellerModel(Base):
    __tablename__ = 'sellers'
    
    id = Column(BigInteger, primary_key=True)  # Uzum Seller ID
    name = Column(String)
    url = Column(String)
    rating = Column(Float)
    reviews_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProductModel(Base):
    __tablename__ = 'products'
    
    id = Column(BigInteger, primary_key=True)  # Uzum Product ID
    title = Column(String)
    category_id = Column(BigInteger)
    category_name = Column(String)
    seller_id = Column(BigInteger, ForeignKey('sellers.id'))
    url = Column(String)
    total_orders = Column(Integer)
    rating = Column(Float)
    reviews_count = Column(Integer)
    is_eco = Column(Boolean)
    adult_category = Column(Boolean)
    specs = Column(JSON) # Store detailed specs if needed
    images = Column(JSON) # Store image URLs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SkuModel(Base):
    __tablename__ = 'skus'
    
    id = Column(BigInteger, primary_key=True) # Uzum SKU ID
    product_id = Column(BigInteger, ForeignKey('products.id'))
    name = Column(String)
    image_url = Column(String)
    full_price = Column(Float)
    sell_price = Column(Float)
    available_amount = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PriceHistoryModel(Base):
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey('products.id'))
    sku_id = Column(BigInteger, ForeignKey('skus.id'))
    price = Column(Float)
    old_price = Column(Float)
    is_available = Column(Boolean)
    timestamp = Column(DateTime, default=datetime.utcnow)
