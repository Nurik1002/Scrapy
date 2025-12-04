import sys
import os
import json
from datetime import datetime

# Add project root to path (assuming running from inside scraper or project root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scraper.api_client import APIClient
from scraper.models import AuctionDeal, ShopDeal, DealProduct

def validate_model(data, model_class):
    try:
        model = model_class(**data)
        return True, None
    except Exception as e:
        return False, str(e)

def main():
    client = APIClient()
    
    print("=== Testing Auctions ===")
    auctions = client.get_auctions(page=1, page_size=5)
    print(f"Fetched {len(auctions)} auctions.")
    
    if auctions:
        # Validate first auction against model
        valid, error = validate_model(auctions[0], AuctionDeal)
        if valid:
            print("AuctionDeal model validation: PASS")
        else:
            print(f"AuctionDeal model validation: FAIL - {error}")
            
        # Fetch details for the first auction
        lot_id = auctions[0].get('lot_id')
        print(f"Fetching details for auction lot {lot_id}...")
        details = client.get_auction_products(lot_id)
        if details:
            print(f"Fetched {len(details)} products for lot {lot_id}.")
            # Validate first product
            valid, error = validate_model(details[0], DealProduct)
            if valid:
                print("DealProduct model validation: PASS")
            else:
                print(f"DealProduct model validation: FAIL - {error}")
        else:
            print("Failed to fetch auction details.")
            
    print("\n=== Testing Shop Deals ===")
    shop_deals = client.get_shop_deals(page=1, page_size=5)
    print(f"Fetched {len(shop_deals)} shop deals.")
    
    if shop_deals:
        # Validate first shop deal against model
        valid, error = validate_model(shop_deals[0], ShopDeal)
        if valid:
            print("ShopDeal model validation: PASS")
        else:
            print(f"ShopDeal model validation: FAIL - {error}")
            
        # Fetch details for the first shop deal
        # Note: Shop deals use 'id' as lot_id
        lot_id = shop_deals[0].get('id')
        print(f"Fetching details for shop lot {lot_id}...")
        details = client.get_shop_products(lot_id)
        if details:
            print(f"Fetched {len(details)} products for shop lot {lot_id}.")
            # Validate first product (which is mapped to DealProduct-like structure in api_client but let's check)
            # In api_client.get_shop_products, we construct a dict. 
            # We should check if it matches DealProduct or if we need a separate model.
            # The dict constructed:
            # {
            #     "rn": deal.get("rn", 1),
            #     "product_name": deal.get("product_name"),
            #     "amount": deal.get("amount"),
            #     "measure_name": deal.get("measure_name", "dona"),
            #     "features": None,
            #     "price": deal.get("price"),
            #     "country_name": None
            # }
            # This matches DealProduct fields.
            valid, error = validate_model(details[0], DealProduct)
            if valid:
                print("Shop Product (as DealProduct) validation: PASS")
            else:
                print(f"Shop Product validation: FAIL - {error}")
        else:
            print("Failed to fetch shop details.")

if __name__ == "__main__":
    main()
