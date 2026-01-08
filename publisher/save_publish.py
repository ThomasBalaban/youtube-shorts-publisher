from playwright.sync_api import Page
import time

def click_save(page: Page):
    print("\n--- Step 8: Save / Publish ---")
    print(">> Looking for 'Save' button...")

    try:
        # We target the specific ID provided in the snippet
        save_btn = page.locator("#done-button")
        
        # Double check visibility
        if save_btn.is_visible():
            print(">> 'Save' button found. Clicking...")
            save_btn.click()
            
            # Wait for the "Video published/saved" confirmation dialog or toast
            # This is critical so the browser doesn't close immediately (if we weren't pausing)
            time.sleep(5) 
            print(">> Success: Save button clicked.")
            return True
        else:
            print(">> Error: 'Save' button not found or not visible.")
            return False

    except Exception as e:
        print(f"Error clicking 'Save': {e}")
        return False