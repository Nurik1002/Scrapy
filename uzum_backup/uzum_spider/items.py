import scrapy

class UzumSeller(scrapy.Item):
    id = scrapy.Field()
    name = scrapy.Field()
    url = scrapy.Field()
    rating = scrapy.Field()
    reviews_count = scrapy.Field()

class UzumProduct(scrapy.Item):
    id = scrapy.Field()
    title = scrapy.Field()
    category_id = scrapy.Field()
    category_name = scrapy.Field()
    seller_id = scrapy.Field()
    url = scrapy.Field()
    total_orders = scrapy.Field()
    rating = scrapy.Field()
    reviews_count = scrapy.Field()
    is_eco = scrapy.Field()
    adult_category = scrapy.Field()
    
    # Nested data for pipeline processing
    seller = scrapy.Field() # UzumSeller item
    skus = scrapy.Field()   # List of UzumSku items

class UzumSku(scrapy.Item):
    id = scrapy.Field()
    product_id = scrapy.Field()
    name = scrapy.Field()
    image_url = scrapy.Field()
    full_price = scrapy.Field()
    sell_price = scrapy.Field()
    available_amount = scrapy.Field()

class UzumPrice(scrapy.Item):
    sku_id = scrapy.Field()
    product_id = scrapy.Field()
    price = scrapy.Field()
    old_price = scrapy.Field()
    is_available = scrapy.Field()
    scraped_at = scrapy.Field()
