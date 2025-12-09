import asyncio
import logging
import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.src.platforms.yandex.platform import YandexPlatform
from app.src.platforms.yandex.client import YandexClient
from app.src.platforms.yandex.debug_config import enable_debug

async def test_slug_extraction(product_id):
    client = YandexClient()
    platform = YandexPlatform(client=client)
    
    # Initialize client session via platform context
    async with platform:
        try:
            print(f"Fetching product {product_id}...")
            model_data = await platform.client.fetch_product(product_id)
            if model_data:
                slug = platform._extract_slug_from_data(model_data, product_id)
                print(f"Extracted Slug: '{slug}'")
                
                # Verify if it matches expected for 1113644663
                if product_id == 1113644663:
                    if "noutbuk-hp" in slug:
                        print("✅ Slug extraction SUCCESS!")
                    else:
                        print(f"❌ Slug extraction FAILED! (Expected 'noutbuk-hp...', got '{slug}')")
                        if model_data.get('html'):
                            with open(f"debug_failed_slug_{product_id}.html", "w") as f:
                                f.write(model_data['html'])
                            print(f"Dumped HTML to debug_failed_slug_{product_id}.html")
                
                # Also try to fetch offers with this slug
                print(f"Attempting to fetch offers with slug '{slug}'...")
                offers = await platform.client.fetch_product_offers(product_id, slug=slug)
                if offers:
                    print(f"✅ Fetch offers SUCCESS! ({len(str(offers))} chars)")
                    # Dump offers HTML/JSON for analysis
                    if offers.get('html'): # Wait, fetch_product_offers might not return 'html'
                         pass
                    
                    # But I want to see the JSON structure for offers
                    import json
                    with open(f"offers_dump_{product_id}.json", "w") as f:
                         json.dump(offers, f, indent=2, default=str)
                    print(f"Dumped offers data to offers_dump_{product_id}.json")
                else:
                    print("❌ Fetch offers FAILED!")
                    
            else:
                print("❌ Fetch product FAILED (No data)")
                
        except Exception as e:
            print(f"Exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    enable_debug()
    # Test with the product that has a named slug
    asyncio.run(test_slug_extraction(1113644663))
