from playwright.sync_api import Page
import time

def update_description(page: Page):
    print("\n--- Step 2: Update Description ---")
    print(">> Waiting for description box...")
    
    # Specific selector for the description box
    description_selector = "div#textbox[aria-label*='Tell viewers']"
    
    try:
        page.wait_for_selector(description_selector, state="visible", timeout=15000)
        desc_box = page.locator(description_selector).first
        
        desc_box.click()
        time.sleep(0.5)
        
        print(">> Clearing old description...")
        page.keyboard.press("Meta+A") 
        page.keyboard.press("Backspace")
        
        print(">> Typing new description...")
        page.keyboard.type("test #test")
        
    except Exception as e:
        print(f"Error handling description: {e}")
        return False

    # --- Click Show More ---
    print(">> Looking for 'Show more' button...")
    try:
        show_more_btn = page.locator("button", has_text="Show more").first
        
        # Scroll to reveal 'Show more'
        show_more_btn.scroll_into_view_if_needed()
        time.sleep(1) 
        
        if show_more_btn.is_visible():
            show_more_btn.click()
            print(">> Clicked 'Show more'.")
        else:
            print(">> 'Show more' button not found (might be already expanded).")
            
    except Exception as e:
        print(f"Error clicking 'Show more': {e}")
        return False
        
    return True