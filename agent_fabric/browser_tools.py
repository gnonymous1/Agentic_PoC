from langchain_core.tools import tool
from typing import Annotated
from playwright.sync_api import sync_playwright
import time

# Global browser instance storage (simple singleton pattern for PoC)
_BROWSER_INSTANCE = None
_PAGE_INSTANCE = None
_PLAYWRIGHT_INSTANCE = None

def get_page():
    global _BROWSER_INSTANCE, _PAGE_INSTANCE, _PLAYWRIGHT_INSTANCE
    if _PAGE_INSTANCE:
        return _PAGE_INSTANCE
    
    _PLAYWRIGHT_INSTANCE = sync_playwright().start()
    # Launch headful so the user can see it
    try:
        _BROWSER_INSTANCE = _PLAYWRIGHT_INSTANCE.chromium.launch(
            headless=False,
            # channel="chrome", # Commented out to use bundled chromium which we know is installed
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        with open("browser_debug.log", "a") as f:
            f.write("Browser launched successfully.\n")
    except Exception as e:
        with open("browser_debug.log", "a") as f:
            f.write(f"Failed to launch browser: {e}\n")
        raise e

    _PAGE_INSTANCE = _BROWSER_INSTANCE.new_page()
    return _PAGE_INSTANCE

@tool
def open_url(url: Annotated[str, "The URL to open (e.g., https://youtube.com)"]) -> str:
    """
    Opens a browser window and navigates to the specified URL.
    """
    try:
        page = get_page()
        page.goto(url)
        title = page.title()
        return f"Successfully opened {url}. Page title: {title}"
    except Exception as e:
        return f"Error opening URL: {str(e)}"

@tool
def login_youtube(username: Annotated[str, "The email/username"], password: Annotated[str, "The password"]) -> str:
    """
    Attempts to login to YouTube/Google. 
    WARNING: This may be blocked by Google's bot detection.
    """
    try:
        page = get_page()
        # Ensure we are at the login page or go there
        if "accounts.google.com" not in page.url:
            page.goto("https://accounts.google.com/signin")
        
        # Type Email
        page.fill('input[type="email"]', username)
        page.click('#identifierNext')
        
        # Wait for password field (naive wait)
        time.sleep(2) 
        
        # Type Password
        if page.is_visible('input[type="password"]'):
            page.fill('input[type="password"]', password)
            page.click('#passwordNext')
            return "Credentials entered. Please verify 2FA manually if requested."
        else:
            return "Could not find password field. Google might have blocked the automation or requires a different flow."
            
    except Exception as e:
        return f"Error during login attempt: {str(e)}"

@tool
def close_browser() -> str:
    """
    Closes the browser session.
    """
    global _BROWSER_INSTANCE, _PAGE_INSTANCE, _PLAYWRIGHT_INSTANCE
    if _BROWSER_INSTANCE:
        _BROWSER_INSTANCE.close()
        _PLAYWRIGHT_INSTANCE.stop()
        _BROWSER_INSTANCE = None
        _PAGE_INSTANCE = None
        return "Browser closed."
    return "No browser was open."
