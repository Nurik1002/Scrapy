import scrapy
import json
import re
from scrapy_playwright.page import PageMethod
from uzum_spider.items import UzumProduct, UzumSeller, UzumSku

class UzumSpider(scrapy.Spider):
    name = "uzum"
    allowed_domains = ["uzum.uz"]
    
    def __init__(self, category_url=None, *args, **kwargs):
        super(UzumSpider, self).__init__(*args, **kwargs)
        self.start_urls = [category_url] if category_url else [
            "https://uzum.uz/ru/category/elektronika-10020"
        ]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    playwright_page_methods=[
                        PageMethod("wait_for_selector", "a[href*='/product/']"),
                        PageMethod("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                        PageMethod("wait_for_timeout", 5000),
                    ],
                ),
                callback=self.parse_category
            )

    async def parse_category(self, response):
        page = response.meta["playwright_page"]
        
        # Extract product links
        product_links = await page.evaluate("""
            Array.from(document.querySelectorAll('a[href*="/product/"]')).map(a => a.href)
        """)
        
        await page.close()

        for link in set(product_links):
            # Extract ID from URL
            # URL format: https://uzum.uz/ru/product/title-12345
            match = re.search(r'-(\d+)(?:\?|$)', link)
            if match:
                product_id = match.group(1)
                api_url = f"https://api.uzum.uz/api/v2/product/{product_id}"
                yield scrapy.Request(
                    api_url,
                    callback=self.parse_product_api,
                    meta={'product_url': link} # Pass original URL for reference
                )
            else:
                self.logger.warning(f"Could not extract ID from link: {link}")

    def parse_product_api(self, response):
        try:
            data = response.json()
            payload = data.get('payload', {}).get('data', {}) # Adjust based on actual API response structure
            
            # If the structure is different, we might need to debug. 
            # Assuming 'payload' -> 'data' based on common patterns, 
            # but if it's direct root, we'll see.
            # Let's try to be robust:
            if 'payload' in data and 'data' in data['payload']:
                product_data = data['payload']['data']
            else:
                product_data = data # Fallback if root is the object

            if not product_data:
                self.logger.error(f"No product data found in API response: {response.url}")
                return

            item = UzumProduct()
            item['id'] = product_data.get('id')
            item['title'] = product_data.get('title')
            item['category_id'] = product_data.get('category', {}).get('id')
            item['category_name'] = product_data.get('category', {}).get('title')
            item['url'] = response.meta.get('product_url')
            item['total_orders'] = product_data.get('ordersQuantity', 0)
            item['rating'] = product_data.get('rating', 0)
            item['reviews_count'] = product_data.get('reviewsAmount', 0)
            item['is_eco'] = product_data.get('isEco', False)
            item['adult_category'] = product_data.get('adultCategory', False)

            # Seller
            seller_data = product_data.get('seller', {})
            seller_item = UzumSeller()
            seller_item['id'] = seller_data.get('id')
            seller_item['name'] = seller_data.get('title')
            seller_item['url'] = f"https://uzum.uz{seller_data.get('url')}" if seller_data.get('url') else None
            seller_item['rating'] = seller_data.get('rating')
            seller_item['reviews_count'] = seller_data.get('reviews')
            item['seller'] = seller_item
            item['seller_id'] = seller_item['id']

            # SKUs
            skus = []
            for sku_data in product_data.get('skuList', []):
                sku = UzumSku()
                sku['id'] = sku_data.get('id')
                sku['product_id'] = item['id']
                
                # Construct name from characteristics
                chars = [c['value'] for c in sku_data.get('characteristics', [])]
                sku['name'] = ", ".join(chars)
                
                sku['available_amount'] = sku_data.get('availableAmount', 0)
                sku['full_price'] = sku_data.get('fullPrice', 0)
                sku['sell_price'] = sku_data.get('purchasePrice', 0)
                
                # Find image for this SKU
                # Usually SKU has an image ID or index, need to map to photos
                # For now, let's grab the first photo of the product or specific if available
                # sku_data might have 'photoKey' or similar?
                # Let's look at 'photos' in product_data
                photos = product_data.get('photos', [])
                # Simple logic: if photos exist, take first. 
                # Better logic: match characteristics to photos if possible.
                if photos:
                     sku['image_url'] = photos[0].get('photo', {}).get('700', {}).get('high') # Example path

                skus.append(sku)
            
            item['skus'] = skus
            
            yield item

        except Exception as e:
            self.logger.error(f"Error parsing API response {response.url}: {e}")
