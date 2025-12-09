
import asyncio
import sys
import os
import json
from datetime import datetime

# Add app directory to path so we can import src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.platforms.yandex.debug_config import enable_full_debug, disable_debug
from src.platforms.yandex.platform import create_yandex_platform
from src.core.config import settings

async def main():
    print("🚀 Starting Yandex Debug Session")
    
    # Enable detailed logging
    # We log to console for immediate feedback as requested ("Show loggers!")
    enable_full_debug()
    
    platform = None
    try:
        platform = create_yandex_platform()
        
        # Open context (initializes client etc)
        await platform.__aenter__()
        
        print("\n🏥 Running Health Check...")
        is_healthy = await platform.client.health_check()
        print(f"Health Check Result: {'✅ PASS' if is_healthy else '❌ FAIL'}")
        
        if not is_healthy:
            print("⚠️ Warning: Health check failed. Proceeding anyway but expect issues.")

        # Search for a product to test with
        search_query = "iphone 15"
        print(f"\nmagnifying_glass_tilted_left: Searching for '{search_query}'...")
        
        search_results = await platform.client.search_products(search_query)
        
        target_product = None
        
        if search_results and 'json_data' in search_results:
             # Try to find a product in the search results
             print("Search completed. Saving HTML to debug_search.html...")
             # Re-fetch with HTML included if search_results doesn't have it (client.search_products doesn't return raw HTML in the dict, only json_data?)
             # Wait, client.search_products returns dict with 'json_data'.
             # Let's check client.search_products implementation.
             # It returns 'json_data': json_data ... and 'url'.
             # It DOES NOT return 'html'.
             
             # We should probably modify client to return HTML or fetch it again here.
             # Or rely on client logging which we can see if we used file logging.
             
             # Let's modify client.search_products to return HTML in debug mode? 
             # Or just fetch here manually.
             
             search_url = platform.client.SEARCH_URL.format(base=platform.client.BASE_URL)
             html = await platform.client._fetch_html(search_url + "?text=" + search_query)
             if html:
                 with open("debug_search.html", "w") as f:
                     f.write(html)
                 print("✅ Saved debug_search.html")
             
             pass
        
        # If search is tricky to parse without knowing structure, 
        # let's try a known ID if possible, or just fail gracefully if search doesn't return obvious list
        # Yandex IDs are confusing. Let's try to just use valid IDs if we find them.
        
        # But wait, the user wants me to "Run yandex!".
        # I'll try to discover some products if search structure is unknown.
        
        print("\n🗺️  Attempting Category Discovery (short run)...")
        # We'll run discovery for a few seconds or until we find 1 product
        
        count = 0
        count = 0
        async for product_data in platform.discover_products_by_categories():
            pid = product_data.get('product_id')
            title = product_data.get('model_data', {}).get('title', 'Unknown')
            offers_count = len(product_data.get('offers_data', []))
            specs_count = len(product_data.get('specs_data', {}))
            
            print(f"\n✨ Processed Product: {pid}")
            print(f"Title: {title}")
            print(f"Offers: {offers_count}")
            print(f"Specs: {specs_count}")
            
            count += 1
            if count >= 1:
                break
        
        if count == 0:
            print("\n⚠️ No products discovered/downloaded in the short run.")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if platform:
            await platform.__aexit__(None, None, None)
        disable_debug()
        print("\n🏁 Debug Session Ended")

if __name__ == "__main__":
    asyncio.run(main())
