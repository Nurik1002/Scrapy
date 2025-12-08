# Scraping Blueprint: olx.uz

## 1. API Reconnaissance & Architecture

### Core Endpoints
- **Listings (JSON)**: `GET https://www.olx.uz/api/v1/offers/?offset=0&limit=50&category_id={id}`
  - *Note:* The web frontend uses server-side rendering but hydrates via internal APIs. We can mimic these or parse the HTML.
  - *Fallback:* HTML parsing of `https://www.olx.uz/{category}/` is often more stable against bot detection than direct API access without valid tokens.

- **Product Details**: `GET https://www.olx.uz/d/obyavlenie/{slug}-{ID}.html`
  - Extract `window.__PRERENDERED_STATE__` or similar JSON blobs script tags for full data.

- **Phone Numbers**: `GET https://www.olx.uz/api/v1/offers/{id}/limited-phones/`
  - **Auth Required**: Bearer token (guest or logged in).
  - **Rate Limit**: Highly sensitive. Requires rotation.

## 2. Execution Strategy

### Phase A: Discovery (The "Divide & Conquer" Loop)
Since pagination stops at Page 25 (~1000 items), we cannot scrape "all cars" linearly.
**Algorithm:**
1.  Hit `https://www.olx.uz/transport/legkovye-avtomobili/`
2.  Check Count: `34,201 ads`
3.  **Split**: Apply Price Filter `$0 - $500`.
4.  Check Count: `400 ads` -> **Scrape Pages 1-8**.
5.  Next Filter: `$500 - $1000`... and so on.

### Phase B: Detail Extraction
- **Concurrency**: 20 workers for HTML pages.
- **Data**: Extract Title, Description, Attributes (Mileage, Year), Images.
- **Seller**: Extract Seller ID and Name from the listing page.

### Phase C: Phone Number Enrichment ("Lazy" Mode)
Do NOT fetch phones for every item. fetch only on demand or for high-value targets.
- **Rate**: 1 request / 5-10 seconds per IP.
- **Proxy**: Residential required.

## 3. Infrastructure & Costs

### Estimated Time (Full Catalog ~500k active items)
- **Discovery**: 4 hours (with effective splitting).
- **Detail Extraction**: ~12 hours (at 300 pages/min).

### Cost Estimate
- **Proxies**: $15/month (Datacenter) + $30/GB (Residential for phones).
- **Server**: $20/month (VPS, 4GB RAM).
- **Total**: ~$65/month to maintain a live mirror.

## 4. Database Write Strategy
- **Batching**: Insert/Upsert products in batches of 100 via `COPY` or `INSERT ... ON CONFLICT`.
- **Deduplication**: Use `external_id` as unique key.
- **History**: Store price changes in a separate `price_history` table (optional extension).

## 5. Anti-Bot Plan
- **User-Agent**: Rotate modern desktop User-Agents.
- **Cookies**: Maintain session cookies for 10-20 requests, then clear.
- **Fingerprint**: Minimal risk for HTML-only scraping. High risk for JSON API.
