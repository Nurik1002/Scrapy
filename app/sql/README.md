# SQL Migrations

This folder contains database schema migrations for the Marketplace Analytics Platform.

## Files

| File | Description |
|------|-------------|
| `001_uzum_schema.sql` | Uzum.uz e-commerce tables (products, sellers, SKUs, etc.) |
| `002_uzex_schema.sql` | UZEX government procurement tables (lots, items, categories) |

## Apply Migrations

```bash
# Apply Uzum schema
docker exec uzum-postgres-1 psql -U scraper -d uzum_scraping -f /tmp/001_uzum_schema.sql

# Apply UZEX schema  
docker exec uzum-postgres-1 psql -U scraper -d uzum_scraping -f /tmp/002_uzex_schema.sql
```

## Tables

### Uzum (E-commerce)
- `sellers` - Marketplace sellers
- `categories` - Product categories
- `products` - Product listings
- `skus` - Product variants with pricing
- `price_history` - Historical prices
- `raw_snapshots` - Raw API responses

### UZEX (Government)
- `uzex_categories` - Product categories
- `uzex_products` - Product catalog
- `uzex_lots` - Deals/tenders
- `uzex_lot_items` - Items per lot
