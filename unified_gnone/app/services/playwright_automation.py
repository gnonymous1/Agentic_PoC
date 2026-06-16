"""
GNONE — Playwright Headless Browser Automation.
For platforms without public APIs (LinkedIn, certain social networks).
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class PlaywrightAutomation:
    """Headless browser automation for web-based interactions."""

    def __init__(self):
        self._browser = None
        self._context = None
        self._page = None

    async def start(self, headless: bool = True) -> None:
        """Initialize Playwright browser instance."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=headless)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self._page = await self._context.new_page()
            logger.info("Playwright browser initialized")
        except ImportError:
            logger.warning("Playwright not installed. Install with: pip install playwright")
        except Exception as exc:
            logger.error("Playwright init failed: %s", exc)

    async def stop(self) -> None:
        """Close browser and clean up resources."""
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_playwright"):
            await self._playwright.stop()
        logger.info("Playwright browser closed")

    async def login(self, url: str, credentials: Dict[str, str]) -> bool:
        """Navigate to URL and submit login credentials."""
        if not self._page:
            logger.error("Browser not initialized")
            return False

        try:
            await self._page.goto(url, wait_until="networkidle")
            for selector, value in credentials.items():
                await self._page.fill(selector, value)
            await self._page.click("button[type='submit']")
            await self._page.wait_for_load_state("networkidle")
            logger.info("Login successful on %s", url)
            return True
        except Exception as exc:
            logger.error("Login failed: %s", exc)
            return False

    async def post_content(self, url: str, content: str, media_path: Optional[str] = None) -> bool:
        """Navigate to posting URL and submit content."""
        if not self._page:
            return False

        try:
            await self._page.goto(url, wait_until="networkidle")
            await self._page.fill("textarea, [contenteditable]", content)
            if media_path:
                async with self._page.expect_file_chooser() as fc_info:
                    await self._page.click("input[type='file']")
                file_chooser = await fc_info.value
                await file_chooser.set_files(media_path)
            await self._page.click("button:has-text('Post'), button:has-text('Publish')")
            await self._page.wait_for_load_state("networkidle")
            logger.info("Content posted on %s", url)
            return True
        except Exception as exc:
            logger.error("Post failed: %s", exc)
            return False

    async def scrape_page(self, url: str, selector: str) -> str:
        """Scrape content from a page using a CSS selector."""
        if not self._page:
            return ""

        try:
            await self._page.goto(url, wait_until="networkidle")
            content = await self._page.text_content(selector)
            return content or ""
        except Exception as exc:
            logger.error("Scrape failed: %s", exc)
            return ""


# Singleton instance
playwright = PlaywrightAutomation()
