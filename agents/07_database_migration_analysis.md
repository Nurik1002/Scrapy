# 📊 Database Migration Analysis

## Current Database Summary

**Database**: `uzum_scraping` (single database)
**Total Size**: ~5.1 GB

### Current Data

| Table | Rows | Size | Platform |
|-------|------|------|----------|
| **skus** | 1,977,117 | 611 MB | uzum |
| **products** | 608,629 | 4.1 GB | uzum |
| **price_history** | 661,235 | 127 MB | uzum |
| **sellers** | 22,981 | 15 MB | uzum |
| **categories** | 4,976 | 6 MB | uzum |
| **uzex_lot_items** | 253,012 | 148 MB | uzex |
| **uzex_lots** | 15,440 | 36 MB | uzex |
| **Total** | **3.54M** | **~5.1 GB** | |

---

## Current Schema Analysis

### ✅ Good: Platform Column Exists

```sql
products.platform = 'uzum'      -- Already has platform column!
sellers.platform = 'uzum'       -- Ready for multi-platform!
categories.platform = 'uzum'    -- Ready for multi-platform!
```

**This means**: Adding Yandex data is EASY - just insert with `platform='yandex'`

### ✅ Good: UZEX Already Separate Tables

```sql
uzex_lots        -- Separate table (not mixed with products)
uzex_lot_items   -- Separate table (not mixed with SKUs)
```

**This means**: UZEX migration is simple - just move to new DB

### ⚠️ Issue: All in One Database

Currently everything is in `uzum_scraping`:
- Uzum B2C data
- UZEX B2B data
- Future Yandex would go here too

---

## Migration Plan

### Option A: Split into 3 Databases (Recommended)

```
CURRENT                          AFTER MIGRATION
─────────────────────           ─────────────────────────────
uzum_scraping (5.1GB)    →      ecommerce_db (4.9GB)
├── products                    ├── products (uzum)
├── skus                        ├── skus (uzum)
├── sellers                     ├── sellers (uzum)
├── categories                  ├── categories (uzum)
├── price_history               ├── price_history (uzum)
├── uzex_lots                   └── (ready for Yandex)
└── uzex_lot_items
                                procurement_db (184MB)
                                ├── uzex_lots
                                └── uzex_lot_items

                                classifieds_db (new)
                                └── (ready for OLX)
```

### Option B: Keep Single Database, Use Schemas

```sql
-- Use PostgreSQL schemas instead of databases
CREATE SCHEMA ecommerce;
CREATE SCHEMA classifieds;
CREATE SCHEMA procurement;

-- Move tables
ALTER TABLE products SET SCHEMA ecommerce;
ALTER TABLE uzex_lots SET SCHEMA procurement;
```

**Pros**: Simpler, single connection
**Cons**: Less isolation

---

## Migration Steps

### Step 1: Create New Databases

```sql
-- On PostgreSQL
CREATE DATABASE ecommerce_db;
CREATE DATABASE classifieds_db;
CREATE DATABASE procurement_db;
```

### Step 2: Export UZEX Data

```bash
# Export UZEX tables only
pg_dump -U scraper -d uzum_scraping \
  -t uzex_lots -t uzex_lot_items -t uzex_categories -t uzex_products \
  > uzex_backup.sql

# Import to new database
psql -U scraper -d procurement_db < uzex_backup.sql
```

### Step 3: Export E-commerce Data

```bash
# Export Uzum tables
pg_dump -U scraper -d uzum_scraping \
  -t products -t skus -t sellers -t categories -t price_history \
  > ecommerce_backup.sql

# Import to new database
psql -U scraper -d ecommerce_db < ecommerce_backup.sql
```

### Step 4: Update Application Config

```python
# config.py - Multiple database connections
class DatabaseSettings:
    ecommerce_url = "postgresql://scraper:***@postgres:5432/ecommerce_db"
    classifieds_url = "postgresql://scraper:***@postgres:5432/classifieds_db"
    procurement_url = "postgresql://scraper:***@postgres:5432/procurement_db"
```

### Step 5: Verify and Cleanup

```sql
-- Verify data moved correctly
SELECT COUNT(*) FROM ecommerce_db.products;       -- 608K
SELECT COUNT(*) FROM procurement_db.uzex_lots;    -- 15K

-- Drop old tables from uzum_scraping (optional)
DROP TABLE uzex_lots CASCADE;
DROP TABLE uzex_lot_items CASCADE;
```

---

## Data Compatibility

### Products Table → ecommerce_db

| Current Column | Keep? | Notes |
|----------------|-------|-------|
| id | ✅ | Primary key |
| platform | ✅ | 'uzum' or 'yandex' |
| title | ✅ | Used for search |
| seller_id | ✅ | FK to sellers |
| category_id | ✅ | FK to categories |
| rating | ✅ | Product rating |
| attributes | ✅ | JSONB, flexible |
| raw_data | ⚠️ | Large, consider dropping |

**raw_data column**: 3GB+ of raw JSON. Consider:
- Keep for debugging → more storage
- Drop to save space → lose raw backup

### UZEX Tables → procurement_db

| Current Column | Keep? | Notes |
|----------------|-------|-------|
| All columns | ✅ | No changes needed |
| raw_data | ✅ | Important for B2B audit |

**No changes needed** - UZEX schema is already well-designed for B2B.

---

## Schema Changes for Yandex

Current Uzum schema needs minor additions for Yandex:

```sql
-- Add to products table
ALTER TABLE products 
  ADD COLUMN min_price DECIMAL(18,2),    -- Yandex shows price range
  ADD COLUMN max_price DECIMAL(18,2);

-- Add to sellers table
ALTER TABLE sellers
  ADD COLUMN is_verified BOOLEAN DEFAULT FALSE,
  ADD COLUMN profile_url TEXT;
```

---

## Estimated Migration Time

| Step | Duration | Downtime |
|------|----------|----------|
| Create DBs | 1 min | None |
| Export UZEX | 2 min | None |
| Import UZEX | 3 min | None |
| Export Uzum | 10 min | None |
| Import Uzum | 15 min | None |
| Update config | 5 min | **Required** |
| Test | 10 min | **Required** |
| **Total** | **~45 min** | **15 min** |

---

## Recommendation

### ✅ DO:
1. Create 3 separate databases for isolation
2. Keep current data (no schema changes needed)
3. Migrate during low-traffic period
4. Keep backup of original database

### ❌ DON'T:
1. Drop raw_data column (useful for debugging)
2. Change primary key strategy
3. Rename platform column values

### Migration Order:
1. **First**: Create procurement_db, move UZEX (smallest, safest)
2. **Then**: Rename uzum_scraping → ecommerce_db (just rename)
3. **Last**: Create classifieds_db (new, empty)

---

*Analysis completed: December 8, 2025*
