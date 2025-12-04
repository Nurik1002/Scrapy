from playwright.sync_api import sync_playwright
import json
import os
import time

class DynamicScraper:
    def __init__(self, data_dir="app/data"):
        self.data_dir = data_dir
        self.raw_dir = os.path.join(data_dir, "raw")
        os.makedirs(self.raw_dir, exist_ok=True)
        self.intercepted_data = []

    def handle_response(self, response):
        # print(f"Response: {response.url}") # Verbose logging
        if "GetAuctions" in response.url or "GetShops" in response.url or "GetProductsForInfo" in response.url or "api" in response.url:
            print(f"Intercepted POTENTIAL match: {response.url}")
            try:
                data = response.json()
                request_payload = None
                try:
                    request_payload = response.request.post_data_json
                except:
                    pass
                
                self.intercepted_data.append({
                    "url": response.url,
                    "request_payload": request_payload,
                    "data": data
                })
                
                save_data = {
                    "url": response.url,
                    "request_payload": request_payload,
                    "response_data": data
                }
                filename = f"intercepted_{int(time.time())}_{os.path.basename(response.url)}.json"
                self._save_json(save_data, filename)
            except Exception as e:
                print(f"Failed to parse JSON from {response.url}: {e}")

    def scrape_auctions(self):
        print("Starting dynamic scrape for Auctions...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Subscribe to response events
            page.on("response", self.handle_response)

            try:
                page.goto("https://xarid.uzex.uz/completed-deals/auction", timeout=60000)
                page.wait_for_load_state("networkidle")
                
                # Scroll to trigger lazy loading if any
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(5) # Wait for any triggered requests
                
                # Try to interact with pagination if possible
                # This is a basic attempt; might need refinement based on actual DOM
                next_button = page.query_selector("li.pagination-next a")
                if next_button:
                    print("Clicking next page...")
                    next_button.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(5)

            except Exception as e:
                print(f"Error during auction scrape: {e}")
            finally:
                browser.close()

    def scrape_shops(self):
        print("Starting dynamic scrape for Shops...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.on("response", self.handle_response)

            try:
                # Setup wait for response BEFORE navigating
                with page.expect_response(lambda response: "GetNotCompletedDeals" in response.url, timeout=60000) as response_info:
                    page.goto("https://xarid.uzex.uz/not-completed-deals/shop/shop", timeout=60000)
                    # We don't strictly need to wait for load state if we wait for the specific response
                    # but it's good practice to ensure page is somewhat ready
                
                response = response_info.value
                print(f"Intercepted Shop Response: {response.url}")
                data = response.json()
                self._save_json(data, f"intercepted_shops_{int(time.time())}.json")
                
                # Now try to click on the first item to trigger details
                # We need to wait for the grid to render.
                # Assuming standard table structure or looking for a link/button
                print("Attempting to click first shop item for details...")
                # Wait a bit for Angular to render the table rows
                time.sleep(5)
                
                # Try clicking the first row or a link in it. 
                # Inspecting the DOM would be better, but let's try a generic selector for the first row's link or the row itself
                # Based on previous screenshots/structure, it's likely a table.
                # Let's try clicking the first 'a' tag in the main container or table
                # Or use the text of the first product from the intercepted data if possible?
                # Let's try a broad selector for the first clickable element in the results area.
                
                # Save HTML for inspection
                # with open(os.path.join(self.raw_dir, "shop_page.html"), "w", encoding="utf-8") as f:
                #     f.write(page.content())
                # print("Saved shop_page.html")

                print("Attempting to click first shop expansion panel...")
                # The deals are in mat-expansion-panel-header
                try:
                    page.click("mat-expansion-panel-header", timeout=5000)
                    print("Clicked expansion panel header.")
                except Exception as click_err:
                    print(f"Failed to click expansion panel: {click_err}")
                
                # Wait for potential details request
                time.sleep(10)
                
            except Exception as e:
                print(f"Error during shop scrape: {e}")
            finally:
                browser.close()

    def _save_json(self, data, filename):
        filepath = os.path.join(self.raw_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved {filename}")

if __name__ == "__main__":
    scraper = DynamicScraper()
    scraper.scrape_auctions()
    scraper.scrape_shops()
