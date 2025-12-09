# 🗄️ Database Setup Guide - Multi-Database Architecture

## Overview

The Marketplace Analytics Platform uses a **three-database architecture** to support different business models and optimize performance:

| Database | Type | Platforms | Purpose |
|----------|------|-----------|---------|
| **ecommerce_db** | B2C | Uzum, Yandex, Wildberries, Ozon | Price monitoring & comparison |
| **classifieds_db** | C2C | OLX | Used goods & local marketplace |
| **procurement_db** | B2B | UZEX | Government procurement analytics |

## 🏗️ Architecture Benefits

### Why Three Databases?

1. **Data Isolation**: Different business models have different data structures
2. **Performance**: Optimized schemas and indexes for each use case
3. **Scalability**: Independent scaling and optimization
4. **Security**: Separate access controls and backup strategies
5. **Maintenance**: Independent schema evolution

### Database Characteristics

```
ecommerce_db (B2C)
├── Products with variants (SKUs/Offers)
├── Cross-platform price comparison
├── Historical price tracking
├── Seller performance metrics
└── ~4.9GB (600K+ products)

classifieds_db (C2C)  
├── Individual listings (temporary)
├── Private sellers
├── Negotiable pricing
├── Location-based search
└── ~500K listings (planned)

procurement_db (B2B)
├── Government tenders/auctions
├── Complex lot structures
├── Bidding process tracking
├── Compliance & audit trails
└── ~184MB (15K lots, 168K items)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file or set environment variables:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5434
DB_USER=scraper
DB_PASSWORD=scraper123

# Specific database names (optional)
ECOMMERCE_DB=ecommerce_db
CLASSIFIEDS_DB=classifieds_db  
PROCUREMENT_DB=procurement_db

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. Create All Databases & Schemas

**Option A: Using the Management Script**
```bash
python manage_db.py init-all
```

**Option B: Manual Schema Creation**
```bash
python create_schemas.py --all
```

**Option C: Individual Database Setup**
```bash
python manage_db.py init-ecommerce
python manage_db.py init-classifieds  
python manage_db.py init-procurement
```

### 4. Verify Setup

```bash
python manage_db.py status
```

Expected output:
```
📊 Database Status Report
================================================================================

🗄️  ECOMMERCE - B2C E-commerce platforms (Uzum, Yandex)
   Database: ecommerce_db
   Platforms: uzum, yandex, wildberries, ozon
   Status: connected
   Current Revision: head

🗄️  CLASSIFIEDS - C2C Classifieds platforms (OLX)
   Database: classifieds_db
   Platforms: olx
   Status: connected
   Current Revision: head

🗄️  PROCUREMENT - B2B Procurement platforms (UZEX)
   Database: procurement_db
   Platforms: uzex
   Status: connected
   Current Revision: head
```

## 🔧 Database Management

### Using the Management Script (`manage_db.py`)

```bash
# Create all databases
python manage_db.py create-all

# Run all migrations  
python manage_db.py migrate-all

# Full initialization (create + migrate + setup)
python manage_db.py init-all

# Create new migration
python manage_db.py revision ecommerce "Add product categories"

# Upgrade specific database
python manage_db.py upgrade classifieds head

# Downgrade database
python manage_db.py downgrade procurement -1

# Check status
python manage_db.py status
```

### Using Alembic Directly

```bash
# Create migration for ecommerce database
alembic -n ecommerce revision --autogenerate -m "Add new indexes"

# Upgrade classifieds database  
alembic -n classifieds upgrade head

# Downgrade procurement database
alembic -n procurement downgrade -1

# Check current revision
alembic -n ecommerce current
```

### Manual Schema Management

```bash
# Create all schemas
python create_schemas.py --all

# Create specific database schema
python create_schemas.py --db ecommerce

# Drop and recreate
python create_schemas.py --all --drop-first

# Verify schemas only
python create_schemas.py --verify-only
```

## 📊 Schema Documentation

### Ecommerce Database (B2C)

**Core Tables:**
- `ecommerce_sellers` - Unified seller data across platforms
- `ecommerce_categories` - Hierarchical product categories  
- `ecommerce_products` - Product catalog with cross-platform mapping
- `ecommerce_offers` - Price variants and stock information
- `ecommerce_price_history` - Historical price tracking

**Key Features:**
- Cross-platform product matching via `title_normalized`
- JSONB attributes for flexible product specifications
- Full-text search on products and categories
- Comprehensive indexing for price queries
- Multi-currency support

**Example Query:**
```sql
-- Find cheapest offers for a product across all platforms
SELECT 
    p.title,
    o.price,
    s.name as seller_name,
    o.platform
FROM ecommerce_offers o
JOIN ecommerce_products p ON o.product_id = p.id  
JOIN ecommerce_sellers s ON o.seller_id = s.id
WHERE p.title_normalized = 'iphone 15 pro'
ORDER BY o.price ASC;
```

### Classifieds Database (C2C)

**Core Tables:**
- `classifieds_sellers` - Private individuals selling items
- `classifieds_listings` - Individual items for sale

**Key Features:**
- Location-based search with coordinates
- Negotiable pricing support
- Full-text search with Russian language support
- Category-specific attributes in JSONB
- Status lifecycle tracking (active → sold/expired)

**Example Query:**
```sql
-- Find cars in Tashkent under $20,000
SELECT 
    title,
    price,
    brand,
    model,
    year,
    mileage,
    location
FROM classifieds_listings
WHERE category_path LIKE 'transport/cars%'
    AND city = 'Tashkent'
    AND price < 20000000  -- 20K USD in UZS
    AND status = 'active'
ORDER BY posted_at DESC;
```

### Procurement Database (B2B)

**Core Tables:**
- `procurement_organizations` - Government entities and vendors
- `procurement_lots` - Tender/auction lots
- `procurement_lot_items` - Individual items within lots

**Key Features:**
- Complex organization relationships (customers/providers)
- Bidding process tracking
- Savings calculation (start_cost vs deal_cost)
- Government compliance fields
- Audit trails with raw data preservation

**Example Query:**
```sql
-- Government procurement savings analysis
SELECT 
    category_name,
    COUNT(*) as lot_count,
    SUM(start_cost) as total_budget,
    SUM(deal_cost) as total_spent,
    SUM(start_cost - deal_cost) as total_savings,
    ROUND(AVG((start_cost - deal_cost) / start_cost * 100), 2) as avg_savings_percent
FROM procurement_lots
WHERE status = 'completed' 
    AND start_cost > 0 
    AND deal_cost > 0
GROUP BY category_name
ORDER BY total_savings DESC;
```

## 🔄 Migration Workflow

### Creating New Migrations

1. **Modify the schema models** in `src/schemas/`

2. **Generate migration:**
   ```bash
   python manage_db.py revision ecommerce "Add product reviews table"
   ```

3. **Review the generated migration** in `migrations/versions/ecommerce/`

4. **Test migration:**
   ```bash
   python manage_db.py upgrade ecommerce
   ```

5. **Rollback if needed:**
   ```bash
   python manage_db.py downgrade ecommerce -1
   ```

### Migration Best Practices

1. **Always backup before migrations**
2. **Test migrations on development first**
3. **Keep migrations small and focused**
4. **Include both upgrade and downgrade logic**
5. **Document breaking changes**

## 🚨 Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Test connections
python -c "
import asyncio
from src.core.database import check_all_databases_health

async def main():
    results = await check_all_databases_health()
    for db, status in results.items():
        print(f'{db}: {\"✅\" if status else \"❌\"}')"

asyncio.run(main())
```

#### 2. Missing Tables

```bash
# Recreate schemas
python create_schemas.py --all --drop-first
```

#### 3. Migration Conflicts

```bash
# Check current state
python manage_db.py status

# Reset to specific revision
alembic -n ecommerce downgrade base
alembic -n ecommerce upgrade head
```

#### 4. Permission Issues

```sql
-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO scraper;
GRANT ALL PRIVILEGES ON DATABASE classifieds_db TO scraper; 
GRANT ALL PRIVILEGES ON DATABASE procurement_db TO scraper;
```

### Performance Issues

#### Slow Queries

1. **Check missing indexes:**
   ```sql
   -- Find slow queries
   SELECT query, calls, total_time, mean_time
   FROM pg_stat_statements 
   ORDER BY mean_time DESC 
   LIMIT 10;
   ```

2. **Add appropriate indexes:**
   ```sql
   -- Example: Index for price range queries
   CREATE INDEX idx_ecommerce_offers_price_range 
   ON ecommerce_offers (price) 
   WHERE is_available = true;
   ```

#### Large Database Size

1. **Vacuum regularly:**
   ```sql
   VACUUM ANALYZE ecommerce_products;
   ```

2. **Archive old data:**
   ```sql
   -- Archive price history older than 1 year
   DELETE FROM ecommerce_price_history 
   WHERE recorded_at < NOW() - INTERVAL '1 year';
   ```

## 🔒 Security & Backup

### Database Security

1. **Use strong passwords**
2. **Limit network access** with `pg_hba.conf`
3. **Regular security updates**
4. **Monitor access logs**

### Backup Strategy

```bash
# Daily backups
pg_dump -U scraper -d ecommerce_db > backups/ecommerce_$(date +%Y%m%d).sql
pg_dump -U scraper -d classifieds_db > backups/classifieds_$(date +%Y%m%d).sql  
pg_dump -U scraper -d procurement_db > backups/procurement_$(date +%Y%m%d).sql

# Restore from backup
psql -U scraper -d ecommerce_db < backups/ecommerce_20241208.sql
```

## 📈 Performance Optimization

### Index Strategy

Each database has optimized indexes:

- **Ecommerce**: Price ranges, seller comparisons, cross-platform matching
- **Classifieds**: Location-based, category, full-text search  
- **Procurement**: Date ranges, organization relationships, savings analysis

### Query Optimization

1. **Use EXPLAIN ANALYZE** for slow queries
2. **Leverage JSONB indexes** for flexible attributes
3. **Consider partial indexes** for common filters
4. **Use connection pooling** for high concurrency

### Monitoring

```sql
-- Database sizes
SELECT 
    datname,
    pg_size_pretty(pg_database_size(datname)) as size
FROM pg_database 
WHERE datname IN ('ecommerce_db', 'classifieds_db', 'procurement_db');

-- Table sizes  
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

## 🛠️ Development Workflow

### Adding New Platform

1. **Determine database type** (B2C/C2C/B2B)
2. **Update configuration** in `src/core/config.py`
3. **Create platform-specific models** if needed
4. **Generate migration** for new fields
5. **Update scrapers** to use correct database

### Schema Evolution

1. **Modify models** in `src/schemas/`
2. **Generate migration:** `python manage_db.py revision <db> "message"`
3. **Test migration:** Apply and verify
4. **Update documentation**
5. **Deploy to production**

## 📚 Additional Resources

### File Structure
```
app/
├── src/schemas/           # Database models
│   ├── ecommerce.py      # B2C platforms
│   ├── classifieds.py    # C2C platforms  
│   └── procurement.py    # B2B platforms
├── migrations/           # Alembic migrations
│   └── versions/
│       ├── ecommerce/    # B2C migrations
│       ├── classifieds/  # C2C migrations
│       └── procurement/  # B2B migrations
├── manage_db.py         # Database management
├── create_schemas.py    # Manual schema creation
└── alembic.ini         # Alembic configuration
```

### Configuration Files
- `alembic.ini` - Multi-database Alembic setup
- `src/core/config.py` - Database connection settings
- `src/core/database.py` - Session management

### Related Documentation
- [Architecture Overview](01_architecture_overview.md)
- [Platform Strategies](02_uzum_platform_strategy.md)
- [Deployment Guide](docker-compose.yml)

---

## 🎯 Summary

The multi-database architecture provides:

✅ **Separation of Concerns** - Each business model has optimized schema  
✅ **Performance** - Specialized indexes and query patterns  
✅ **Scalability** - Independent scaling and maintenance  
✅ **Flexibility** - Easy addition of new platforms  
✅ **Maintainability** - Clear boundaries and responsibilities  

For questions or issues, check the troubleshooting section or review the management scripts.

**Last Updated:** December 8, 2025