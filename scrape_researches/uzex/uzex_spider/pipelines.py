from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from .models import Base, AuctionDealModel, AuctionProductModel, ShopDealModel, ShopProductModel
from .items import AuctionItem, ShopItem
import os
from datetime import datetime

class PostgresPipeline:
    def __init__(self, db_url):
        self.db_url = db_url
        self.engine = None
        self.Session = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            db_url=crawler.settings.get('DATABASE_URL')
        )

    def open_spider(self, spider):
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def close_spider(self, spider):
        pass

    def process_item(self, item, spider):
        session = self.Session()
        try:
            if isinstance(item, AuctionItem):
                self._process_auction(session, item)
            elif isinstance(item, ShopItem):
                self._process_shop(session, item)
            session.commit()
        except Exception as e:
            session.rollback()
            spider.logger.error(f"Error saving item: {e}")
        finally:
            session.close()
        return item

    def _process_auction(self, session, item):
        # Check if exists
        exists = session.query(AuctionDealModel).filter_by(lot_id=item['lot_id']).first()
        if exists:
            return # Skip duplicates

        deal = AuctionDealModel(
            lot_id=item['lot_id'],
            lot_start_date=self._parse_date(item.get('lot_start_date')),
            lot_end_date=self._parse_date(item.get('lot_end_date')),
            category_name=item.get('category_name'),
            start_cost=item.get('start_cost'),
            deal_cost=item.get('deal_cost'),
            customer_name=item.get('customer_name'),
            provider_name=item.get('provider_name'),
            deal_date=self._parse_date(item.get('deal_date')),
            deal_id=item.get('deal_id'),
            lot_display_no=item.get('lot_display_no')
        )
        session.add(deal)
        session.flush() # Get ID

        for prod in item.get('products', []):
            product = AuctionProductModel(
                deal_id=deal.id,
                rn=prod.get('rn'),
                product_name=prod.get('product_name'),
                amount=prod.get('amount'),
                measure_name=prod.get('measure_name'),
                features=prod.get('features'),
                price=prod.get('price'),
                country_name=prod.get('country_name'),
                description=prod.get('description'),
                currency_name=prod.get('currency_name'),
                js_properties=prod.get('js_properties'),
                cost=prod.get('cost')
            )
            session.add(product)

    def _process_shop(self, session, item):
        exists = session.query(ShopDealModel).filter_by(lot_id=item['id']).first()
        if exists:
            return

        deal = ShopDealModel(
            lot_id=item['id'],
            start_date=self._parse_date(item.get('start_date')),
            end_date=self._parse_date(item.get('end_date')),
            product_name=item.get('product_name'),
            category_name=item.get('category_name'),
            cost=item.get('cost'),
            price=item.get('price'),
            amount=item.get('amount'),
            pcp_count=item.get('pcp_count'),
            rn=item.get('rn'),
            total_count=item.get('total_count')
        )
        session.add(deal)
        session.flush()

        for prod in item.get('products', []):
            product = ShopProductModel(
                deal_id=deal.id,
                rn=prod.get('rn'),
                product_name=prod.get('product_name'),
                amount=prod.get('amount'),
                measure_name=prod.get('measure_name'),
                features=prod.get('features'),
                price=prod.get('price'),
                country_name=prod.get('country_name')
            )
            session.add(product)

    def _parse_date(self, date_str):
        if not date_str:
            return None
        # Handle various date formats if needed, but API usually sends ISO or standard
        # Example: "04.12.2024 16:15" or ISO
        try:
            # Try ISO first
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            try:
                # Try DD.MM.YYYY HH:MM:SS
                return datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")
            except:
                try:
                    return datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                except:
                    return None
