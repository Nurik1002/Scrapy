import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scraper.api_client import APIClient
from scraper.models import AuctionDeal, ShopDeal, DealProduct

def audit_model(data, model_class, name):
    print(f"\n--- Auditing {name} ---")
    try:
        # 1. Validation
        model = model_class(**data)
        print(f"✅ Model Validation: PASS")
        
        # 2. Check for extra fields in JSON not in Model
        model_keys = set(model.model_dump().keys())
        json_keys = set(data.keys())
        
        extra_keys = json_keys - model_keys
        if extra_keys:
            print(f"⚠️  Extra fields in JSON (not in Model): {extra_keys}")
        else:
            print(f"✅ No extra fields in JSON.")
            
        # 3. Check for missing fields (keys in Model not in JSON)
        # Note: Pydantic fills defaults, so we check if the key was in the input data
        missing_keys = model_keys - json_keys
        if missing_keys:
            print(f"ℹ️  Fields in Model not in JSON (using defaults/None): {missing_keys}")
            
    except Exception as e:
        print(f"❌ Model Validation: FAIL - {e}")

def main():
    client = APIClient()
    
    # 1. Auction Audit (Lot 379556)
    print("\n=== AUDIT: AUCTION (Lot 379556) ===")
    # We need to fetch the deal object first (from list) to audit AuctionDeal
    # Since we can't fetch a single deal by ID easily without searching, 
    # we'll fetch a page and find it, or just audit the first one found if specific one not in page 1.
    # Actually, let's just audit the first one returned by get_auctions to verify the MODEL structure generally.
    # But for the DETAILS, we use the specific lot.
    
    auctions = client.get_auctions(page=1)
    if auctions:
        audit_model(auctions[0], AuctionDeal, "AuctionDeal")
        
        # Now fetch details for the specific lot observed in browser if possible, 
        # or just the one we have. Let's try to fetch details for 379556 specifically.
        lot_id = 379556
        print(f"\nFetching details for Lot {lot_id}...")
        products = client.get_auction_products(lot_id)
        if products:
            print(f"Fetched {len(products)} products.")
            audit_model(products[0], DealProduct, "DealProduct (Auction)")
        else:
            print(f"Could not fetch details for {lot_id}")

    # 2. Shop Audit (Lot 4558638)
    print("\n=== AUDIT: SHOP (Lot 4558638) ===")
    # Fetch specific shop deal details
    lot_id = 4558638
    print(f"Fetching details for Shop Lot {lot_id}...")
    shop_products = client.get_shop_products(lot_id)
    if shop_products:
        print(f"Fetched {len(shop_products)} products.")
        # The 'product' here is constructed from the deal data. 
        # We should also audit the raw deal data if possible.
        # get_shop_products returns a list of dicts that match DealProduct.
        audit_model(shop_products[0], DealProduct, "DealProduct (Shop)")
        
        # To audit ShopDeal model, we need the raw response from get_shop_products (which calls GetNotCompletedDeals)
        # We can't easily get the raw dict from the client method as it processes it.
        # Let's manually call the internal method or just trust the previous validation.
        # Or better, let's modify the client temporarily or just use the _post method here.
        
        url = "https://xarid-api-shop.uzex.uz/Common/GetNotCompletedDeals"
        payload = {
            "region_ids": [],
            "display_on_shop": 1,
            "display_on_national": 0,
            "from": 1,
            "to": 10,
            "lot_id": str(lot_id)
        }
        print(f"Fetching raw shop deal data for model audit from {url}...")
        # Use requests directly to avoid base URL issue
        import requests
        try:
            resp = requests.post(url, headers=client.HEADERS, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if data:
                audit_model(data[0], ShopDeal, "ShopDeal")
        except Exception as e:
            print(f"Error fetching raw shop data: {e}")

if __name__ == "__main__":
    main()
