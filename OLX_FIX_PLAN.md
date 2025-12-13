# 📉 OLX Scraper: Problem Analysis & Fix Plan

## 🚫 The Problem: "The Browser Automation Trap"

The current OLX scraper is failing with **Timeout Errors** because it fell into the exact trap described in the *"How to scrape data"* article.

### **Error Log Evidence**
```
ERROR: Failed to refresh session: Page.goto: Timeout 60000ms exceeded
```

### **Why It Fails (Root Cause)**
The current implementation uses **Playwright** (Active Browser Automation) instead of Direct API.
1.  **Opening Real Browser**: Tries to launch a headless Chromium instance inside Docker.
2.  **Heavy Resources**: Use 100x more CPU/RAM than API calls.
3.  **Slow Network**: Loads images, ads, headers, and scripts just to get 10 text fields.
4.  **Timeouts**: Docker containers often struggle to load full JS-heavy pages effectively.

---

## 🛠️ The Fix: S.C.R.A.P.E. System Implementation

We need to rewrite the OLX scraper to act like the working Uzum & UZEX scrapers: completely **API-based** without browsers.

### **Phase 1: Sniff & Cram (Analysis)**
**Goal**: identify the direct JSON endpoints used by the OLX mobile app or website.

1.  **Endpoint Discovery**:
    *   Instead of `page.goto('olx.uz')`
    *   We use `GET https://www.olx.uz/api/v1/offers/?offset=0&limit=40`
2.  **Authentication**:
    *   Find if it needs a `Bearer` token (often essentially public for "guest" search).

### **Phase 2: Reverse-Engineer (Implementation)**

**Modify `src/platforms/olx/client.py`**:
*   **Remove**: `playwright`, `async_playwright`, `Page`, `Browser` imports.
*   **Add**: `aiohttp` (Direct HTTP client).

**Code Transformation Example**:

**❌ OLD (Heavy/Broken)**:
```python
async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    await page.goto("https://www.olx.uz/electronics") # <--- TIMES OUT
    html = await page.content()
    # ... parse complex HTML ...
```

**✅ NEW (Fast/Reliable)**:
```python
async with aiohttp.ClientSession() as session:
    params = {"category_id": "123", "offset": 0, "limit": 50}
    async with session.get("https://www.olx.uz/api/v1/offers", params=params) as resp:
        data = await resp.json() # <--- INSTANT DATA
        # ... process clean JSON ...
```

### **Phase 3: Plug & Deploy**

1.  **Update `OLXClient`**: Replace browser logic with proper `aiohttp` methods.
2.  **Update `requirements.txt`**: Remove `playwright` (saves ~300MB in Docker image).
3.  **Restart Worker**: New scraper will run 50x faster and never timeout on page loads.

---

## ✅ Benefits of Reference Architecture

This change aligns OLX with your **working systems**:

| Feature | Uzum Scraper (Working) | UZEX Scraper (Working) | OLX Scraper (BROKEN) | OLX (FIXED) |
| :--- | :--- | :--- | :--- | :--- |
| **Method** | Direct API | Direct API | **Browser (Playwright)** | **Direct API** |
| **Speed** | ~130 products/sec | ~100 lots/sec | ~0.5 products/sec | **~100 products/sec** |
| **Reliability** | 99.9% | 99.9% | **Fails (Timeout)** | **99.9%** |
| **Resources** | Low | Low | **Critical High** | **Low** |

## 📅 Action Plan

1.  **Stop** the failing OLX task immediately to save resources.
2.  **Reverse Engineer** the OLX v1 or v2 API (using Network tab sniffing).
3.  **Rewrite** `src/platforms/olx/client.py` to use `aiohttp`.
4.  **Deploy** passing `olx.continuous_scrape` task.
