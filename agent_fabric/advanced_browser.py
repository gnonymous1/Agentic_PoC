
import os
import asyncio
import json
import random
from langchain_core.tools import tool
from typing import Annotated
from playwright.async_api import async_playwright, Page, BrowserContext

# --- Configuration ---
AUTH_FILE = "browser_auth.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class BrowserManager:
    """
    Manages a persistent Playwright browser session (Async).
    """
    _instance = None
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_running = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = BrowserManager()
        return cls._instance

    async def start(self):
        if self.is_running and self.page and not self.page.is_closed():
            return

        self.playwright = await async_playwright().start()
        
        # Launch options
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            channel="chrome",
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )

        # Load storage state if exists
        storage_state = AUTH_FILE if os.path.exists(AUTH_FILE) else None
        
        # Create Context with persistence
        try:
            self.context = await self.browser.new_context(
                storage_state=storage_state,
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                no_viewport=True  # Use maximized window size
            )
        except Exception as e:
            print(f"Error loading storage state: {e}")
            self.context = await self.browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
                no_viewport=True
            )
        
        # Add anti-detection scripts
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        self.page = await self.context.new_page()
        self.is_running = True
        print("[BrowserManager] Browser started with persistent context (Async).")

    async def get_page(self) -> Page:
        if not self.is_running or not self.page or self.page.is_closed():
            await self.start()
        return self.page

    async def save_storage(self):
        """Saves cookies and local storage to disk."""
        if self.context:
            await self.context.storage_state(path=AUTH_FILE)

    async def close(self):
        if self.is_running:
            await self.save_storage()
            try:
                await self.context.close()
                await self.browser.close()
                await self.playwright.stop()
            except:
                pass
            self.is_running = False
            self.page = None
            print("[BrowserManager] Browser closed.")

# --- Helper Functions ---

async def _get_page():
    return await BrowserManager.get_instance().get_page()

async def _wait_for_idle(page: Page, timeout: int = 5000):
    """Waits for network to settle."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except:
        pass 

async def _semantic_mapper(page: Page) -> str:
    """
    Returns a simplified representation of interactable elements.
    """
    script = """
    () => {
        const interestingTags = ['a', 'button', 'input', 'textarea', 'select', '[role="button"]', '[role="link"]', '[onclick]'];
        const elements = document.querySelectorAll(interestingTags.join(','));
        
        let report = [];
        let idCounter = 1;
        
        elements.forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0 || window.getComputedStyle(el).visibility === 'hidden') return;
            
            if (!el.getAttribute('data-agent-id')) {
                el.setAttribute('data-agent-id', idCounter++);
            } else {
                 el.setAttribute('data-agent-id', idCounter++);
            }
            
            let text = el.innerText || el.placeholder || el.value || el.getAttribute('aria-label') || "";
            text = text.replace(/\\s+/g, ' ').trim().substring(0, 50); 
            
            let tagName = el.tagName.toLowerCase();
            let agentId = el.getAttribute('data-agent-id');
            
            report.push(`[${agentId}] <${tagName}> "${text}"`);
        });
        return report.join('\\n');
    }
    """
    try:
        tree = await page.evaluate(script)
        title = await page.title()
        url = page.url
        return f"Title: {title}\nURL: {url}\n\n--- Interactable Elements (Use ID to Click) ---\n{tree}"
    except Exception as e:
        return f"Error building semantic tree: {e}"

# --- Tools ---

@tool
async def open_url(url: Annotated[str, "The URL to open"]) -> str:
    """
    Opens a URL. Returns the semantic map of the page.
    """
    try:
        page = await _get_page()
        await page.goto(url)
        await _wait_for_idle(page)
        await BrowserManager.get_instance().save_storage()
        return await _semantic_mapper(page)
    except Exception as e:
        return f"Error opening URL: {e}"

@tool
async def read_page() -> str:
    """
    Returns the current page content as a semantic map (IDs and text).
    """
    try:
        page = await _get_page()
        return await _semantic_mapper(page)
    except Exception as e:
        return f"Error reading page: {e}"

@tool
async def smart_click(element_id: Annotated[int, "The ID of the element to click (from read_page)"]) -> str:
    """
    Clicks an element by its ID. Verification included.
    """
    try:
        page = await _get_page()
        selector = f'[data-agent-id="{element_id}"]'
        if await page.is_visible(selector):
            prev_url = page.url
            await page.click(selector)
            await _wait_for_idle(page)
            await BrowserManager.get_instance().save_storage()
            
            new_url = page.url
            if new_url != prev_url:
                return f"Clicked element [{element_id}]. Navigated to {new_url}.\nNew state:\n{await _semantic_mapper(page)}"
            else:
                return f"Clicked element [{element_id}]. Page URL did not change.\nNew state:\n{await _semantic_mapper(page)}"
        else:
            return f"Element [{element_id}] not found or not visible."
    except Exception as e:
        return f"Error clicking element: {e}"

@tool
async def type_text(element_id: Annotated[int, "The ID of the input field"], text: Annotated[str, "The text to type"]) -> str:
    """
    Types text into a field with human-like delays.
    """
    try:
        page = await _get_page()
        selector = f'[data-agent-id="{element_id}"]'
        if await page.is_visible(selector):
            await page.click(selector)
            for char in text:
                await page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            return f"Typed '{text}' into element [{element_id}]."
        else:
            return f"Element [{element_id}] not found."
    except Exception as e:
        return f"Error typing text: {e}"

@tool
async def scroll_page(direction: Annotated[str, "'up' or 'down'"]) -> str:
    """
    Scrolls the page.
    """
    try:
        page = await _get_page()
        if direction == "down":
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        else:
            await page.evaluate("window.scrollBy(0, -window.innerHeight * 0.8)")
        return "Scrolled."
    except Exception as e:
        return f"Error scrolling: {e}"

@tool
async def close_browser() -> str:
    """Closes the browser session."""
    await BrowserManager.get_instance().close()
    return "Browser closed."

@tool
async def browser_screenshot(filename: Annotated[str, "Filename to save as (e.g. 'browser_screen.png')"] = "browser_screen.png") -> str:
    """Takes a screenshot of the current browser page and saves it for visual monitoring."""
    try:
        page = await _get_page()
        static_dir = os.path.join("static", "screenshots")
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
            
        filepath = os.path.abspath(os.path.join(static_dir, filename))
        await page.screenshot(path=filepath)
        
        # Web-accessible URL
        image_url = f"/dashboard/screenshots/{filename}"
        
        return f"Browser screenshot saved to {image_url}."
    except Exception as e:
        return f"Error taking browser screenshot: {e}"
