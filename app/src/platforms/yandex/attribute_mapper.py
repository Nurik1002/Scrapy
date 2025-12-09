"""
Yandex Market Attribute Mapper - Uzbek to Canonical Key Mapping

This module handles the complex attribute mapping for Yandex Market Uzbekistan,
converting localized Uzbek attribute keys to canonical English keys for
cross-platform analytics and comparison.

Key Features:
- Category-specific attribute mappings
- Value normalization and unit conversion
- Variant logic handling (color/size/configuration splits)
- Extensible schema for new categories
- Fallback handling for unknown attributes
"""

import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

# Create debug logger for detailed troubleshooting
debug_logger = logging.getLogger(f"{__name__}.debug")


class AttributeMapper:
    """
    Maps Yandex Market's localized Uzbek attributes to canonical English keys.

    Handles category-specific mappings, value normalization, and variant detection.
    """

    # Common attributes across all categories
    COMMON_MAPPINGS = {
        # Universal product identifiers
        "Market maqolasi": "articul",
        "Artikel": "articul",
        "SKU": "sku",
        "Model kodi": "model_code",
        # Brand and manufacturer
        "Brend": "brand",
        "Brand": "brand",
        "Ishlab chiqaruvchi": "manufacturer",
        "Ishlab chiqaruvchi mamlakat": "country_of_origin",
        # Basic properties
        "Rangi": "color",
        "Rang": "color",
        "Material": "material",
        "O'lcham": "size",
        "Og'irligi": "weight",
        "Balandligi": "height",
        "Kengligi": "width",
        "Chuqurligi": "depth",
        "Uzunligi": "length",
        # Quality and certification
        "Kafolat": "warranty",
        "Kafolat muddati": "warranty_period",
        "Sertifikat": "certification",
        "Sifat belgisi": "quality_mark",
        # Seasonal and category
        "Fasl": "season",
        "Kategoriya": "category",
        "Turi": "type",
    }

    # Category-specific mappings
    CATEGORY_MAPPINGS = {
        # Electronics - Smartphones
        "electronics_smartphones": {
            "Ichki xotira": "storage",
            "Operativ xotira": "ram",
            "Sim-kartalar soni": "sim_slots",
            "Batareya quvvati": "battery_capacity",
            "Ekran diagonali": "screen_size",
            "Ekran o'lchamlari": "screen_resolution",
            "Operatsion tizim": "operating_system",
            "Protsessor": "processor",
            "Kamera": "camera",
            "Asosiy kamera": "main_camera",
            "Old kamera": "front_camera",
            "Bluetooth": "bluetooth_version",
            "Wi-Fi": "wifi_standard",
            "NFC": "nfc_support",
            "5G qo'llab-quvvatlash": "5g_support",
        },
        # Computers - Laptops
        "computers_laptops": {
            "Hukmdor": "product_line",
            "Seriya": "series",
            "Protsessor liniyasi": "cpu_line",
            "Protsessor modeli": "cpu_model",
            "Operativ xotira": "ram",
            "SSD disklarining umumiy hajmi": "ssd_storage",
            "HDD disklarining umumiy hajmi": "hdd_storage",
            "Video karta": "gpu",
            "Ekran diagonali": "screen_size",
            "Ekran o'lchamlari": "screen_resolution",
            "Ekranni yangilash tezligi": "refresh_rate",
            "Ekran matritsasi turi": "panel_type",
            "Operatsion tizim": "operating_system",
            "Klaviatura": "keyboard_layout",
            "Portlar soni": "port_count",
            "USB portlar": "usb_ports",
            "HDMI": "hdmi_ports",
            "Batareya": "battery_life",
        },
        # Appliances - Refrigerators
        "appliances_refrigerators": {
            "Umumiy hajmi": "total_volume",
            "Muzlatkich bo'limi hajmi": "fridge_volume",
            "Muzxona bo'limi hajmi": "freezer_volume",
            "Sovutish tizimi": "cooling_system",
            "Kompressor turi": "compressor_type",
            "Energiya samaradorligi sinfi": "energy_class",
            "Energiya iste'moli": "energy_consumption",
            "Muzdan erish": "defrost_system",
            "Shovqin darajasi": "noise_level",
            "Eshiklar soni": "door_count",
            "Polkalar soni": "shelf_count",
            "Iqlim sinfi": "climate_class",
        },
        # Tools - Drills
        "tools_drills": {
            "Maksimal aylanish tezligi": "max_rpm",
            "Batareya kuchlanishi": "voltage",
            "Maksimal moment": "max_torque",
            "Batareya turi": "battery_type",
            "Batareya quvvati": "battery_capacity",
            "Patronga diametri": "chuck_diameter",
            "Zarbalar soni": "impact_rate",
            "Tezlik soni": "speed_settings",
            "LED yoritish": "led_light",
            "Teskari aylantirish": "reverse_rotation",
            "Komplektatsiya": "kit_contents",
        },
        # Clothing - General
        "clothing": {
            "Jins": "gender",
            "Yosh guruhi": "age_group",
            "Kiyim turi": "clothing_type",
            "Uzunlik": "length",
            "Yeng uzunligi": "sleeve_length",
            "Yoqa turi": "collar_type",
            "Mahsulot xususiyatlari": "features",
            "Parvarish qilish": "care_instructions",
            "Kolleksiya": "collection",
            "Stil": "style",
        },
        # Home & Garden
        "home_garden": {
            "Xona turi": "room_type",
            "Materiallar": "materials",
            "Dizayn": "design_style",
            "Montaj turi": "installation_type",
            "Sig'im": "capacity",
            "Quvvat": "power",
            "Temperatura diapazon": "temperature_range",
            "Suv himoyasi": "water_resistance",
        },
        # Beauty & Health
        "beauty_health": {
            "Teri turi": "skin_type",
            "Tarkib": "ingredients",
            "Hajm": "volume",
            "SPF": "spf_level",
            "Yosh": "age_range",
            "Mahsulot turi": "product_type",
            "Qo'llash usuli": "application_method",
        },
    }

    # Variant logic patterns
    VARIANT_PATTERNS = {
        "color_storage_split": ["color", "storage", "ram"],
        "size_color_split": ["size", "color"],
        "configuration_split": ["ram", "storage", "gpu"],
        "kit_split": ["battery_included", "charger_included", "case_included"],
    }

    # Value normalization patterns
    VALUE_NORMALIZERS = {
        # Storage capacities (convert to GB)
        "storage": {
            r"(\d+)\s*TB": lambda m: str(int(m.group(1)) * 1024),
            r"(\d+)\s*GB": lambda m: m.group(1),
            r"(\d+)\s*MB": lambda m: str(int(m.group(1)) // 1024),
        },
        # RAM (convert to GB)
        "ram": {
            r"(\d+)\s*GB": lambda m: m.group(1),
            r"(\d+)\s*MB": lambda m: str(int(m.group(1)) // 1024),
        },
        # Screen sizes (convert to inches)
        "screen_size": {
            r"(\d+\.?\d*)\s*\"": lambda m: m.group(1),
            r"(\d+\.?\d*)\s*дюйм": lambda m: m.group(1),
            r"(\d+\.?\d*)\s*inch": lambda m: m.group(1),
        },
        # Weights (convert to kg)
        "weight": {
            r"(\d+\.?\d*)\s*кг": lambda m: m.group(1),
            r"(\d+\.?\d*)\s*kg": lambda m: m.group(1),
            r"(\d+)\s*г": lambda m: str(int(m.group(1)) / 1000),
            r"(\d+)\s*g": lambda m: str(int(m.group(1)) / 1000),
        },
        # Dimensions (convert to cm)
        "height": {
            r"(\d+\.?\d*)\s*см": lambda m: m.group(1),
            r"(\d+\.?\d*)\s*cm": lambda m: m.group(1),
            r"(\d+)\s*мм": lambda m: str(int(m.group(1)) / 10),
        },
        "width": {
            r"(\d+\.?\d*)\s*см": lambda m: m.group(1),
            r"(\d+\.?\d*)\s*cm": lambda m: m.group(1),
            r"(\d+)\s*мм": lambda m: str(int(m.group(1)) / 10),
        },
        "depth": {
            r"(\d+\.?\d*)\s*см": lambda m: m.group(1),
            r"(\d+\.?\d*)\s*cm": lambda m: m.group(1),
            r"(\d+)\s*мм": lambda m: str(int(m.group(1)) / 10),
        },
        # Boolean values
        "boolean": {
            r"(?i)(да|yes|bor|mavjud|true|+)": lambda m: True,
            r"(?i)(нет|no|yo'q|mavjud emas|false|-)": lambda m: False,
        },
    }

    def __init__(self):
        """Initialize attribute mapper with all category mappings."""
        debug_logger.debug("Initializing AttributeMapper")
        self._build_master_mapping()
        debug_logger.debug(
            f"Master mapping built with {len(self.master_mapping)} total mappings"
        )
        debug_logger.debug(
            f"Category mappings available: {list(self.CATEGORY_MAPPINGS.keys())}"
        )

    def _build_master_mapping(self):
        """Build consolidated mapping from all categories."""
        debug_logger.debug("Building master attribute mapping")
        self.master_mapping = self.COMMON_MAPPINGS.copy()
        debug_logger.debug(f"Added {len(self.COMMON_MAPPINGS)} common mappings")

        # Add all category-specific mappings to master
        for category_name, category_mappings in self.CATEGORY_MAPPINGS.items():
            self.master_mapping.update(category_mappings)
            debug_logger.debug(
                f"Added {len(category_mappings)} mappings from category '{category_name}'"
            )

        debug_logger.debug(
            f"Master mapping completed with {len(self.master_mapping)} total mappings"
        )

    def map_attributes(
        self, raw_attributes: Dict[str, Any], category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Map raw Uzbek attributes to canonical English keys.

        Args:
            raw_attributes: Raw attribute dict with Uzbek keys
            category: Category for context-specific mapping

        Returns:
            Mapped attributes with canonical keys
        """
        debug_logger.debug(
            f"Mapping {len(raw_attributes)} attributes for category '{category}'"
        )
        debug_logger.debug(f"Raw attributes keys: {list(raw_attributes.keys())}")

        mapped = {}
        unmapped = {}

        # Get category-specific mappings if available
        category_mapping = {}
        if category and category in self.CATEGORY_MAPPINGS:
            category_mapping = self.CATEGORY_MAPPINGS[category]
            debug_logger.debug(
                f"Using category-specific mapping for '{category}' with {len(category_mapping)} keys"
            )
        else:
            debug_logger.debug(
                f"No category-specific mapping found for '{category}', using common mappings only"
            )

        for raw_key, raw_value in raw_attributes.items():
            if not raw_key or raw_value is None:
                debug_logger.debug(
                    f"Skipping empty key or null value: '{raw_key}' = {raw_value}"
                )
                continue

            debug_logger.debug(f"Processing attribute: '{raw_key}' = '{raw_value}'")

            # Try category-specific mapping first
            canonical_key = category_mapping.get(raw_key)
            if canonical_key:
                debug_logger.debug(
                    f"Found category-specific mapping: '{raw_key}' -> '{canonical_key}'"
                )

            # Fall back to common mapping
            if not canonical_key:
                canonical_key = self.master_mapping.get(raw_key)
                if canonical_key:
                    debug_logger.debug(
                        f"Found common mapping: '{raw_key}' -> '{canonical_key}'"
                    )

            if canonical_key:
                # Normalize value
                debug_logger.debug(
                    f"Normalizing value for key '{canonical_key}': '{raw_value}'"
                )
                normalized_value = self._normalize_value(canonical_key, raw_value)
                mapped[canonical_key] = normalized_value
                debug_logger.debug(
                    f"Mapped and normalized: '{canonical_key}' = '{normalized_value}'"
                )
            else:
                # Keep unmapped attributes with original keys
                debug_logger.debug(
                    f"No mapping found for key '{raw_key}', keeping as unmapped"
                )
                unmapped[raw_key] = raw_value

        # Add unmapped attributes with warning
        if unmapped:
            logger.debug(f"Unmapped attributes for {category}: {list(unmapped.keys())}")
            debug_logger.debug(f"Unmapped attributes details: {unmapped}")
            mapped.update(unmapped)

        debug_logger.debug(
            f"Mapping completed: {len(mapped)} total attributes ({len(mapped) - len(unmapped)} mapped, {len(unmapped)} unmapped)"
        )
        return mapped

    def _normalize_value(self, canonical_key: str, raw_value: Any) -> Any:
        """Normalize attribute value based on canonical key."""
        debug_logger.debug(
            f"Normalizing value for key '{canonical_key}': '{raw_value}' (type: {type(raw_value)})"
        )

        if raw_value is None:
            debug_logger.debug("Value is None, returning None")
            return None

        value_str = str(raw_value).strip()
        if not value_str:
            debug_logger.debug("Value is empty string, returning None")
            return None

        # Get normalizers for this key type
        normalizers = self.VALUE_NORMALIZERS.get(canonical_key, {})
        debug_logger.debug(
            f"Found {len(normalizers)} normalizers for key '{canonical_key}'"
        )

        # Try each normalization pattern
        for pattern, normalizer_func in normalizers.items():
            debug_logger.debug(
                f"Testing pattern '{pattern}' against value '{value_str}'"
            )
            match = re.search(pattern, value_str, re.IGNORECASE)
            if match:
                debug_logger.debug(f"Pattern matched! Groups: {match.groups()}")
                try:
                    normalized = normalizer_func(match)
                    debug_logger.debug(
                        f"Normalization successful: '{raw_value}' -> '{normalized}' using pattern '{pattern}'"
                    )
                    return normalized
                except Exception as e:
                    logger.debug(
                        f"Error normalizing {canonical_key}='{raw_value}': {e}"
                    )
                    debug_logger.debug(
                        f"Normalization error details: {type(e).__name__}: {str(e)}"
                    )
                    continue

        # Apply boolean normalization to all fields
        boolean_normalizers = self.VALUE_NORMALIZERS.get("boolean", {})
        debug_logger.debug(f"Testing {len(boolean_normalizers)} boolean patterns")
        for pattern, normalizer_func in boolean_normalizers.items():
            if re.search(pattern, value_str):
                boolean_result = normalizer_func(None)
                debug_logger.debug(
                    f"Boolean normalization applied: '{raw_value}' -> {boolean_result} using pattern '{pattern}'"
                )
                return boolean_result

        # Return original value if no normalization applied
        debug_logger.debug(
            f"No normalization applied, returning original value: '{raw_value}'"
        )
        return raw_value

    def detect_variants(
        self, attributes: Dict[str, Any], category: Optional[str] = None
    ) -> str:
        """
        Detect variant logic pattern for this product.

        Args:
            attributes: Mapped attributes
            category: Product category

        Returns:
            Variant pattern name or "single" if no variants
        """
        debug_logger.debug(
            f"Detecting variants for category '{category}' with {len(attributes)} attributes"
        )
        attribute_keys = set(attributes.keys())
        debug_logger.debug(f"Available attribute keys: {attribute_keys}")

        # Check each variant pattern
        debug_logger.debug(f"Testing {len(self.VARIANT_PATTERNS)} variant patterns")
        for pattern_name, required_keys in self.VARIANT_PATTERNS.items():
            debug_logger.debug(
                f"Testing pattern '{pattern_name}' requiring keys: {required_keys}"
            )
            required_keys_set = set(required_keys)
            if required_keys_set.issubset(attribute_keys):
                debug_logger.debug(
                    f"Variant pattern matched: '{pattern_name}' (all required keys present)"
                )
                return pattern_name
            else:
                missing_keys = required_keys_set - attribute_keys
                debug_logger.debug(
                    f"Pattern '{pattern_name}' not matched, missing keys: {missing_keys}"
                )

        debug_logger.debug("No variant pattern matched, returning 'single'")
        return "single"

    def get_category_attributes(self, category: str) -> List[str]:
        """Get expected attributes for a category."""
        debug_logger.debug(f"Getting expected attributes for category '{category}'")
        category_mapping = self.CATEGORY_MAPPINGS.get(category, {})
        common_keys = list(self.COMMON_MAPPINGS.values())
        category_keys = list(category_mapping.values())

        debug_logger.debug(f"Common attributes: {len(common_keys)}")
        debug_logger.debug(f"Category-specific attributes: {len(category_keys)}")

        result = common_keys + category_keys
        debug_logger.debug(f"Total expected attributes for '{category}': {len(result)}")
        return result

    def suggest_category(self, attributes: Dict[str, Any]) -> Optional[str]:
        """Suggest category based on present attributes."""
        debug_logger.debug(f"Suggesting category based on {len(attributes)} attributes")
        attribute_keys = set(attributes.keys())
        debug_logger.debug(f"Attribute keys for matching: {attribute_keys}")

        best_match = None
        best_score = 0

        debug_logger.debug(
            f"Testing {len(self.CATEGORY_MAPPINGS)} categories for best match"
        )
        for category, mapping in self.CATEGORY_MAPPINGS.items():
            category_keys = set(mapping.values())
            match_score = len(attribute_keys.intersection(category_keys))
            debug_logger.debug(
                f"Category '{category}': {match_score} matching attributes out of {len(category_keys)} possible"
            )

            if match_score > best_score:
                debug_logger.debug(
                    f"New best match: '{category}' with score {match_score} (was {best_score})"
                )
                best_score = match_score
                best_match = category

        result = best_match if best_score > 2 else None
        debug_logger.debug(
            f"Category suggestion result: '{result}' (best score: {best_score}, threshold: 2)"
        )
        return result

    def validate_attributes(self, attributes: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate mapped attributes and return issues.

        Returns:
            Dict of attribute_key -> issue_description
        """
        debug_logger.debug(f"Validating {len(attributes)} attributes")
        issues = {}

        # Check for required attributes
        debug_logger.debug("Checking for required attributes")
        if "articul" not in attributes and "sku" not in attributes:
            issues["articul"] = "Missing product identifier (articul or sku)"
            debug_logger.debug("Missing product identifier")
        else:
            debug_logger.debug(
                f"Product identifier present: articul={attributes.get('articul')}, sku={attributes.get('sku')}"
            )

        if "brand" not in attributes:
            issues["brand"] = "Missing brand information"
            debug_logger.debug("Missing brand information")
        else:
            debug_logger.debug(f"Brand present: {attributes.get('brand')}")

        # Validate numeric ranges
        numeric_validations = {
            "storage": (1, 10000),  # 1GB to 10TB in GB
            "ram": (1, 1024),  # 1GB to 1TB
            "screen_size": (3, 100),  # 3" to 100"
            "weight": (0.01, 1000),  # 10g to 1000kg
        }

        debug_logger.debug(
            f"Validating numeric ranges for {len(numeric_validations)} attributes"
        )
        for key, (min_val, max_val) in numeric_validations.items():
            if key in attributes:
                debug_logger.debug(
                    f"Validating numeric attribute '{key}': '{attributes[key]}'"
                )
                try:
                    val = float(attributes[key])
                    debug_logger.debug(f"Parsed numeric value: {val}")
                    if not (min_val <= val <= max_val):
                        issue = (
                            f"Value {val} outside expected range [{min_val}, {max_val}]"
                        )
                        issues[key] = issue
                        debug_logger.debug(
                            f"Range validation failed for '{key}': {issue}"
                        )
                    else:
                        debug_logger.debug(
                            f"Range validation passed for '{key}': {val}"
                        )
                except (ValueError, TypeError) as e:
                    issue = f"Invalid numeric value: {attributes[key]}"
                    issues[key] = issue
                    debug_logger.debug(f"Numeric parsing failed for '{key}': {e}")

        debug_logger.debug(
            f"Validation completed with {len(issues)} issues: {list(issues.keys())}"
        )
        return issues


# Singleton instance
_mapper = None


def get_attribute_mapper() -> AttributeMapper:
    """Get singleton attribute mapper instance."""
    global _mapper
    if _mapper is None:
        debug_logger.debug("Creating singleton AttributeMapper instance")
        _mapper = AttributeMapper()
    else:
        debug_logger.debug("Returning existing AttributeMapper singleton")
    return _mapper
