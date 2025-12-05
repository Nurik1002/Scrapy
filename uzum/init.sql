-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sellers Table
CREATE TABLE IF NOT EXISTS sellers (
    id BIGINT PRIMARY KEY, -- Uzum's internal seller ID
    name VARCHAR(255) NOT NULL,
    url VARCHAR(512),
    rating DECIMAL(3, 2),
    reviews_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Products Table
CREATE TABLE IF NOT EXISTS products (
    id BIGINT PRIMARY KEY, -- Uzum's internal product ID
    title TEXT NOT NULL,
    category_id BIGINT,
    category_name VARCHAR(255),
    seller_id BIGINT REFERENCES sellers(id),
    url VARCHAR(512) NOT NULL,
    total_orders BIGINT DEFAULT 0,
    rating DECIMAL(3, 2),
    reviews_count INTEGER DEFAULT 0,
    is_eco BOOLEAN DEFAULT FALSE, -- "Eco-friendly" or similar tag
    adult_category BOOLEAN DEFAULT FALSE,
    specs JSONB,
    images JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- SKUs Table (Variants)
CREATE TABLE IF NOT EXISTS skus (
    id BIGINT PRIMARY KEY, -- Uzum's internal SKU ID
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(255), -- e.g. "Red, 64GB"
    image_url TEXT,
    full_price DECIMAL(12, 2), -- Price before discount
    sell_price DECIMAL(12, 2), -- Current selling price
    available_amount INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Price History Table
CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku_id BIGINT REFERENCES skus(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE, -- Denormalized for faster queries
    price DECIMAL(12, 2) NOT NULL,
    old_price DECIMAL(12, 2),
    is_available BOOLEAN DEFAULT TRUE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Analytics
CREATE INDEX idx_products_seller ON products(seller_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_price_history_sku_date ON price_history(sku_id, timestamp DESC);
CREATE INDEX idx_price_history_product_date ON price_history(product_id, timestamp DESC);
