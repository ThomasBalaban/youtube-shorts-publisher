from playwright.sync_api import Page
from settings import ENABLE_SCRAPING_MODE
import time

def filter_for_drafts(page: Page):
    """
    Applies the 'Visibility: Draft' filter using specific user-provided IDs.
    """
    print(">> Filtering for 'Draft' visibility...")
    try:
        # 1. Click the Filter Bar (Input)
        # IDs provided: id="video-filter" id="text-input"
        filter_input = page.locator("#video-filter #text-input")
        filter_input.wait_for(state="visible", timeout=5000)
        filter_input.click()
        
        # 2. Click the 'Visibility' menu item
        # ID provided: text-item-9
        visibility_option = page.locator("#text-item-9")
        visibility_option.wait_for(state="visible", timeout=5000)
        visibility_option.click()
        
        # 3. Click the 'Draft' checkbox
        # ID provided: test-id="DRAFT"
        draft_checkbox = page.locator("[test-id='DRAFT']")
        draft_checkbox.wait_for(state="visible", timeout=5000)
        draft_checkbox.click()
        
        # 4. Click Apply
        # Selector provided: .ytcp-filter-dialog id="apply-button" button
        apply_btn = page.locator(".ytcp-filter-dialog #apply-button")
        apply_btn.click()
        
        # Wait for the table to refresh with the new filter
        time.sleep(2)
        print(">> Filter applied: Showing only Drafts.")

        return True

    except Exception as e:
        print(f"Warning: Could not apply Draft filter: {e}")
        # We return True anyway because we don't want to crash the whole bot 
        # just because the filter failed; it can still try to scan manually.
        return True

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
    print("Looking for 'Shorts' filter...")
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
            filter_for_drafts(page)
            page.wait_for_timeout(3000)
            header =  page.locator("h1.page-title").first
            header.click()
        
        print("--- Navigation Complete ---")
        return True
    
    print("ERROR: Could not find 'Shorts' tab.")
    return False