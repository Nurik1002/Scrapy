from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Category(BaseModel):
    id: int
    name: str

class Product(BaseModel):
    id: int
    product_code: str
    name: str
    category_id: int
    category_name: Optional[str] = None
    measure_id: Optional[int] = None
    measure_name: Optional[str] = None

class AuctionDeal(BaseModel):
    lot_id: int
    lot_start_date: Optional[datetime] = None
    lot_end_date: Optional[datetime] = None
    category_name: Optional[str] = None
    start_cost: float
    deal_cost: float
    customer_name: Optional[str] = None
    provider_name: Optional[str] = None
    deal_date: Optional[datetime] = None
    deal_id: Optional[int] = None
    lot_display_no: Optional[str] = None

class DealProduct(BaseModel):
    rn: int
    product_name: Optional[str] = None
    amount: float
    measure_name: Optional[str] = None
    features: Optional[str] = None
    price: float
    country_name: Optional[str] = None
    # Extra fields found during audit
    description: Optional[str] = None
    currency_name: Optional[str] = None
    js_properties: Optional[List[dict]] = None
    cost: Optional[float] = None
    quantity: Optional[float] = None # Original field for amount
    order_num: Optional[int] = None # Original field for rn
    
class ShopDeal(BaseModel):
    id: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    product_name: Optional[str] = None
    category_name: Optional[str] = None
    cost: float
    price: float
    amount: float
    pcp_count: Optional[int] = None
    rn: Optional[int] = None
    total_count: Optional[int] = None
