import scrapy
import json
from ..items import AuctionItem

class AuctionSpider(scrapy.Spider):
    name = "auctions"
    allowed_domains = ["xarid-api-auction.uzex.uz"]
    
    # API Endpoints
    LIST_URL = "https://xarid-api-auction.uzex.uz/Common/GetCompletedDeals"
    DETAILS_URL_TEMPLATE = "https://xarid-api-auction.uzex.uz/Common/GetCompletedDealProducts/{}"
    
    def start_requests(self):
        # Initial request to get first page
        yield self.make_list_request(page=1)

    def make_list_request(self, page):
        payload = {
            "region_ids": [],
            "district_ids": [],
            "from": (page - 1) * 10 + 1,
            "to": page * 10,
            "lot_id": None,
            "inn": None,
            "customer_name": None,
            "start_date": None,
            "end_date": None
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
            self.logger.info("No more auctions found.")
            return

        for deal in data:
            lot_id = deal.get('lot_id')
            if lot_id:
                # Request details
                yield scrapy.Request(
                    url=self.DETAILS_URL_TEMPLATE.format(lot_id),
                    callback=self.parse_details,
                    meta={'deal_data': deal}
                )

        # Pagination: Request next page
        current_page = response.meta['page']
        # Limit for testing, remove or increase for production
        if current_page < 5: 
            yield self.make_list_request(current_page + 1)

    def parse_details(self, response):
        deal_data = response.meta['deal_data']
        products_data = response.json()
        
        item = AuctionItem()
        item.update(deal_data)
        
        # Normalize products
        normalized_products = []
        for p in products_data:
            norm = p.copy()
            norm['rn'] = p.get('order_num', p.get('rn'))
            norm['amount'] = p.get('quantity', p.get('amount'))
            normalized_products.append(norm)
            
        item['products'] = normalized_products
        yield item
