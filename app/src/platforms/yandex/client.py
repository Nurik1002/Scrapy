"""
Yandex Market Client - Anti-bot HTTP client for market.yandex.uz

This client handles Yandex Market's aggressive bot protection including:
- SmartCaptcha evasion
- TLS fingerprinting resistance
- Session management with cookies
- Proxy rotation support
- Rate limiting and request throttling
"""

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from aiohttp_proxy import ProxyConnector
from bs4 import BeautifulSoup

from ...core.config import settings

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


class YandexClient:
    """
    Advanced HTTP client for Yandex Market with anti-bot capabilities.

    Features:
    - Proxy rotation and session persistence
    - Browser-like TLS fingerprinting
    - Smart rate limiting (10-60 req/min)
    - HTML parsing with JSON extraction
    - Multiple endpoint support (products, offers, specs, categories)
    """

    BASE_URL = "https://market.yandex.uz"

    # URL patterns
    PRODUCT_URL = "{base}/product--{slug}/{product_id}"
    OFFERS_URL = "{base}/product--{slug}/{product_id}/offers"
    SPECS_URL = "{base}/product--{slug}/{product_id}/spec"
    CATEGORY_URL = "{base}/catalog--{slug}/{category_id}/list"
    SEARCH_URL = "{base}/search"

    # Browser-like headers for TLS fingerprinting evasion
    BASE_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,uz;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    def __init__(
        self,
        concurrency: int = 10,
        timeout: int = 30,
        retries: int = 3,
        min_delay: float = 3.0,  # Conservative rate limiting
        max_delay: float = 6.0,
        use_proxy: bool = True,
        session_persistence: bool = True,
    ):
        self.concurrency = concurrency
        self.timeout = timeout
        self.retries = retries
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.use_proxy = use_proxy
        self.session_persistence = session_persistence

        self._session: Optional[ClientSession] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._last_request_time: float = 0.0
        self._request_count = 0
        self._session_cookies = {}

    async def __aenter__(self):
        await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _create_session(self):
        """Create optimized session with proxy support and browser-like settings."""
        if self._session is not None:
            return

        # Setup connector (with or without proxy)
        if self.use_proxy and settings.proxy.enabled:
            proxy_url = settings.proxy.get_proxy_url(
                country="uz", session_id=f"yandex_{random.randint(1000, 9999)}"
            )
            if proxy_url:
                connector = ProxyConnector.from_url(proxy_url)
                logger.info(
                    f"Using proxy for Yandex: {proxy_url.split('@')[1]}"
                )  # Hide credentials
            else:
                connector = TCPConnector(limit=self.concurrency, ttl_dns_cache=300)
        else:
            connector = TCPConnector(limit=self.concurrency, ttl_dns_cache=300)

        # Browser-like headers with random User-Agent
        headers = self.BASE_HEADERS.copy()
        headers["User-Agent"] = random.choice(self.USER_AGENTS)

        # Create session
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=ClientTimeout(total=self.timeout),
            headers=headers,
            cookie_jar=aiohttp.CookieJar(unsafe=True)
            if self.session_persistence
            else None,
        )

        self._semaphore = asyncio.Semaphore(self.concurrency)
        logger.info(
            f"Yandex client initialized - concurrency: {self.concurrency}, proxy: {self.use_proxy}"
        )
        debug_logger.debug(
            f"Client configuration: timeout={self.timeout}, retries={self.retries}, "
            f"delays={self.min_delay}-{self.max_delay}s, session_persistence={self.session_persistence}"
        )
        debug_logger.debug(f"User-Agent pool size: {len(self.USER_AGENTS)}")
        debug_logger.debug(f"Headers configured: {list(headers.keys())}")

    async def close(self):
        """Close session and cleanup."""
        if self._session:
            debug_logger.debug(
                f"Closing Yandex client session after {self._request_count} requests"
            )
            await self._session.close()
            self._session = None

    async def _rate_limit(self):
        """Smart rate limiting to avoid detection."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        delay = 0

        # Calculate delay based on request frequency
        if time_since_last < self.min_delay:
            delay = self.min_delay - time_since_last
            # Add random jitter to avoid patterns
            delay += random.uniform(0, self.max_delay - self.min_delay)
            await asyncio.sleep(delay)

        self._last_request_time = asyncio.get_event_loop().time()
        self._request_count += 1

        debug_logger.debug(
            f"Request #{self._request_count}: Applied {delay:.2f}s delay (time_since_last: {time_since_last:.2f}s)"
        )

        # Add extra delay every 10 requests to simulate human behavior
        if self._request_count % 10 == 0:
            human_pause = random.uniform(10, 30)
            logger.debug(
                f"Human-like pause: {human_pause:.1f}s after {self._request_count} requests"
            )
            debug_logger.debug(
                f"Human behavior simulation: pausing for {human_pause:.1f}s"
            )
            await asyncio.sleep(human_pause)

    async def _fetch_html(self, url: str, **kwargs) -> Optional[str]:
        """Fetch HTML content with anti-bot evasion."""
        if not self._session:
            await self._create_session()

        debug_logger.debug(f"Fetching HTML from: {url}")
        debug_logger.debug(f"Request kwargs: {kwargs}")

        await self._rate_limit()

        for attempt in range(self.retries):
            try:
                debug_logger.debug(
                    f"Attempt {attempt + 1}/{self.retries} for URL: {url}"
                )
                async with self._semaphore:
                    async with self._session.get(url, **kwargs) as response:
                        debug_logger.debug(
                            f"Response status: {response.status}, headers: {dict(response.headers)}"
                        )

                        if response.status == 200:
                            html = await response.text()
                            debug_logger.debug(
                                f"Received HTML content: {len(html)} characters"
                            )

                            # Check for captcha or bot detection
                            if self._is_blocked_response(html):
                                logger.warning(f"Bot detection triggered on {url}")
                                debug_logger.debug(
                                    f"Bot detection details - HTML snippet: {html[:500]}..."
                                )
                                # Implement captcha solving or rotation logic here
                                block_delay = random.uniform(60, 120)
                                debug_logger.debug(
                                    f"Bot block detected, waiting {block_delay:.1f}s before retry"
                                )
                                await asyncio.sleep(block_delay)
                                continue

                            debug_logger.debug(f"Successfully fetched HTML from {url}")
                            return html

                        elif response.status == 429:
                            wait_time = (attempt + 1) * 30
                            logger.warning(
                                f"Rate limited (429) on {url}, waiting {wait_time}s"
                            )
                            debug_logger.debug(
                                f"Rate limit headers: {dict(response.headers)}"
                            )
                            await asyncio.sleep(wait_time)
                            continue

                        elif response.status == 404:
                            debug_logger.debug(f"Resource not found (404): {url}")
                            debug_logger.debug(
                                f"All {self.retries} attempts failed for URL: {url}"
                            )
                            return None

                        else:
                            logger.debug(f"HTTP {response.status} for {url}")
                            debug_logger.debug(
                                f"Unexpected status {response.status}, headers: {dict(response.headers)}"
                            )
                            error_delay = random.uniform(5, 15)
                            debug_logger.debug(
                                f"Waiting {error_delay:.1f}s before retry"
                            )
                            await asyncio.sleep(error_delay)
                            continue

            except asyncio.TimeoutError:
                logger.debug(f"Timeout on {url} (attempt {attempt + 1})")
                debug_logger.debug(
                    f"Timeout after {self.timeout}s on attempt {attempt + 1}"
                )
                timeout_delay = random.uniform(5, 15)
                debug_logger.debug(f"Timeout recovery delay: {timeout_delay:.1f}s")
                await asyncio.sleep(timeout_delay)
            except Exception as e:
                logger.debug(f"Error fetching {url}: {e}")
                debug_logger.debug(
                    f"Exception type: {type(e).__name__}, details: {str(e)}"
                )
                exception_delay = random.uniform(5, 15)
                debug_logger.debug(f"Exception recovery delay: {exception_delay:.1f}s")
                await asyncio.sleep(exception_delay)

        return None

    def _is_blocked_response(self, html: str) -> bool:
        """Detect if response indicates bot blocking."""
        blocked_indicators = [
            "SmartCaptcha",
            "Доступ ограничен",
            "Access denied",
            "Проверка браузера",
            "showcaptcha",
        ]

        html_lower = html.lower()
        for indicator in blocked_indicators:
            if indicator.lower() in html_lower:
                debug_logger.debug(f"Bot detection trigger string found: '{indicator}'")
                return True
        
        return False

    def _extract_json_data(self, html: str) -> Dict[str, Any]:
        """Extract JSON data from HTML (window.apiary, LD+JSON, noframes patches)."""
        data = {}
        debug_logger.debug(f"Extracting JSON data from HTML ({len(html)} chars)")

        try:
            soup = BeautifulSoup(html, "html.parser")
            debug_logger.debug("BeautifulSoup parsing successful")

            # 1. Extract window.apiary data (Legacy/Fallback)
            apiary_match = re.search(r"window\.apiary\s*=\s*({.+?});", html, re.DOTALL)
            if apiary_match:
                debug_logger.debug(
                    f"Found window.apiary data ({len(apiary_match.group(1))} chars)"
                )
                try:
                    apiary_data = json.loads(apiary_match.group(1))
                    data["apiary"] = apiary_data
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse apiary JSON: {e}")
            else:
                debug_logger.debug("No window.apiary data found")

            # 2. Extract LD+JSON structured data (Standard)
            ld_json_scripts = soup.find_all("script", type="application/ld+json")
            if ld_json_scripts:
                debug_logger.debug(f"Found {len(ld_json_scripts)} LD+JSON script tags")
                ld_json_data = []
                for i, script in enumerate(ld_json_scripts):
                    try:
                        parsed_json = json.loads(script.string)
                        ld_json_data.append(parsed_json)
                    except json.JSONDecodeError as e:
                        debug_logger.debug(
                            f"Failed to parse LD+JSON script {i + 1}: {e}"
                        )
                        continue
                data["ld_json"] = ld_json_data
            else:
                debug_logger.debug("No LD+JSON scripts found")

            # 3. Extract noframes apiary patches (New/LazyLoader)
            # Yandex injects data patches in <noframes data-apiary="patch"> tags
            patches = soup.find_all("noframes", attrs={"data-apiary": "patch"})
            if patches:
                debug_logger.debug(f"Found {len(patches)} apiary patches")
                apiary_patches = []
                for i, patch in enumerate(patches):
                    try:
                        # Patches are raw JSON inside the tag
                        patch_content = patch.string
                        if patch_content:
                            parsed_patch = json.loads(patch_content)
                            apiary_patches.append(parsed_patch)
                    except json.JSONDecodeError as e:
                        debug_logger.debug(f"Failed to parse apiary patch {i + 1}: {e}")
                        continue
                data["apiary_patches"] = apiary_patches
            else:
                # Fallback to regex if BS4 fails to find them (sometimes nested weirdly)
                patch_matches = re.findall(r'<noframes data-apiary="patch">(.+?)</noframes>', html, re.DOTALL)
                if patch_matches:
                    debug_logger.debug(f"Found {len(patch_matches)} apiary patches via regex")
                    apiary_patches = []
                    for content in patch_matches:
                        try:
                            apiary_patches.append(json.loads(content))
                        except json.JSONDecodeError:
                            pass
                    data["apiary_patches"] = apiary_patches
                else:
                    debug_logger.debug("No apiary patches found")

            # 4. Extract serpEntity data (listings - old method)
            serp_match = re.search(r'"serpEntity":\s*({.+?})', html)
            if serp_match:
                debug_logger.debug(
                    f"Found serpEntity data ({len(serp_match.group(1))} chars)"
                )
                try:
                    serp_data = json.loads(serp_match.group(1))
                    data["serp_entity"] = serp_data
                except json.JSONDecodeError as e:
                    debug_logger.debug(f"Failed to parse serpEntity JSON: {e}")
            else:
                debug_logger.debug("No serpEntity data found")

        except Exception as e:
            logger.debug(f"Error extracting JSON from HTML: {e}")
            debug_logger.debug(
                f"JSON extraction error details: {type(e).__name__}: {str(e)}"
            )

        debug_logger.debug(
            f"JSON extraction completed, found data sources: {list(data.keys())}"
        )
        return data

    async def fetch_product(
        self, product_id: Union[int, str], slug: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch product page data.

        Args:
            product_id: Yandex product ID
            slug: Product URL slug (can be empty)

        Returns:
            Parsed product data or None
        """
        # Generate slug if not provided (basic fallback)
        if not slug:
            slug = f"product-{product_id}"

        url = self.PRODUCT_URL.format(
            base=self.BASE_URL, slug=slug, product_id=product_id
        )

        debug_logger.debug(
            f"Fetching product {product_id} with slug '{slug}' from: {url}"
        )

        html = await self._fetch_html(url)
        if not html:
            debug_logger.debug(f"No HTML content received for product {product_id}")
            return None

        debug_logger.debug(f"Product {product_id}: Received {len(html)} chars of HTML")
        json_data = self._extract_json_data(html)
        debug_logger.debug(
            f"Product {product_id}: Extracted JSON with sources: {list(json_data.keys())}"
        )

        result = {
            "product_id": str(product_id),
            "url": url,
            "html": html,  # Store full HTML for parsing logic (e.g. slug extraction)
            "json_data": json_data,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        debug_logger.debug(f"Product {product_id}: Successfully compiled result data")
        return result

    async def fetch_product_offers(
        self, product_id: Union[int, str], slug: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Fetch product offers (seller listings)."""
        if not slug:
            slug = f"product-{product_id}"

        url = self.OFFERS_URL.format(
            base=self.BASE_URL, slug=slug, product_id=product_id
        )

        debug_logger.debug(f"Fetching offers for product {product_id} from: {url}")

        html = await self._fetch_html(url)
        if not html:
            debug_logger.debug(
                f"No HTML content received for offers of product {product_id}"
            )
            return None

        debug_logger.debug(
            f"Product {product_id} offers: Received {len(html)} chars of HTML"
        )
        json_data = self._extract_json_data(html)
        debug_logger.debug(
            f"Product {product_id} offers: Extracted JSON with sources: {list(json_data.keys())}"
        )

        result = {
            "product_id": str(product_id),
            "type": "offers",
            "url": url,
            "json_data": json_data,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        debug_logger.debug(f"Product {product_id}: Successfully compiled offers data")
        return result

    async def fetch_product_specs(
        self, product_id: Union[int, str], slug: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Fetch product specifications."""
        if not slug:
            slug = f"product-{product_id}"

        url = self.SPECS_URL.format(
            base=self.BASE_URL, slug=slug, product_id=product_id
        )

        debug_logger.debug(f"Fetching specs for product {product_id} from: {url}")

        html = await self._fetch_html(url)
        if not html:
            debug_logger.debug(
                f"No HTML content received for specs of product {product_id}"
            )
            return None

        debug_logger.debug(
            f"Product {product_id} specs: Received {len(html)} chars of HTML"
        )
        json_data = self._extract_json_data(html)
        debug_logger.debug(
            f"Product {product_id} specs: Extracted JSON with sources: {list(json_data.keys())}"
        )

        result = {
            "product_id": str(product_id),
            "type": "specs",
            "url": url,
            "json_data": json_data,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        debug_logger.debug(f"Product {product_id}: Successfully compiled specs data")
        return result

    async def fetch_category_page(
        self, category_id: Union[int, str], slug: str = "", page: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch category listing page.

        Args:
            category_id: Category ID
            slug: Category URL slug
            page: Page number (1-based)

        Returns:
            Category page data with product listings
        """
        if not slug:
            slug = f"category-{category_id}"

        url = self.CATEGORY_URL.format(
            base=self.BASE_URL, slug=slug, category_id=category_id
        )

        params = {"page": page} if page > 1 else {}
        debug_logger.debug(
            f"Fetching category {category_id} page {page} from: {url} with params: {params}"
        )

        html = await self._fetch_html(url, params=params)
        if not html:
            debug_logger.debug(
                f"No HTML content received for category {category_id} page {page}"
            )
            return None

        debug_logger.debug(
            f"Category {category_id} page {page}: Received {len(html)} chars of HTML"
        )
        json_data = self._extract_json_data(html)
        debug_logger.debug(
            f"Category {category_id} page {page}: Extracted JSON with sources: {list(json_data.keys())}"
        )

        result = {
            "category_id": str(category_id),
            "page": page,
            "url": url,
            "html": html,
            "json_data": json_data,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        debug_logger.debug(
            f"Category {category_id} page {page}: Successfully compiled result data"
        )
        return result

    async def search_products(
        self, query: str, page: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Search for products."""
        url = self.SEARCH_URL.format(base=self.BASE_URL)
        params = {"text": query, "page": page}

        debug_logger.debug(
            f"Searching for '{query}' page {page} from: {url} with params: {params}"
        )

        html = await self._fetch_html(url, params=params)
        if not html:
            debug_logger.debug(
                f"No HTML content received for search '{query}' page {page}"
            )
            return None

        debug_logger.debug(
            f"Search '{query}' page {page}: Received {len(html)} chars of HTML"
        )
        json_data = self._extract_json_data(html)
        debug_logger.debug(
            f"Search '{query}' page {page}: Extracted JSON with sources: {list(json_data.keys())}"
        )

        result = {
            "query": query,
            "page": page,
            "url": url,
            "json_data": json_data,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        debug_logger.debug(
            f"Search '{query}' page {page}: Successfully compiled result data"
        )
        return result

    async def health_check(self) -> bool:
        """Check if the client can access Yandex Market."""
        debug_logger.debug("Starting Yandex Market health check")
        try:
            debug_logger.debug(f"Health check: Fetching {self.BASE_URL}")
            html = await self._fetch_html(self.BASE_URL)
            if html:
                debug_logger.debug(f"Health check: Received {len(html)} chars of HTML")
                is_blocked = self._is_blocked_response(html)
                debug_logger.debug(
                    f"Health check: Bot detection check result: {is_blocked}"
                )

                if not is_blocked:
                    logger.info("Yandex Market health check passed")
                    debug_logger.debug("Health check: All tests passed successfully")
                    return True
                else:
                    debug_logger.debug("Health check: Failed due to bot detection")
            else:
                debug_logger.debug("Health check: No HTML content received")
        except Exception as e:
            logger.error(f"Yandex Market health check failed: {e}")
            debug_logger.debug(f"Health check exception: {type(e).__name__}: {str(e)}")

        debug_logger.debug("Health check: Failed")
        return False


# Factory function for creating clients
def create_yandex_client(**kwargs) -> YandexClient:
    """Create a configured Yandex client."""
    platform_config = settings.get_platform_config("yandex")

    default_kwargs = {
        "concurrency": platform_config.concurrency if platform_config else 10,
        "use_proxy": settings.proxy.enabled,
    }
    default_kwargs.update(kwargs)

    return YandexClient(**default_kwargs)
