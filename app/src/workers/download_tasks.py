"""
Download Tasks - Celery tasks for downloading products.
"""

import asyncio
import logging
from typing import Optional

from celery import shared_task

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


def run_async(coro):
    """Run async function in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scan_id_range(
    self, platform: str, start_id: int, end_id: int, target: int = None
) -> dict:
    """
    Scan product ID range and download valid products.

    Args:
        platform: Platform name (e.g., 'uzum')
        start_id: Starting product ID
        end_id: Ending product ID
        target: Stop after finding N products

    Returns:
        Statistics dict
    """
    logger.info(f"Starting scan: {platform} IDs {start_id}-{end_id} (target={target})")

    try:
        if platform == "uzum":
            from src.platforms.uzum import UzumDownloader

            async def do_download():
                downloader = UzumDownloader(concurrency=50)
                stats = await downloader.download_range(
                    start_id=start_id, end_id=end_id, target=target, resume=True
                )
                return {
                    "processed": stats.processed,
                    "found": stats.found,
                    "rate": stats.rate,
                    "success_rate": stats.success_rate,
                }

            return run_async(do_download())

        elif platform == "uzex":
            from src.platforms.uzex import UzexDownloader

            async def do_download():
                downloader = UzexDownloader(batch_size=100)
                stats = await downloader.download_lots(
                    lot_type="auction",
                    status="completed",
                    target=target,
                    start_from=start_id,
                    resume=True,
                    skip_existing=True,
                )
                return {
                    "processed": stats.processed,
                    "found": stats.found,
                    "rate": stats.rate,
                }

            return run_async(do_download())

        else:
            raise ValueError(f"Unknown platform: {platform}")

    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3)
def download_product(self, platform: str, product_id: int) -> Optional[dict]:
    """
    Download a single product.

    Args:
        platform: Platform name
        product_id: Product ID

    Returns:
        Parsed product data or None
    """
    try:
        if platform == "uzum":
            from src.platforms.uzum import UzumClient, parser

            async def do_fetch():
                client = UzumClient()
                await client.connect()
                try:
                    raw = await client.fetch_product(product_id)
                    if raw:
                        parsed = parser.parse_product(raw)
                        if parsed:
                            return {
                                "id": parsed.id,
                                "title": parsed.title,
                                "seller_id": parsed.seller_id,
                                "price": parsed.skus[0]["purchase_price"]
                                if parsed.skus
                                else None,
                            }
                finally:
                    await client.close()
                return None

            return run_async(do_fetch())

        elif platform == "uzex":
            # For Uzex, product_id is lot_id
            from src.platforms.uzex import UzexClient, parser

            async def do_fetch():
                client = UzexClient()
                await client.connect()
                try:
                    # Fetch completed auction lot
                    data = await client.get_completed_auctions(product_id, product_id)
                    if data:
                        lot = parser.parse_lot(data[0], "auction", "completed")
                        if lot:
                            return {
                                "id": lot.id,
                                "title": lot.title,
                                "price": lot.price,
                                "status": lot.status,
                            }
                finally:
                    await client.close()
                return None

            return run_async(do_fetch())

        raise ValueError(f"Unknown platform: {platform}")

    except Exception as e:
        logger.error(f"Download failed for {product_id}: {e}")
        raise self.retry(exc=e)


@shared_task
def download_batch(platform: str, product_ids: list) -> dict:
    """
    Download a batch of products.

    Args:
        platform: Platform name
        product_ids: List of product IDs

    Returns:
        Statistics dict
    """
    logger.info(f"Downloading batch of {len(product_ids)} products")

    if platform == "uzum":
        from src.platforms.uzum import UzumClient

        async def do_batch():
            client = UzumClient(concurrency=50)
            await client.connect()
            try:
                results = await client.fetch_batch(product_ids)
                return {
                    "requested": len(product_ids),
                    "found": len(results),
                }
            finally:
                await client.close()

        return run_async(do_batch())

    elif platform == "uzex":
        # For Uzex, batch download lots
        from src.platforms.uzex import UzexClient, parser

        async def do_batch():
            client = UzexClient()
            await client.connect()
            try:
                results = []
                # Fetch lots individually (no batch API available)
                for lot_id in product_ids:
                    data = await client.get_completed_auctions(lot_id, lot_id)
                    if data:
                        results.append(data[0])
                return {
                    "requested": len(product_ids),
                    "found": len(results),
                }
            finally:
                await client.close()

        return run_async(do_batch())

    raise ValueError(f"Unknown platform: {platform}")
