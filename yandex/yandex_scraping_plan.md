# Scraping Blueprint: market.yandex.uz

## 1. API Reconnaissance & Architecture

### Core Structure
- **Frontend**: Server-Side Rendered (SSR) React with hydration (`window.apiary` state).
- **Data Loading**: Primary data is HTML-embedded. `application/ld+json` provides canonical product data. `serpEntity` blobs provide listings.
- **Bot Defense**: Aggressive. Requires browser-like User-Agent and TLS fingerprinting. Simple `curl` works occasionally but fails at scale without proxies.

### Critical Endpoints
- **Category Listing**: `GET https://market.yandex.uz/catalog--{slug}/{id}/list?page={N}`
- **Product Model**: `GET https://market.yandex.uz/product--{slug}/{id}`
- **Product Offers**: `GET https://market.yandex.uz/product--{slug}/{id}/offers` (or `?tab=offers`)
- **Search**: `GET https://market.yandex.uz/search?text={query}`

## 2. Execution Strategy

### Phase A: Discovery (Category Walker)
Since IDs are non-sequential (alphanumeric hashes or large integers), ID iteration is impossible.
**Algorithm:**
1.  **Seed**: Load a manual list of 500+ lowest-level category URLs (extracted from `sitemap.xml` or UI).
2.  **Crawl**: For each category, iterate pages `page=1` to `page=MAX`.
3.  **Extract**: Harvest Product URLs (`/product--...`) from listing pages.

### Phase B: Detail Extraction (The "Two-Tier" Scrape)
Yandex separates **Models** (Abstract) from **Offers** (Sellers).
1.  **Fetch Model Page**: `GET /product--{slug}/{id}`. Extract universal specs from `LD+JSON` and `apiary` state.
2.  **Fetch Offers List**: `GET /product--{slug}/{id}/offers` (or the `/p/{id}` alias). This contains the aggregations of all sellers (Price, Delivery, SellerID).
3.  **Fetch Specs Tab**: `GET /product--{slug}/{id}/spec`. Extract the full EAV attribute list if `apiary` on main page is incomplete.
4.  **Variants**: If a product has "Select Color", capture the linked Product IDs for other colors from the main page JSON.

### Phase C: Anti-Bot Evasion
- **User-Agent**: Must rotate modern Chrome/Desktop UAs.
- **Cookies**: Maintain `yandexuid` session cookies for 10-20 requests to look "human".
- **Rate Limit**:
    -   *Safe*: 10 requests/minute per IP.
    -   *Aggressive*: 60 requests/minute (Requires high-quality Residential Proxies).

## 3. Infrastructure & Costs

### Resource Estimates
- **Catalog Size**: ~20M+ offers (Uzbekistan region).
- **Throughput**: With 20 threads + Proxies -> ~100k items/day.
- **Duration**: ~20 days for full sync (Initial). Incremental updates daily.

### Cost Estimate
- **Proxies**: $50/month (Residential Bandwidth 5GB+) - CRITICAL for Yandex.
- **Server**: $20/month (VPS 4GB RAM).

## 4. Database Write Strategy
- **Upsert Logic**: Use `external_id` (Yandex Model ID / Offer ID).
- **Order**: Write `yandex_products` (Models) first, then `yandex_sellers`, then `yandex_offers`.
- **History**: Store daily price snapshots in `price_history`.

## 5. Risk Management
| Risk | Probability | Mitigation |
|------|-------------|------------|
| Captcha (SmartCaptcha) | High | Use "2Captcha" or similar if critical, or slow down. |
| IP Ban | High | Rotate IPs every 100 requests. |
| Structure Change | Medium | Monitor `window.apiary` changes weekly. |
