"""
UZEX Session Manager - Capture browser session for API authentication.
Uses Playwright to get valid session cookies.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)


class UzexSession:
    """
    Manages UZEX browser sessions for API authentication.
    
    The UZEX APIs require session cookies that are set by the frontend.
    This class uses Playwright to:
    1. Open the UZEX site
    2. Wait for initial page load (which sets cookies)
    3. Extract cookies for API requests
    """
    
    SITE_URL = "https://xarid.uzex.uz"
    SESSION_FILE = Path.home() / ".uzex_session.json"
    SESSION_TTL = timedelta(hours=1)
    
    def __init__(self):
        self._cookies: List[Dict] = []
        self._headers: Dict[str, str] = {}
        self._last_refresh: Optional[datetime] = None
    
    @property
    def cookies(self) -> List[Dict]:
        return self._cookies
    
    @property
    def cookie_header(self) -> str:
        """Get cookies as header string."""
        return "; ".join(f"{c['name']}={c['value']}" for c in self._cookies)
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers including cookies."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Origin": self.SITE_URL,
            "Referer": f"{self.SITE_URL}/completed-deals/auction",
            "Cookie": self.cookie_header,
            **self._headers,
        }
    
    def is_valid(self) -> bool:
        """Check if session is still valid."""
        if not self._cookies or not self._last_refresh:
            return False
        return datetime.now() - self._last_refresh < self.SESSION_TTL
    
    async def refresh(self, headless: bool = True) -> bool:
        """
        Refresh session by capturing browser cookies.
        
        Args:
            headless: Run browser in headless mode
        
        Returns:
            True if session was captured successfully
        """
        logger.info("Refreshing UZEX session...")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Capture network requests to get any auth headers
                captured_headers = {}
                
                def capture_request(request):
                    if "xarid-api" in request.url:
                        for k, v in request.headers.items():
                            if k.lower() not in ('content-type', 'accept', 'user-agent'):
                                captured_headers[k] = v
                
                page.on("request", capture_request)
                
                # Navigate to the auction page (triggers API calls)
                await page.goto(
                    f"{self.SITE_URL}/completed-deals/auction",
                    wait_until="networkidle",
                    timeout=30000
                )
                
                # Wait for content to load
                await asyncio.sleep(3)
                
                # Get all cookies
                self._cookies = await context.cookies()
                self._headers = captured_headers
                self._last_refresh = datetime.now()
                
                await browser.close()
                
                logger.info(f"Captured {len(self._cookies)} cookies")
                
                # Save session
                self._save_session()
                
                return len(self._cookies) > 0
                
        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            return False
    
    def _save_session(self):
        """Save session to file."""
        try:
            data = {
                "cookies": self._cookies,
                "headers": self._headers,
                "refreshed_at": self._last_refresh.isoformat() if self._last_refresh else None,
            }
            with open(self.SESSION_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def _load_session(self) -> bool:
        """Load session from file."""
        try:
            if not self.SESSION_FILE.exists():
                return False
            
            with open(self.SESSION_FILE) as f:
                data = json.load(f)
            
            self._cookies = data.get("cookies", [])
            self._headers = data.get("headers", {})
            
            if data.get("refreshed_at"):
                self._last_refresh = datetime.fromisoformat(data["refreshed_at"])
            
            return self.is_valid()
            
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False
    
    async def ensure_valid(self) -> bool:
        """Ensure we have a valid session, refreshing if needed."""
        if self._load_session() and self.is_valid():
            logger.info("Using cached session")
            return True
        return await self.refresh()


# Global session instance
_session: Optional[UzexSession] = None


def get_session() -> UzexSession:
    """Get or create UZEX session."""
    global _session
    if _session is None:
        _session = UzexSession()
    return _session


async def main():
    """Test session capture."""
    session = get_session()
    success = await session.refresh(headless=True)
    
    if success:
        print(f"✅ Session captured!")
        print(f"   Cookies: {len(session.cookies)}")
        print(f"   Cookie header: {session.cookie_header[:100]}...")
    else:
        print("❌ Failed to capture session")


if __name__ == "__main__":
    asyncio.run(main())
