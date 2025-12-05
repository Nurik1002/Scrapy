#!/usr/bin/env python
"""
Full Pipeline Test Script

Tests the complete scraping pipeline:
1. Process existing product.json as sample
2. Verify database records
3. Test API endpoints
"""
import os
import sys
import json
import asyncio
import psycopg2
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config, RAW_STORAGE_DIR


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(success: bool, message: str):
    status = "✅" if success else "❌"
    print(f"{status} {message}")


def test_database_connection():
    """Test PostgreSQL connection."""
    print_header("1. Database Connection Test")
    
    try:
        conn = psycopg2.connect(config.database.url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print_result(True, f"Connected to PostgreSQL")
        print(f"   Version: {version[:50]}...")
        
        # Check tables exist
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   Tables: {', '.join(tables[:8])}...")
        
        conn.close()
        return True
    except Exception as e:
        print_result(False, f"Database connection failed: {e}")
        return False


def test_process_sample_product():
    """Process the existing product.json file."""
    print_header("2. Process Sample Product")
    
    sample_file = Path(__file__).parent.parent / "product.json"
    
    if not sample_file.exists():
        print_result(False, f"Sample file not found: {sample_file}")
        return False
    
    try:
        from processors.product_processor import ProductProcessor
        
        processor = ProductProcessor()
        processor.connect()
        
        success = processor.process_file(sample_file)
        
        print_result(success, f"Processed {sample_file.name}")
        print(f"   Processed: {processor.processed}")
        print(f"   Failed: {processor.failed}")
        print(f"   Alerts: {processor.alerts_created}")
        
        processor.close()
        return success
    except Exception as e:
        print_result(False, f"Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_records():
    """Verify records were created in database."""
    print_header("3. Database Records Verification")
    
    try:
        conn = psycopg2.connect(config.database.url)
        cursor = conn.cursor()
        
        # Check counts
        checks = [
            ("sellers", "SELECT COUNT(*) FROM sellers"),
            ("products", "SELECT COUNT(*) FROM products"),
            ("skus", "SELECT COUNT(*) FROM skus"),
            ("price_history", "SELECT COUNT(*) FROM price_history"),
            ("categories", "SELECT COUNT(*) FROM categories"),
        ]
        
        all_ok = True
        for name, query in checks:
            cursor.execute(query)
            count = cursor.fetchone()[0]
            ok = count > 0
            all_ok = all_ok and ok
            print_result(ok, f"{name}: {count} records")
        
        # Show sample data
        print("\n   Sample Product:")
        cursor.execute("""
            SELECT p.title, s.name as seller, MIN(sk.sell_price) as price
            FROM products p
            JOIN sellers s ON p.seller_id = s.id
            JOIN skus sk ON p.id = sk.product_id
            GROUP BY p.id, s.id
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            print(f"   - Title: {row[0][:50]}...")
            print(f"   - Seller: {row[1]}")
            print(f"   - Price: {row[2]:,.0f} UZS")
        
        conn.close()
        return all_ok
    except Exception as e:
        print_result(False, f"Database check failed: {e}")
        return False


def test_api_endpoints():
    """Test FastAPI endpoints."""
    print_header("4. API Endpoints Test")
    
    try:
        import aiohttp
        
        async def check_endpoints():
            base_url = "http://localhost:8000"
            endpoints = [
                ("/", "Health check"),
                ("/api/stats", "Stats overview"),
                ("/api/sellers?limit=5", "List sellers"),
                ("/api/products/catalog?limit=5", "Product catalog"),
            ]
            
            results = []
            async with aiohttp.ClientSession() as session:
                for path, name in endpoints:
                    try:
                        async with session.get(f"{base_url}{path}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            ok = resp.status == 200
                            results.append((ok, name, resp.status))
                    except aiohttp.ClientError as e:
                        results.append((False, name, str(e)))
            
            return results
        
        results = asyncio.run(check_endpoints())
        
        all_ok = True
        for ok, name, status in results:
            all_ok = all_ok and ok
            print_result(ok, f"{name}: {status}")
        
        return all_ok
    except Exception as e:
        print_result(False, f"API test failed: {e}")
        print("   (Make sure API is running: uvicorn api.main:app)")
        return False


def test_downloader():
    """Test product downloader (single product)."""
    print_header("5. Downloader Test")
    
    try:
        from downloaders.product_downloader import ProductDownloader
        
        async def download_one():
            downloader = ProductDownloader()
            await downloader.setup()
            
            # Download a known product
            result = await downloader.download_product(1772350)
            
            await downloader.cleanup()
            return result
        
        result = asyncio.run(download_one())
        
        if result.success:
            print_result(True, f"Downloaded product {result.product_id}")
            print(f"   File: {result.file_path}")
            print(f"   Response time: {result.response_time_ms}ms")
            return True
        else:
            print_result(False, f"Download failed: {result.error}")
            return False
    except Exception as e:
        print_result(False, f"Downloader test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crawler():
    """Test category crawler (limited)."""
    print_header("6. Crawler Test (Limited)")
    
    try:
        from crawlers.category_crawler import CategoryCrawler
        
        async def crawl_limited():
            crawler = CategoryCrawler()
            await crawler.setup()
            
            # Only get a few products
            page = await crawler.create_page()
            
            try:
                await page.goto("https://uzum.uz/ru/category/elektronika-10020", 
                              wait_until='networkidle', timeout=30000)
                await asyncio.sleep(2)
                
                # Extract just first few links
                links = await page.evaluate("""
                    Array.from(document.querySelectorAll('a[href*="/product/"]'))
                        .slice(0, 5)
                        .map(a => a.href)
                """)
                
                product_ids = []
                for link in links:
                    pid = crawler.extract_product_id(link)
                    if pid:
                        product_ids.append(pid)
                
                return product_ids
            finally:
                await page.close()
                await crawler.cleanup()
        
        product_ids = asyncio.run(crawl_limited())
        
        if product_ids:
            print_result(True, f"Found {len(product_ids)} products")
            print(f"   Sample IDs: {product_ids[:3]}")
            return True
        else:
            print_result(False, "No products found")
            return False
    except Exception as e:
        print_result(False, f"Crawler test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("    UZUM.UZ SCRAPER - FULL PIPELINE TEST")
    print("    " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    results = []
    
    # Test 1: Database
    results.append(("Database Connection", test_database_connection()))
    
    # Test 2: Process sample
    results.append(("Process Sample", test_process_sample_product()))
    
    # Test 3: Verify records
    results.append(("Database Records", test_database_records()))
    
    # Test 4: API (skip if not running)
    try:
        import aiohttp
        results.append(("API Endpoints", test_api_endpoints()))
    except ImportError:
        print_result(False, "aiohttp not installed, skipping API test")
    
    # Test 5: Downloader
    results.append(("Downloader", test_downloader()))
    
    # Test 6: Crawler
    results.append(("Crawler", test_crawler()))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        print_result(ok, name)
    
    print(f"\n{'='*60}")
    print(f"  RESULT: {passed}/{total} tests passed")
    if passed == total:
        print("  🎉 All tests passed!")
    else:
        print("  ⚠️  Some tests failed - check output above")
    print(f"{'='*60}\n")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
