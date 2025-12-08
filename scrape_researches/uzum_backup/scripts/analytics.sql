-- ============================================
-- UZUM.UZ ANALYTICS QUERIES
-- ============================================

-- ============================================
-- 1. SELLER ANALYTICS
-- ============================================

-- Top 20 Sellers by Order Volume
SELECT 
    s.id,
    s.name as seller_name,
    s.link,
    s.rating,
    s.total_orders,
    s.reviews_count,
    COUNT(DISTINCT p.id) as product_count,
    COUNT(DISTINCT CASE WHEN p.is_available THEN p.id END) as available_products,
    ROUND(AVG(sk.sell_price)::numeric, 0) as avg_price,
    MIN(sk.sell_price) as min_price,
    MAX(sk.sell_price) as max_price,
    SUM(sk.available_amount) as total_stock
FROM sellers s
LEFT JOIN products p ON s.id = p.seller_id
LEFT JOIN skus sk ON p.id = sk.product_id AND sk.is_available
GROUP BY s.id
ORDER BY s.total_orders DESC NULLS LAST
LIMIT 20;


-- Seller Performance Comparison
SELECT 
    s.name,
    s.rating,
    s.total_orders,
    COUNT(p.id) as products,
    ROUND(s.total_orders::numeric / NULLIF(COUNT(p.id), 0), 1) as orders_per_product,
    ROUND(AVG(p.rating), 2) as avg_product_rating
FROM sellers s
JOIN products p ON s.id = p.seller_id
GROUP BY s.id
HAVING COUNT(p.id) >= 10  -- At least 10 products
ORDER BY orders_per_product DESC;


-- ============================================
-- 2. PRODUCT CATALOG BY SELLER
-- ============================================

-- Full Product Catalog with Seller Info
SELECT 
    s.name as seller_name,
    s.rating as seller_rating,
    p.id as product_id,
    p.title,
    c.title as category,
    MIN(sk.sell_price) as min_price,
    MAX(sk.sell_price) as max_price,
    MIN(sk.full_price) as full_price,
    ROUND(
        CASE WHEN MIN(sk.full_price) > 0 
        THEN ((MIN(sk.full_price) - MIN(sk.sell_price)) / MIN(sk.full_price) * 100)::numeric
        ELSE 0 END, 1
    ) as discount_percent,
    SUM(sk.available_amount) as total_stock,
    p.total_orders,
    p.rating as product_rating,
    p.reviews_count,
    p.url
FROM sellers s
JOIN products p ON s.id = p.seller_id
LEFT JOIN categories c ON p.category_id = c.id
LEFT JOIN skus sk ON p.id = sk.product_id
WHERE p.is_available = true
GROUP BY s.id, s.name, s.rating, p.id, c.title
ORDER BY s.name, p.total_orders DESC;


-- Products by Category with Seller Distribution
SELECT 
    c.title as category,
    COUNT(DISTINCT p.id) as total_products,
    COUNT(DISTINCT p.seller_id) as seller_count,
    ROUND(AVG(sk.sell_price)::numeric, 0) as avg_price,
    MIN(sk.sell_price) as min_price,
    MAX(sk.sell_price) as max_price
FROM categories c
JOIN products p ON c.id = p.category_id
JOIN skus sk ON p.id = sk.product_id AND sk.is_available
GROUP BY c.id, c.title
ORDER BY total_products DESC
LIMIT 30;


-- ============================================
-- 3. PRICE ANALYSIS
-- ============================================

-- Recent Price Changes (Last 24 hours)
WITH ranked_prices AS (
    SELECT 
        ph.*,
        LAG(ph.price) OVER (PARTITION BY ph.sku_id ORDER BY ph.scraped_at) as prev_price,
        LAG(ph.scraped_at) OVER (PARTITION BY ph.sku_id ORDER BY ph.scraped_at) as prev_scraped_at
    FROM price_history ph
    WHERE ph.scraped_at > NOW() - INTERVAL '24 hours'
)
SELECT 
    p.title as product,
    s.name as seller,
    rp.prev_price,
    rp.price as current_price,
    ROUND(((rp.price - rp.prev_price) / rp.prev_price * 100)::numeric, 1) as change_percent,
    rp.prev_scraped_at as previous_time,
    rp.scraped_at as current_time
FROM ranked_prices rp
JOIN products p ON rp.product_id = p.id
JOIN sellers s ON rp.seller_id = s.id
WHERE rp.prev_price IS NOT NULL 
  AND rp.price != rp.prev_price
ORDER BY ABS(rp.price - rp.prev_price) DESC
LIMIT 50;


-- Biggest Discounts Currently Active
SELECT 
    p.title,
    s.name as seller,
    sk.full_price as original_price,
    sk.sell_price as current_price,
    sk.discount_percent,
    sk.available_amount as stock,
    p.url
FROM skus sk
JOIN products p ON sk.product_id = p.id
JOIN sellers s ON p.seller_id = s.id
WHERE sk.discount_percent > 20
  AND sk.is_available = true
ORDER BY sk.discount_percent DESC
LIMIT 50;


-- Price Trends (7-day moving average)
SELECT 
    DATE(ph.scraped_at) as date,
    p.title,
    ROUND(AVG(ph.price)::numeric, 0) as avg_price,
    MIN(ph.price) as min_price,
    MAX(ph.price) as max_price
FROM price_history ph
JOIN products p ON ph.product_id = p.id
WHERE ph.scraped_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(ph.scraped_at), p.id, p.title
ORDER BY p.title, date;


-- ============================================
-- 4. INVENTORY ANALYSIS
-- ============================================

-- Low Stock Products (less than 5 items)
SELECT 
    p.title,
    s.name as seller,
    sk.name as variant,
    sk.sell_price as price,
    sk.available_amount as stock,
    p.total_orders
FROM skus sk
JOIN products p ON sk.product_id = p.id
JOIN sellers s ON p.seller_id = s.id
WHERE sk.available_amount > 0 
  AND sk.available_amount < 5
ORDER BY p.total_orders DESC
LIMIT 50;


-- Out of Stock Products (were available recently)
SELECT 
    p.title,
    s.name as seller,
    p.total_orders,
    p.last_seen_at,
    MAX(ph.scraped_at) as last_available
FROM products p
JOIN sellers s ON p.seller_id = s.id
JOIN price_history ph ON p.id = ph.product_id AND ph.is_available = true
WHERE p.is_available = false
GROUP BY p.id, s.id
ORDER BY p.total_orders DESC
LIMIT 30;


-- ============================================
-- 5. DATA QUALITY MONITORING
-- ============================================

-- Unresolved Alerts by Type
SELECT 
    alert_type,
    severity,
    COUNT(*) as count,
    MIN(created_at) as oldest
FROM data_alerts
WHERE is_resolved = false
GROUP BY alert_type, severity
ORDER BY 
    CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
    count DESC;


-- Products with Suspicious Price Changes
SELECT 
    p.title,
    s.name as seller,
    da.message,
    da.details,
    da.created_at
FROM data_alerts da
JOIN products p ON da.product_id = p.id
JOIN sellers s ON da.seller_id = s.id
WHERE da.is_resolved = false
  AND da.alert_type IN ('price_drop_suspicious', 'zero_price')
ORDER BY da.created_at DESC
LIMIT 20;


-- Scraping Coverage Stats
SELECT 
    'Sellers' as entity,
    COUNT(*) as total,
    COUNT(CASE WHEN last_seen_at > NOW() - INTERVAL '24 hours' THEN 1 END) as updated_24h,
    COUNT(CASE WHEN last_seen_at > NOW() - INTERVAL '7 days' THEN 1 END) as updated_7d
FROM sellers

UNION ALL

SELECT 
    'Products' as entity,
    COUNT(*) as total,
    COUNT(CASE WHEN last_seen_at > NOW() - INTERVAL '24 hours' THEN 1 END) as updated_24h,
    COUNT(CASE WHEN last_seen_at > NOW() - INTERVAL '7 days' THEN 1 END) as updated_7d
FROM products;


-- ============================================
-- 6. SELLER DAILY STATS (Run daily via cron)
-- ============================================

-- Insert daily seller stats snapshot
INSERT INTO seller_daily_stats (
    seller_id, stat_date, 
    total_products, available_products,
    total_orders, new_orders,
    avg_rating, total_reviews, new_reviews,
    avg_price, min_price, max_price, total_stock
)
SELECT 
    s.id,
    CURRENT_DATE,
    COUNT(DISTINCT p.id),
    COUNT(DISTINCT CASE WHEN p.is_available THEN p.id END),
    s.total_orders,
    s.total_orders - COALESCE(prev.total_orders, 0),
    s.rating,
    s.reviews_count,
    s.reviews_count - COALESCE(prev.total_reviews, 0),
    ROUND(AVG(sk.sell_price)::numeric, 0),
    MIN(sk.sell_price),
    MAX(sk.sell_price),
    SUM(sk.available_amount)
FROM sellers s
LEFT JOIN products p ON s.id = p.seller_id
LEFT JOIN skus sk ON p.id = sk.product_id AND sk.is_available
LEFT JOIN seller_daily_stats prev ON s.id = prev.seller_id AND prev.stat_date = CURRENT_DATE - 1
GROUP BY s.id, prev.total_orders, prev.total_reviews
ON CONFLICT (seller_id, stat_date) DO UPDATE SET
    total_products = EXCLUDED.total_products,
    available_products = EXCLUDED.available_products,
    total_orders = EXCLUDED.total_orders,
    new_orders = EXCLUDED.new_orders,
    avg_rating = EXCLUDED.avg_rating,
    total_reviews = EXCLUDED.total_reviews,
    new_reviews = EXCLUDED.new_reviews,
    avg_price = EXCLUDED.avg_price,
    min_price = EXCLUDED.min_price,
    max_price = EXCLUDED.max_price,
    total_stock = EXCLUDED.total_stock;
