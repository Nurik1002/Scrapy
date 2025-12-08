"""
UZEX Parser - Parse API responses into structured data.
"""
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class LotItem:
    """Single item/product within a lot."""
    order_num: int
    product_name: Optional[str] = None
    description: Optional[str] = None
    quantity: float = 0
    amount: float = 0  # Total amount (quantity × price typically)
    measure_name: Optional[str] = None
    price: float = 0
    cost: float = 0
    country_name: Optional[str] = None
    currency_name: str = "Сом"
    properties: Optional[List[Dict]] = None


@dataclass
class LotData:
    """Parsed lot/deal data."""
    id: int
    display_no: Optional[str] = None
    lot_type: str = "auction"  # auction, shop, national
    status: str = "completed"  # completed, active
    
    # Pricing
    start_cost: float = 0
    deal_cost: float = 0
    currency_name: str = "Сом"
    
    # Customer
    customer_name: Optional[str] = None
    customer_inn: Optional[str] = None
    customer_region: Optional[str] = None
    
    # Provider
    provider_name: Optional[str] = None
    provider_inn: Optional[str] = None
    
    # Deal info
    deal_id: Optional[int] = None
    deal_date: Optional[datetime] = None
    category_name: Optional[str] = None
    pcp_count: int = 0
    is_budget: bool = False
    type_name: Optional[str] = None
    
    # Dates
    lot_start_date: Optional[datetime] = None
    lot_end_date: Optional[datetime] = None
    
    # Kazna
    kazna_status: Optional[str] = None
    kazna_status_id: Optional[int] = None
    kazna_payment_status: Optional[str] = None
    
    # Items
    items: List[LotItem] = field(default_factory=list)
    
    # Raw
    raw_data: Optional[Dict] = None


class UzexParser:
    """Parser for UZEX API responses."""
    
    @staticmethod
    def parse_datetime(value: Any) -> Optional[datetime]:
        """Parse datetime string."""
        if not value:
            return None
        try:
            if isinstance(value, datetime):
                return value
            # Format: 2025-11-27T17:46:56
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return None
    
    def parse_lot(
        self,
        data: Dict,
        lot_type: str = "auction",
        status: str = "completed"
    ) -> Optional[LotData]:
        """
        Parse a lot/deal from API response.
        
        Args:
            data: Raw API response dict
            lot_type: Type of lot (auction, shop, national)
            status: Deal status (completed, active)
        """
        try:
            lot_id = data.get("lot_id") or data.get("id")
            if not lot_id:
                return None
            
            return LotData(
                id=lot_id,
                display_no=data.get("lot_display_no"),
                lot_type=lot_type,
                status=status,
                
                start_cost=float(data.get("start_cost", 0) or 0),
                deal_cost=float(data.get("deal_cost", 0) or 0),
                currency_name=data.get("currency_name") or "Сом",
                
                customer_name=data.get("customer_name"),
                customer_inn=data.get("customer_inn"),
                customer_region=data.get("customer_region"),
                
                provider_name=data.get("provider_name"),
                provider_inn=data.get("provider_inn"),
                
                deal_id=data.get("deal_id"),
                deal_date=self.parse_datetime(data.get("deal_date")),
                category_name=data.get("category_name"),
                pcp_count=int(data.get("pcp_count", 0) or 0),
                is_budget=bool(data.get("is_budget")),
                type_name=data.get("type_name"),
                
                lot_start_date=self.parse_datetime(data.get("lot_start_date")),
                lot_end_date=self.parse_datetime(data.get("lot_end_date")),
                
                kazna_status=data.get("kazna_status"),
                kazna_status_id=data.get("kazna_status_id"),
                kazna_payment_status=data.get("kazna_payment_status"),
                
                raw_data=data,
            )
        except Exception as e:
            logger.error(f"Error parsing lot: {e}")
            return None
    
    def parse_lot_items(self, data: List[Dict]) -> List[LotItem]:
        """Parse lot items/products."""
        items = []
        for item in data:
            try:
                items.append(LotItem(
                    order_num=item.get("order_num") or item.get("rn", 0),
                    product_name=item.get("product_name"),
                    description=item.get("description"),
                    quantity=float(item.get("quantity") or item.get("amount", 0) or 0),
                    measure_name=item.get("measure_name"),
                    price=float(item.get("price", 0) or 0),
                    cost=float(item.get("cost", 0) or 0),
                    country_name=item.get("country_name"),
                    currency_name=item.get("currency_name") or "Сом",
                    properties=item.get("js_properties"),
                ))
            except Exception as e:
                logger.error(f"Error parsing lot item: {e}")
        return items
    
    def parse_category(self, data: Dict) -> Dict:
        """Parse category."""
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "parent_id": data.get("parent_id"),
        }
    
    def parse_product(self, data: Dict) -> Dict:
        """Parse product from catalog."""
        return {
            "id": data.get("id"),
            "code": data.get("product_code"),
            "name": data.get("name"),
            "category_id": data.get("category_id"),
            "category_name": data.get("category_name"),
            "measure_id": data.get("measure_id"),
            "measure_name": data.get("measure_name"),
        }


# Singleton
parser = UzexParser()
