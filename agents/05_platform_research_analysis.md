# 🔍 Platform Research Summary

## Overview

| Platform | Type | Size | Status | Database |
|----------|------|------|--------|----------|
| **Uzum** | B2C E-commerce | 3M products | ✅ Live | ecommerce_db |
| **Yandex** | B2C E-commerce | 20M+ offers | 📋 Ready | ecommerce_db |
| **OLX** | C2C Classifieds | 500K listings | 📋 Ready | classifieds_db |
| **UZEX** | B2B Procurement | 1.3M lots | ✅ Live | procurement_db |

---

## E-commerce Platforms (B2C)

### Uzum.uz ✅ LIVE

| Metric | Value |
|--------|-------|
| **Status** | ✅ Running 24/7 |
| **Speed** | 100+ products/sec |
| **Coverage** | 600K+ products |
| **Method** | REST API + ID iteration |
| **Database** | ecommerce_db |

**Key Features**:
- Direct API access (no auth needed)
- High concurrency (150 connections)
- Direct DB insertion

---

### Yandex Market 📋 READY

| Metric | Value |
|--------|-------|
| **Status** | Research complete |
| **Size** | 20M+ offers |
| **Speed** | 100K items/day |
| **Method** | SSR parsing + category walking |
| **Database** | ecommerce_db |
| **Cost** | $70/month (proxies) |

**Key Features**:
- Model → Offers structure
- Aggressive anti-bot (SmartCaptcha)
- Residential proxies required

**Files Ready**:
- `scrape_researches/yandex/yandex_scraping_plan.md`
- `scrape_researches/yandex/yandex_database_schema.sql`
- `scrape_researches/yandex/site_analysis_report.json`

---

## Classifieds Platform (C2C)

### OLX.uz 📋 READY

| Metric | Value |
|--------|-------|
| **Status** | Research complete |
| **Size** | 500K listings |
| **Speed** | 20 pages/sec |
| **Method** | REST API + divide/conquer |
| **Database** | classifieds_db |
| **Cost** | $65/month |

**Key Features**:
- User-generated listings
- Private sellers (individuals)
- Negotiable prices
- Pagination limit workaround (price filters)

**Files Ready**:
- `scrape_researches/olx/scraping_strategy.md`
- `scrape_researches/olx/database_schema.sql`
- `scrape_researches/olx/site_analysis_report.json`

---

## Procurement Platform (B2B)

### UZEX ✅ LIVE

| Metric | Value |
|--------|-------|
| **Status** | ✅ Running |
| **Size** | 222K items / 15K lots |
| **Speed** | 8-10 lots/sec |
| **Method** | Session-based + Playwright |
| **Database** | procurement_db |

**Key Features**:
- Government auction data
- Cookie-based authentication
- Two-phase processing (raw → DB)

---

## Implementation Priority

### Phase 1: Current (✅ Complete)
- Uzum scraper: 100+ prod/sec
- UZEX scraper: 8 lots/sec
- Combined: 820K+ records

### Phase 2: Next (OLX)
| Task | Effort | Impact |
|------|--------|--------|
| Create classifieds_db | 1 day | Required |
| Build OLX scraper | 1 week | 500K listings |
| Add to Celery | 1 day | 24/7 operation |

**Why OLX first?**
- Simpler than Yandex (REST API)
- Lower cost ($65 vs $70/mo)
- Different market segment (C2C)

### Phase 3: Later (Yandex)
| Task | Effort | Impact |
|------|--------|--------|
| Set up proxies | 1 day | $50/mo cost |
| Build category walker | 2 weeks | 20M offers |
| Handle SmartCaptcha | 1 week | Anti-bot bypass |

**Why Yandex last?**
- Highest complexity (anti-bot)
- Highest cost (residential proxies)
- Requires more development time

---

## Database Separation

```
┌─────────────────────────────────────────────────────────────┐
│  ecommerce_db (B2C)                                        │
│  ├── Uzum tables ✅                                        │
│  └── Yandex tables (planned)                               │
│  Purpose: Price monitoring SaaS                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  classifieds_db (C2C)                                      │
│  └── OLX tables (planned)                                  │
│  Purpose: Local deals / used items                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  procurement_db (B2B)                                      │
│  └── UZEX tables ✅                                        │
│  Purpose: Government tender analytics                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Cost Summary

| Platform | Monthly Cost | Notes |
|----------|-------------|-------|
| Uzum | $20 | VPS only |
| Yandex | $70 | VPS + residential proxies |
| OLX | $65 | VPS + datacenter proxies |
| UZEX | $20 | VPS only |
| **Total** | **$175** | All 4 platforms |

---

## Technical Comparison

| Feature | Uzum | Yandex | OLX | UZEX |
|---------|------|--------|-----|------|
| **API** | REST | Hidden/SSR | REST | Session |
| **Auth** | None | None | None | Cookies |
| **Anti-bot** | Low | High | Medium | Low |
| **ID iteration** | ✅ Yes | ❌ No | ❌ No | ✅ Yes |
| **Pagination** | None | 400 pages | 25 pages | None |
| **Proxies** | Optional | Required | Recommended | Optional |

---

*Updated: December 8, 2025*
