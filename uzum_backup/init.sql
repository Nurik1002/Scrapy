-- =============================================================================
-- UZUM.UZ COMPREHENSIVE DATABASE SCHEMA
-- =============================================================================
-- Optimized for:
-- - Price comparison across sellers
-- - Category hierarchy analytics
-- - Historical price tracking
-- - Seller performance metrics
-- - Product availability monitoring
-- =============================================================================

-- Drop existing tables for clean slate
DROP TABLE IF EXISTS price_history CASCADE;
DROP TABLE IF EXISTS sku_price_snapshots CASCADE;
DROP TABLE IF EXISTS product_sellers CASCADE;
DROP TABLE IF EXISTS skus CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS sellers CASCADE;
DROP TABLE IF EXISTS scrape_jobs CASCADE;
DROP TABLE IF EXISTS raw_snapshots CASCADE;

-- =============================================================================
-- 1. SELLERS - Store all seller information
-- =============================================================================
CREATE TABLE sellers (
    id BIGINT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    link VARCHAR(255),                    -- URL slug
    description TEXT,
    rating DECIMAL(2,1),                  -- 0.0 to 5.0
    review_count INTEGER DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    total_products INTEGER DEFAULT 0,
    is_official BOOLEAN DEFAULT FALSE,
    registration_date TIMESTAMP,
    account_id BIGINT,                    -- Internal seller account ID
    
    -- Tracking
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Raw data backup
    raw_data JSONB
);

CREATE INDEX idx_sellers_rating ON sellers(rating DESC);
CREATE INDEX idx_sellers_orders ON sellers(order_count DESC);
CREATE INDEX idx_sellers_link ON sellers(link);

-- =============================================================================
-- 2. CATEGORIES - Hierarchical category tree
-- =============================================================================
CREATE TABLE categories (
    id BIGINT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    title_ru VARCHAR(500),                -- Russian translation
    title_uz VARCHAR(500),                -- Uzbek translation
    parent_id BIGINT REFERENCES categories(id),
    product_count INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,              -- 0=root, 1=child, etc.
    
    -- Full path for easy querying
    path_ids BIGINT[],                    -- [root_id, parent_id, id]
    path_titles TEXT,                     -- "Electronics > Phones > Smartphones"
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_categories_parent ON categories(parent_id);
CREATE INDEX idx_categories_level ON categories(level);
CREATE INDEX idx_categories_path ON categories USING GIN(path_ids);

-- =============================================================================
-- 3. PRODUCTS - Core product information
-- =============================================================================
CREATE TABLE products (
    id BIGINT PRIMARY KEY,
    title VARCHAR(1000) NOT NULL,
    title_ru VARCHAR(1000),
    title_uz VARCHAR(1000),
    
    -- Category reference
    category_id BIGINT REFERENCES categories(id),
    category_path TEXT,                   -- Denormalized for fast queries
    
    -- Seller reference
    seller_id BIGINT REFERENCES sellers(id),
    
    -- Ratings & Reviews
    rating DECIMAL(2,1),
    review_count INTEGER DEFAULT 0,
    order_count INTEGER DEFAULT 0,
    
    -- Availability
    is_available BOOLEAN DEFAULT TRUE,
    total_available INTEGER DEFAULT 0,
    
    -- Content
    description TEXT,
    photos JSONB,                         -- Array of photo URLs
    video_url TEXT,
    
    -- Attributes & Characteristics
    attributes JSONB,                     -- Product attributes
    characteristics JSONB,                -- Technical specs
    tags TEXT[],                          -- Search tags
    
    -- Flags
    is_eco BOOLEAN DEFAULT FALSE,
    is_adult BOOLEAN DEFAULT FALSE,
    is_perishable BOOLEAN DEFAULT FALSE,
    has_warranty BOOLEAN DEFAULT FALSE,
    warranty_info TEXT,
    
    -- Tracking
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Raw API response
    raw_data JSONB
);

CREATE INDEX idx_products_seller ON products(seller_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_rating ON products(rating DESC);
CREATE INDEX idx_products_available ON products(is_available, total_available DESC);
CREATE INDEX idx_products_title ON products USING GIN(to_tsvector('russian', title));

-- =============================================================================
-- 4. SKUS - Product variants with pricing
-- =============================================================================
CREATE TABLE skus (
    id BIGINT PRIMARY KEY,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
    
    -- Pricing
    full_price BIGINT,                    -- Original/list price (tiyin)
    purchase_price BIGINT,                -- Current sale price (tiyin)
    discount_percent DECIMAL(5,2),        -- Calculated discount
    
    -- Availability
    available_amount INTEGER DEFAULT 0,
    is_available BOOLEAN GENERATED ALWAYS AS (available_amount > 0) STORED,
    
    -- Variant details
    characteristics JSONB,                -- Color, size, etc.
    barcode VARCHAR(100),
    
    -- Tracking
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_skus_product ON skus(product_id);
CREATE INDEX idx_skus_price ON skus(purchase_price);
CREATE INDEX idx_skus_available ON skus(is_available, available_amount DESC);
CREATE INDEX idx_skus_discount ON skus(discount_percent DESC);

-- =============================================================================
-- 5. PRICE HISTORY - Track price changes over time
-- =============================================================================
CREATE TABLE price_history (
    id BIGSERIAL PRIMARY KEY,
    sku_id BIGINT REFERENCES skus(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES products(id) ON DELETE CASCADE,
    
    -- Price at this point in time
    full_price BIGINT,
    purchase_price BIGINT,
    discount_percent DECIMAL(5,2),
    available_amount INTEGER,
    
    -- When recorded
    recorded_at TIMESTAMP DEFAULT NOW(),
    
    -- Change from previous
    price_change BIGINT,                  -- Difference from previous
    price_change_percent DECIMAL(5,2)
);

CREATE INDEX idx_price_history_sku ON price_history(sku_id, recorded_at DESC);
CREATE INDEX idx_price_history_product ON price_history(product_id, recorded_at DESC);
CREATE INDEX idx_price_history_date ON price_history(recorded_at);

-- Partition by month for performance (optional)
-- CREATE INDEX idx_price_history_month ON price_history(date_trunc('month', recorded_at));

-- =============================================================================
-- 6. PRODUCT_SELLERS - Track same product from multiple sellers
-- =============================================================================
-- This is KEY for price comparison!
CREATE TABLE product_sellers (
    id BIGSERIAL PRIMARY KEY,
    
    -- Matching criteria
    product_title_normalized VARCHAR(1000),  -- Normalized for matching
    barcode VARCHAR(100),                    -- If available
    
    -- Product instance  
    product_id BIGINT REFERENCES products(id),
    seller_id BIGINT REFERENCES sellers(id),
    
    -- Current best price from this seller
    min_price BIGINT,
    max_price BIGINT,
    
    -- Tracking
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(product_id, seller_id)
);

CREATE INDEX idx_product_sellers_title ON product_sellers(product_title_normalized);
CREATE INDEX idx_product_sellers_barcode ON product_sellers(barcode);
CREATE INDEX idx_product_sellers_price ON product_sellers(min_price);

-- =============================================================================
-- 7. SELLER DAILY STATS - Daily aggregated metrics
-- =============================================================================
CREATE TABLE seller_daily_stats (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT REFERENCES sellers(id),
    stats_date DATE NOT NULL,
    
    -- Counts
    product_count INTEGER DEFAULT 0,
    available_product_count INTEGER DEFAULT 0,
    sku_count INTEGER DEFAULT 0,
    
    -- Pricing stats
    avg_price DECIMAL(12,2),
    min_price BIGINT,
    max_price BIGINT,
    total_inventory_value DECIMAL(15,2),
    
    -- Ratings
    avg_rating DECIMAL(2,1),
    total_reviews INTEGER,
    total_orders INTEGER,
    
    recorded_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(seller_id, stats_date)
);

CREATE INDEX idx_seller_stats_date ON seller_daily_stats(stats_date DESC);

-- =============================================================================
-- 8. RAW SNAPSHOTS - Never lose raw data
-- =============================================================================
CREATE TABLE raw_snapshots (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT,
    raw_json JSONB NOT NULL,
    file_path TEXT,
    fetched_at TIMESTAMP DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP
);

CREATE INDEX idx_raw_snapshots_product ON raw_snapshots(product_id);
CREATE INDEX idx_raw_snapshots_pending ON raw_snapshots(processed) WHERE processed = FALSE;

-- =============================================================================
-- VIEWS FOR ANALYTICS
-- =============================================================================

-- Price comparison: Same/similar products from different sellers
CREATE OR REPLACE VIEW v_price_comparison AS
SELECT 
    ps.product_title_normalized,
    ps.barcode,
    p.title,
    s.title AS seller_name,
    s.rating AS seller_rating,
    ps.min_price,
    ps.max_price,
    (ps.min_price::DECIMAL / 100) AS min_price_sum,
    COUNT(*) OVER (PARTITION BY ps.product_title_normalized) AS seller_count,
    RANK() OVER (PARTITION BY ps.product_title_normalized ORDER BY ps.min_price) AS price_rank
FROM product_sellers ps
JOIN products p ON ps.product_id = p.id
JOIN sellers s ON ps.seller_id = s.id
WHERE ps.min_price IS NOT NULL;

-- Best deals: Products with biggest discounts
CREATE OR REPLACE VIEW v_best_deals AS
SELECT 
    p.id,
    p.title,
    s.title AS seller,
    sk.full_price,
    sk.purchase_price,
    sk.discount_percent,
    (sk.full_price - sk.purchase_price) AS savings,
    sk.available_amount
FROM skus sk
JOIN products p ON sk.product_id = p.id
JOIN sellers s ON p.seller_id = s.id
WHERE sk.discount_percent > 10
  AND sk.is_available = TRUE
ORDER BY sk.discount_percent DESC;

-- Seller leaderboard
CREATE OR REPLACE VIEW v_seller_leaderboard AS
SELECT 
    s.id,
    s.title,
    s.rating,
    s.order_count,
    s.review_count,
    COUNT(DISTINCT p.id) AS product_count,
    COUNT(DISTINCT CASE WHEN p.is_available THEN p.id END) AS available_products,
    AVG(sk.purchase_price)::BIGINT AS avg_price,
    MIN(sk.purchase_price) AS min_price,
    MAX(sk.purchase_price) AS max_price
FROM sellers s
LEFT JOIN products p ON s.id = p.seller_id
LEFT JOIN skus sk ON p.id = sk.product_id
GROUP BY s.id
ORDER BY s.order_count DESC;

-- Category stats
CREATE OR REPLACE VIEW v_category_stats AS
SELECT 
    c.id,
    c.title,
    c.level,
    c.path_titles,
    COUNT(DISTINCT p.id) AS product_count,
    COUNT(DISTINCT p.seller_id) AS seller_count,
    AVG(sk.purchase_price)::BIGINT AS avg_price,
    MIN(sk.purchase_price) AS min_price,
    MAX(sk.purchase_price) AS max_price
FROM categories c
LEFT JOIN products p ON c.id = p.category_id
LEFT JOIN skus sk ON p.id = sk.product_id
GROUP BY c.id
ORDER BY product_count DESC;

-- Price history overview
CREATE OR REPLACE VIEW v_price_changes AS
SELECT 
    ph.product_id,
    p.title,
    s.title AS seller,
    ph.recorded_at,
    ph.purchase_price,
    ph.price_change,
    ph.price_change_percent,
    CASE 
        WHEN ph.price_change < 0 THEN 'DOWN'
        WHEN ph.price_change > 0 THEN 'UP'
        ELSE 'SAME'
    END AS direction
FROM price_history ph
JOIN products p ON ph.product_id = p.id
JOIN sellers s ON p.seller_id = s.id
WHERE ph.price_change != 0
ORDER BY ph.recorded_at DESC;

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Normalize product title for comparison
CREATE OR REPLACE FUNCTION normalize_title(title TEXT) 
RETURNS TEXT AS $$
BEGIN
    RETURN LOWER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(title, '[^\w\s]', '', 'g'),
            '\s+', ' ', 'g'
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Calculate category path
CREATE OR REPLACE FUNCTION update_category_path() 
RETURNS TRIGGER AS $$
DECLARE
    parent_path BIGINT[];
    parent_titles TEXT;
    parent_level INTEGER;
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path_ids := ARRAY[NEW.id];
        NEW.path_titles := NEW.title;
        NEW.level := 0;
    ELSE
        SELECT path_ids, path_titles, level 
        INTO parent_path, parent_titles, parent_level
        FROM categories WHERE id = NEW.parent_id;
        
        NEW.path_ids := parent_path || NEW.id;
        NEW.path_titles := parent_titles || ' > ' || NEW.title;
        NEW.level := parent_level + 1;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_category_path
BEFORE INSERT OR UPDATE ON categories
FOR EACH ROW EXECUTE FUNCTION update_category_path();

-- Auto-calculate discount percent on SKU insert/update
CREATE OR REPLACE FUNCTION calculate_discount() 
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.full_price > 0 AND NEW.full_price > NEW.purchase_price THEN
        NEW.discount_percent := ROUND(
            ((NEW.full_price - NEW.purchase_price)::DECIMAL / NEW.full_price) * 100, 2
        );
    ELSE
        NEW.discount_percent := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_calculate_discount
BEFORE INSERT OR UPDATE ON skus
FOR EACH ROW EXECUTE FUNCTION calculate_discount();

-- =============================================================================
-- DONE!
-- =============================================================================
