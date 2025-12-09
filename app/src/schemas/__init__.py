"""
Database Schemas Package

Provides unified access to all database models across the three-database architecture:
- ecommerce: B2C platforms (Uzum, Yandex)
- classifieds: C2C platforms (OLX)
- procurement: B2B platforms (UZEX)
"""

# Import ecommerce models (B2C)
# Import classifieds models (C2C)
from .classifieds import (
    ClassifiedsBase,
    ClassifiedsListing,
    ClassifiedsSeller,
    create_search_vector_trigger,
)
from .classifieds import (
    create_additional_constraints as create_classifieds_constraints,
)
from .classifieds import (
    create_useful_views as create_classifieds_views,
)
from .ecommerce import (
    EcommerceBase,
    EcommerceCategory,
    EcommerceOffer,
    EcommercePriceHistory,
    EcommerceProduct,
    EcommerceSeller,
)
from .ecommerce import (
    create_additional_indexes as create_ecommerce_indexes,
)

# Import procurement models (B2B)
from .procurement import (
    ProcurementBase,
    ProcurementLot,
    ProcurementLotItem,
    ProcurementOrganization,
    create_procurement_constraints,
    create_procurement_functions,
    create_procurement_views,
)
from .procurement import (
    create_additional_indexes as create_procurement_indexes,
)

# Database type mapping
DATABASE_BASES = {
    "ecommerce": EcommerceBase,
    "classifieds": ClassifiedsBase,
    "procurement": ProcurementBase,
}

# Model collections for easy access
ECOMMERCE_MODELS = [
    EcommerceSeller,
    EcommerceCategory,
    EcommerceProduct,
    EcommerceOffer,
    EcommercePriceHistory,
]

CLASSIFIEDS_MODELS = [
    ClassifiedsSeller,
    ClassifiedsListing,
]

PROCUREMENT_MODELS = [
    ProcurementOrganization,
    ProcurementLot,
    ProcurementLotItem,
]

ALL_MODELS = {
    "ecommerce": ECOMMERCE_MODELS,
    "classifieds": CLASSIFIEDS_MODELS,
    "procurement": PROCUREMENT_MODELS,
}

# Platform to database mapping
PLATFORM_DATABASE_MAPPING = {
    # B2C E-commerce platforms
    "uzum": "ecommerce",
    "yandex": "ecommerce",
    "wildberries": "ecommerce",
    "ozon": "ecommerce",
    # C2C Classifieds platforms
    "olx": "classifieds",
    # B2B Procurement platforms
    "uzex": "procurement",
}


def get_database_for_platform(platform: str) -> str:
    """Get the appropriate database name for a platform."""
    return PLATFORM_DATABASE_MAPPING.get(platform, "ecommerce")


def get_models_for_database(database: str) -> list:
    """Get all models for a specific database."""
    return ALL_MODELS.get(database, [])


def get_base_for_database(database: str):
    """Get the SQLAlchemy base for a specific database."""
    return DATABASE_BASES.get(database)


# Post-creation functions mapping
POST_CREATE_FUNCTIONS = {
    "ecommerce": [create_ecommerce_indexes],
    "classifieds": [
        create_classifieds_constraints,
        create_search_vector_trigger,
        create_classifieds_views,
    ],
    "procurement": [
        create_procurement_indexes,
        create_procurement_constraints,
        create_procurement_functions,
        create_procurement_views,
    ],
}


def get_post_create_functions(database: str) -> list:
    """Get post-creation functions for a database."""
    return POST_CREATE_FUNCTIONS.get(database, [])


__all__ = [
    # Bases
    "EcommerceBase",
    "ClassifiedsBase",
    "ProcurementBase",
    # Ecommerce models
    "EcommerceSeller",
    "EcommerceCategory",
    "EcommerceProduct",
    "EcommerceOffer",
    "EcommercePriceHistory",
    # Classifieds models
    "ClassifiedsSeller",
    "ClassifiedsListing",
    # Procurement models
    "ProcurementOrganization",
    "ProcurementLot",
    "ProcurementLotItem",
    # Utility functions
    "get_database_for_platform",
    "get_models_for_database",
    "get_base_for_database",
    "get_post_create_functions",
    # Collections
    "DATABASE_BASES",
    "ECOMMERCE_MODELS",
    "CLASSIFIEDS_MODELS",
    "PROCUREMENT_MODELS",
    "ALL_MODELS",
    "PLATFORM_DATABASE_MAPPING",
    "POST_CREATE_FUNCTIONS",
]
