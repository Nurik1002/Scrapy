"""
Yandex Market Parser - Data extraction and parsing for market.yandex.uz

This module handles parsing of complex Yandex Market data structures including:
- window.apiary hydration data
- LD+JSON structured data
- serpEntity listings
- HTML fallback extraction
- Model-Offer separation
- Uzbek attribute mapping to canonical keys
"""

import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..base import ProductData
from .attribute_mapper import get_attribute_mapper

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


class YandexParser:
    """
    Parser for Yandex Market data with support for complex data structures.

    Handles the Model-Offer architecture where:
    - Models are abstract products with specifications
    - Offers are specific seller listings with prices
    """

    def __init__(self):
        self.attribute_mapper = get_attribute_mapper()

    def parse_product_response(self, raw_data: Dict[str, Any]) -> Optional[ProductData]:
        """
        Parse raw product page response into ProductData.

        Args:
            raw_data: Raw response from YandexClient.fetch_product()

        Returns:
            Parsed ProductData or None if parsing failed
        """
        debug_logger.debug(f"Starting product response parsing for raw data: {len(str(raw_data))} chars")
        try:
            product_id = raw_data.get("product_id")
            debug_logger.debug(f"Extracted product_id: {product_id}")
            if not product_id:
                debug_logger.debug("No product_id found in raw data")
                return None

            json_data = raw_data.get("json_data", {})
            debug_logger.debug(f"JSON data sources available: {list(json_data.keys())}")

            # Try different data sources in priority order
            debug_logger.debug("Attempting LD+JSON parsing")
            product_data = self._parse_from_ld_json(json_data, product_id)

            if not product_data:
                debug_logger.debug("LD+JSON parsing failed, attempting Apiary parsing")
                product_data = self._parse_from_apiary(json_data, product_id)

            if not product_data:
                debug_logger.debug("Apiary parsing failed, attempting HTML fallback")
                product_data = self._parse_from_html_fallback(raw_data.get("html", ""), product_id)

            if product_data:
                debug_logger.debug(f"Successfully parsed product data for {product_id}")
                product_data.raw_data = raw_data
                debug_logger.debug(f"Added raw data to product: {product_data.title}")
            else:
                debug_logger.debug(f"All parsing methods failed for product {product_id}")

            return product_data

        except Exception as e:
            logger.error(f"Error parsing Yandex product {raw_data.get('product_id')}: {e}")
            debug_logger.debug(f"Product parsing error details: {type(e).__name__}: {str(e)}")
            return None

    def _parse_from_ld_json(self, json_data: Dict, product_id: str) -> Optional[ProductData]:
        """Parse from LD+JSON structured data (most reliable)."""
        debug_logger.debug(f"Parsing LD+JSON for product {product_id}")
        ld_json_list = json_data.get("ld_json", [])
        debug_logger.debug(f"Found {len(ld_json_list)} LD+JSON items")
        if not ld_json_list:
            debug_logger.debug("No LD+JSON data available")
            return None

        for i, ld_item in enumerate(ld_json_list):
            item_type = ld_item.get("@type")
            debug_logger.debug(f"LD+JSON item {i + 1}: @type = {item_type}")
            if item_type in ["Product", "ProductModel"]:
                debug_logger.debug(f"Found compatible LD+JSON type: {item_type}")
                result = self._extract_product_from_ld_json(ld_item, product_id)
                if result:
                    debug_logger.debug("Successfully extracted product from LD+JSON")
                    return result
                else:
                    debug_logger.debug("LD+JSON extraction failed")

        debug_logger.debug("No compatible LD+JSON items found")
        return None

    def _parse_from_apiary(self, json_data: Dict, product_id: str) -> Optional[ProductData]:
        """Parse from window.apiary hydration data."""
        debug_logger.debug(f"Parsing Apiary data for product {product_id}")
        apiary = json_data.get("apiary", {})
        debug_logger.debug(f"Apiary data available: {bool(apiary)} ({len(str(apiary)) if apiary else 0} chars)")
        if not apiary:
            debug_logger.debug("No apiary data available")
            return None

        # Navigate apiary structure to find product data
        # Structure varies but typically: apiary.services.marketContentApi.reducers.product
        try:
            debug_logger.debug("Searching for product data in apiary structure")
            product_info = self._find_product_in_apiary(apiary, product_id)
            if product_info:
                debug_logger.debug("Found product info in apiary, extracting data")
                result = self._extract_product_from_apiary(product_info, product_id)
                if result:
                    debug_logger.debug("Successfully extracted product from apiary")
                    return result
                else:
                    debug_logger.debug("Apiary extraction failed")
            else:
                debug_logger.debug("No product info found in apiary structure")
        except Exception as e:
            logger.debug(f"Error parsing apiary data: {e}")
            debug_logger.debug(f"Apiary parsing error details: {type(e).__name__}: {str(e)}")

        return None

    def _parse_from_html_fallback(self, html: str, product_id: str) -> Optional[ProductData]:
        """Fallback HTML parsing when JSON extraction fails."""
        debug_logger.debug(f"HTML fallback parsing for product {product_id}")
        debug_logger.debug(f"HTML content length: {len(html)}")
        if not html:
            debug_logger.debug("No HTML content available for fallback parsing")
            return None

        try:
            debug_logger.debug("Creating BeautifulSoup parser for HTML")
            soup = BeautifulSoup(html, 'html.parser')

            # Extract basic info from HTML structure
            debug_logger.debug("Extracting title from HTML")
            title = self._extract_title_from_html(soup)
            debug_logger.debug(f"Extracted title: '{title}'")
            if not title:
                debug_logger.debug("No title found in HTML, fallback parsing failed")
                return None

            debug_logger.debug("Creating minimal ProductData from HTML fallback")
            result = ProductData(
                id=int(product_id) if product_id.isdigit() else hash(product_id),
                title=title,
                # Add other basic fields that can be extracted from HTML
            )
            debug_logger.debug("HTML fallback parsing successful")
            return result

        except Exception as e:
            logger.debug(f"HTML fallback parsing failed: {e}")
            debug_logger.debug(f"HTML parsing error details: {type(e).__name__}: {str(e)}")
            return None

    def _extract_product_from_ld_json(self, ld_item: Dict, product_id: str) -> ProductData:
        """Extract ProductData from LD+JSON structured data."""
        debug_logger.debug(f"Extracting product from LD+JSON for {product_id}")
        debug_logger.debug(f"LD+JSON keys: {list(ld_item.keys())}")

        # Basic product information
        title = ld_item.get("name", "")
        description = ld_item.get("description", "")
        debug_logger.debug(f"Basic info - Title: '{title}', Description: {len(description)} chars")

        # Images
        images = []
        image_data = ld_item.get("image", [])
        debug_logger.debug(f"Image data type: {type(image_data)}, content: {len(str(image_data))} chars")
        if isinstance(image_data, list):
            images = [img.get("url") if isinstance(img, dict) else str(img) for img in image_data]
            debug_logger.debug(f"Processed {len(images)} images from list")
        elif isinstance(image_data, dict):
            images = [image_data.get("url", "")]
            debug_logger.debug(f"Processed 1 image from dict")
        elif isinstance(image_data, str):
            images = [image_data]
            debug_logger.debug(f"Processed 1 image from string")

        # Brand and manufacturer
        brand_info = ld_item.get("brand", {})
        brand_name = brand_info.get("name", "") if isinstance(brand_info, dict) else str(brand_info)
        manufacturer = ld_item.get("manufacturer", {})
        manufacturer_name = manufacturer.get("name", "") if isinstance(manufacturer, dict) else ""
        debug_logger.debug(f"Brand: '{brand_name}', Manufacturer: '{manufacturer_name}'")

        # Category
        category = ld_item.get("category", "")
        debug_logger.debug(f"Category: '{category}'")

        # Rating and reviews
        rating_info = ld_item.get("aggregateRating", {})
        rating = None
        review_count = 0
        debug_logger.debug(f"Rating info available: {bool(rating_info)}")

        if rating_info:
            try:
                rating = float(rating_info.get("ratingValue", 0))
                review_count = int(rating_info.get("reviewCount", 0))
                debug_logger.debug(f"Parsed rating: {rating}, review count: {review_count}")
            except (ValueError, TypeError) as e:
                debug_logger.debug(f"Rating parsing failed: {e}")

        # Offers (prices and sellers)
        offers_data = ld_item.get("offers", [])
        if not isinstance(offers_data, list):
            offers_data = [offers_data] if offers_data else []
        debug_logger.debug(f"Processing {len(offers_data)} offers")

        skus = []
        min_price = None
        max_price = None

        for i, offer in enumerate(offers_data):
            debug_logger.debug(f"Processing offer {i + 1}/{len(offers_data)}")
            if not isinstance(offer, dict):
                continue

            try:
                price = float(offer.get("price", 0))
                currency = offer.get("priceCurrency", "UZS")
                availability = offer.get("availability", "")
                is_available = "InStock" in availability

                seller_info = offer.get("seller", {})
                seller_name = seller_info.get("name", "") if isinstance(seller_info, dict) else ""

                sku_data = {
                    "price": price,
                    "currency": currency,
                    "is_available": is_available,
                    "seller_name": seller_name,
                    "seller_data": seller_info
                }
                skus.append(sku_data)

                # Track price range
                if price > 0:
                    if min_price is None or price < min_price:
                        min_price = price
                    if max_price is None or price > max_price:
                        max_price = price

            except (ValueError, TypeError) as e:
                logger.debug(f"Error parsing offer: {e}")
                continue

        # Extract attributes/specifications
        raw_attributes = {}

        # Check for additional properties
        additional_props = ld_item.get("additionalProperty", [])
        if isinstance(additional_props, list):
            for prop in additional_props:
                if isinstance(prop, dict):
                    name = prop.get("name", "")
                    value = prop.get("value", "")
                    if name and value:
                        raw_attributes[name] = value

        # Check for model-specific attributes
        model_info = ld_item.get("model", {})
        if isinstance(model_info, dict):
            for key, value in model_info.items():
                if isinstance(value, (str, int, float)):
                    raw_attributes[key] = value

        # Map attributes using AttributeMapper
        mapped_attributes = self.attribute_mapper.map_attributes(raw_attributes)

        # Determine category for better attribute mapping
        suggested_category = self.attribute_mapper.suggest_category(mapped_attributes)
        if suggested_category:
            mapped_attributes = self.attribute_mapper.map_attributes(
                raw_attributes, suggested_category
            )

        return ProductData(
            id=int(product_id) if product_id.isdigit() else hash(product_id),
            title=title,
            description=description,
            category_title=category,
            rating=rating,
            review_count=review_count,
            photos=images,
            attributes=mapped_attributes,
            characteristics=raw_attributes,  # Keep raw for reference
            skus=skus,
            # Price range from offers
            **{f"min_price": min_price} if min_price else {},
            **{f"max_price": max_price} if max_price else {},
        )

    def _extract_product_from_apiary(self, product_info: Dict, product_id: str) -> ProductData:
        """Extract ProductData from apiary hydration data."""
        debug_logger.debug(f"Extracting product from apiary for {product_id}")
        debug_logger.debug(f"Apiary product info keys: {list(product_info.keys())}")

        # Apiary structure varies, this handles common patterns
        title = product_info.get("title", "") or product_info.get("name", "")
        description = product_info.get("description", "")
        debug_logger.debug(f"Apiary basic info - Title: '{title}', Description: {len(description)} chars")

        # Images from various possible locations
        images = []
        photo_sources = [
            product_info.get("photos", []),
            product_info.get("images", []),
            product_info.get("gallery", []),
        ]
        debug_logger.debug(f"Checking {len(photo_sources)} photo sources")

        for source_idx, source in enumerate(photo_sources):
            debug_logger.debug(f"Photo source {source_idx + 1}: {len(source) if isinstance(source, list) else 'not list'} items")
            if isinstance(source, list):
                for img in source:
                    if isinstance(img, dict):
                        url = img.get("url", "") or img.get("src", "")
                        if url:
                            images.append(url)
                    elif isinstance(img, str):
                        images.append(img)

        # Rating and reviews
        rating = product_info.get("rating", {}).get("value")
        review_count = product_info.get("rating", {}).get("count", 0)

        try:
            if rating:
                rating = float(rating)
            if review_count:
                review_count = int(review_count)
        except (ValueError, TypeError):
            rating = None
            review_count = 0

        # Category information
        category_info = product_info.get("category", {})
        category_title = ""
        if isinstance(category_info, dict):
            category_title = category_info.get("name", "")
        elif isinstance(category_info, str):
            category_title = category_info

        # Specifications/attributes
        raw_attributes = {}
        specs_sources = [
            product_info.get("specs", {}),
            product_info.get("characteristics", {}),
            product_info.get("attributes", {}),
        ]

        for specs in specs_sources:
            if isinstance(specs, dict):
                raw_attributes.update(specs)

        # Map attributes
        mapped_attributes = self.attribute_mapper.map_attributes(raw_attributes)

        return ProductData(
            id=int(product_id) if product_id.isdigit() else hash(product_id),
            title=title,
            description=description,
            category_title=category_title,
            rating=rating,
            review_count=review_count,
            photos=images,
            attributes=mapped_attributes,
            characteristics=raw_attributes,
        )

    def _find_product_in_apiary(self, apiary: Dict, product_id: str) -> Optional[Dict]:
        """Recursively search for product data in apiary structure."""
        debug_logger.debug(f"Finding product {product_id} in apiary structure")
        debug_logger.debug(f"Apiary root keys: {list(apiary.keys())}")

        # Common apiary paths for product data
        search_paths = [
            ["services", "marketContentApi", "reducers", "product"],
            ["stores", "product"],
            ["entities", "product"],
            ["data", "product"],
        ]
        debug_logger.debug(f"Testing {len(search_paths)} common search paths")

        for path_idx, path in enumerate(search_paths):
            debug_logger.debug(f"Testing path {path_idx + 1}: {' -> '.join(path)}")
            current = apiary
            try:
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                        debug_logger.debug(f"Successfully navigated to key '{key}'")
                    else:
                        debug_logger.debug(f"Key '{key}' not found, path failed")
                        break
                else:
                    # Successfully navigated the path
                    debug_logger.debug(f"Successfully navigated full path: {' -> '.join(path)}")
                    if isinstance(current, dict):
                        debug_logger.debug(f"Found dict with keys: {list(current.keys())}")
                        # Look for product by ID
                        if product_id in current:
                            debug_logger.debug(f"Found product by ID: {product_id}")
                            return current[product_id]
                        # Or look for single product data
                        elif len(current) == 1:
                            debug_logger.debug("Found single product data")
                            return list(current.values())[0]
                        # Or return if it looks like product data
                        elif "title" in current or "name" in current:
                            debug_logger.debug("Found product-like data structure")
                            return current
                    else:
                        debug_logger.debug(f"Path result is not dict: {type(current)}")
            except Exception as e:
                debug_logger.debug(f"Exception on path {' -> '.join(path)}: {e}")
                continue

        # Fallback: recursive search for anything that looks like product data
        debug_logger.debug("Common paths failed, starting recursive search")
        result = self._recursive_product_search(apiary, product_id)
        if result:
            debug_logger.debug("Recursive search found product data")
        else:
            debug_logger.debug("Recursive search failed to find product data")
        return result

    def _recursive_product_search(self, data: Any, product_id: str, max_depth: int = 5) -> Optional[Dict]:
        """Recursively search for product-like data structures."""
        if max_depth <= 0:
            debug_logger.debug("Maximum search depth reached")
            return None

        if isinstance(data, dict):
            debug_logger.debug(f"Searching dict with {len(data)} keys at depth {5 - max_depth}")
            # Check if this looks like product data
            if ("title" in data or "name" in data) and ("price" in data or "rating" in data):
                debug_logger.debug("Found product-like data structure")
                return data

            # Check if product ID is a key
            if product_id in data and isinstance(data[product_id], dict):
                debug_logger.debug(f"Found product by ID key: {product_id}")
                return data[product_id]

            # Recursively search values
            for key, value in data.items():
                if max_depth > 1:  # Avoid too much debug spam
                    debug_logger.debug(f"Recursively searching key '{key}': {type(value)}")
                result = self._recursive_product_search(value, product_id, max_depth - 1)
                if result:
                    return result

        elif isinstance(data, list):
            debug_logger.debug(f"Searching list with {len(data)} items at depth {5 - max_depth}")
            # Search list items
            for i, item in enumerate(data):
                if max_depth > 1:  # Avoid too much debug spam
                    debug_logger.debug(f"Recursively searching list item {i}: {type(item)}")
                result = self._recursive_product_search(item, product_id, max_depth - 1)
                if result:
                    return result

        return None

    def _extract_title_from_html(self, soup: BeautifulSoup) -> str:
        """Extract product title from HTML as fallback."""
        debug_logger.debug("Extracting title from HTML using CSS selectors")
        # Try various title selectors
        title_selectors = [
            'h1[data-auto="productCardTitle"]',
            'h1.n-title__text',
            '.product-title h1',
            'h1',
            'title',
        ]
        debug_logger.debug(f"Testing {len(title_selectors)} title selectors")

        for i, selector in enumerate(title_selectors):
            debug_logger.debug(f"Testing selector {i + 1}: {selector}")
            element = soup.select_one(selector)
            if element and element.get_text().strip():
                title = element.get_text().strip()
                debug_logger.debug(f"Found title with selector '{selector}': '{title}'")
                return title
            else:
                debug_logger.debug(f"Selector '{selector}' found no results")

        debug_logger.debug("No title found with any selector")
        return ""

    def parse_offers_response(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse offers page response to extract seller listings.

        Args:
            raw_data: Raw response from YandexClient.fetch_product_offers()

        Returns:
            List of offer dictionaries
        """
        debug_logger.debug(f"Parsing offers response: {len(str(raw_data))} chars")
        try:
            json_data = raw_data.get("json_data", {})
            debug_logger.debug(f"Offers JSON data sources: {list(json_data.keys())}")
            offers = []

            # Try to extract from different data sources
            apiary = json_data.get("apiary", {})
            if apiary:
                debug_logger.debug("Extracting offers from apiary data")
                apiary_offers = self._extract_offers_from_apiary(apiary)
                offers.extend(apiary_offers)
                debug_logger.debug(f"Extracted {len(apiary_offers)} offers from apiary")

            serp_entity = json_data.get("serp_entity", {})
            if serp_entity:
                debug_logger.debug("Extracting offers from serp_entity data")
                serp_offers = self._extract_offers_from_serp(serp_entity)
                offers.extend(serp_offers)
                debug_logger.debug(f"Extracted {len(serp_offers)} offers from serp_entity")

            return offers

        except Exception as e:
            logger.error(f"Error parsing offers: {e}")
            debug_logger.debug(f"Offers parsing error details: {type(e).__name__}: {str(e)}")
            return []

    def _extract_offers_from_apiary(self, apiary: Dict) -> List[Dict[str, Any]]:
        """Extract offers from apiary data."""
        debug_logger.debug("Extracting offers from apiary not implemented yet")
        return []

    def _extract_offers_from_serp(self, serp: Dict) -> List[Dict[str, Any]]:
        """Extract offers from serp entity."""
        debug_logger.debug("Extracting offers from serp entity not implemented yet")
        return []
