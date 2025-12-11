# Reddit Web Scraping Community Insights
## Comprehensive Knowledge Summary from r/webscraping and Related Communities

**Compiled:** December 11, 2024  
**Sources:** 17 Reddit discussion threads  
**Topics:** Large-scale scraping, anti-bot bypass, tools, monetization, legal considerations, cost optimization

---

## Executive Summary

This document synthesizes valuable insights from Reddit's web scraping community, covering practical advice from practitioners scraping at scale (millions to billions of requests), tool recommendations, anti-detection techniques, cost optimization strategies, and business applications.

---

## 1. Production Architecture at Scale

### 1.1 Battle-Tested Tech Stacks

| Company/User | Scale | Stack | Infrastructure |
|--------------|-------|-------|----------------|
| **@RandomPantsAppear** | Billions scraped | Django/Celery + S3 + Fargate | Auto-scaling EC2 based on queue size |
| **@webscraping-net** | Millions daily | Python + Scrapy + Redis + PostgreSQL + Playwright | Bare metal + cloud hybrids |
| **@Smatei_sm** | 1B+ product prices/month | Java (Apache HTTPClient/OkHttp/Playwright) | AWS EC2 + S3 + Aurora MySQL |
| **@Pigik83** | 1B product prices/month | Custom automation | Cloud VMs rotation |
| **@Playful-Battle992** | 5k+ scrapes/second | NodeJS → migrating to Go, Chromium in K8s | Kubernetes cluster |
| **@qzkl** | 20+ sites | Python + asyncio + aiohttp | Per-site microservices |

### 1.2 Recommended Architecture Patterns

```
┌──────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR SERVICE                      │
│  (Django/FastAPI + Celery + Redis Queue)                     │
└──────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│   SCRAPER      │  │   SCRAPER      │  │   SCRAPER      │
│   Service A    │  │   Service B    │  │   Service N    │
│   (Amazon)     │  │   (Airbnb)     │  │   (Site N)     │
└────────────────┘  └────────────────┘  └────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────────────────────────────────────────────────────┐
│                     PROXY ROTATION LAYER                      │
│  (Residential → Mobile → Datacenter fallback)                │
└──────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│               STORAGE + PROCESSING PIPELINE                   │
│  JSON → S3 → Parser → PostgreSQL/Aurora                      │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 Key Infrastructure Insights

**From @RandomPantsAppear (billions scale):**
> "I upload JSON to S3, and have an event occur that makes AWS process the data on upload. For scrapers themselves I run tiny Fargate instances... There is a scheduler task that runs every 5 minutes to check the queue size in Celery, and based on that scales up or down."

**From @Mysterious-Web-8788:**
> "One centralized service that's a lightweight registry of 'requests' (things that need to be scraped) and then I spin up N microservices to do the dirty work. Old used Optiplex Dell workstations off eBay are dirt cheap."

---

## 2. Anti-Bot Detection & Bypass Techniques

### 2.1 Detection Methods (Know Your Enemy)

Modern anti-bot systems check for:

| Detection Type | What It Checks | Bypass Difficulty |
|---------------|----------------|-------------------|
| **IP Reputation** | Datacenter vs residential IPs, rate patterns | Medium |
| **TLS/JA3 Fingerprint** | SSL handshake patterns, cipher order | High |
| **Browser Fingerprint** | Canvas, WebGL, fonts, screen resolution | High |
| **JavaScript Execution** | CDP detection, timing, behavior | High |
| **Request Timing** | Humanlike delays, mouse movements | Medium |
| **Headers Order** | Header order consistency | Low |
| **Cookie Management** | Session consistency | Low |

### 2.2 Recommended Anti-Detection Tools

**Browser Automation (Ranked by Detection Resistance):**

| Tool | Language | Stealth Level | Notes |
|------|----------|---------------|-------|
| **Patchright** | Python/Node | ⭐⭐⭐⭐⭐ | Patched Playwright, best detection bypass |
| **Camoufox** | Python | ⭐⭐⭐⭐ | Stealth Firefox build (⚠️ maintainer hospitalized) |
| **Nodriver/Zendriver** | Python | ⭐⭐⭐⭐ | Modern undetectable drivers |
| **Playwright Stealth** | Python/Node | ⭐⭐⭐ | Patches common detection signals |
| **Puppeteer Stealth** | Node | ⭐⭐⭐ | Similar to Playwright Stealth |
| **Selenium** | Python/Java | ⭐⭐ | Easily detected, use only with real Chrome |

**HTTP Libraries (For API Scraping):**

| Tool | Language | TLS Spoofing | Notes |
|------|----------|--------------|-------|
| **curl_cffi** | Python | ✅ Yes | Mimics real Chrome TLS fingerprints |
| **rnet** | Python | ✅ Yes | Good browser-like fingerprint |
| **hrequests** | Python | ✅ Yes | Modern alternative to requests |
| **aiohttp** | Python | ❌ No | Async but needs header tuning |

### 2.3 Practical Bypass Strategies

**1. Launch Real Chrome Instead of Automated Browser:**
```bash
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome \
  --remote-debugging-port=39405 \
  --no-first-run \
  --no-default-browser-check \
  --user-data-dir=/path/to/profile \
  --disable-renderer-accessibility
```
> "It's like launching a real chrome browser — there is 0 fingerprinting"

**2. Use Your OWN Browser Headers:**
- Visit: `https://httpbin.org/headers` or "Am I Headless" detector sites
- Copy exact header order and User-Agent
- Maintain consistency between TLS fingerprint and headers

**3. Block Unnecessary Resources:**
```python
# Playwright example - saves 90%+ bandwidth
page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
```

**4. Find Hidden APIs (Game Changer):**
> "Most important tip: before scraping the content, see via Chrome inspector where the frontend fetched the data from the backend. Tapping into that endpoint gives you the exact structure you're looking for."

**Steps to discover APIs:**
1. Open Chrome DevTools → Network tab
2. Filter by XHR/Fetch
3. Look for JSON responses
4. Reverse-engineer pagination (e.g., `?page=3`, `?offset=100`)
5. Check mobile apps using Charles Proxy / HTTP Toolkit

**5. Mobile App API Sniffing (Advanced):**
> "Root Android phone and use Charles proxy to sniff the API used by the website's apps. The server can't distinguish between apps and bots, and you don't have to deal with CAPTCHAs."

**6. Hybrid Manual/Auto (Vibe Coding):**
> "Run your scraper in a Docker container with noVNC. When it hits a CAPTCHA or blockage, pause the script, alert you, and let you manually solve it via the VNC interface, then resume. Great for high-value, low-volume targets."

---

## 3. Proxy Strategy & Cost Optimization

### 3.1 Proxy Type Comparison

| Type | Cost | Detection Risk | Best For |
|------|------|----------------|----------|
| **Datacenter** | $0.01-0.05/req | 🔴 High | Static sites, no protection |
| **Residential** | $0.50-3/GB | 🟡 Medium | Protected sites |
| **ISP Proxies** | $0.10-0.50/GB | 🟢 Low | Long sessions, logins |
| **Mobile** | $3-10/GB | 🟢 Lowest | Hardest targets |

### 3.2 Real-World Cost Examples

| Operation | Monthly Scale | Proxy Cost | Cloud Cost | Notes |
|-----------|---------------|------------|------------|-------|
| **@webscraping-net** | Millions | ~$600/mo | ~$250/mo | Bare metal + cloud |
| **@Pigik83** | 1B prices | ~$1k/mo | $5-7k/mo | Multi-cloud VMs |
| **@Smatei_sm** | Millions | ~$20k/mo | ~$50k/mo | Google SERP heavy |
| **@albert_in_vine** | 2M requests | ~$12/mo | N/A | ISP proxies, $3/week |

### 3.3 Cost Reduction Strategies

**1. Block Unnecessary Resources (Saves 90-95%!):**
```python
# Only load HTML, block images/CSS/fonts
await page.route("**/*", lambda route: 
    route.abort() if route.request.resource_type in ["image", "stylesheet", "font", "media"] 
    else route.continue_()
)
```

**2. Use API Instead of Browser When Possible:**
> "Calling hidden APIs is highly bandwidth-efficient vs real browser requests"

**3. Tiered Proxy Fallback:**
```
Attempt 1: Datacenter proxy ($$$)
Attempt 2: Residential proxy ($$$$)  
Attempt 3: Mobile proxy ($$$$$)
```

**4. Rotate Cloud VMs for IP Diversity:**
> "Rotating IPs by using cloud providers' VMs, you can scrape 60-70% of e-commerces out there. Create VMs, run scraper, kill VM."

**5. Cache and Reuse Sessions:**
> "Reuse the session and store cache, cookies, local storage. Warmed-up browsers save significant resources."

---

## 4. Scraping Tools Comparison

### 4.1 Framework Rankings

**For Static Sites:**
1. **Scrapy** - Super fast, async, Python
2. **Beautiful Soup + requests** - Simple, great for learning
3. **lxml** - Extremely fast parsing

**For Dynamic/JS Sites:**
1. **Playwright + Patchright** - Best detection bypass
2. **Puppeteer** - Node.js, good ecosystem
3. **Selenium** - Legacy, but universal

**Scraping APIs (When DIY is Too Hard):**
- **Oxylabs** - Fast Google Search API, reliable
- **Apify** - Pre-built actors, good infra
- **BrightData** - Won lawsuits, enterprise-grade
- **ScraperAPI** - Simple, handles most anti-bot

### 4.2 Tool-Specific Tips

**Scrapy:**
> "Super fast on static sites, though adding support for dynamic content takes extra work."

**Playwright:**
> "Great for structured automation and testing, though a bit code-heavy for lightweight scraping. Playwright Stealth is easily caught—use Patchright patches."

**Selenium:**
> "Selenium is extremely unstable and sucks resources. It is better to not rely on it (I use it to get cookies and then close it)."

---

## 5. Business & Monetization

### 5.1 Ways to Make Money with Scraping

| Business Model | Example Use Case | Revenue Potential |
|----------------|------------------|-------------------|
| **Lead Generation** | B2B contact lists for sales teams | $$ |
| **Price Monitoring** | E-commerce competitor tracking | $$$ |
| **Data API Service** | Sell structured data access | $$$ |
| **Market Research** | Industry reports, trends | $$ |
| **Real Estate Data** | Listings, price trends | $$$ |
| **AI Training Data** | Clean datasets for ML | $$$$ |
| **Sports Betting** | Live odds monitoring | $$$$ |
| **SEO Analysis** | Competitor keyword research | $$ |
| **MAP Monitoring** | Detect Minimum Advertised Price violations | $$$ |
| **Checkout Widgets** | Scrape shipping rates/taxes | $$ |
| **Trend Spotting** | TikTok/Reddit viral product finding | $$$ |

### 5.2 Practical Monetization Advice

**From @cgoldberg:**
> "Scraping is just a tool to collect data. The question you should be asking is how can you make collected data valuable to someone."

**From @kylegawley:**
> "General web scraping is quite saturated but niche scraping/data isn't. People don't buy scraping tools, they buy DATA. Find groups who need specific DATA that is hard to obtain."

**From @ogandrea:**
> "AI training data is huge right now. Companies need clean, structured data for their models. Lead generation for sales teams, price monitoring for e-commerce, real estate data..."

**Unique Ideas from the Community:**
1. **Gambling/Betting Data APIs** - Winning numbers history, live odds
2. **Horse Racing Data** - Performance stats, odds history
3. **B2B Lead Generation** - Recruiting agencies need leads
4. **Software Testing** - Your Playwright/Selenium skills translate directly

---

## 6. Legal Considerations

### 6.1 Key Legal Precedents

| Case | Outcome | Implication |
|------|---------|-------------|
| **HiQ Labs v. LinkedIn** | Mixed - CFAA doesn't apply to public data | Scraping public data isn't "unauthorized access" |
| **Meta v. Bright Data** | Meta dropped the case | Scraping public profiles may be permissible |

### 6.2 Practical Legal Guidance

**What's Generally Accepted:**
- ✅ Scraping publicly available data (no login required)
- ✅ Personal/research use
- ✅ Transformative use (like AI training)

**Where You Get in Trouble:**
- ❌ Bypassing authentication/login walls
- ❌ Violating explicit contracts you've signed
- ❌ Scraping copyrighted content for resale
- ❌ Causing service disruption (DDoS-like scraping)

**From @copytightco:**
> "Big companies use third-party data brokers—it's not technically scraping if you're buying from someone who's already done the work. Also gray-hat methods with offshore firms and 'don't ask, don't tell' policies."

**For Startups Planning Exit:**
> "If your goal is an exit, you don't want a data skeleton in your closet. Focus on publicly available but structured data, or user-generated contributions (crowdsourcing)."

---

## 7. E-commerce Specific Insights

### 7.1 Common E-commerce Scraping Use Cases

From the Reddit threads:

| Use Case | Description | Mentioned Tools |
|----------|-------------|-----------------|
| **Price Monitoring** | Track competitor prices | Custom scrapers, Prisync, Price2Spy |
| **Inventory Tracking** | Monitor stock levels | Custom + API |
| **Product Research** | Find trending products | Amazon/Alibaba scrapers |
| **Catalog Cloning** | Clone Shopify stores | Apify actors |
| **Review Sentiment** | Understand customer needs | Custom + NLP |
| **SEO Analysis** | Competitor keyword research | SERP scrapers |

### 7.2 Platform-Specific Challenges

**Shopify:**
> "Shopify stores—dropshippers clone product catalogs. Many use pre-built Apify actors."

**Amazon:**
> "Amazon will 100% implement multiple strategies to block bots if you scrape repeatedly. Heavy protection, likely 9-10/10 difficulty."

**Airbnb:**
> "Airbnb is an absolute pain to scrape. I rely on Airbnb API endpoints & creative usage of AWS services. Even with all this, I need robust error checking and retry logic."

### 7.3 E-commerce Scraper Features to Build

Based on successful e-commerce scrapers:

1. **Engine Detection** - Auto-detect Shopify vs WooCommerce vs custom
2. **Variant Extraction** - Sizes, colors, in-stock status (requires JS execution)
3. **Price History** - Track changes over time
4. **Seller Analysis** - Performance metrics, ratings
5. **reCAPTCHA Handling** - Manual via noVNC or AI extensions

---

## 8. Tools & Resources Mentioned

### 8.1 Open Source Tools

| Tool | Purpose | URL/Installation |
|------|---------|------------------|
| **caniscrape** | Analyze site scraping difficulty | `pip install caniscrape` |
| **Camoufox** | Stealth Firefox build | GitHub (maintainer issue) |
| **Patchright** | Patched Playwright | `pip install patchright` |
| **curl_cffi** | TLS fingerprint spoofing | `pip install curl_cffi` |
| **Tor Rotator** | Free proxy rotation | github.com/hatemjaber/tor-rotator |
| **lxml** | Fast HTML parsing | `pip install lxml` |
| **Beautiful Soup** | HTML parsing | `pip install beautifulsoup4` |

### 8.2 Commercial Services

| Service | Type | Best For |
|---------|------|----------|
| **Oxylabs** | Proxy + API | Google Search, reliable proxies |
| **BrightData** | Proxy + API | Enterprise, legal coverage |
| **Apify** | Scraping platform | Pre-built actors, infra |
| **ScraperAPI** | API | Simple anti-bot bypass |
| **MagneticProxy** | Residential proxies | Affordable residential |
| **2Captcha** | CAPTCHA solving | Cheap captcha bypass |
| **Price2Spy/Prisync** | Competitor Intelligence | Specialized e-commerce tracking |
| **Kadoa** | AI Scraping | LLM-based extraction |

### 8.3 Learning Resources

- **John Watson Rooney** (YouTube) - API discovery tutorials
- **caniscrape.org** - Check scraping difficulty
- **HTTP Toolkit** - API sniffing
- **Charles Proxy / Burp Suite** - Traffic analysis
- **Practice Targets** - Wikipedia, scraping sandboxes. *Avoid* big sites like Amazon/BestBuy when learning (too strict).

---

## 9. Key Takeaways & Recommendations

### 9.1 For Your Marketplace Analytics Platform

Based on the Reddit insights and your current architecture:

**Immediate Improvements:**
1. **Add API Discovery** - Before browser scraping, check if the marketplace has hidden APIs
2. **Implement Request Blocking** - Block images/CSS to reduce bandwidth 90%+
3. **Use curl_cffi** - For API-based scraping with TLS fingerprint spoofing
4. **Consider Patchright** - Replace stock Playwright for better detection bypass

**Architecture Enhancements:**
1. **Tiered Proxy Strategy** - Datacenter → Residential → Mobile fallback
2. **VM Rotation** - Spawn/kill VMs for natural IP rotation
3. **Session Caching** - Reuse authenticated sessions across requests
4. **Rate Limiting with Delays** - 800ms-2s random delays between requests

**Cost Optimization:**
1. Prioritize API scraping over browser automation
2. Block unnecessary network requests
3. Use ISP proxies for high-volume sites ($3/week for 2M requests cited)
4. Cache parsed data to avoid re-scraping

### 9.2 General Best Practices Summary

```
✅ DO:
- Find hidden APIs before browser scraping
- Use residential/ISP proxies for protected sites
- Block unnecessary resources (images, CSS)
- Add random delays (800ms-2s)
- Mimic YOUR browser's exact headers
- Use modern stealth tools (Patchright, curl_cffi)
- Cache sessions and cookies
- Implement exponential backoff on errors

❌ DON'T:
- Use AWS Lambda for browser scraping
- Rely on Selenium for production workloads
- Trust default user-agents
- Use datacenter proxies for protected sites
- Make rapid-fire requests without delays
- Store sensitive sessions in plain files
- Ignore rate limits (you'll get banned)
```

---

## 10. Actionable Recommendations for Scrapy Platform

Based on these Reddit insights, here are specific suggestions for your Marketplace Analytics Platform:

### High Priority

1. **Implement API-First Scraping Strategy**
   - Before browser automation, discover if Uzum/UZEX/OLX have internal APIs
   - Use Chrome DevTools Network tab to find endpoints
   - Mobile app sniffing can reveal additional APIs

2. **Upgrade to Patchright**
   - Replace stock Playwright with Patchright for better stealth
   - `pip install patchright`

3. **Add Resource Blocking**
   - Block images, CSS, fonts in Playwright
   - Will reduce bandwidth usage by 90%+

4. **Implement Tiered Proxy Fallback**
   - Try datacenter first (cheap)
   - Fall back to residential
   - Mobile as last resort

### Medium Priority

5. **Add curl_cffi for API Calls**
   - Better TLS fingerprinting than aiohttp
   - Mimics real Chrome signatures

6. **Session Caching**
   - Store cookies/sessions in Redis per site
   - Reuse across worker instances

7. **VM-Based IP Rotation**
   - Consider spawning/killing VMs for natural IP diversity
   - Cloud providers give different IPs on each spawn

### Low Priority

8. **caniscrape Integration**
   - Use to assess new sites before building scrapers
   - `pip install caniscrape`

9. **Mobile App Reverse Engineering**
   - For hardest targets, sniff mobile app APIs
   - Often less protected than web

---

*This document synthesizes insights from 17 Reddit discussions. Always verify current tool versions and legal requirements for your jurisdiction.*
