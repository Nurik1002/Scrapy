import scrapy
import json
from ..items import ShopItem

class ShopSpider(scrapy.Spider):
    name = "shops"
    allowed_domains = ["xarid-api-shop.uzex.uz"]
    
    LIST_URL = "https://xarid-api-shop.uzex.uz/Common/GetNotCompletedDeals"
    
    def start_requests(self):
        yield self.make_list_request(page=1)

    def make_list_request(self, page):
        payload = {
            "region_ids": [],
            "display_on_shop": 1,
            "display_on_national": 0,
            "from": (page - 1) * 10 + 1,
            "to": page * 10
        }
        return scrapy.Request(
            url=self.LIST_URL,
            method="POST",
            body=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
            callback=self.parse_list,
            meta={'page': page}
        )

    def parse_list(self, response):
        data = response.json()
        if not data:
            self.logger.info("No more shop deals found.")
            return

        for deal in data:
            # Shop deals in the list already contain "details" enough for us,
            # but to be consistent with the "details" fetch pattern (and if we needed more info),
            # we could fetch individual items.
            # However, our research showed that fetching by lot_id returns the same object in a list.
            # So we can just process this deal directly as an item.
            
            item = ShopItem()
            item.update(deal)
            
            # Construct "products" list from the deal itself as per our model
            product = {
                "rn": deal.get("rn", 1),
                "product_name": deal.get("product_name"),
                "amount": deal.get("amount"),
                "measure_name": deal.get("measure_name"),
                "features": None,
                "price": deal.get("price"),
                "country_name": None
            }
            item['products'] = [product]
            yield item

        # Pagination
        current_page = response.meta['page']
        if current_page < 5:
            yield self.make_list_request(current_page + 1)
