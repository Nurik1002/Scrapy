-- Universal Products Table (OLX Optimized)
CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE NOT NULL, -- OLX ID (e.g. 782312)
    source VARCHAR(50) NOT NULL DEFAULT 'olx.uz',
    category_path VARCHAR(200) NOT NULL, -- e.g. "transport/legkovye-avtomobili"
    listing_type VARCHAR(20) DEFAULT 'simple',
    
    title TEXT NOT NULL,
    description TEXT,
    price DECIMAL(15,2),
    currency CHAR(3) DEFAULT 'UZS',
    location VARCHAR(200),
    url TEXT,
    
    images JSONB DEFAULT '[]',
    seller_id BIGINT REFERENCES sellers(id),
    
    -- EAV for category-specific attributes (brand, model, mileage, etc.)
    attributes JSONB DEFAULT '{}',
    
    status VARCHAR(20) DEFAULT 'active',
    scraped_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Full-text search
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('russian', coalesce(title,'') || ' ' || coalesce(description,''))
    ) STORED
);

-- Variant support (future proofing, though OLX is mostly flat)
CREATE TABLE product_variants (
    id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
    sku VARCHAR(100) UNIQUE NOT NULL,
    
    variant_attributes JSONB NOT NULL, -- {"color": "Red", "size": "M"}
    stock INTEGER DEFAULT 1,
    price DECIMAL(15,2),
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sellers (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(100) UNIQUE NOT NULL, -- OLX User hash/ID
    source VARCHAR(50) NOT NULL DEFAULT 'olx.uz',
    
    name VARCHAR(300) NOT NULL,
    seller_type VARCHAR(20), -- 'Private person', 'Business'
    rating DECIMAL(3,2),
    total_reviews INTEGER DEFAULT 0,
    location VARCHAR(200),
    
    -- Contact info (fetched via separate request)
    contact_phone VARCHAR(30),
    contact_telegram VARCHAR(100),
    
    registered_since VARCHAR(50), -- e.g. "on OLX since Oct 2020"
    last_seen TIMESTAMP,
    
    scraped_at TIMESTAMP DEFAULT NOW()
);

-- Performance Indexes
CREATE INDEX idx_products_external_id ON products(external_id);
CREATE INDEX idx_products_category ON products(category_path);
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_products_search ON products USING GIN(search_vector);
CREATE INDEX idx_products_attrs ON products USING GIN(attributes);
CREATE INDEX idx_sellers_external_id ON sellers(external_id);
