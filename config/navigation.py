from playwright.sync_api import Page
from settings import ENABLE_SCRAPING_MODE
import time

def navigate_to_shorts(page):
    print("--- Starting Navigation Sequence ---")
    
    # --- STEP 1: CLICK CONTENT ---
    print("Looking for 'Content' button...")
    content_clicked = False
    
    # We will try 3 different selectors ranging from specific to general
    selectors = [
        "div.nav-item-text:has-text('Content')",
        "a[href*='/videos/upload']",
        "text='Content'"
    ]

    for i in range(30):
        # First, try to hover the sidebar to expand it if it's collapsed
        try:
            page.locator("ytcp-navigation-drawer").hover(timeout=500)
        except:
            pass

        # Iterate through our list of potential selectors
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible():
                    btn.click(force=True)
                    print(f">> Success: Clicked Content using selector: {selector}")
                    content_clicked = True
                    break
            except Exception:
                continue
        
        if content_clicked:
            break
            
        print(f"Waiting for Content button... ({i+1}/30)")
        page.wait_for_timeout(1000)

    if not content_clicked:
        print("ERROR: Could not click 'Content' button.")
        return False

    # --- STEP 2: WAIT FOR PAGE CHANGE ---
    try:
        page.wait_for_url("**/videos/**", timeout=10000)
    except:
        print("Warning: URL update slow.")

    # --- STEP 3: CLICK SHORTS ---
    print("Looking for 'Shorts'...")
    shorts_clicked = False
    
    for i in range(15):
        try:
            # Try to click the specific custom element
            shorts_filter = page.locator("ytcp-ve", has_text="Shorts")
            if shorts_filter.is_visible():
                shorts_filter.click(force=True)
                print(">> Success: Clicked 'Shorts'.")
                shorts_clicked = True
                break
        except Exception:
            pass
        page.wait_for_timeout(1000)

    if shorts_clicked:
        if ENABLE_SCRAPING_MODE == False: 
            page.wait_for_timeout(3000)
            header =  page.locator("h1.page-title").first
            header.click()
        
        print("--- Navigation Complete ---")
        return True
    
    print("ERROR: Could not find 'Shorts' tab.")
    return False