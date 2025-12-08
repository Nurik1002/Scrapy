import requests
import json
import time

# Configuration for Big 5
TARGETS = [
    {
        "name": "Electronics_Smartphones",
        # Smartpones usually: catalog/elektronika/smartfony-i-telefony/vse-smartfony
        # Need to find the exact shard/query. 
        # Using a known search query is safer if shard is complex to derive dynamically.
        # But let's try to search or use a hardcoded known shard for smartphones if possible.
        # "shard": "electron", "query": "subject=515" is common. 
        # Let's use search API for simplicity to find IDs, then Card API for details.
        "search_query": "iphone 15"
    },
    {
        "name": "Clothing_Dresses",
        "search_query": "платье женское"
    },
    {
        "name": "Home_Bedding",
        "search_query": "постельное белье"
    },
    {
        "name": "Auto_Accessories",
        "search_query": "автомобильный пылесос"
    },
    {
        "name": "Beauty_Lipstick",
        "search_query": "помада"
    }
]

SEARCH_API = "https://search.wb.ru/exactmatch/ru/common/v4/search?appType=1&curr=rub&dest=-1257786&query={q}&resultset=catalog&sort=popular&spp=0&suppressSpellcheck=false"
CARD_API = "https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={ids}"

def fetch_samples():
    samples = {}
    
    for target in TARGETS:
        print(f"Fetching {target['name']}...")
        
        # 1. Search to get IDs
        q = target['search_query']
        url = SEARCH_API.format(q=q)
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            products = data.get('data', {}).get('products', [])
            
            # Take top 3
            top_3 = products[:3]
            ids = [str(p['id']) for p in top_3]
            print(f"  Found IDs: {ids}")
            
            if not ids:
                print("  No products found!")
                continue
                
            # 2. Fetch Details
            ids_str = ";".join(ids)
            card_url = CARD_API.format(ids=ids_str)
            card_resp = requests.get(card_url, timeout=10)
            card_data = card_resp.json()
            
            items = card_data.get('data', {}).get('products', [])
            samples[target['name']] = items
            
            time.sleep(1) # Be nice
            
        except Exception as e:
            print(f"  Error: {e}")

    # Save to file
    with open('product_samples.json', 'w', encoding='utf-8') as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    
    print("Saved samples to product_samples.json")

if __name__ == "__main__":
    fetch_samples()
