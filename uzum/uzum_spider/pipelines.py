import os
import psycopg2
from psycopg2.extras import Json
from uzum_spider.items import UzumProduct, UzumSeller, UzumSku

class PostgresPipeline:
    def __init__(self):
        self.connection_url = os.environ.get("DATABASE_URL")
        self.conn = None
        self.cur = None

    def open_spider(self, spider):
        self.conn = psycopg2.connect(self.connection_url)
        self.cur = self.conn.cursor()

    def close_spider(self, spider):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        if isinstance(item, UzumProduct):
            self._process_product(item)
        return item

    def _process_product(self, item):
        try:
            # 1. Upsert Seller
            seller = item.get('seller')
            if seller:
                self.cur.execute("""
                    INSERT INTO sellers (id, name, url, rating, reviews_count, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        rating = EXCLUDED.rating,
                        reviews_count = EXCLUDED.reviews_count,
                        updated_at = CURRENT_TIMESTAMP
                """, (seller['id'], seller['name'], seller['url'], seller['rating'], seller['reviews_count']))

            # 2. Upsert Product
            # Prepare specs and images as JSON
            specs = Json(item.get('specs', {})) # Assuming specs are in item, though not explicitly extracted yet
            images = Json(item.get('images', [])) # Assuming images are in item

            self.cur.execute("""
                INSERT INTO products (id, title, category_id, category_name, seller_id, url, total_orders, rating, reviews_count, is_eco, adult_category, specs, images, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    total_orders = EXCLUDED.total_orders,
                    rating = EXCLUDED.rating,
                    reviews_count = EXCLUDED.reviews_count,
                    updated_at = CURRENT_TIMESTAMP
            """, (item['id'], item['title'], item['category_id'], item['category_name'], item['seller_id'], 
                  item['url'], item['total_orders'], item['rating'], item['reviews_count'], item['is_eco'], item['adult_category'],
                  specs, images))

            # 3. Process SKUs and Prices
            skus = item.get('skus', [])
            for sku in skus:
                # Upsert SKU
                self.cur.execute("""
                    INSERT INTO skus (id, product_id, name, image_url, full_price, sell_price, available_amount, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        full_price = EXCLUDED.full_price,
                        sell_price = EXCLUDED.sell_price,
                        available_amount = EXCLUDED.available_amount,
                        updated_at = CURRENT_TIMESTAMP
                """, (sku['id'], item['id'], sku['name'], sku['image_url'], sku['full_price'], sku['sell_price'], sku['available_amount']))

                # Insert Price History
                self.cur.execute("""
                    INSERT INTO price_history (sku_id, product_id, price, old_price, is_available, timestamp)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (sku['id'], item['id'], sku['sell_price'], sku['full_price'], sku['available_amount'] > 0))

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Error processing item {item.get('id')}: {e}")
            raise
