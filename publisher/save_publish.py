from playwright.sync_api import Page
import time
from settings import TEST_MODE  # <--- Import this

def click_save(page: Page):
    print("\n--- Step 8: Save / Publish ---")
    
    # --- NEW TEST MODE CHECK ---
    if TEST_MODE:
        print("\n**************************************************")
        print(">> TEST MODE ENABLED: Skipping 'Save' button click.")
        print(">> The video will remain a draft so you can verify changes.")
        print("**************************************************\n")
        # Return True so the bot thinks it succeeded and finishes gracefully
        return True
    # ---------------------------

    print(">> Looking for 'Save' button...")

    try:
        # 1. Click the main Save/Schedule button
        save_btn = page.locator("#done-button")
        
        if save_btn.is_visible():
            save_btn.click()
            print(">> 'Save' button clicked. Waiting for confirmation dialog...")
            
            # 2. Wait for the confirmation dialog to appear
            close_button = page.locator("ytcp-video-share-dialog #close-button")
            
            try:
                # Wait up to 10 seconds for the "Video scheduled/published" popup
                close_button.wait_for(state="visible", timeout=10000)
                print(">> Confirmation dialog detected. Clicking 'Close'...")
                
                # Click the Close button
                close_button.click()
                print(">> Success: Confirmation dialog closed.")
                
                time.sleep(2)
                return True
                
            except Exception as e:
                print(f">> Warning: Close button not found or dialog didn't appear: {e}")
                return True
        else:
            print(">> Error: 'Save' button not found or not visible.")
            return False

    except Exception as e:
        print(f"Error clicking 'Save': {e}")
        return False