-- Database Schema for Yandex Market (Uzum_Scraping Extension)

-- 1. Main Products (Models) Table
-- Yandex separates "Models" (Abstract Product) from "Offers" (Specific Seller Listing)
CREATE TABLE yandex_products (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE NOT NULL, -- Yandex Model ID or SKU ID
    source VARCHAR(50) DEFAULT 'market.yandex.uz',
    
    category_id BIGINT REFERENCES categories(id),
    title TEXT NOT NULL,
    description TEXT,
    
    -- Price Range for Models
    min_price DECIMAL(15,2),
    max_price DECIMAL(15,2),
    currency CHAR(3) DEFAULT 'UZS',
    
    rating DECIMAL(3,2),
    reviews_count INTEGER DEFAULT 0,
    
    images JSONB DEFAULT '[]', -- Array of image URLs
    videos JSONB DEFAULT '[]',
    
    attributes JSONB DEFAULT '{}', -- EAV for specs (Screen, RAM, etc.)
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Sellers (Shops) Table
CREATE TABLE yandex_sellers (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE NOT NULL, -- Shop ID
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255),
    
    rating DECIMAL(3,2),
    reviews_count INTEGER DEFAULT 0,
    registration_date DATE,
    
    is_verified BOOLEAN DEFAULT FALSE,
    logo_url TEXT,
    profile_url TEXT, -- https://market.yandex.uz/business--remac/207171656
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 3. Offers (Specific Listings) Table
-- Links a Product Model to a Seller with a specific price
CREATE TABLE yandex_offers (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE NOT NULL, -- Offer ID (hash)
    
    product_id BIGINT REFERENCES yandex_products(id),
    seller_id BIGINT REFERENCES yandex_sellers(id),
    
    price DECIMAL(15,2) NOT NULL,
    old_price DECIMAL(15,2), -- For discounts
    currency CHAR(3) DEFAULT 'UZS',
    
    is_available BOOLEAN DEFAULT TRUE,
    delivery_options JSONB, -- {"courier": true, "pickup": false}
    
    sku_attributes JSONB, -- Specifics for this offer if variant (e.g. Color: Red)
    
    scraped_at TIMESTAMP DEFAULT NOW()
);

-- 4. Category Hierarchies (Shared with other platforms but specific mapping)
CREATE TABLE yandex_category_mappings (
    id SERIAL PRIMARY KEY,
    yandex_category_id INTEGER UNIQUE NOT NULL,
    local_category_id INTEGER REFERENCES categories(id),
    name_path TEXT -- "Electronics > Phones"
);

-- Indexes
CREATE INDEX idx_yandex_products_ext ON yandex_products(external_id);
CREATE INDEX idx_yandex_offers_product ON yandex_offers(product_id);
CREATE INDEX idx_yandex_offers_seller ON yandex_offers(seller_id);
CREATE INDEX idx_yandex_products_attrs ON yandex_products USING GIN(attributes);
