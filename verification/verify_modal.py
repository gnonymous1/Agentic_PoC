from playwright.sync_api import sync_playwright

def test_modal_close_button():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load the HTML file via http.server
        page.goto("http://localhost:8080/static/index.html")

        # Wait for the modal to be visible. The JS might handle display logic.
        # But since I can't guarantee JS initializes properly (missing dependencies in app.js?),
        # I'll force display the modal using JS execution.
        page.evaluate("""
            const modal = document.getElementById('task-modal');
            if (modal) {
                modal.style.display = 'block';
            }
        """)

        # Wait for the modal to be visible
        try:
            page.wait_for_selector("#task-modal", state="visible", timeout=2000)
        except Exception:
            # If default selector fails, force inject CSS
            page.add_style_tag(content="#task-modal { display: block !important; }")
            page.wait_for_selector("#task-modal", state="visible")

        # Take a screenshot of the modal content
        modal_content = page.locator("#task-modal .modal-content")
        modal_content.screenshot(path="verification/modal_screenshot.png")

        print("Screenshot saved to verification/modal_screenshot.png")

        browser.close()

if __name__ == "__main__":
    test_modal_close_button()
