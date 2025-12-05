-- Seller Summary
SELECT 
    s.name as seller_name,
    s.rating,
    COUNT(p.id) as product_count,
    ROUND(AVG(ph.price)::numeric, 2) as avg_price
FROM sellers s
JOIN products p ON s.id = p.seller_id
JOIN price_history ph ON p.id = ph.product_id
GROUP BY s.id, s.name, s.rating
ORDER BY product_count DESC
LIMIT 20;

-- Product Catalog by Seller
SELECT 
    s.name as seller_name,
    p.title as product_title,
    ph.price,
    ph.currency
FROM products p
JOIN sellers s ON p.seller_id = s.id
JOIN price_history ph ON p.id = ph.product_id
WHERE ph.timestamp = (
    SELECT MAX(timestamp) 
    FROM price_history 
    WHERE product_id = p.id
)
ORDER BY s.name, ph.price DESC
LIMIT 50;
