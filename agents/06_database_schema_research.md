# 🗄️ Database Architecture Design

## Summary

**Three separate databases** for three different business models:

| Database | Platforms | Type | Use Case |
|----------|-----------|------|----------|
| **ecommerce_db** | Uzum + Yandex | B2C | Price monitoring SaaS |
| **classifieds_db** | OLX | C2C | Local marketplace deals |
| **procurement_db** | UZEX | B2B | Government procurement analytics |

---

## Why Three Databases?

### Different Data Models

| Aspect | E-commerce (B2C) | Classifieds (C2C) | Procurement (B2B) |
|--------|------------------|-------------------|-------------------|
| **Entity** | Products with SKUs | Listings | Lots with items |
| **Sellers** | Businesses | Private persons | Government vendors |
| **Pricing** | Fixed + discounts | Negotiable | Auction/tender |
| **Stock** | Multiple units | Usually 1 | Contract quantity |
| **Lifecycle** | Ongoing catalog | Sell → Remove | Tender → Award |

### Different Users

- **E-commerce**: Consumers comparing prices
- **Classifieds**: People buying/selling used items
- **Procurement**: Businesses bidding on contracts

---

## Database 1: E-commerce (B2C)

**Platforms**: Uzum + Yandex Market

### Schema Design

```sql
-- Sellers (unified for both platforms)
CREATE TABLE sellers (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,        -- 'uzum' or 'yandex'
    external_id VARCHAR(100) NOT NULL,
    UNIQUE(platform, external_id),
    
    name VARCHAR(500) NOT NULL,
    rating DECIMAL(3,2),
    review_count INTEGER DEFAULT 0,
    is_official BOOLEAN DEFAULT FALSE,
    
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW()
);

-- Categories (unified with cross-platform mapping)
CREATE TABLE categories (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    external_id VARCHAR(100),
    UNIQUE(platform, external_id),
    
    name VARCHAR(500) NOT NULL,
    parent_id BIGINT REFERENCES categories(id),
    level INTEGER DEFAULT 0,
    path TEXT                             -- "Electronics > Phones"
);

-- Products (unified catalog)
CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    external_id VARCHAR(100) NOT NULL,
    UNIQUE(platform, external_id),
    
    title TEXT NOT NULL,
    title_normalized TEXT,
    description TEXT,
    
    category_id BIGINT REFERENCES categories(id),
    seller_id BIGINT REFERENCES sellers(id),
    
    rating DECIMAL(3,2),
    review_count INTEGER DEFAULT 0,
    
    images JSONB DEFAULT '[]',
    attributes JSONB DEFAULT '{}',        -- Flexible attributes
    
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW()
);

-- SKUs/Offers (price variants)
CREATE TABLE offers (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    external_id VARCHAR(100),
    
    product_id BIGINT REFERENCES products(id),
    seller_id BIGINT REFERENCES sellers(id),
    
    price DECIMAL(18,2) NOT NULL,
    old_price DECIMAL(18,2),
    currency VARCHAR(10) DEFAULT 'UZS',
    
    is_available BOOLEAN DEFAULT TRUE,
    stock_quantity INTEGER,
    
    variant_attrs JSONB,                  -- {color: "Black", size: "M"}
    
    scraped_at TIMESTAMP DEFAULT NOW()
);

-- Price history for analytics
CREATE TABLE price_history (
    id BIGSERIAL PRIMARY KEY,
    offer_id BIGINT REFERENCES offers(id),
    
    price DECIMAL(18,2),
    old_price DECIMAL(18,2),
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_products_platform ON products(platform);
CREATE INDEX idx_products_seller ON products(seller_id);
CREATE INDEX idx_offers_product ON offers(product_id);
CREATE INDEX idx_offers_price ON offers(price);
CREATE INDEX idx_price_history_offer ON price_history(offer_id, recorded_at DESC);
```

### Key Features
- **Cross-platform comparison**: Same product from Uzum and Yandex
- **Price history**: Track changes over time
- **JSONB attributes**: Flexible product specs
- **Unified sellers**: Compare seller performance

---

## Database 2: Classifieds (C2C)

**Platform**: OLX.uz

### Schema Design

```sql
-- Private sellers (individuals)
CREATE TABLE olx_sellers (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE NOT NULL,
    
    name VARCHAR(300) NOT NULL,
    seller_type VARCHAR(20),              -- 'private', 'business'
    rating DECIMAL(3,2),
    location VARCHAR(200),
    
    phone VARCHAR(30),
    member_since VARCHAR(50),
    
    scraped_at TIMESTAMP DEFAULT NOW()
);

-- Listings (not products - temporary items)
CREATE TABLE olx_listings (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE NOT NULL,
    
    title TEXT NOT NULL,
    description TEXT,
    
    category_path VARCHAR(200),           -- "transport/cars"
    
    price DECIMAL(15,2),
    currency VARCHAR(10) DEFAULT 'UZS',
    is_negotiable BOOLEAN DEFAULT FALSE,
    
    location VARCHAR(200),
    seller_id BIGINT REFERENCES olx_sellers(id),
    
    images JSONB DEFAULT '[]',
    attributes JSONB DEFAULT '{}',        -- {brand, model, year, mileage}
    
    status VARCHAR(20) DEFAULT 'active',  -- active, sold, expired
    
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW()
);

-- Full-text search
ALTER TABLE olx_listings ADD COLUMN search_vector TSVECTOR 
    GENERATED ALWAYS AS (to_tsvector('russian', title || ' ' || COALESCE(description, ''))) STORED;

-- Indexes
CREATE INDEX idx_olx_listings_category ON olx_listings(category_path);
CREATE INDEX idx_olx_listings_price ON olx_listings(price);
CREATE INDEX idx_olx_listings_search ON olx_listings USING GIN(search_vector);
CREATE INDEX idx_olx_listings_attrs ON olx_listings USING GIN(attributes);
```

### Key Differences from E-commerce
- **Listings vs Products**: Temporary, one-time sales
- **Negotiable prices**: Not fixed catalog prices
- **Private sellers**: Individuals, not businesses
- **No SKUs**: Single items, no variants
- **Status tracking**: Sold, expired, renewed

---

## Database 3: Procurement (B2B)

**Platform**: UZEX

### Schema Design

```sql
-- Government procurement lots
CREATE TABLE uzex_lots (
    id BIGINT PRIMARY KEY,
    display_no VARCHAR(50),
    
    lot_type VARCHAR(30) NOT NULL,        -- auction, shop, tender
    status VARCHAR(20) NOT NULL,          -- completed, active
    is_budget BOOLEAN DEFAULT FALSE,
    
    -- Pricing
    start_cost DECIMAL(18,2),
    deal_cost DECIMAL(18,2),
    
    -- Customer (buyer)
    customer_name VARCHAR(500),
    customer_inn VARCHAR(20),
    
    -- Provider (winner)
    provider_name VARCHAR(500),
    provider_inn VARCHAR(20),
    
    deal_date TIMESTAMP,
    category_name VARCHAR(500),
    
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Items within each lot
CREATE TABLE uzex_lot_items (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT REFERENCES uzex_lots(id) ON DELETE CASCADE,
    
    product_name TEXT,
    description TEXT,
    
    quantity DECIMAL(12,2),
    measure_name VARCHAR(100),
    
    price DECIMAL(18,2),
    cost DECIMAL(18,2),
    
    country_name VARCHAR(100),
    properties JSONB
);

-- Indexes
CREATE INDEX idx_uzex_lots_type ON uzex_lots(lot_type);
CREATE INDEX idx_uzex_lots_date ON uzex_lots(deal_date);
CREATE INDEX idx_uzex_items_lot ON uzex_lot_items(lot_id);
```

### Key Differences
- **Lots, not products**: Contract bundles
- **Tenders**: Auction/bidding model
- **Government data**: Customer/provider with INN
- **Different lifecycle**: Announce → Bid → Award

---

## Data Flow Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      SCRAPERS                              │
├──────────────────┬──────────────────┬──────────────────────┤
│  Uzum Scraper    │  Yandex Scraper  │                      │
│  (100+ prod/sec) │  (planned)       │                      │
└────────┬─────────┴────────┬─────────┘                      │
         │                  │                                │
         ▼                  ▼                                │
┌────────────────────────────────────────┐                   │
│        ecommerce_db (B2C)              │                   │
│  products, offers, sellers, prices     │                   │
│  ► Price comparison SaaS               │                   │
└────────────────────────────────────────┘                   │
                                                             │
┌────────────────────┐        ┌──────────────────────────────┤
│  OLX Scraper       │        │  UZEX Scraper               │
│  (20 pages/sec)    │        │  (8 lots/sec)               │
└────────┬───────────┘        └────────┬─────────────────────┘
         │                             │
         ▼                             ▼
┌────────────────────┐        ┌────────────────────────────┐
│  classifieds_db    │        │    procurement_db (B2B)    │
│  (C2C)             │        │  lots, items, contracts    │
│  ► Local deals app │        │  ► Tender analytics        │
└────────────────────┘        └────────────────────────────┘
```

---

## Implementation Priority

| Phase | Database | Tables | Effort |
|-------|----------|--------|--------|
| **Now** | ecommerce_db | Uzum tables | ✅ Done |
| **Next** | ecommerce_db | Yandex tables | 2 weeks |
| **Then** | classifieds_db | OLX tables | 1 week |
| **Later** | procurement_db | UZEX tables | ✅ Done |

---

## JSONB for Flexible Attributes

**Recommended** for all platforms:

```sql
-- Store category-specific attributes
attributes JSONB DEFAULT '{}'

-- Example: Electronics
{"brand": "Samsung", "model": "Galaxy S24", "ram": "8GB", "storage": "256GB"}

-- Example: Cars (OLX)
{"brand": "Chevrolet", "model": "Malibu", "year": 2020, "mileage": 45000}

-- Example: Clothing
{"brand": "Nike", "size": "M", "color": "Black", "material": "Cotton"}

-- Fast queries with GIN index
CREATE INDEX idx_attrs ON products USING GIN(attributes);

-- Query example
SELECT * FROM products WHERE attributes->>'brand' = 'Samsung';
```

---

## Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Database separation** | 3 databases | Different data models, users, use cases |
| **Uzum + Yandex** | Same DB | Both B2C, enable price comparison |
| **OLX** | Separate | C2C listings, not product catalog |
| **UZEX** | Separate | B2B procurement, government data |
| **Attributes** | JSONB | Flexible, fast, no EAV complexity |

---

*Updated: December 8, 2025*
