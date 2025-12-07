#!/usr/bin/env python3
"""
Quick script to process UZEX JSON files into database.
"""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

# Setup path
import sys
sys.path.insert(0, '/app')

from src.core.database import get_session
from src.platforms.uzex.models import UzexLot, UzexLotItem
from src.platforms.uzex.parser import parser
from src.core.bulk_ops import bulk_upsert_uzex_lots, bulk_insert_uzex_items

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_uzex_files(directory: str) -> dict:
    """Process UZEX JSON files."""
    base_path = Path(directory)
    
    # Find all JSON files
    json_files = list(base_path.rglob("*.json"))
    logger.info(f"Found {len(json_files)} UZEX JSON files")
    
    stats = {"total": len(json_files), "processed": 0, "lots": 0, "items": 0, "errors": 0}
    
    lots_buffer = []
    items_buffer = []
    
    async with get_session() as session:
        for json_file in json_files:
            try:
                with open(json_file) as f:
                    raw_data = json.load(f)
                
                # Determine lot type from path
                lot_type = "auction"
                if "auction" in str(json_file):
                    lot_type = "auction"
                elif "shop" in str(json_file):
                    lot_type = "shop"
                
                # Parse lot
                lot_data = parser.parse_lot(raw_data, lot_type=lot_type, status="completed")
                if not lot_data:
                    continue
                
                # Prepare lot dict for bulk insert
                lot_dict = {
                    "id": lot_data.id,
                    "display_no": lot_data.display_no,
                    "lot_type": lot_data.lot_type,
                    "status": lot_data.status,
                    "is_budget": lot_data.is_budget,
                    "type_name": lot_data.type_name,
                    "start_cost": lot_data.start_cost,
                    "deal_cost": lot_data.deal_cost,
                    "currency_name": lot_data.currency_name,
                    "customer_name": lot_data.customer_name,
                    "customer_inn": lot_data.customer_inn,
                    "customer_region": lot_data.customer_region,
                    "provider_name": lot_data.provider_name,
                    "provider_inn": lot_data.provider_inn,
                    "deal_id": lot_data.deal_id,
                    "deal_date": lot_data.deal_date,
                    "category_name": lot_data.category_name,
                    "pcp_count": lot_data.pcp_count,
                    "lot_start_date": lot_data.lot_start_date,
                    "lot_end_date": lot_data.lot_end_date,
                    "kazna_status": lot_data.kazna_status,
                    "raw_data": lot_data.raw_data,
                }
                lots_buffer.append(lot_dict)
                stats["lots"] += 1
                
                # Parse items if present
                items_data = raw_data.get("lot_items") or raw_data.get("items") or []
                if items_data:
                    parsed_items = parser.parse_lot_items(items_data)
                    for item in parsed_items:
                        item_dict = {
                            "lot_id": lot_data.id,
                            "order_num": item.order_num,
                            "product_name": item.product_name,
                            "description": item.description,
                            "quantity": item.quantity,
                            "measure_name": item.measure_name,
                            "price": item.price,
                            "cost": item.cost,
                            "currency_name": item.currency_name,
                            "country_name": item.country_name,
                            "properties": item.properties,
                        }
                        items_buffer.append(item_dict)
                        stats["items"] += 1
                
                stats["processed"] += 1
                
                # Bulk insert every 500 records
                if len(lots_buffer) >= 500:
                    await bulk_upsert_uzex_lots(session, lots_buffer)
                    if items_buffer:
                        await bulk_insert_uzex_items(session, items_buffer)
                    await session.commit()
                    logger.info(f"Processed {stats['processed']}/{stats['total']}: {stats['lots']} lots, {stats['items']} items")
                    lots_buffer = []
                    items_buffer = []
                    
            except Exception as e:
                logger.error(f"Error processing {json_file}: {e}")
                stats["errors"] += 1
        
        # Insert remaining
        if lots_buffer:
            await bulk_upsert_uzex_lots(session, lots_buffer)
            if items_buffer:
                await bulk_insert_uzex_items(session, items_buffer)
            await session.commit()
        
        logger.info(f"FINAL: {stats}")
    
    return stats


if __name__ == "__main__":
    result = asyncio.run(process_uzex_files("/app/storage/raw/uzex/"))
    print(f"\n=== UZEX PROCESSING COMPLETE ===")
    print(result)
