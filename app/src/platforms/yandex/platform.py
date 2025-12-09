"""
Yandex Market Platform Implementation - market.yandex.uz

This module implements the MarketplacePlatform interface for Yandex Market,
handling the unique characteristics of this platform including:
- Model-Offer separation (Products vs Seller listings)
- Category-based product discovery (no sequential ID iteration)
- Complex bot protection requiring proxies and session management
- Localized Uzbek attribute keys requiring mapping
- Three-tier data extraction (Model, Offers, Specs)

The platform integrates with the existing multi-database architecture,
storing data in the ecommerce_db for B2C analytics.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional
from bs4 import BeautifulSoup

from ...core.config import settings
from ..base import MarketplacePlatform, ProductData
from .attribute_mapper import AttributeMapper, get_attribute_mapper
from .category_walker import CategoryWalker, create_category_walker
from .client import YandexClient, create_yandex_client

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


class YandexPlatform(MarketplacePlatform):
    """
    Yandex Market platform implementation.

    Implements the three-tier scraping strategy:
    1. Model page: Basic product info, reviews, ratings
    2. Offers page: All seller listings with prices
    3. Specs page: Complete technical specifications

    Key Features:
    - Category-based product discovery
    - Model-Offer data structure handling
    - Uzbek attribute mapping to canonical keys
    - Anti-bot evasion with proxy support
    - Resumable crawling with checkpoints
    """

    name = "yandex"
    api_base_url = "https://market.yandex.uz"

    def __init__(
        self,
        client: Optional[YandexClient] = None,
        category_walker: Optional[CategoryWalker] = None,
        attribute_mapper: Optional[AttributeMapper] = None,
        use_category_discovery: bool = True,
    ):
        """
        Initialize Yandex platform.

        Args:
            client: HTTP client for Yandex Market
            category_walker: Category-based product discovery
            attribute_mapper: Uzbek to canonical attribute mapping
            use_category_discovery: Use category walking instead of ID range
        """
        self.client = client
        self.category_walker = category_walker
        self.attribute_mapper = attribute_mapper or get_attribute_mapper()
        self.use_category_discovery = use_category_discovery

        # Platform statistics
        self.stats = {
            "products_scraped": 0,
            "offers_scraped": 0,
            "specs_scraped": 0,
            "parsing_errors": 0,
            "start_time": None,
        }

    async def __aenter__(self):
        """Async context manager entry."""
        debug_logger.debug("Initializing YandexPlatform context")
        debug_logger.debug(
            f"Configuration: use_category_discovery={self.use_category_discovery}"
        )

        if not self.client:
            debug_logger.debug("Creating new YandexClient")
            self.client = create_yandex_client()
        await self.client.__aenter__()
        debug_logger.debug("YandexClient initialized successfully")

        if self.use_category_discovery and not self.category_walker:
            debug_logger.debug("Creating CategoryWalker for product discovery")
            self.category_walker = create_category_walker(client=self.client)
            await self.category_walker.__aenter__()
            debug_logger.debug("CategoryWalker initialized successfully")

        self.stats["start_time"] = datetime.now(timezone.utc)
        debug_logger.debug(f"YandexPlatform initialized at {self.stats['start_time']}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        debug_logger.debug("Cleaning up YandexPlatform context")

        if self.client:
            debug_logger.debug("Closing YandexClient")
            await self.client.__aexit__(exc_type, exc_val, exc_tb)

        if self.category_walker:
            debug_logger.debug("Closing CategoryWalker")
            await self.category_walker.__aexit__(exc_type, exc_val, exc_tb)

        debug_logger.debug("YandexPlatform cleanup completed")

    async def discover_products_by_categories(
        self, custom_categories: List[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Discover products by walking category pages and then deep-downloading each.
        """
        async for product_info in self.category_walker.discover_products(custom_categories):
            try:
                product_id = int(product_info["product_id"])
                slug = product_info.get("slug", "")
                
                # Perform the three-tier download for the discovered product
                raw_data = await self.download_product(product_id, slug=slug)
                
                if raw_data:
                    yield raw_data

            except Exception as e:
                logger.error(f"Error processing discovered product {product_info}: {e}")
                continue

    async def download_product(self, product_id: int, slug: str = "") -> Optional[Dict[str, Any]]:
        """
        Perform a full three-tier download for a normalized product ID.
        
        Args:
            product_id: The normalized Yandex product ID
            slug: Optional product slug to use for URL construction
            
        Returns:
            Dictionary containing model, offers, and specs data
        """
        debug_logger.debug(f"Starting three-tier download for product {product_id}")
        
        try:
            # Step 1: Model/Product Page
            debug_logger.debug(f"Step 1: Fetching model data for product {product_id}")
            model_data = await self.client.fetch_product(product_id, slug=slug)
            
            if not model_data:
                debug_logger.debug(f"Failed to fetch model data for product {product_id}")
                return None
            
            debug_logger.debug(
                f"Model data received: {len(str(model_data))} chars"
            )

            # Extract slug if not provided or if we want to confirm it
            extracted_slug = self._extract_slug_from_data(model_data, product_id)
            if extracted_slug and not slug:
                slug = extracted_slug
                debug_logger.debug(f"Using extracted slug: '{slug}'")
            elif slug:
                 debug_logger.debug(f"Using provided slug: '{slug}'")
            
            if not slug or slug == f"product-{product_id}":
                debug_logger.warning(f"Slug extraction failed or fell back to default for product {product_id}. Dumping HTML.")
                try:
                    if isinstance(model_data, dict) and 'html' in model_data:
                        dump_filename = f"product_dump_{product_id}.html"
                        with open(dump_filename, "w", encoding="utf-8") as f:
                            f.write(model_data['html'])
                        debug_logger.warning(f"Dumped HTML to {dump_filename}")
                    else:
                        debug_logger.warning("No 'html' key in model_data to dump.")
                except Exception as e:
                    debug_logger.error(f"Failed to dump debug HTML: {e}")
            
            # Step 2: Offers
            debug_logger.debug(f"Step 2: Fetching offers data for product {product_id} with slug '{slug}'")
            offers_data = await self.client.fetch_product_offers(product_id, slug=slug)
            
            if not offers_data:
                debug_logger.debug(f"No offers data received for product {product_id}")
                # We continue even if offers are missing, as model data might be enough
            else:
                debug_logger.debug(
                    f"Offers data received: {len(str(offers_data))} chars"
                )

            # Step 3: Specs
            debug_logger.debug(f"Step 3: Fetching specs data for product {product_id} with slug '{slug}'")
            specs_data = await self.client.fetch_product_specs(product_id, slug=slug)
            
            if not specs_data:
                debug_logger.debug(f"No specs data received for product {product_id}")
            else:
                 debug_logger.debug(
                    f"Specs data received: {len(str(specs_data))} chars"
                )

            # Combine data
            combined_data = {
                "product_id": product_id,
                "slug": slug,
                "model": model_data,
                "offers": offers_data,
                "specs": specs_data,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Update ephemeral stats
            self.stats["products_scraped"] += 1
            if offers_data:
                self.stats["offers_scraped"] += 1
            if specs_data:
                self.stats["specs_scraped"] += 1

            debug_logger.debug(
                f"Three-tier download completed for product {product_id}"
            )
            debug_logger.debug(f"Combined data size: {len(str(combined_data))} chars")
            debug_logger.debug(
                f"Updated stats: products={self.stats['products_scraped']}, offers={self.stats['offers_scraped']}, specs={self.stats['specs_scraped']}"
            )

            return combined_data

        except Exception as e:
            logger.error(f"Error downloading Yandex product {product_id}: {e}")
            debug_logger.debug(f"Download error details: {type(e).__name__}: {str(e)}")
            return None

    def _extract_slug_from_data(
        self, model_data: Dict[str, Any], product_id: int
    ) -> str:
        """Extract product slug from model page data."""
        debug_logger.debug(f"Extracting slug from model data for product {product_id}")
        try:
            # Try to extract from URL in the data (least reliable if it's the requested URL)
            url = model_data.get("url", "")
            debug_logger.debug(f"Model data URL: {url}")
            
            # 1. Try to extract from HTML Canonical/Meta tags (Most Reliable)
            html = model_data.get("html", "")
            if html:
                try:
                    soup = BeautifulSoup(html, "lxml")
                    
                    # Try canonical link
                    canonical = soup.find("link", rel="canonical")
                    if canonical and canonical.get("href"):
                        href = canonical["href"]
                        debug_logger.debug(f"Found canonical URL: {href}")
                        if "/product--" in href:
                            parts = href.split("/product--")[1].split("/")
                            if len(parts) >= 1:
                                slug = parts[0]
                                debug_logger.debug(f"Extracted slug from canonical: '{slug}'")
                                return slug
                    else:
                        debug_logger.debug("No canonical link found")
                    
                    # Try og:url
                    og_url = soup.find("meta", property="og:url")
                    if og_url and og_url.get("content"):
                        content = og_url["content"]
                        debug_logger.debug(f"Found og:url: {content}")
                        if "/product--" in content:
                            parts = content.split("/product--")[1].split("/")
                            if len(parts) >= 1:
                                slug = parts[0]
                                debug_logger.debug(f"Extracted slug from og:url: '{slug}'")
                                return slug
                    else:
                        debug_logger.debug("No og:url meta tag found")

                except Exception as e:
                    debug_logger.debug(f"Error parsing HTML for slug: {e}")
            else:
                debug_logger.debug("No HTML content available for slug extraction")

            # 2. Fallback to extracting from provided URL
            if "/product--" in url:
                parts = url.split("/product--")[1].split("/")
                debug_logger.debug(f"URL parts after product--: {parts}")
                if len(parts) >= 2:
                    slug = parts[0]
                    # Avoid returning the fallback slug if possible, but if we have nothing else...
                    if not slug.startswith("product-") or len(slug.split("-")) > 2:
                         debug_logger.debug(f"Extracted slug from URL: '{slug}'")
                         return slug
            
            # 3. Try to extract from JSON data
            debug_logger.debug("Attempting to extract slug from JSON data")
            json_data = model_data.get("json_data", {})
            
            # 3a. Try LD+JSON (Schema.org)
            ld_json = json_data.get("ld_json", [])
            debug_logger.debug(f"LD+JSON data available: {bool(ld_json)}")
            if ld_json:
                if isinstance(ld_json, list):
                    items = ld_json
                else:
                    items = [ld_json]
                
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "Product":
                        product_url = item.get("url", "")
                        debug_logger.debug(f"Found Product URL in LD+JSON: {product_url}")
                        if "/product--" in product_url:
                            parts = product_url.split("/product--")[1].split("/")
                            if len(parts) >= 1:
                                slug_part = parts[0]
                                # Clean query params if any
                                if "?" in slug_part:
                                    slug_part = slug_part.split("?")[0]
                                
                                debug_logger.debug(f"Extracted slug from LD+JSON: '{slug_part}'")
                                return slug_part

            # 3b. Try Apiary
            apiary = json_data.get("apiary", {})
            debug_logger.debug(f"Apiary data available: {bool(apiary)}")

            # Look for slug in various nested structures
            if isinstance(apiary, dict):
                # Check common locations for slug
                debug_logger.debug("Searching for slug in nested apiary structures")
                for key_path in [
                    ["product", "slug"],
                    ["model", "slug"],
                    ["entity", "slug"],
                    ["page", "product", "slug"],
                ]:
                    debug_logger.debug(f"Checking key path: {key_path}")
                    slug = self._get_nested_value(apiary, key_path)
                    if slug:
                        debug_logger.debug(
                            f"Found slug in apiary at {key_path}: '{slug}'"
                        )
                        return slug
                    else:
                        debug_logger.debug(f"No slug found at key path: {key_path}")
            else:
                debug_logger.debug("Apiary data is not a dictionary")

        except Exception as e:
            logger.debug(f"Error extracting slug for product {product_id}: {e}")
            debug_logger.debug(
                f"Slug extraction error details: {type(e).__name__}: {str(e)}"
            )

        # Fallback slug
        fallback_slug = f"product-{product_id}"
        debug_logger.debug(f"Using fallback slug: '{fallback_slug}'")
        return fallback_slug

    def _get_nested_value(self, data: Dict, key_path: List[str]) -> Optional[str]:
        """Get value from nested dictionary using key path."""
        debug_logger.debug(f"Getting nested value with key path: {key_path}")
        current = data
        for i, key in enumerate(key_path):
            debug_logger.debug(
                f"Step {i + 1}: Looking for key '{key}' in {type(current)}"
            )
            if isinstance(current, dict) and key in current:
                current = current[key]
                debug_logger.debug(
                    f"Found key '{key}', current value type: {type(current)}"
                )
            else:
                debug_logger.debug(f"Key '{key}' not found or current is not dict")
                return None
        result = str(current) if current else None
        debug_logger.debug(f"Final nested value result: '{result}'")
        return result

    def parse_product(self, raw_data: Dict[str, Any]) -> Optional[ProductData]:
        """
        Parse raw Yandex data into ProductData format.

        Args:
            raw_data: Combined data from three-tier scraping

        Returns:
            Parsed ProductData or None if parsing fails
        """
        debug_logger.debug(
            f"Starting product parsing for product ID: {raw_data.get('product_id', 'unknown')}"
        )
        try:
            model_data = raw_data.get("model_data", {})
            offers_data = raw_data.get("offers_data", {})
            specs_data = raw_data.get("specs_data", {})

            debug_logger.debug(
                f"Data sources available - Model: {bool(model_data)}, Offers: {bool(offers_data)}, Specs: {bool(specs_data)}"
            )

            # Extract core product information from model data
            debug_logger.debug("Parsing model data for core product information")
            core_info = self._parse_model_data(model_data)
            if not core_info:
                debug_logger.debug("Failed to extract core info from model data")
                return None
            debug_logger.debug(f"Core info extracted: {list(core_info.keys())}")

            # Extract offer information
            debug_logger.debug("Parsing offers data")
            offers = self._parse_offers_data(offers_data)
            debug_logger.debug(f"Parsed {len(offers) if offers else 0} offers")

            # Extract and map technical specifications
            debug_logger.debug("Parsing specs data and mapping attributes")
            attributes = self._parse_specs_data(specs_data)
            debug_logger.debug(f"Raw attributes extracted: {len(attributes)} items")
            mapped_attributes = self.attribute_mapper.map_attributes(
                attributes, category=core_info.get("category_slug")
            )
            debug_logger.debug(f"Mapped attributes: {len(mapped_attributes)} items")

            # Create ProductData instance
            debug_logger.debug("Creating ProductData instance")
            product = ProductData(
                id=int(core_info["product_id"]),
                title=core_info.get("title", ""),
                title_ru=core_info.get("title_ru"),
                title_uz=core_info.get("title_uz"),
                category_id=core_info.get("category_id"),
                category_title=core_info.get("category_title"),
                category_path=core_info.get("category_path"),
                seller_id=None,  # Will be populated from offers
                seller_title=None,
                seller_data=offers,
                rating=core_info.get("rating"),
                review_count=core_info.get("review_count", 0),
                order_count=0,  # Not available in Yandex
                is_available=core_info.get("is_available", True),
                total_available=len(offers) if offers else 0,
                description=core_info.get("description"),
                photos=core_info.get("images", []),
                video_url=core_info.get("video_url"),
                attributes=mapped_attributes,
                characteristics=attributes,  # Raw attributes
                # Yandex-specific flags
                is_eco=self._detect_eco_product(mapped_attributes),
                has_warranty=bool(mapped_attributes.get("warranty")),
                warranty_info=mapped_attributes.get("warranty_period"),
                skus=self._generate_skus_from_offers(offers, mapped_attributes),
                raw_data=raw_data,
            )

            debug_logger.debug(
                f"ProductData created successfully for product {core_info['product_id']}"
            )
            debug_logger.debug(f"Product title: '{product.title}'")
            debug_logger.debug(f"Product attributes: {len(product.attributes)} mapped")
            debug_logger.debug(f"Product SKUs: {len(product.skus)}")
            return product

        except Exception as e:
            logger.error(f"Error parsing Yandex product data: {e}")
            debug_logger.debug(
                f"Product parsing error details: {type(e).__name__}: {str(e)}"
            )
            self.stats["parsing_errors"] += 1
            return None

    def _parse_model_data(self, model_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse main product information from model page."""
        debug_logger.debug(f"Parsing model data: {len(str(model_data))} chars")
        if not model_data:
            debug_logger.debug("No model data provided")
            return None

        try:
            json_data = model_data.get("json_data", {})
            debug_logger.debug(f"JSON data sources available: {list(json_data.keys())}")

            # Try LD+JSON first (most reliable)
            ld_json = json_data.get("ld_json", [])
            debug_logger.debug(f"Found {len(ld_json)} LD+JSON items")
            for i, ld_item in enumerate(ld_json):
                debug_logger.debug(
                    f"Processing LD+JSON item {i + 1}: type={ld_item.get('@type') if isinstance(ld_item, dict) else type(ld_item)}"
                )
                if isinstance(ld_item, dict) and ld_item.get("@type") == "Product":
                    debug_logger.debug("Found Product type in LD+JSON, parsing...")
                    result = self._parse_ld_json_product(ld_item)
                    if result:
                        debug_logger.debug("Successfully parsed LD+JSON product")
                        return result

            # Fall back to apiary data
            apiary = json_data.get("apiary", {})
            if apiary:
                debug_logger.debug("Falling back to apiary data parsing")
                result = self._parse_apiary_product(apiary)
                if result:
                    debug_logger.debug("Successfully parsed apiary product data")
                    return result

            # Last resort: extract from HTML
            html = model_data.get("html", "")
            if html:
                debug_logger.debug("Falling back to HTML parsing as last resort")
                result = self._parse_html_product(html)
                if result:
                    debug_logger.debug("Successfully parsed HTML product data")
                    return result

        except Exception as e:
            logger.debug(f"Error parsing model data: {e}")
            debug_logger.debug(
                f"Model data parsing error details: {type(e).__name__}: {str(e)}"
            )

        debug_logger.debug("Failed to parse model data from all sources")
        return None

    def _parse_ld_json_product(self, ld_product: Dict[str, Any]) -> Dict[str, Any]:
        """Parse product from LD+JSON structured data."""
        offers = ld_product.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        # Extract images
        images = []
        image_data = ld_product.get("image", [])
        if isinstance(image_data, list):
            images = [
                img.get("url", img) if isinstance(img, dict) else str(img)
                for img in image_data
            ]
        elif isinstance(image_data, str):
            images = [image_data]

        return {
            "product_id": ld_product.get("productID") or ld_product.get("sku"),
            "title": ld_product.get("name", ""),
            "description": ld_product.get("description", ""),
            "brand": ld_product.get("brand", {}).get("name")
            if isinstance(ld_product.get("brand"), dict)
            else ld_product.get("brand"),
            "images": images,
            "rating": self._extract_rating(ld_product.get("aggregateRating", {})),
            "review_count": self._extract_review_count(
                ld_product.get("aggregateRating", {})
            ),
            "category_title": ld_product.get("category"),
            "is_available": offers.get("availability") == "InStock",
        }

    def _parse_apiary_product(self, apiary: Dict[str, Any]) -> Dict[str, Any]:
        """Parse product from window.apiary data."""
        # This would need to be implemented based on actual apiary structure
        # from the HTML samples
        product_data = {}

        # Try to find product information in various nested structures
        for key_path in [
            ["page", "product"],
            ["product"],
            ["model"],
            ["entity"],
        ]:
            product_info = self._get_nested_dict(apiary, key_path)
            if product_info:
                product_data.update(
                    self._extract_product_from_apiary_section(product_info)
                )
                break

        return product_data

    def _get_nested_dict(self, data: Dict, key_path: List[str]) -> Optional[Dict]:
        """Get nested dictionary using key path."""
        current = data
        for key in key_path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current if isinstance(current, dict) else None

    def _extract_product_from_apiary_section(
        self, section: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract product data from apiary section."""
        return {
            "product_id": section.get("id"),
            "title": section.get("title") or section.get("name"),
            "description": section.get("description"),
            "images": section.get("images", []),
            "rating": section.get("rating"),
            "review_count": section.get("reviewCount")
            or section.get("reviews", {}).get("count"),
        }

    def _parse_html_product(self, html: str) -> Dict[str, Any]:
        """Parse product from HTML as last resort."""
        # Basic HTML parsing for essential fields
        import re

        product_data = {}

        # Extract title
        title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if title_match:
            product_data["title"] = title_match.group(1).strip()

        # Extract images from meta tags
        images = re.findall(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            html,
            re.IGNORECASE,
        )
        if images:
            product_data["images"] = images

        return product_data

    def _parse_offers_data(self, offers_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse seller offers from offers page."""
        debug_logger.debug(
            f"Parsing offers data: {len(str(offers_data)) if offers_data else 0} chars"
        )
        if not offers_data:
            debug_logger.debug("No offers data provided")
            return []

        offers = []
        json_data = offers_data.get("json_data", {})
        debug_logger.debug(f"Offers JSON data sources: {list(json_data.keys())}")

        # Try to extract offers from various data sources
        # This would need to be implemented based on actual offers page structure
        debug_logger.debug("Offers parsing not yet implemented - placeholder")

        debug_logger.debug(f"Parsed {len(offers)} offers")
        return offers

    def _parse_specs_data(self, specs_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse technical specifications from specs page."""
        debug_logger.debug(
            f"Parsing specs data: {len(str(specs_data)) if specs_data else 0} chars"
        )
        if not specs_data:
            debug_logger.debug("No specs data provided")
            return {}

        specs = {}
        json_data = specs_data.get("json_data", {})
        debug_logger.debug(f"Specs JSON data sources: {list(json_data.keys())}")

        # Try to extract specifications from various data sources
        # This would need to be implemented based on actual specs page structure
        debug_logger.debug("Specs parsing not yet implemented - placeholder")

        debug_logger.debug(f"Parsed {len(specs)} specifications")
        return specs

    def _extract_rating(self, rating_data: Dict[str, Any]) -> Optional[float]:
        """Extract rating value from rating data."""
        if isinstance(rating_data, dict):
            rating = rating_data.get("ratingValue")
            if rating is not None:
                try:
                    return float(rating)
                except (ValueError, TypeError):
                    pass
        return None

    def _extract_review_count(self, rating_data: Dict[str, Any]) -> int:
        """Extract review count from rating data."""
        if isinstance(rating_data, dict):
            count = rating_data.get("reviewCount") or rating_data.get("ratingCount")
            if count is not None:
                try:
                    return int(count)
                except (ValueError, TypeError):
                    pass
        return 0

    def _detect_eco_product(self, attributes: Dict[str, Any]) -> bool:
        """Detect if product is eco-friendly based on attributes."""
        eco_indicators = ["eco", "organic", "bio", "green", "sustainable"]

        for value in attributes.values():
            if isinstance(value, str) and any(
                indicator in value.lower() for indicator in eco_indicators
            ):
                return True

        return False

    def _generate_skus_from_offers(
        self, offers: List[Dict[str, Any]], attributes: Dict[str, Any]
    ) -> List[Dict]:
        """Generate SKU data from offers and attributes."""
        skus = []

        # Generate SKUs based on variant attributes
        variant_logic = self.attribute_mapper.detect_variants(attributes)

        if variant_logic != "single" and offers:
            # Create SKUs from offers with variant attributes
            for offer in offers:
                sku = {
                    "id": offer.get("offer_id"),
                    "price": offer.get("price"),
                    "currency": offer.get("currency", "UZS"),
                    "seller_id": offer.get("seller_id"),
                    "is_available": offer.get("available", True),
                    "variant_attributes": offer.get("variant_attributes", {}),
                }
                skus.append(sku)
        else:
            # Single SKU product
            if offers:
                main_offer = offers[0]  # Use first offer as main
                sku = {
                    "id": main_offer.get("offer_id"),
                    "price": main_offer.get("price"),
                    "currency": main_offer.get("currency", "UZS"),
                    "seller_id": main_offer.get("seller_id"),
                    "is_available": main_offer.get("available", True),
                }
                skus.append(sku)

        return skus

    async def download_range(
        self, start_id: int, end_id: int, concurrency: int = 10
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Download products in ID range.

        For Yandex, this uses category discovery instead of direct ID iteration
        since product IDs are not sequential.
        """
        if not self.use_category_discovery:
            # Fall back to direct ID range (will likely have low success rate)
            current_id = start_id
            semaphore = asyncio.Semaphore(concurrency)

            while current_id <= end_id:
                batch_size = min(100, end_id - current_id + 1)
                batch_ids = range(current_id, current_id + batch_size)

                tasks = []
                for product_id in batch_ids:

                    async def download_single(pid):
                        async with semaphore:
                            return await self.download_product(pid)

                    tasks.append(download_single(product_id))

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, dict):
                        yield result

                current_id += batch_size

        else:
            # Use category discovery (recommended approach)
            if not self.category_walker:
                logger.warning(
                    "Category walker not available, falling back to ID range"
                )
                return

            async for product_info in self.category_walker.discover_products():
                try:
                    product_id = int(product_info["product_id"])
                    if start_id <= product_id <= end_id:
                        raw_data = await self.download_product(product_id)
                        if raw_data:
                            yield raw_data
                except (ValueError, KeyError):
                    continue

    def get_id_range(self) -> tuple[int, int]:
        """
        Get valid product ID range for Yandex Market.

        Note: Yandex uses non-sequential IDs, so this range is mostly theoretical.
        Category discovery is the recommended approach.
        """
        return (1000000, 10000000)  # Rough estimate based on research

    async def discover_products_by_categories(
        self, custom_categories: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Discover products using category walking strategy.

        This is the primary method for product discovery on Yandex Market.
        """
        if not self.category_walker:
            self.category_walker = create_category_walker(client=self.client)
            await self.category_walker.__aenter__()

        async for product_info in self.category_walker.discover_products(
            custom_categories
        ):
            try:
                product_id = int(product_info["product_id"])
                raw_data = await self.download_product(product_id)
                if raw_data:
                    # Add category context from discovery
                    raw_data["discovery_info"] = product_info
                    yield raw_data
            except Exception as e:
                logger.debug(f"Error processing discovered product {product_info}: {e}")
                continue

    def get_platform_stats(self) -> Dict[str, Any]:
        """Get platform scraping statistics."""
        debug_logger.debug("Generating platform statistics")
        stats = self.stats.copy()

        if stats["start_time"]:
            elapsed = datetime.now(timezone.utc) - stats["start_time"]
            stats["elapsed_seconds"] = int(elapsed.total_seconds())
            stats["products_per_hour"] = (
                stats["products_scraped"] / (elapsed.total_seconds() / 3600)
                if elapsed.total_seconds() > 0
                else 0
            )
            debug_logger.debug(
                f"Runtime stats: {elapsed.total_seconds():.1f}s elapsed, {stats['products_per_hour']:.1f} products/hour"
            )

        # Add category walker stats if available
        if self.category_walker:
            debug_logger.debug("Adding category walker stats")
            stats["category_walker"] = self.category_walker.get_progress_stats()

        debug_logger.debug(f"Platform stats generated: {list(stats.keys())}")
        return stats


# Factory function
def create_yandex_platform(**kwargs) -> YandexPlatform:
    """Create a configured Yandex platform instance."""
    return YandexPlatform(**kwargs)
