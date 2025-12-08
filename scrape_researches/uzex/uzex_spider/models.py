from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class AuctionDealModel(Base):
    __tablename__ = 'auction_deals'

    id = Column(Integer, primary_key=True)
    lot_id = Column(Integer, unique=True, index=True)
    lot_start_date = Column(DateTime)
    lot_end_date = Column(DateTime)
    category_name = Column(String)
    start_cost = Column(Float)
    deal_cost = Column(Float)
    customer_name = Column(String)
    provider_name = Column(String)
    deal_date = Column(DateTime)
    deal_id = Column(Integer)
    lot_display_no = Column(String)
    
    products = relationship("AuctionProductModel", back_populates="deal")

class AuctionProductModel(Base):
    __tablename__ = 'auction_products'
    
    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey('auction_deals.id'))
    rn = Column(Integer)
    product_name = Column(String, nullable=True)
    amount = Column(Float)
    measure_name = Column(String, nullable=True)
    features = Column(String, nullable=True)
    price = Column(Float)
    country_name = Column(String, nullable=True)
    description = Column(String, nullable=True)
    currency_name = Column(String, nullable=True)
    js_properties = Column(JSON, nullable=True)
    cost = Column(Float, nullable=True)
    
    deal = relationship("AuctionDealModel", back_populates="products")

class ShopDealModel(Base):
    __tablename__ = 'shop_deals'

    id = Column(Integer, primary_key=True) # This is the internal DB ID
    lot_id = Column(Integer, unique=True, index=True) # This is the shop deal ID from API
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    product_name = Column(String)
    category_name = Column(String)
    cost = Column(Float)
    price = Column(Float)
    amount = Column(Float)
    pcp_count = Column(Integer)
    rn = Column(Integer)
    total_count = Column(Integer)
    
    products = relationship("ShopProductModel", back_populates="deal")

class ShopProductModel(Base):
    __tablename__ = 'shop_products'
    
    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey('shop_deals.id'))
    rn = Column(Integer)
    product_name = Column(String, nullable=True)
    amount = Column(Float)
    measure_name = Column(String, nullable=True)
    features = Column(String, nullable=True)
    price = Column(Float)
    country_name = Column(String, nullable=True)
    
    deal = relationship("ShopDealModel", back_populates="products")
