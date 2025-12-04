import requests
import json
import time
import os

class APIClient:
    BASE_URL = "https://xarid-api-trade.uzex.uz"
    HEADERS = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    }

    def __init__(self, data_dir="app/data"):
        self.data_dir = data_dir
        self.raw_dir = os.path.join(data_dir, "raw")
        os.makedirs(self.raw_dir, exist_ok=True)

    def _get(self, endpoint, params=None):
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = requests.get(url, headers=self.HEADERS, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _post(self, endpoint, payload=None):
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            print(f"POSTing to {url} with payload {payload}")
            response = requests.post(url, headers=self.HEADERS, json=payload or {})
            print(f"Response status: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error posting to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
            return None

    def get_categories(self):
        print("Fetching categories...")
        data = self._get("Lib/GetCategories")
        if data:
            self._save_json(data, "categories.json")
            return data
        return []

    def get_products(self, page=1, page_size=100):
        print(f"Fetching products page {page}...")
        # Payload derived from interception (though explicit payload wasn't captured for this one, 
        # the shop payload suggests a pattern. Let's try a standard pagination payload)
        # Actually, let's use the one from Shop deals as a template if needed, 
        # but for now, simple pagination might work or we can stick to what worked in curl (empty payload returned empty list?)
        # Wait, curl with empty payload returned [], so we NEED a payload.
        # Let's try a generic filter payload.
        payload = {
            "page": page,
            "count": page_size,
            # "search": "" # Optional
        }
        data = self._post("Lib/GetProductsForInfo", payload)
        if data:
            self._save_json(data, f"products_page_{page}.json")
            return data
        return []

    def get_auctions(self, page=1, page_size=10):
        print(f"Fetching auctions page {page}...")
        # Payload from intercepted_1764831330_GetCompletedDeals.json
        payload = {
            "region_ids": [],
            "district_ids": [],
            "from": (page - 1) * page_size + 1,
            "to": page * page_size,
            "lot_id": None,
            "inn": None,
            "customer_name": None,
            "start_date": None,
            "end_date": None
        }
        # Use full URL to be safe and specific
        url = "https://xarid-api-auction.uzex.uz/Common/GetCompletedDeals"
        try:
            print(f"POSTing to {url} with payload {payload}")
            response = requests.post(url, headers=self.HEADERS, json=payload)
            print(f"Response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            if data:
                self._save_json(data, f"auctions_page_{page}.json")
                return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching auctions: {e}")
            return None
        return []

    def get_shop_deals(self, page=1, page_size=10):
        print(f"Fetching shop deals page {page}...")
        # Payload from intercepted_1764831340_GetNotCompletedDeals.json
        # Note: The endpoint is on a DIFFERENT subdomain: xarid-api-shop.uzex.uz
        # We need to handle this.
        url = "https://xarid-api-shop.uzex.uz/Common/GetNotCompletedDeals"
        payload = {
            "region_ids": [],
            "display_on_shop": 1,
            "display_on_national": 0,
            "from": (page - 1) * page_size + 1,
            "to": page * page_size
        }
        
        try:
            print(f"POSTing to {url} with payload {payload}")
            response = requests.post(url, headers=self.HEADERS, json=payload)
            print(f"Response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            if data:
                self._save_json(data, f"shop_deals_page_{page}.json")
                return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching shop deals: {e}")
            return None
        return []

    def get_auction_products(self, lot_id):
        print(f"Fetching products for auction lot {lot_id}...")
        url = f"https://xarid-api-auction.uzex.uz/Common/GetCompletedDealProducts/{lot_id}"
        try:
            response = requests.get(url, headers=self.HEADERS)
            response.raise_for_status()
            data = response.json()
            if data:
                # Normalize data to match DealProduct model
                normalized_data = []
                for item in data:
                    normalized_item = item.copy()
                    # Map fields
                    if "order_num" in item:
                        normalized_item["rn"] = item["order_num"]
                    if "quantity" in item:
                        normalized_item["amount"] = item["quantity"]
                    
                    # Ensure product_name is handled (it can be null)
                    # We keep it as is, but model needs to be Optional
                    
                    normalized_data.append(normalized_item)
                
                self._save_json(normalized_data, f"auction_products_{lot_id}.json")
                return normalized_data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching auction products for {lot_id}: {e}")
            return None
        return []

    def get_shop_products(self, lot_id):
        print(f"Fetching products for shop lot {lot_id}...")
        # Since shop deals seem to be single items and details are in the list,
        # we try to fetch the specific deal using the list endpoint with a filter.
        url = "https://xarid-api-shop.uzex.uz/Common/GetNotCompletedDeals"
        payload = {
            "region_ids": [],
            "display_on_shop": 1,
            "display_on_national": 0,
            "from": 1,
            "to": 10,
            "lot_id": str(lot_id) # Try passing lot_id
        }
        
        try:
            print(f"POSTing to {url} with payload {payload}")
            response = requests.post(url, headers=self.HEADERS, json=payload)
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                # The response is a list of deals.
                # We map this single deal to a list of "products" (which is just the deal itself)
                # to match the interface of get_auction_products
                deal = data[0]
                product = {
                    "rn": deal.get("rn", 1),
                    "product_name": deal.get("product_name"),
                    "amount": deal.get("amount"),
                    "measure_name": deal.get("measure_name", "dona"), # Default or missing
                    "features": None, # Shop deals might not have this detailed feature list in the same way
                    "price": deal.get("price"),
                    "country_name": None
                }
                self._save_json([product], f"shop_products_{lot_id}.json")
                return [product]
            else:
                print(f"No shop deal found for lot_id {lot_id}")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching shop products for {lot_id}: {e}")
            return None
        return []

    def _save_json(self, data, filename):
        filepath = os.path.join(self.raw_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved {filename}")

if __name__ == "__main__":
    client = APIClient()
    # Example usage:
    # categories = client.get_categories()
    # products = client.get_products(page=1)
    # auctions = client.get_auctions(page=1)
    # shop_deals = client.get_shop_deals(page=1)
    
    # if auctions:
    #     auction_details = client.get_auction_products(auctions[0]['lot_id'])
    
    # if shop_deals:
    #     shop_details = client.get_shop_products(shop_deals[0]['lot_id'])
    pass
