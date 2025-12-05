-- =============================================================================
-- UZEX GOVERNMENT PROCUREMENT DATABASE SCHEMA
-- =============================================================================
-- Separate tables from Uzum (e-commerce) for government auction data
-- =============================================================================

-- Categories for products
CREATE TABLE IF NOT EXISTS uzex_categories (
    id INT PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    parent_id INT REFERENCES uzex_categories(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Product catalog (from /info/products)
CREATE TABLE IF NOT EXISTS uzex_products (
    id INT PRIMARY KEY,
    code VARCHAR(50) UNIQUE,
    name VARCHAR(500) NOT NULL,
    category_id INT REFERENCES uzex_categories(id),
    category_name VARCHAR(500),
    measure_id INT,
    measure_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Main lots/deals table
CREATE TABLE IF NOT EXISTS uzex_lots (
    id BIGINT PRIMARY KEY,                    -- lot_id
    display_no VARCHAR(50),                   -- lot_display_no (25111007379701)
    
    -- Type classification
    lot_type VARCHAR(30) NOT NULL,            -- auction, shop, national, tender, best_offer, green
    status VARCHAR(20) NOT NULL,              -- completed, active
    is_budget BOOLEAN DEFAULT FALSE,          -- Budget (true) or Corporate (false)
    type_name VARCHAR(50),                    -- "Бюджет" or "Корпоратив"
    
    -- Pricing
    start_cost DECIMAL(18,2),                 -- Starting/estimated cost
    deal_cost DECIMAL(18,2),                  -- Final contract cost
    currency_name VARCHAR(20) DEFAULT 'Сом',
    
    -- Customer (buyer)
    customer_name VARCHAR(500),
    customer_inn VARCHAR(20),
    customer_region VARCHAR(200),
    
    -- Provider (winner/seller)
    provider_name VARCHAR(500),
    provider_inn VARCHAR(20),
    
    -- Deal information
    deal_id BIGINT,
    deal_date TIMESTAMP,
    category_name VARCHAR(500),
    pcp_count INT DEFAULT 0,                  -- Number of participants
    
    -- Dates
    lot_start_date TIMESTAMP,
    lot_end_date TIMESTAMP,
    
    -- Treasury (Kazna) status
    kazna_status VARCHAR(100),
    kazna_status_id INT,
    kazna_payment_status VARCHAR(100),
    kazna_created_date TIMESTAMP,
    
    -- Additional info
    beneficiary VARCHAR(500),
    founder VARCHAR(500),
    deal_status_name VARCHAR(100),
    
    -- Metadata
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Lot items/products (products within each lot)
CREATE TABLE IF NOT EXISTS uzex_lot_items (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT NOT NULL REFERENCES uzex_lots(id) ON DELETE CASCADE,
    
    order_num INT,                            -- Item number in lot
    product_name TEXT,                        -- Product name (can be null)
    description TEXT,                         -- Detailed description
    
    -- Quantities
    quantity DECIMAL(12,2),
    amount DECIMAL(12,2),                     -- Same as quantity in most cases
    measure_name VARCHAR(100),
    
    -- Pricing
    price DECIMAL(18,2),                      -- Unit price
    cost DECIMAL(18,2),                       -- Total cost (price * quantity)
    currency_name VARCHAR(20) DEFAULT 'Сом',
    
    -- Origin
    country_name VARCHAR(100),
    
    -- Dynamic properties/specifications
    properties JSONB,                         -- js_properties array
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily statistics for analytics
CREATE TABLE IF NOT EXISTS uzex_daily_stats (
    id BIGSERIAL PRIMARY KEY,
    stats_date DATE NOT NULL,
    lot_type VARCHAR(30) NOT NULL,
    
    -- Counts
    total_lots INT DEFAULT 0,
    completed_lots INT DEFAULT 0,
    active_lots INT DEFAULT 0,
    
    -- Values
    total_start_value DECIMAL(18,2) DEFAULT 0,
    total_deal_value DECIMAL(18,2) DEFAULT 0,
    avg_discount_percent DECIMAL(5,2),
    
    -- Participants
    avg_participants DECIMAL(5,2),
    total_participants INT DEFAULT 0,
    
    recorded_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(stats_date, lot_type)
);

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_uzex_lots_type ON uzex_lots(lot_type);
CREATE INDEX IF NOT EXISTS idx_uzex_lots_status ON uzex_lots(status);
CREATE INDEX IF NOT EXISTS idx_uzex_lots_customer ON uzex_lots(customer_inn);
CREATE INDEX IF NOT EXISTS idx_uzex_lots_provider ON uzex_lots(provider_inn);
CREATE INDEX IF NOT EXISTS idx_uzex_lots_dates ON uzex_lots(lot_start_date, lot_end_date);
CREATE INDEX IF NOT EXISTS idx_uzex_lots_deal_date ON uzex_lots(deal_date);

CREATE INDEX IF NOT EXISTS idx_uzex_lot_items_lot ON uzex_lot_items(lot_id);
CREATE INDEX IF NOT EXISTS idx_uzex_products_code ON uzex_products(code);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Top winners by deal value
CREATE OR REPLACE VIEW v_uzex_top_winners AS
SELECT 
    provider_name,
    provider_inn,
    COUNT(*) as total_wins,
    SUM(deal_cost) as total_value,
    AVG(deal_cost) as avg_deal_value,
    AVG(pcp_count) as avg_competition
FROM uzex_lots
WHERE status = 'completed' AND provider_name IS NOT NULL
GROUP BY provider_name, provider_inn
ORDER BY total_value DESC;

-- Top buyers by spend
CREATE OR REPLACE VIEW v_uzex_top_buyers AS
SELECT 
    customer_name,
    customer_inn,
    COUNT(*) as total_deals,
    SUM(deal_cost) as total_spent,
    AVG(deal_cost) as avg_deal_value,
    COUNT(DISTINCT provider_inn) as unique_suppliers
FROM uzex_lots
WHERE status = 'completed' AND customer_name IS NOT NULL
GROUP BY customer_name, customer_inn
ORDER BY total_spent DESC;

-- Price reduction analysis
CREATE OR REPLACE VIEW v_uzex_price_reduction AS
SELECT 
    lot_type,
    COUNT(*) as deals,
    AVG((start_cost - deal_cost) / NULLIF(start_cost, 0) * 100) as avg_reduction_percent,
    SUM(start_cost - deal_cost) as total_savings
FROM uzex_lots
WHERE status = 'completed' 
    AND start_cost > 0 
    AND deal_cost > 0
    AND start_cost >= deal_cost
GROUP BY lot_type;

-- Category distribution
CREATE OR REPLACE VIEW v_uzex_category_stats AS
SELECT 
    category_name,
    COUNT(*) as total_deals,
    SUM(deal_cost) as total_value,
    AVG(pcp_count) as avg_participants
FROM uzex_lots
WHERE status = 'completed' AND category_name IS NOT NULL
GROUP BY category_name
ORDER BY total_value DESC;
