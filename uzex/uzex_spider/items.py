import scrapy

class AuctionItem(scrapy.Item):
    lot_id = scrapy.Field()
    lot_start_date = scrapy.Field()
    lot_end_date = scrapy.Field()
    category_name = scrapy.Field()
    start_cost = scrapy.Field()
    deal_cost = scrapy.Field()
    customer_name = scrapy.Field()
    provider_name = scrapy.Field()
    deal_date = scrapy.Field()
    deal_id = scrapy.Field()
    lot_display_no = scrapy.Field()
    # Details
    products = scrapy.Field() # List of dicts

class ShopItem(scrapy.Item):
    id = scrapy.Field()
    start_date = scrapy.Field()
    end_date = scrapy.Field()
    product_name = scrapy.Field()
    category_name = scrapy.Field()
    cost = scrapy.Field()
    price = scrapy.Field()
    amount = scrapy.Field()
    pcp_count = scrapy.Field()
    rn = scrapy.Field()
    total_count = scrapy.Field()
    # Details
    products = scrapy.Field() # List of dicts
