import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scraper.api_client import APIClient

def main():
    client = APIClient()
    lot_id = 379514 # From the screenshot context (Vehicle parts)
    
    print(f"Fetching details for auction lot {lot_id}...")
    products = client.get_auction_products(lot_id)
    
    if products:
        print(f"Successfully fetched {len(products)} products.")
        print("-" * 40)
        for p in products:
            # Print key fields to compare with screenshot
            # Screenshot columns: No, Name, Count, Unit, Properties, Price, Country
            # API fields might be: product_name, quantity, measure_name, js_properties, price, country_name
            
            name = p.get('product_name') or p.get('description') # Description sometimes holds the name if product_name is null
            count = p.get('amount') or p.get('quantity')
            price = p.get('price')
            
            print(f"Product: {name}")
            print(f"Count: {count}")
            print(f"Price: {price}")
            print("-" * 20)
    else:
        print("Failed to fetch products.")

if __name__ == "__main__":
    main()
