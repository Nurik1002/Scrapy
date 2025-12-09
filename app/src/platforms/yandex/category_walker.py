"""
Yandex Market Category Walker - Product discovery through category traversal

This module implements the "Category Walker" strategy for discovering products
on Yandex Market, since direct ID iteration is not possible due to non-sequential
alphanumeric product IDs.

Key Features:
- Seed category loading from sitemap or manual lists
- Deep pagination support (up to 400 pages per category)
- Product URL extraction with ID/slug parsing
- Resumable crawling with Redis checkpointing
- Rate limiting and anti-bot evasion
- Subcategory discovery and traversal
- Progress tracking and statistics
"""

import asyncio
import logging
import re
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, unquote, parse_qs, urlparse

import redis.asyncio as redis
from bs4 import BeautifulSoup

from ...core.config import settings
from .client import YandexClient

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


class CategoryWalker:
    """
    Discovers products by walking through Yandex Market category pages.

    Uses the "Category Walker" strategy to overcome the limitation of
    non-sequential product IDs on Yandex Market.
    """

    # Product URL patterns to extract from category pages
    PRODUCT_URL_PATTERNS = [
        r'href="(/product--[^"]+)"',
        r'href="(/offer/[^"]+)"',
        r'href="(https://market\.yandex\.uz/product--[^"]+)"',
        r'"url":"(/product--[^"]+)"',
        r"/product--([^/]+)/(\d+)",  # Extract slug and ID
    ]

    # Category URL patterns
    CATEGORY_URL_PATTERNS = [
        r'href="(/catalog--[^"]+)"',
        r'href="(https://market\.yandex\.uz/catalog--[^"]+)"',
        r"/catalog--([^/]+)/(\d+)",  # Extract category slug and ID
    ]

    def __init__(
        self,
        client: Optional[YandexClient] = None,
        redis_client: Optional[redis.Redis] = None,
        max_pages_per_category: int = 400,
        max_concurrent_categories: int = 3,
        checkpoint_interval: int = 100,  # Save progress every N products
    ):
        self.client = client
        self.redis_client = redis_client
        self.max_pages_per_category = max_pages_per_category
        self.max_concurrent_categories = max_concurrent_categories
        self.checkpoint_interval = checkpoint_interval

        # Progress tracking
        self.stats = {
            "categories_processed": 0,
            "pages_processed": 0,
            "products_discovered": 0,
            "subcategories_discovered": 0,
            "start_time": None,
            "last_checkpoint": None,
        }

        # Discovered data storage
        self.discovered_products: Set[str] = set()
        self.discovered_categories: Set[str] = set()

        # Checkpoint keys for Redis
        self.checkpoint_key = "yandex:category_walker:progress"
        self.products_key = "yandex:category_walker:products"

    async def __aenter__(self):
        """Async context manager entry."""
        debug_logger.debug("Initializing CategoryWalker context")

        if not self.client:
            debug_logger.debug("Creating new YandexClient with concurrency=5")
            self.client = YandexClient(concurrency=5)  # Conservative for categories
            await self.client.__aenter__()

        if not self.redis_client:
            debug_logger.debug(f"Connecting to Redis: {settings.redis.url}")
            self.redis_client = redis.from_url(settings.redis.url)

        debug_logger.debug("Loading checkpoint data")
        await self._load_checkpoint()
        debug_logger.debug("CategoryWalker initialized successfully")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        debug_logger.debug("Cleaning up CategoryWalker context")
        await self._save_checkpoint()
        if self.client:
            debug_logger.debug("Closing YandexClient")
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
        if self.redis_client:
            debug_logger.debug("Closing Redis connection")
            await self.redis_client.close()
        debug_logger.debug("CategoryWalker cleanup completed")

    async def _load_checkpoint(self):
        """Load progress from Redis checkpoint."""
        debug_logger.debug(f"Loading checkpoint from Redis key: {self.checkpoint_key}")
        try:
            if not self.redis_client:
                debug_logger.debug("No Redis client available, skipping checkpoint load")
                return

            # Load statistics
            stats_data = await self.redis_client.hgetall(self.checkpoint_key)
            debug_logger.debug(f"Retrieved stats data from Redis: {len(stats_data) if stats_data else 0} keys")

            if stats_data:
                for key, value in stats_data.items():
                    key = key.decode() if isinstance(key, bytes) else key
                    value = value.decode() if isinstance(value, bytes) else value

                    if key in [
                        "categories_processed",
                        "pages_processed",
                        "products_discovered",
                        "subcategories_discovered",
                    ]:
                        self.stats[key] = int(value)
                        debug_logger.debug(f"Loaded stat {key}: {value}")
                    elif key in ["start_time", "last_checkpoint"]:
                        self.stats[key] = value
                        debug_logger.debug(f"Loaded timestamp {key}: {value}")

            # Load discovered products
            debug_logger.debug(f"Loading discovered products from Redis key: {self.products_key}")
            product_ids = await self.redis_client.smembers(self.products_key)
            self.discovered_products = {
                pid.decode() if isinstance(pid, bytes) else pid for pid in product_ids
            }

            logger.info(
                f"Loaded checkpoint: {len(self.discovered_products)} products discovered"
            )
            debug_logger.debug(f"Checkpoint loaded successfully: {self.stats}")

        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            debug_logger.debug(f"Checkpoint load error details: {type(e).__name__}: {str(e)}")

    async def _save_checkpoint(self):
        """Save progress to Redis checkpoint."""
        debug_logger.debug(f"Saving checkpoint to Redis key: {self.checkpoint_key}")
        try:
            if not self.redis_client:
                debug_logger.debug("No Redis client available, skipping checkpoint save")
                return

            # Save statistics
            stats_to_save = {k: str(v) for k, v in self.stats.items() if v is not None}
            stats_to_save["last_checkpoint"] = datetime.now(timezone.utc).isoformat()

            debug_logger.debug(f"Saving stats to Redis: {stats_to_save}")
            await self.redis_client.hset(self.checkpoint_key, mapping=stats_to_save)

            # Save discovered products (using sets for deduplication)
            if self.discovered_products:
                debug_logger.debug(f"Saving {len(self.discovered_products)} discovered products to Redis")
                await self.redis_client.delete(self.products_key)
                await self.redis_client.sadd(
                    self.products_key, *self.discovered_products
                )
                await self.redis_client.expire(self.products_key, 86400 * 7)  # 7 days
                debug_logger.debug(f"Products saved with 7-day expiration")
            else:
                debug_logger.debug("No discovered products to save")

            debug_logger.debug("Checkpoint saved successfully")

        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
            debug_logger.debug(f"Checkpoint save error details: {type(e).__name__}: {str(e)}")

    def _parse_product_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Parse product URL to extract ID and slug.

        Args:
            url: Product URL (relative or absolute)

        Returns:
            Dict with product_id, slug, and full_url
        """
        debug_logger.debug(f"Parsing product URL: {url}")
        try:
            # Handle relative URLs
            if url.startswith("/"):
                full_url = urljoin(self.client.BASE_URL, url)
                debug_logger.debug(f"Converted relative URL to absolute: {full_url}")
                url = full_url

            # Parse product--slug/id OR card/slug/id pattern
            match = re.search(r"/(?:product--|card/)([^/]+)/(\d+)", url)
            if match:
                slug, product_id = match.groups()
                result = {
                    "product_id": product_id,
                    "slug": slug,
                    "url": url,
                    "source": "category_walker",
                }
                debug_logger.debug(f"Successfully parsed product URL: {result}")
                return result
            else:
                debug_logger.debug(f"Product URL pattern not matched: {url}")

        except Exception as e:
            logger.debug(f"Error parsing product URL {url}: {e}")
            debug_logger.debug(f"URL parsing error details: {type(e).__name__}: {str(e)}")

        return None

    def _parse_category_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse category URL to extract ID and slug."""
        debug_logger.debug(f"Parsing category URL: {url}")
        try:
            if url.startswith("/"):
                full_url = urljoin(self.client.BASE_URL, url)
                debug_logger.debug(f"Converted relative category URL to absolute: {full_url}")
                url = full_url

            match = re.search(r"/catalog--([^/]+)/(\d+)", url)
            if match:
                slug, category_id = match.groups()
                result = {"category_id": category_id, "slug": slug, "url": url}
                debug_logger.debug(f"Successfully parsed category URL: {result}")
                return result
            else:
                debug_logger.debug(f"Category URL pattern not matched: {url}")

        except Exception as e:
            logger.debug(f"Error parsing category URL {url}: {e}")
            debug_logger.debug(f"Category URL parsing error details: {type(e).__name__}: {str(e)}")

        return None

    def _extract_products_from_html(self, html: str, json_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """Extract product information from category page HTML using APIARY JSON and Regex fallback."""
        debug_logger.debug(f"Extracting products from HTML ({len(html)} chars)")
        products = []

        # 1. Try to extract from APIARY JSON data (patches)
        try:
            if not json_data:
                # We access the client's method. Ideally should be public, but using private for now.
                json_data = self.client._extract_json_data(html)
            
            patches = json_data.get("apiary_patches", [])
            
            if patches:
                debug_logger.debug(f"Processing {len(patches)} apiary patches for products")
                for patch in patches:
                    widgets = patch.get("widgets", {})
                    
                    # A. Check SearchSchemaOrg for URLs (Most reliable for full URLs)
                    schema_widget = widgets.get("@marketfront/SearchSchemaOrg", {})
                    for key, data in schema_widget.items():
                        url = data.get("url")
                        if url:
                            product_info = self._parse_product_url(url)
                            if (
                                product_info 
                                and product_info["product_id"] not in self.discovered_products
                            ):
                                products.append(product_info)
                                self.discovered_products.add(product_info["product_id"])
                                debug_logger.debug(f"Found product via SchemaOrg: {product_info['slug']}")

                    # B. Check AddToCartButton for Product IDs (Reliable for IDs)
                    cart_widget = widgets.get("@light/AddToCartButton", {})
                    for key, data in cart_widget.items():
                        pending = data.get("pendingCartItem", {})
                        if pending and "productId" in pending:
                            pid = str(pending["productId"])
                            if pid not in self.discovered_products:
                                name = pending.get("name", "")
                                slug = "unknown"
                                if name:
                                    # Basic slugify
                                    slug = "-".join(re.findall(r'\w+', name.lower()))
                                
                                product_info = {
                                    "product_id": pid,
                                    "slug": slug,
                                    "url": f"/product--{slug}/{pid}",
                                    "source": "apiary_cart"
                                }
                                products.append(product_info)
                                self.discovered_products.add(pid)
                                debug_logger.debug(f"Found product via CartButton: {pid}")

            if products:
                debug_logger.debug(f"Found {len(products)} products via JSON patches")
                return products

        except Exception as e:
            debug_logger.debug(f"JSON extraction failed in walker: {e}")

        try:
            # Try regex patterns first (faster)
            debug_logger.debug(f"Testing {len(self.PRODUCT_URL_PATTERNS)} regex patterns")
            for i, pattern in enumerate(self.PRODUCT_URL_PATTERNS):
                matches = re.findall(pattern, html)
                debug_logger.debug(f"Pattern {i + 1} found {len(matches)} matches: {pattern}")

                for match in matches:
                    if isinstance(match, tuple):
                        # Pattern with groups (slug, id)
                        slug, pid = match
                        full_url = f"/product--{slug}/{pid}"
                        product_info = {
                            "product_id": pid,
                            "slug": slug,
                            "url": full_url,
                            "source": "regex_tuple"
                        }
                        
                        if (
                            product_info
                            and product_info["product_id"]
                            not in self.discovered_products
                        ):
                            products.append(product_info)
                            self.discovered_products.add(product_info["product_id"])
                            debug_logger.debug(f"Added new product from regex tuple: {product_info['product_id']}")
                    else:
                        # Simple URL match
                        product_info = self._parse_product_url(match)
                        if (
                            product_info
                            and product_info["product_id"]
                            not in self.discovered_products
                        ):
                            products.append(product_info)
                            self.discovered_products.add(product_info["product_id"])
                            debug_logger.debug(f"Added new product from regex: {product_info['product_id']}")
                        elif product_info and product_info["product_id"] in self.discovered_products:
                            debug_logger.debug(f"Skipping already discovered product: {product_info['product_id']}")

            # Extract from BeautifulSoup for more complex cases
            debug_logger.debug("Using BeautifulSoup for additional product extraction")
            soup = BeautifulSoup(html, "html.parser")

            # Find product links
            product_links = soup.find_all("a", href=re.compile(r"/product--"))
            debug_logger.debug(f"Found {len(product_links)} product links with BeautifulSoup")

            for i, link in enumerate(product_links):
                href = link.get("href")
                if href:
                    debug_logger.debug(f"Processing link {i + 1}: {href}")
                    product_info = self._parse_product_url(href)
                    if (
                        product_info
                        and product_info["product_id"] not in self.discovered_products
                    ):
                        products.append(product_info)
                        self.discovered_products.add(product_info["product_id"])
                        debug_logger.debug(f"Added new product from BeautifulSoup: {product_info['product_id']}")

            debug_logger.debug(f"Product extraction completed: {len(products)} new products found")

        except Exception as e:
            logger.debug(f"Error extracting products from HTML: {e}")
            debug_logger.debug(f"Product extraction error details: {type(e).__name__}: {str(e)}")

        return products

    def _extract_subcategories_from_html(self, html: str) -> List[Dict[str, str]]:
        """Extract subcategory links from category page."""
        debug_logger.debug(f"Extracting subcategories from HTML ({len(html)} chars)")
        subcategories = []

        try:
            debug_logger.debug(f"Testing {len(self.CATEGORY_URL_PATTERNS)} category patterns")
            for i, pattern in enumerate(self.CATEGORY_URL_PATTERNS):
                matches = re.findall(pattern, html)
                debug_logger.debug(f"Category pattern {i + 1} found {len(matches)} matches: {pattern}")

                for match in matches:
                    if isinstance(match, tuple):
                        slug, cat_id = match
                        full_url = f"/catalog--{slug}/{cat_id}"
                        category_info = {"category_id": cat_id, "slug": slug, "url": full_url}
                        
                        if (
                            category_info
                            and category_info["category_id"]
                            not in self.discovered_categories
                        ):
                            subcategories.append(category_info)
                            self.discovered_categories.add(category_info["category_id"])
                            debug_logger.debug(f"Added new subcategory from regex tuple: {category_info['category_id']}")
                    else:
                        category_info = self._parse_category_url(match)
                        if (
                            category_info
                            and category_info["category_id"]
                            not in self.discovered_categories
                        ):
                            subcategories.append(category_info)
                            self.discovered_categories.add(category_info["category_id"])
                            debug_logger.debug(f"Added new subcategory: {category_info['category_id']}")

            debug_logger.debug(f"Subcategory extraction completed: {len(subcategories)} new subcategories found")

        except Exception as e:
            logger.debug(f"Error extracting subcategories: {e}")
            debug_logger.debug(f"Subcategory extraction error details: {type(e).__name__}: {str(e)}")

        return subcategories

    async def walk_category(
        self, category_id: str, category_slug: str = "", max_pages: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, str], None]:
        """
        Walk through all pages of a single category.

        Args:
            category_id: Yandex category ID
            category_slug: Category URL slug
            max_pages: Override max pages for this category

        Yields:
            Product information dictionaries
        """
        max_pages = max_pages or self.max_pages_per_category
        page = 1
        consecutive_empty_pages = 0

        logger.info(f"Walking category {category_id} (slug: {category_slug})")
        debug_logger.debug(f"Category walk config: max_pages={max_pages}, checkpoint_interval={self.checkpoint_interval}")

        while page <= max_pages and consecutive_empty_pages < 3:
            debug_logger.debug(f"Processing category {category_id} page {page}/{max_pages}")
            try:
                # Fetch category page
                debug_logger.debug(f"Fetching category page: {category_id}, slug: {category_slug}, page: {page}")
                category_data = await self.client.fetch_category_page(
                    category_id=category_id, slug=category_slug, page=page
                )

                if not category_data:
                    consecutive_empty_pages += 1
                    logger.debug(
                        f"Empty response for category {category_id} page {page}"
                    )
                    debug_logger.debug(f"Consecutive empty pages count: {consecutive_empty_pages}/3")
                    page += 1
                    continue

                # Extract products from HTML and JSON
                html = category_data.get("html", "") or category_data.get("json_data", {}).get("html", "")
                json_data = category_data.get("json_data", {})
                
                if not html and json_data:
                    # If we have JSON but no HTML string, we might rely solely on JSON
                    # But if we need HTML for fallback regex, we might be out of luck unless we stringify
                    # For now, let's allow empty HTML if we have JSON
                    pass 
                elif not html:
                     html = str(category_data) # Last resort fallback

                debug_logger.debug(f"Extracting products from category {category_id} page {page}")
                products = self._extract_products_from_html(html, json_data)

                if not products:
                    consecutive_empty_pages += 1
                    logger.debug(
                        f"No products found on category {category_id} page {page}"
                    )
                    debug_logger.debug(f"Consecutive empty pages count: {consecutive_empty_pages}/3")
                else:
                    consecutive_empty_pages = 0
                    logger.debug(
                        f"Found {len(products)} products on category {category_id} page {page}"
                    )
                    debug_logger.debug(f"Reset consecutive empty pages counter")

                # Yield discovered products
                for i, product in enumerate(products):
                    product["category_id"] = category_id
                    product["category_slug"] = category_slug
                    product["page"] = page
                    debug_logger.debug(f"Yielding product {i + 1}/{len(products)}: {product['product_id']}")
                    yield product

                    self.stats["products_discovered"] += 1

                    # Checkpoint periodically
                    if (
                        self.stats["products_discovered"] % self.checkpoint_interval
                        == 0
                    ):
                        debug_logger.debug(f"Checkpoint triggered at {self.stats['products_discovered']} products")
                        await self._save_checkpoint()

                # Extract subcategories for deeper traversal
                debug_logger.debug(f"Extracting subcategories from category {category_id} page {page}")
                subcategories = self._extract_subcategories_from_html(html)
                self.stats["subcategories_discovered"] += len(subcategories)
                if subcategories:
                    debug_logger.debug(f"Found {len(subcategories)} subcategories on page {page}")

                self.stats["pages_processed"] += 1
                page += 1

                # Rate limiting between pages
                debug_logger.debug(f"Rate limiting: sleeping 2.0s before next page")
                await asyncio.sleep(2.0)

            except Exception as e:
                logger.warning(
                    f"Error processing category {category_id} page {page}: {e}"
                )
                debug_logger.debug(f"Category page processing error: {type(e).__name__}: {str(e)}")
                consecutive_empty_pages += 1
                page += 1
                debug_logger.debug(f"Error recovery: sleeping 5.0s, moving to page {page}")
                await asyncio.sleep(5.0)  # Longer delay on errors

        self.stats["categories_processed"] += 1
        logger.info(
            f"Completed category {category_id}: {self.stats['products_discovered']} total products discovered"
        )
        debug_logger.debug(f"Category {category_id} completed: {page - 1} pages processed, {consecutive_empty_pages} consecutive empty pages at end")

    async def walk_categories(
        self, seed_categories: List[Dict[str, str]]
    ) -> AsyncGenerator[Dict[str, str], None]:
        """
        Walk through multiple categories concurrently and stream results.

        Args:
           seed_categories: List of dicts with category_id and slug

        Yields:
           Product information dictionaries
        """
        self.stats["start_time"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"Starting category walk with {len(seed_categories)} seed categories"
        )

        queue = asyncio.Queue()

        async def producer(cat: Dict[str, str]):
            try:
                async for item in self.walk_category(
                    cat["category_id"], cat.get("slug", "")
                ):
                    await queue.put(item)
            except Exception as e:
                logger.error(f"Error processing category {cat}: {e}")

        # Process categories in batches to avoid overwhelming the server
        for i in range(0, len(seed_categories), self.max_concurrent_categories):
            batch = seed_categories[i : i + self.max_concurrent_categories]
            tasks = [asyncio.create_task(producer(cat)) for cat in batch]

            # Monitor task to know when all producers in batch are done
            monitor_task = asyncio.gather(*tasks)

            while not monitor_task.done() or not queue.empty():
                try:
                    # Wait for item with timeout to check monitor status
                    item = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield item
                    queue.task_done()
                except asyncio.TimeoutError:
                    if monitor_task.done() and queue.empty():
                        break
                    continue
                except Exception as e:
                    logger.error(f"Error retrieving from queue: {e}")

            # Ensure monitor task is cleaned up
            try:
                await monitor_task
            except Exception as e:
                logger.error(f"Error in batch execution: {e}")

            # Delay between batches
            await asyncio.sleep(2.0)

        logger.info(f"Category walk completed: {self.stats}")

    def get_seed_categories(self) -> List[Dict[str, str]]:
        """
        Get seed categories for crawling.

        This should be expanded to load from sitemap.xml or a comprehensive
        category list. For now, returns a basic set of major categories.
        """
        categories = [
            # Electronics
            {"category_id": "91013", "slug": "elektronika"},
            {"category_id": "91491", "slug": "smartfony"},
            {"category_id": "91491", "slug": "noutbuki"},
            {"category_id": "91533", "slug": "televizory"},
            # Home & Garden
            {"category_id": "91074", "slug": "dom-i-sad"},
            {"category_id": "91268", "slug": "mebel"},
            {"category_id": "91339", "slug": "bytovaya-tekhnika"},
            # Clothing
            {"category_id": "91039", "slug": "odezhda-obuv-i-aksessuary"},
            {"category_id": "91158", "slug": "muzhskaya-odezhda"},
            {"category_id": "91172", "slug": "zhenskaya-odezhda"},
        ]
        return categories

    async def discover_products(
        self, custom_categories: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[Dict[str, str], None]:
        """
        Main method to discover products through category walking.

        Args:
            custom_categories: Custom list of seed categories

        Yields:
            Product information dictionaries ready for detailed scraping
        """
        seed_categories = custom_categories or self.get_seed_categories()

        logger.info(f"Starting product discovery with category walking strategy")
        logger.info(f"Target categories: {len(seed_categories)}")
        logger.info(f"Max pages per category: {self.max_pages_per_category}")

        async for product in self.walk_categories(seed_categories):
            yield product

    def get_progress_stats(self) -> Dict[str, Any]:
        """Get current progress statistics."""
        stats = self.stats.copy()
        stats["discovered_products_count"] = len(self.discovered_products)
        stats["discovered_categories_count"] = len(self.discovered_categories)

        if stats["start_time"]:
            start_time = datetime.fromisoformat(
                stats["start_time"].replace("Z", "+00:00")
            )
            elapsed = datetime.now(timezone.utc) - start_time
            stats["elapsed_seconds"] = int(elapsed.total_seconds())
            stats["products_per_hour"] = (
                stats["products_discovered"] / (elapsed.total_seconds() / 3600)
                if elapsed.total_seconds() > 0
                else 0
            )

        return stats


# Factory function
def create_category_walker(**kwargs) -> CategoryWalker:
    """Create a configured category walker."""
    return CategoryWalker(**kwargs)
